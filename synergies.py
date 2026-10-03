"""Reviewed build affinities, computed from observable state without game actions.

These percentages are a documented heuristic index, never a win probability.
Internet sources identify archetypes; numeric weights are our own model.
"""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).parent
LIBRARY = json.loads((ROOT / 'builds.json').read_text(encoding='utf-8'))
JOKERS = json.loads((ROOT / 'joker_catalog.json').read_text(encoding='utf-8'))
COPIERS = {'j_blueprint', 'j_brainstorm'}
WEIGHTS = {'partners': 40, 'deck': 25, 'alignment': 20, 'development': 15}


def cards(state, area):
    value = state.get(area) or {}
    return value.get('cards', []) if isinstance(value, dict) else value if isinstance(value, list) else []


def known(card):
    return not (card.get('state') or {}).get('hidden')


def active(card):
    return known(card) and not (card.get('state') or {}).get('debuff')


def name(key):
    return JOKERS.get(key, {}).get('name', key)


def owned_keys(state):
    return {c.get('key') for c in cards(state, 'jokers') if active(c)}


def deck_readiness(state, build, keys):
    kind = build['deck']
    if kind == 'any':
        return 1.0, 'Esta estrategia no exige un rango, palo o mejora concreto.'
    composition = cards(state, 'deck_composition')
    raw_collection = cards(state, 'collection')
    if not composition and any(not known(c) for c in raw_collection):
        return None, 'La colección contiene cartas ocultas y falta su composición anónima: actualizá el lector.'
    collection = composition or [c for c in raw_collection if known(c)]
    if not collection:
        return None, 'Falta la baraja completa: reiniciá Balatro con el mod actualizado.'
    n = len(collection)
    playable = [c for c in collection if (c.get('modifier') or {}).get('enhancement') != 'STONE'
                and (c.get('value') or {}).get('rank')]
    def rank(c): return (c.get('value') or {}).get('rank')
    def enhanced(c, enhancement): return (c.get('modifier') or {}).get('enhancement') == enhancement
    if kind == 'faces':
        amount = sum(rank(c) in ('J', 'Q', 'K') or 'j_pareidolia' in keys for c in playable)
        target, label = .35, 'figuras'
    elif kind == 'kings':
        amount = sum(rank(c) == 'K' for c in playable)
        target, label = .35, 'reyes'
    elif kind == 'twos':
        amount = sum(rank(c) == '2' for c in playable)
        target, label = .35, 'doses'
    elif kind == 'royals':
        amount = sum(rank(c) in ('K', 'Q') for c in playable)
        target, label = .5, 'reyes o reinas'
    elif kind == 'lucky':
        amount = sum(enhanced(c, 'LUCKY') for c in playable)
        target, label = .5, 'cartas de la suerte'
    elif kind == 'stone':
        amount = sum(enhanced(c, 'STONE') for c in collection)
        target, label = .4, 'piedras'
    elif kind == 'hearts':
        amount = sum((c.get('value') or {}).get('suit') == 'H'
                     or ('j_smeared' in keys and (c.get('value') or {}).get('suit') == 'D')
                     or enhanced(c, 'WILD') for c in playable)
        target, label = .65, 'corazones efectivos'
    elif kind == 'ranks':
        diversity = len({rank(c) for c in playable})
        return min(1.0, diversity / 10) * len(playable) / n, f'{diversity} rangos distintos; las piedras no forman escaleras.'
    elif kind == 'pairs':
        from collections import Counter
        counts = Counter(rank(c) for c in playable)
        amount = sum(v for v in counts.values() if v >= 2)
        target, label = 1, 'cartas con otro ejemplar del mismo rango'
    else:
        raise ValueError('Perfil de baraja desconocido: ' + kind)
    return min(1.0, amount / n / target), f'{amount} de {n} cartas son {label}; referencia de afinidad máxima: {target:.0%} de la baraja.'


def development(state, build):
    rows = [(state.get('hands') or {}).get(h, {}) for h in build['hands']]
    if rows:
        level = max(float(r.get('level') or 1) for r in rows)
        played = max(float(r.get('played') or 0) for r in rows)
        return min(1, (level - 1) / 9) * .6 + min(1, played / 20) * .4
    # Current persistent XMult, not predicted future growth.
    values = []
    for c in cards(state, 'jokers'):
        if active(c) and c.get('key') in build['core']:
            ability = c.get('ability') or {}
            extra = ability.get('extra')
            x = ability.get('x_mult', ability.get('Xmult', 1))
            if isinstance(extra, dict): x = max(x or 1, extra.get('Xmult', extra.get('x_mult', 1)) or 1)
            if isinstance(x, (int, float)): values.append(min(1, max(0, (x - 1) / 3)))
    return max(values, default=0)


def profile(state, build, keys):
    coverage = len(keys.intersection(build['core'])) / len(build['core'])
    readiness, detail = deck_readiness(state, build, keys)
    progress = development(state, build)
    percent = None if readiness is None else round(60 * coverage + 25 * readiness + 15 * progress)
    return dict(build, percent=percent, core_owned=[k for k in build['core'] if k in keys],
                missing=[k for k in build['core'] if k not in keys], deck_detail=detail,
                deck_readiness=readiness, development=progress)


def affinity(state, candidate, build, keys):
    key = candidate.get('key', '')
    members = set(build['core'] + build['support'])
    copier = key in COPIERS
    consumable = key in build['tarots'] + build['planets']
    if key not in members and not copier and not consumable:
        return None
    if copier:
        partners = keys.intersection(members) - COPIERS
        partners = {k for k in partners if JOKERS.get(k, {}).get('blueprint_compat')}
        if not partners:
            return None
    else:
        partners = keys.intersection(members) - {key}
    # A chosen goal cannot pretend we already own its other pieces.
    if consumable and not keys.intersection(build['core']):
        return None
    core_needed = set(build['core']) - {key}
    if copier: core_needed = set(build['core'])
    partner_score = min(1, (len(partners.intersection(core_needed)) + .35 * len(partners - core_needed))
                        / max(1, len(core_needed)))
    if copier: partner_score = min(1, len(partners))
    after = keys | {key}
    ready, detail = deck_readiness(state, build, after)
    alignment = len(keys.intersection(build['core'])) / len(build['core'])
    progress = development(state, build)
    parts = {'partners': round(40 * partner_score, 1), 'deck': None if ready is None else round(25 * ready, 1),
             'alignment': round(20 * alignment, 1), 'development': round(15 * progress, 1)}
    percent = None if ready is None else int(sum(parts.values()) + .5)
    reasons = []
    if partners:
        reasons.append('Combina con: ' + ', '.join(name(k) for k in sorted(partners)) + '.')
    else:
        reasons.append('Todavía no tenés una pieza complementaria de esta combinación.')
    reasons.append(detail)
    if copier:
        reasons.append('Blueprint copia al comodín de la derecha; Brainstorm al primero. Reordená para copiar una pieza compatible; el índice supone esa colocación.')
    elif key in build['support']:
        # Support is useful, but is not equivalent to buying a missing core.
        percent = None if percent is None else round(percent * .85)
        reasons.append('Es una pieza de apoyo; no completa el núcleo por sí sola (factor ×0,85).')
    if key in keys and not copier:
        percent = None if percent is None else round(percent * .7)
        reasons.append('Ya tenés esta pieza; su copia recibe factor ×0,70. No se estima su ganancia marginal de puntuación.')
    if ready == 0:
        percent = None if percent is None else min(30, percent)
        reasons.append('La baraja todavía no tiene cartas que activen este perfil. Afinidad limitada a 30%.')
    if key == 'j_steel_joker':
        collection = cards(state, 'deck_composition') or cards(state, 'collection')
        steel = sum((c.get('modifier') or {}).get('enhancement') == 'STEEL' for c in collection if known(c))
        if collection and not steel:
            percent = None if percent is None else min(30, percent)
            reasons.append('No hay acero en tu baraja: Steel Joker todavía no aumenta el multiplicador. Afinidad limitada a 30%.')
    return {'build_id': build['id'], 'build_name': build['name'], 'percent': percent,
            'components': parts, 'reasons': reasons, 'sources': build['sources'], 'partners': sorted(partners)}


def conflicts(state, candidate, keys):
    key = candidate.get('key')
    combined = keys | {key}
    notes, penalty = [], 0
    def clash(pair, reason, cost):
        nonlocal penalty
        if key in pair and pair <= combined:
            notes.append(reason); penalty += cost
    clash({'j_pareidolia', 'j_ride_the_bus'}, 'Pareidolia convierte las cartas con rango en figuras: una figura que puntúe reinicia Ride the Bus.', 45)
    for other in ('j_lucky_cat', 'j_steel_joker', 'j_glass'):
        clash({'j_vampire', other}, 'Vampire elimina mejoras de cartas que puntúan y puede consumir mejoras que necesita ' + name(other) + '.', 20)
    for other in ('j_banner', 'j_trading', 'j_burnt', 'j_castle', 'j_yorick', 'j_hit_the_road', 'j_mail'):
        clash({'j_burglar', other}, 'Burglar elimina los descartes al elegir la ciega; interfiere con ' + name(other) + '.', 30)
    for other in ('j_burnt', 'j_trading', 'j_castle', 'j_yorick', 'j_hit_the_road', 'j_mail'):
        for fragile in ('j_green_joker', 'j_ramen'):
            clash({fragile, other}, 'Los descartes que necesita ' + name(other) + ' reducen el Mult de ' + name(fragile) + '.', 15)
    return notes, min(70, penalty)


def purchase(state, candidate):
    money = float(state.get('money') or 0)
    credit = 20 if 'j_credit_card' in owned_keys(state) else 0
    price = (candidate.get('cost') or {}).get('buy')
    modifier, ability = candidate.get('modifier') or {}, candidate.get('ability') or {}
    key = candidate.get('key', '')
    area = 'jokers' if key.startswith('j_') else 'consumables'
    inventory = cards(state, area)
    limit = (state.get(area) or {}).get('limit') if isinstance(state.get(area), dict) else None
    negative = modifier.get('edition') == 'NEGATIVE'
    full = limit is not None and len(inventory) >= limit and not negative
    sellable = any(known(c) and not ((c.get('modifier') or {}).get('eternal') or (c.get('ability') or {}).get('eternal')) for c in inventory)
    affordable = None if price is None else money + credit >= price
    notes = []
    if affordable is False: notes.append('No alcanza el dinero disponible, incluido el crédito activo.')
    if full: notes.append('Necesitás liberar un espacio.' if sellable else 'Sin espacio y sin cartas visibles que puedas vender.')
    if limit is None: notes.append('La API no informó el límite de espacios.')
    if modifier.get('rental') or ability.get('rental'):
        rate = (state.get('joker_context') or {}).get('rental_rate', 3)
        notes.append(f'Alquiler: ${rate} por ronda.')
    tally = ability.get('perish_tally', modifier.get('perishable'))
    if tally is not None: notes.append(f'Perecedero: {tally} rondas antes de quedar debilitado.')
    if modifier.get('eternal') or ability.get('eternal'): notes.append('Eterno: no podrás venderlo después.')
    return {'price': price, 'affordable': affordable, 'space_available': None if limit is None else not full,
            'can_buy_now': affordable is True and (negative or (limit is not None and not full)), 'notes': notes}


def evaluate(state, target='auto'):
    if target != 'auto' and target not in {b['id'] for b in LIBRARY['builds']}:
        raise ValueError('Build desconocida.')
    keys = owned_keys(state)
    profiles = [profile(state, b, keys) for b in LIBRARY['builds']]
    profiles.sort(key=lambda p: (bool(p['core_owned']), p['percent'] or 0, len(p['core_owned'])), reverse=True)
    detected = next((p for p in profiles if p['core_owned']), None)
    selected = next((p for p in profiles if p['id'] == target), detected)
    shop = []
    # Shop inventories can linger in the API after leaving the shop.
    if state.get('state') == 'SHOP':
        for c in cards(state, 'shop'):
            key = c.get('key', '')
            options = [a for b in LIBRARY['builds'] if (a := affinity(state, c, b, keys))] if known(c) else []
            options.sort(key=lambda a: (a['percent'] is not None, a['percent'] or 0, len(a['partners'])), reverse=True)
            best = options[0] if options else None
            notes, penalty = conflicts(state, c, keys)
            # Unknown or face-down objects have no attributable fit score.
            if not known(c) or (key.startswith('j_') and key not in JOKERS): best = None
            safe_card = copy.deepcopy(c) if known(c) else {'label':'Carta oculta','state':{'hidden':True}}
            if not known(c): notes, penalty = [], 0
            result = {'card': safe_card, 'percent': None, 'reasons': [], 'warnings': notes,
                      'penalty': penalty, 'purchase': purchase(state, safe_card), 'matches': options[:3]}
            if best:
                result.update(best)
                result['percent'] = None if best['percent'] is None else max(0, best['percent'] - penalty)
            else:
                result['reasons'] = ['Sin relación revisada en esta biblioteca. Esto no significa que la carta sea mala.']
            if (c.get('state') or {}).get('debuff') or (c.get('ability') or {}).get('perish_tally') == 0:
                result['percent'] = 0 if best else None
                result['warnings'].append('Está debilitado: su habilidad no aporta mientras siga así.')
            if selected and known(c):
                result['target_match'] = next((a for a in options if a['build_id'] == selected['id']), None)
                result['target_piece'] = key in selected['core'] + selected['support'] + selected['tarots'] + selected['planets']
            shop.append(result)
    warnings = []
    if any(not known(c) for c in cards(state, 'jokers')):
        warnings.append('Hay comodines ocultos: el índice usa solamente las piezas identificables.')
    boss = state.get('active_blind') or {}
    upcoming = (state.get('blinds') or {}).get('boss') or {}
    boss_key = boss.get('key') or upcoming.get('key')
    if boss_key in ('bl_plant', 'bl_head', 'bl_eye', 'bl_mouth', 'bl_mark', 'bl_window', 'bl_final_acorn'):
        warnings.append('Ciega a revisar: ' + (upcoming.get('name') or boss_key) + '. El índice no reproduce su impacto; usá Simular cuando comience la ronda.')
    return {'status': 'ready', 'in_shop': state.get('state') == 'SHOP', 'researched_on': LIBRARY['researched_on'],
            'sources': LIBRARY['sources'], 'builds': profiles, 'detected_id': detected['id'] if detected else None,
            'selected_id': selected['id'] if selected else None, 'shop': shop, 'warnings': warnings,
            'weights': WEIGHTS, 'method': 'Afinidad heurística: compañeros 40 + baraja 25 + núcleo ya presente 20 + desarrollo 15, con factores de apoyo/copias y penalizaciones por conflictos. Precio y espacio se informan por separado. No es probabilidad de victoria ni ganancia de puntuación.'}
