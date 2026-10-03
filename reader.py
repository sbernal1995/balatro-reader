"""Local, read-only Balatro dashboard with an offline rules engine."""
import json
import copy
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlsplit, parse_qs
from native_engine import analyze
from synergies import LIBRARY, JOKERS, evaluate as evaluate_synergies

API = 'http://127.0.0.1:12346'
RECORDS = Path(__file__).with_name('registros')

class Recorder:
    def __init__(self, folder=RECORDS):
        self.folder = folder
        self.previous = None
        self.total = 0
        self.saved_at = None

    def save(self, data):
        canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
        if canonical == self.previous:
            return
        self.folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).isoformat()
        record = {'capturado_en': stamp, 'estado': data}
        encoded = json.dumps(record, ensure_ascii=False)
        with (self.folder / 'historial.jsonl').open('a', encoding='utf-8') as f:
            f.write(encoded + '\n')
        temporary = self.folder / 'actual.tmp'
        temporary.write_text(encoded, encoding='utf-8')
        temporary.replace(self.folder / 'actual.json')
        self.previous = canonical
        self.total += 1
        self.saved_at = stamp

recorder = Recorder()
cache_lock = threading.Lock()
cached = None
problem = 'Esperando conexión con Balatro'
def fingerprint(data):
    """Compare gameplay inputs, following the native engine's import contract.

    Live tables also contain UI objects: round_resets.blind_tag.tag_sprite has
    transforms and timers that change every frame. They must not cancel work.
    Keep ordered hands/inventory so suggested indices and joker order stay valid.
    """
    def fields(value, keys):
        value = value if isinstance(value,dict) else {}
        return {k:value[k] for k in keys if k in value}

    def card_value(card):
        value = fields(card, ('id','key','modifier'))
        value['value'] = fields(card.get('value'), ('rank','suit'))
        value['state'] = fields(card.get('state'), ('hidden','debuff','forced_selection'))
        value['ability'] = fields(card.get('ability'), (
            'perma_bonus','played_this_ante','forced_selection','debuff',
            'mult','extra','x_mult','Xmult','yorick_discards','caino_xmult',
            'invis_rounds','to_do_poker_hand','eternal','rental','perishable',
            'perish_tally','hands_played_at_create','extra_value'))
        return value

    value = fields(data, ('state','ante_num','round_num','deck','money','excluded_jokers'))
    value['round'] = fields(data.get('round'),
        ('hands_left','discards_left','chips','hands_played','discards_used'))
    for key in ('hand','jokers','consumables','draw_pool','discard_pool'):
        area = data.get(key) or {}
        value[key] = fields(area, ('limit','highlighted_limit'))
        value[key]['cards'] = [card_value(c) for c in area.get('cards',[])]
    for key in ('unseen_cards','unknown_jokers'):
        value[key] = [card_value(c) for c in data.get(key,[])]
    value['hands'] = {k:fields(v, ('level','chips','mult','played','played_this_round','visible'))
                      for k,v in (data.get('hands') or {}).items()}
    value['active_blind'] = fields(data.get('active_blind'),
        ('key','chips','disabled','triggered','prepped','hands','only_hand','discards_sub','hands_sub'))
    value['blinds'] = {k:fields(v, ('key','type','status','score'))
                       for k,v in (data.get('blinds') or {}).items()}
    value['used_vouchers'] = sorted((data.get('used_vouchers') or {}).keys())
    ctx = data.get('joker_context') or {}
    value['joker_context'] = fields(ctx, (
        'hands_played','skips','rental_rate','starting_deck_size','discount_percent',
        'edition_rate','bankrupt_at','ecto_minus','interest_cap','interest_amount',
        'last_hand_played','last_tarot_planet','playing_card','probabilities',
        'consumeable_usage_total','consumeable_usage','pool_flags'))
    value['joker_context']['round_resets'] = fields(ctx.get('round_resets'), ('hands','discards'))
    value['joker_context']['current_round'] = fields(ctx.get('current_round'),
        ('most_played_poker_hand','mail_card','castle_card','ancient_card','idol_card'))
    value['joker_context']['blind'] = fields(ctx.get('blind'), ('disabled',))
    return json.dumps(value,sort_keys=True)


def current_input():
    with cache_lock:
        return cached if not problem else None


class SimulationController:
    def __init__(self, current=current_input):
        self.current = current
        self.lock = threading.Lock()
        self.wakeup = threading.Event()
        self.generation = 0
        self.pending = None
        self.result = {'status':'idle','reason':'Presioná Simular para analizar esta mano.'}

    def submit(self, data):
        data = copy.deepcopy({k:v for k,v in data.items() if k != 'registro'})
        with self.lock:
            self.generation += 1
            self.pending = (self.generation,data,fingerprint(data))
            self.result = {'status':'running','fingerprint':fingerprint(data),'completed':0,'total':0}
            self.wakeup.set()
            return self.generation

    def view(self):
        data = self.current()
        with self.lock:
            result = dict(self.result)
        stored = result.pop('fingerprint',None)
        if data is None:
            return {'status':'waiting','reason':'Esperando conexión con Balatro.'}
        if stored is not None and stored != fingerprint(data):
            return {'status':'stale','reason':'La partida cambió. Presioná Simular para recalcular con la mano y los recursos actuales.'}
        return result

    def run(self):
        while True:
            self.wakeup.wait()
            with self.lock:
                job = self.pending
                self.pending = None
                self.wakeup.clear()
            if job is None:
                continue
            generation,data,signature = job
            def cancelled():
                current = self.current()
                with self.lock:
                    return generation != self.generation or current is None or fingerprint(current) != signature
            def progress(done,total,partial):
                with self.lock:
                    if generation == self.generation:
                        self.result = dict(partial,fingerprint=signature)
            try:
                result = analyze(data,trials=1000,progress=progress,cancelled=cancelled)
                if result.get('status') == 'superseded' or cancelled():
                    with self.lock:
                        if generation == self.generation:
                            self.result = {'status':'stale','fingerprint':signature,
                                'reason':'El cálculo se interrumpió. Presioná Simular para usar el estado actual.'}
                    continue
                if result.get('status') == 'ready':
                    RECORDS.mkdir(parents=True,exist_ok=True)
                    temporary = RECORDS / 'recomendacion.tmp'
                    temporary.write_text(json.dumps({'capturado_en':datetime.now(timezone.utc).isoformat(),
                        'estado':data,'analisis':result},ensure_ascii=False),encoding='utf-8')
                    temporary.replace(RECORDS / 'recomendacion.json')
            except Exception as exc:
                result = {'status':'blocked','reason':str(exc)}
            with self.lock:
                if generation == self.generation:
                    self.result = dict(result,fingerprint=signature)


simulations = SimulationController()

def monitor():
    global cached, problem
    while True:
        try:
            data = state()
            recorder.save(data)
            with cache_lock:
                cached = dict(data, registro={'guardado_en': recorder.saved_at, 'cambios': recorder.total})
                problem = None
        except Exception as exc:
            with cache_lock:
                problem = str(exc)
        threading.Event().wait(1)

def state():
    payload = json.dumps(dict(jsonrpc='2.0', method='gamestate', params={}, id=1)).encode()
    with urlopen(Request(API, payload, {'Content-Type': 'application/json'}), timeout=3) as r:
        result = json.load(r)
    if 'error' in result:
        raise RuntimeError(result['error'].get('message', 'Error de API'))
    data = result['result']
    for area_key in ('hand','jokers','consumables','cards','discard_pool'):
        area = data.get(area_key)
        if not isinstance(area,dict):
            data[area_key] = {'cards':area if isinstance(area,list) else []}
        for card in data[area_key].get('cards',[]):
            for field in ('state','value','modifier','cost','ability'):
                if not isinstance(card.get(field),dict):
                    card[field] = {}
    # Anonymous belief bags: hidden identities cannot be mapped back to a slot.
    hidden_cards = [copy.deepcopy(c) for c in (data.get('hand') or {}).get('cards', [])
                    if (c.get('state') or {}).get('hidden')]
    if hidden_cards:
        bag = hidden_cards + copy.deepcopy((data.get('cards') or {}).get('cards', []))
        for card in bag:
            for field in ('id', 'runtime', 'state'):
                card.pop(field, None)
            (card.get('ability') or {}).pop('forced_selection', None)
        data['unseen_cards'] = sorted(bag, key=lambda c: json.dumps(c,sort_keys=True))
    hidden_jokers = [copy.deepcopy(c) for c in (data.get('jokers') or {}).get('cards', [])
                     if (c.get('state') or {}).get('hidden')]
    if hidden_jokers:
        for card in hidden_jokers:
            card.pop('id',None)
            card.pop('runtime',None)
            if isinstance(card.get('state'),dict):
                card['state'].pop('highlight',None)
        data['unknown_jokers'] = sorted(hidden_jokers,key=lambda c:json.dumps(c,sort_keys=True))
    # Whole-deck composition is an anonymous multiset, like the draw belief bag.
    # A card facing down in the deck must not disappear from shop fit counts.
    collection = data.get('collection') or {}
    collection_cards = collection.get('cards',[]) if isinstance(collection,dict) else collection
    if collection_cards:
        for card in collection_cards:
            for field in ('value','modifier'):
                if not isinstance(card.get(field),dict): card[field] = {}
        composition = [{'value':{k:v for k,v in (c.get('value') or {}).items() if k in ('rank','suit')},
                        'modifier':{k:v for k,v in (c.get('modifier') or {}).items() if k in ('enhancement','edition','seal')}}
                       for c in collection_cards]
        data['deck_composition'] = {'cards':sorted(composition,key=lambda c:json.dumps(c,sort_keys=True))}
    # Do not expose the draw pile or identities of face-down cards.
    pool = data.pop('cards', None)
    if isinstance(pool, dict):
        # Composition only: never expose or use the future draw order.
        pool['cards'] = sorted(pool.get('cards', []), key=lambda c: c.get('id', 0))
        for card in pool['cards']:
            card['state'] = dict(card.get('state') or {},hidden=False)
        data['draw_pool'] = pool
    for key in ('hand', 'jokers', 'consumables', 'shop', 'pack', 'collection'):
        if key not in data:
            continue
        area = data.get(key)
        if not isinstance(area, dict):
            area = {'cards': area if isinstance(area, list) else []}
            data[key] = area
        for card in area.get('cards', []):
            for field in ('state', 'value', 'modifier', 'cost'):
                if not isinstance(card.get(field), dict):
                    card[field] = {}
            if card['state'].get('hidden'):
                flags = card['state']
                forced = bool((card.get('ability') or {}).get('forced_selection'))
                card.clear()
                card.update(label='Carta oculta', state=dict(flags,forced_selection=forced))
    return data

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = urlsplit(self.path)
        if route.path == '/builds':
            body = json.dumps(dict(LIBRARY, jokers=JOKERS)).encode()
            status, kind = 200, 'application/json; charset=utf-8'
        elif route.path == '/synergies':
            data = current_input()
            try:
                if data is None:
                    result, status = {'status':'waiting','reason':'Esperando conexión para evaluar la tienda.'},503
                else:
                    target = parse_qs(route.query).get('build',['auto'])[0]
                    result, status = evaluate_synergies(data,target),200
            except ValueError as exc:
                result, status = {'status':'blocked','reason':str(exc)},400
            body = json.dumps(result).encode()
            kind = 'application/json; charset=utf-8'
        elif self.path == '/analysis':
            body = json.dumps(simulations.view()).encode()
            status, kind = 200, 'application/json; charset=utf-8'
        elif self.path == '/state':
            try:
                with cache_lock:
                    if problem:
                        raise RuntimeError(problem)
                    body = json.dumps(cached).encode()
                status = 200
            except Exception as exc:
                body = json.dumps({'error': 'Sin conexión con Balatro: ' + str(exc)}).encode()
                status = 503
            kind = 'application/json; charset=utf-8'
        elif self.path == '/':
            body = Path(__file__).with_name('index.html').read_bytes()
            status, kind = 200, 'text/html; charset=utf-8'
        elif self.path in ('/synergies.js','/synergies.css'):
            body = Path(__file__).with_name(self.path[1:]).read_bytes()
            status = 200
            kind = 'text/javascript; charset=utf-8' if self.path.endswith('.js') else 'text/css; charset=utf-8'
        elif self.path == '/favicon.ico':
            body, status, kind = b'', 204, 'image/x-icon'
        else:
            body, status, kind = b'Not found', 404, 'text/plain'
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        global cached, problem
        if self.path != '/simulate':
            self.send_error(404)
            return
        # Browser-triggered writes are restricted to this local panel.
        origin = self.headers.get('Origin')
        if origin and origin not in ('http://127.0.0.1:8765','http://localhost:8765'):
            self.send_error(403)
            return
        try:
            data = state()
            if data.get('state') != 'SELECTING_HAND' or (data.get('round') or {}).get('hands_left',0)<1:
                raise ValueError('Esperando una mano disponible para jugar.')
            with cache_lock:
                cached = dict(data,registro={'guardado_en':recorder.saved_at,'cambios':recorder.total})
                problem = None
            request_id = simulations.submit(data)
            result, status = {'status':'running','request_id':request_id},202
        except Exception as exc:
            result,status = {'status':'blocked','reason':str(exc)},409
        body=json.dumps(result).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass

if __name__ == '__main__':
    threading.Thread(target=monitor, daemon=True).start()
    threading.Thread(target=simulations.run, daemon=True).start()
    print('Lector de Balatro: http://127.0.0.1:8765', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
