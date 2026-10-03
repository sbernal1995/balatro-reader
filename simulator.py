"""Finite-round Monte Carlo: compare first actions with all remaining resources.

Only supported rules produce a recommendation. This is not a full-run solver.
The draw pool is shuffled independently; the game's actual draw order is unused.
"""
import itertools
import math
import time
from functools import lru_cache

import numpy as np

NAMES = ['High Card', 'Pair', 'Two Pair', 'Three of a Kind', 'Straight',
         'Flush', 'Full House', 'Four of a Kind', 'Straight Flush',
         'Five of a Kind', 'Flush House', 'Flush Five']
BASE = [(5, 1), (10, 2), (20, 2), (30, 3), (30, 4), (35, 4),
        (40, 4), (60, 7), (100, 8), (120, 12), (140, 14), (160, 16)]
RANKS = {r: i + 2 for i, r in enumerate('23456789TJQKA')}
SUITS = {s: i + 1 for i, s in enumerate('HDCS')}
ENHANCEMENTS = {'': 0, 'BONUS': 1, 'MULT': 2, 'WILD': 3, 'GLASS': 4,
                'STEEL': 5, 'STONE': 6, 'GOLD': 7}
EDITIONS = {'': 0, 'FOIL': 1, 'HOLO': 2, 'POLYCHROME': 3, 'NEGATIVE': 0}
SUPPORTED = {'j_joker', 'j_half', 'j_banner', 'j_mystic_summit', 'j_blue_joker',
             'j_abstract', 'j_fortune_teller', 'j_bull', 'j_bootstraps',
             'j_gros_michel', 'j_cavendish', 'j_jolly', 'j_zany', 'j_mad',
             'j_crazy', 'j_droll', 'j_sly', 'j_wily', 'j_clever', 'j_devious',
             'j_crafty', 'j_green_joker'}

def mapping(value):
    return value if isinstance(value, dict) else {}

def normalized(value):
    return str(value or '').upper().removeprefix('M_').removeprefix('E_').replace(' CARD', '')

def pack(card):
    v, a, mod, flags = [mapping(card.get(k)) for k in ('value', 'ability', 'modifier', 'state')]
    enhancement = normalized(mod.get('enhancement'))
    edition = normalized(mod.get('edition'))
    if enhancement not in ENHANCEMENTS:
        raise ValueError(f'Mejora pendiente de implementar: {enhancement}')
    if edition not in EDITIONS:
        raise ValueError(f'Edición pendiente de implementar: {edition}')
    stone = enhancement == 'STONE'
    if flags.get('hidden'):
        raise ValueError('Hay cartas ocultas en la mano; no se conoce su identidad.')
    if not stone and (v.get('rank') not in RANKS or v.get('suit') not in SUITS):
        raise ValueError('Faltan el valor o el palo de una carta.')
    rank = 0 if stone else RANKS[v['rank']]
    chips = 0 if stone else 11 if rank == 14 else min(rank, 10)
    bonus = a.get('bonus', 50 if stone else 30 if enhancement == 'BONUS' else 0)
    chips += bonus + a.get('perma_bonus', 0)
    # rank, suit, enhancement, edition, red seal, debuff, chips, mult, Xmult
    return [rank, 0 if stone else SUITS[v['suit']], ENHANCEMENTS[enhancement],
            EDITIONS[edition], int(normalized(mod.get('seal')) == 'RED'),
            int(bool(flags.get('debuff') or a.get('debuff'))), chips,
            a.get('mult', 4 if enhancement == 'MULT' else 0),
            a.get('h_x_mult', 1.5) if enhancement == 'STEEL' else
            a.get('Xmult', 2) if enhancement == 'GLASS' else 1]

@lru_cache(maxsize=16)
def selections(size, limit):
    groups = [c for k in range(1, min(size, limit) + 1)
              for c in itertools.combinations(range(size), k)]
    padded = np.array([list(c) + [size] * (5-len(c)) for c in groups])
    return groups, padded

class Evaluator:
    def __init__(self, state, all_cards):
        self.state = state
        self.cards = np.array([pack(c) for c in all_cards] + [[0]*9], dtype=float)
        self.base_chips = np.array([mapping(mapping(state.get('hands')).get(n)).get('chips', b[0])
                                    for n, b in zip(NAMES, BASE)])
        self.base_mult = np.array([mapping(mapping(state.get('hands')).get(n)).get('mult', b[1])
                                   for n, b in zip(NAMES, BASE)])
        self.jokers = mapping(state.get('jokers')).get('cards', [])
        self.limit = min(5, mapping(state.get('hand')).get('highlighted_limit', 5))
        self.simple = bool(np.all(np.isin(self.cards[:,2],[0,1,7])) and np.all(self.cards[:,3:5] == 0) and np.all(self.cards[:,7] == 0))

    def order(self, indices):
        def key(index):
            c = self.cards[index]
            if c[5]: return -1
            factor = (c[8] if c[2] == 4 else 1) * (1.5 if c[3] == 3 else 1)
            addition = c[7] * factor + (10 if c[3] == 2 else 0) * (1.5 if c[3] == 3 else 1)
            if factor == 1: return 1e15 + addition
            return addition / (factor - 1)
        return sorted(indices, key=key, reverse=True)

    def scores(self, hands, discards_left, remaining, green_mult=None):
        """Evaluate every subset for all supplied hands in one vectorized batch."""
        groups, padded = selections(hands.shape[1], self.limit)
        hands = np.concatenate((hands, np.full((len(hands), 1), len(self.cards)-1)), axis=1)
        picked = hands[:, padded]
        rank = self.cards[:,0][picked]
        suit = self.cards[:,1][picked]
        enh = self.cards[:,2][picked]
        valid = picked != len(self.cards)-1
        real = valid & (rank > 0)
        size = valid.sum(axis=-1)
        counts = np.zeros(rank.shape, dtype=np.int8)
        for i in range(5):
            counts += ((rank == rank[..., i, None]) & real & real[..., i, None])
        biggest = counts.max(axis=-1)
        pair_positions = (counts == 2).sum(axis=-1)
        three = biggest >= 3
        two_pair = pair_positions >= 4
        pair = (biggest >= 2)
        full = three & (pair_positions >= 2)
        two_pair |= full
        four = biggest >= 4
        five = biggest >= 5
        sorted_rank = np.sort(rank, axis=-1)
        straight = (real.sum(axis=-1) == 5) & (biggest == 1) & (
            ((sorted_rank[..., -1] - sorted_rank[..., 0]) == 4) |
            np.all(sorted_rank == np.array([2, 3, 4, 5, 14]), axis=-1))
        # Wild cards match any suit; they still need five non-stone cards.
        fixed_suit = np.where(enh == 3, 0, suit)
        max_suit = fixed_suit.max(axis=-1)
        flush = (real.sum(axis=-1) == 5) & np.all(
            (fixed_suit == 0) | (fixed_suit == max_suit[..., None]), axis=-1)
        kind = np.zeros(size.shape, dtype=np.int8)
        for condition, number in [(pair,1),(two_pair,2),(three,3),(straight,4),
                                  (flush,5),(full,6),(four,7),(straight&flush,8),
                                  (five,9),(full&flush,10),(five&flush,11)]:
            kind = np.where(condition, number, kind)
        high = rank.max(axis=-1)
        scoring = ((kind[..., None] == 0) & (rank == high[..., None]) & real)
        scoring |= ((kind[..., None] == 1) & (counts == 2))
        scoring |= ((kind[..., None] == 2) & (counts == 2))
        scoring |= ((kind[..., None] == 3) & (counts == 3))
        scoring |= ((kind[..., None] == 7) & (counts == 4))
        scoring |= (np.isin(kind, [4,5,6,8,9,10,11])[..., None] & real)
        scoring |= ((enh == 6) & valid)
        scoring &= (self.cards[:,5][picked] == 0)
        if self.simple:
            chips = self.base_chips[kind] + np.sum(np.where(scoring,self.cards[:,6][picked],0),axis=-1)
            mult = self.base_mult[kind].astype(float)
        else:
            values = self.cards[picked]
            edition = values[...,3]
            # For supported deterministic cards, place additive Mult before Xmult.
            factors = np.where(enh == 4,values[...,8],1)*np.where(edition == 3,1.5,1)
            additions = values[...,7]*factors + np.where(edition == 2,10,0)*np.where(edition == 3,1.5,1)
            priority = np.where(factors == 1,1e15+additions,
                                additions/np.where(factors == 1,1,factors-1))
            priority = np.where(scoring,priority,-1)
            order = np.argsort(-priority,axis=-1,kind='stable')
            values = np.take_along_axis(values,order[...,None],axis=-2)
            scoring = np.take_along_axis(scoring,order,axis=-1)
            enh, edition = values[...,2],values[...,3]
            chips = self.base_chips[kind].astype(float)
            mult = self.base_mult[kind].astype(float)
            for i in range(5):
                active = scoring[..., i]
                # A red seal retriggers the card and its edition.
                for repeat in range(2):
                    triggered = active & ((repeat == 0) | (values[..., i, 4] == 1))
                    chips += np.where(triggered, values[..., i, 6], 0)
                    mult += np.where(triggered, values[..., i, 7], 0)
                    mult *= np.where(triggered & (enh[..., i] == 4), values[..., i, 8], 1)
                    chips += np.where(triggered & (edition[..., i] == 1), 50, 0)
                    mult += np.where(triggered & (edition[..., i] == 2), 10, 0)
                    mult *= np.where(triggered & (edition[..., i] == 3), 1.5, 1)
            # Held steel cards apply after scoring played cards.
            original = self.cards[hands[:, :-1]]
            for i in range(hands.shape[1]-1):
                held = np.all(padded != i, axis=-1)[None, :]
                steel = (original[:, i, 2] == 5) & (original[:, i, 5] == 0)
                multiplier = original[:, i, 8] ** (1 + original[:, i, 4])
                mult *= np.where(held & steel[:, None], multiplier[:, None], 1)
        green_index = 0
        for joker in self.jokers:
            if mapping(joker.get('state')).get('debuff'):
                continue
            key = joker['key']
            a = mapping(joker.get('ability'))
            extra = a.get('extra', 0)
            e = mapping(extra)
            scalar = extra if isinstance(extra, (int,float)) else 0
            ed = normalized(mapping(joker.get('modifier')).get('edition'))
            if ed == 'FOIL': chips += 50
            elif ed == 'HOLO': mult += 10
            if key == 'j_joker': mult += a.get('mult',4)
            elif key == 'j_half': mult += np.where(size <= e.get('size',3),e.get('mult',20),0)
            elif key == 'j_banner': chips += discards_left * scalar
            elif key == 'j_mystic_summit': mult += np.where(discards_left == e.get('d_remaining',0),e.get('mult',15),0)
            elif key == 'j_blue_joker': chips += scalar * remaining
            elif key == 'j_abstract': mult += scalar * len(self.jokers)
            elif key == 'j_fortune_teller': mult += mapping(mapping(self.state.get('joker_context')).get('consumeable_usage_total')).get('tarot',0)
            elif key == 'j_bull': chips += scalar * max(0,self.state.get('money',0)+mapping(self.state.get('joker_context')).get('dollar_buffer',0))
            elif key == 'j_bootstraps': mult += e.get('mult',2) * max(0,math.floor((self.state.get('money',0)+mapping(self.state.get('joker_context')).get('dollar_buffer',0))/e.get('dollars',5)))
            elif key == 'j_gros_michel': mult += e.get('mult',15)
            elif key == 'j_cavendish': mult *= e.get('Xmult',3)
            elif key == 'j_green_joker':
                # Its "before" event adds Mult before this hand is scored.
                current = a.get('mult',0) if green_mult is None else green_mult[:,green_index,None]
                mult += current + e.get('hand_add',1)
                green_index += 1
            else:
                condition = {'j_jolly':pair,'j_zany':three,'j_mad':two_pair,
                             'j_crazy':straight,'j_droll':flush,'j_sly':pair,
                             'j_wily':three,'j_clever':two_pair,'j_devious':straight,
                             'j_crafty':flush}[key]
                if key in {'j_sly','j_wily','j_clever','j_devious','j_crafty'}:
                    chips += np.where(condition, a.get('t_chips',0),0)
                else: mult += np.where(condition,a.get('t_mult',0),0)
            if ed == 'POLYCHROME': mult *= 1.5
        return np.floor(chips * mult), kind, groups

    def best(self, hands, discards_left, remaining, green_mult=None):
        score, kinds, groups = self.scores(hands, discards_left, remaining, green_mult)
        # Subsets are ordered by size: ties preserve cards.
        index = score.argmax(axis=1)
        rows = np.arange(len(hands))
        return score[rows,index], kinds[rows,index], index, groups

def analyze(state, trials=1000, seed=20261002, progress=None, cancelled=None):
    from round_planner import RoundPlanner, preference
    started = time.perf_counter()
    if trials < 1:
        raise ValueError('Se necesita al menos una tirada.')
    if state.get('state') != 'SELECTING_HAND':
        return {'status':'waiting','reason':'Esperando una mano para evaluar.'}
    hand = mapping(state.get('hand')).get('cards', [])
    pool = mapping(state.get('draw_pool')).get('cards', [])
    round_info = mapping(state.get('round'))
    if not hand or round_info.get('hands_left',0) < 1:
        return {'status':'waiting','reason':'No hay manos disponibles para jugar.'}
    if len(hand)>12:
        return {'status':'blocked','reason':'Esta versión admite hasta 12 cartas en la mano.'}
    jokers = mapping(state.get('jokers')).get('cards',[])
    unknown = [j.get('label') or j.get('key') for j in jokers if j.get('key') not in SUPPORTED
               and not mapping(j.get('state')).get('debuff')]
    if unknown:
        return {'status':'blocked','reason':'Faltan efectos de estos comodines: '+', '.join(unknown)}
    if jokers and any('ability' not in j for j in jokers):
        return {'status':'blocked','reason':'Reiniciá Balatro para leer los valores internos de los comodines.'}
    current_blind = next((b for b in mapping(state.get('blinds')).values()
                          if isinstance(b,dict) and b.get('status')=='CURRENT'),{})
    blind_ctx = mapping(mapping(state.get('joker_context')).get('blind'))
    if current_blind.get('type') == 'BOSS' and not blind_ctx.get('disabled'):
        return {'status':'blocked','reason':'Los efectos de la ciega jefe todavía requieren simulación específica.'}
    if str(state.get('deck','')).upper() in {'PLASMA','B_PLASMA'}:
        return {'status':'blocked','reason':'Falta implementar la puntuación de la baraja Plasma.'}
    target = max(0,current_blind.get('score',0)-round_info.get('chips',0))
    if not current_blind:
        return {'status':'blocked','reason':'No se pudo identificar la ciega actual.'}
    evaluator = Evaluator(state, hand+pool)
    original = np.arange(len(hand))[None,:]
    discards = round_info.get('discards_left',0)
    scores, kinds, groups = evaluator.scores(original,discards,len(pool))
    hands_left = round_info.get('hands_left',0)
    planner = RoundPlanner(evaluator,len(hand),len(pool),hands_left,discards,target)
    plays, candidates = [], []
    rng = np.random.default_rng(seed)
    # Complete hypothetical decks, shared between first actions. No actual draw order.
    permutations = (np.argsort(rng.random((trials,len(pool))),axis=1)
                    if pool else np.empty((trials,0),dtype=int))
    max_discard = min(5,len(hand))
    def snapshot(done, total, final=False):
        ranked_discards=sorted(candidates,key=preference)
        ranked_plays=sorted(plays,key=preference)
        ranked_all=sorted(plays+candidates,key=preference)
        best=ranked_all[0] if ranked_all else None
        result = {'status':'ready' if final else 'running','partial':not final,
                'completed':done,'total':total,'plays':ranked_plays[:5],
                'discards':ranked_discards[:5],
                'play_options':len(plays), 'discard_options':len(candidates),
                'trials_per_option':trials,'target':target,
                'hands_left':round_info.get('hands_left'), 'discards_left':discards,
                'hand_number':round_info.get('hands_played',0)+1,
                'hands_after_next_play':round_info.get('hands_left',0)-1,
                'discards_after_action':discards-int(best is not None and best['action']=='discard'),
                'hand_cards':hand,
                'elapsed_seconds':round(time.perf_counter()-started,2),
                'scope':'Probabilidad estimada de ganar esta ciega usando todas las manos y descartes disponibles. Prioriza más victorias, después menos manos para ganar y luego el uso de descartes. '+
                        ('Las continuaciones se resuelven exactamente para este estado pequeño.' if planner.exact else
                         'Las continuaciones usan una estrategia aproximada que decide con las cartas visibles y una muestra independiente; no garantiza el óptimo global.')+
                        ' No usa consumibles ni decide compras.',
                'planning_mode':'exact_continuations' if planner.exact else 'adaptive_rollouts',
                'score_mode':'Fichas adicionales acumuladas desde el estado actual; robos sin reemplazo y costos de descarte incluidos.'}
        if best is not None:
            result['recommendation']=best
        return result
    discard_groups = [remove for count in range(1,max_discard+1)
                      for remove in itertools.combinations(range(len(hand)),count)
                      if len(remove)<len(hand) or pool] if discards>0 else []
    total_options=len(groups)+len(discard_groups)
    if progress:
        progress(0,total_options,snapshot(0,total_options))
    # Start with high-scoring plays so early partial results are useful.
    play_order=sorted(range(len(groups)),key=lambda i:(-scores[0,i],len(groups[i]),groups[i]))
    actions=[('play',groups[j],j) for j in play_order]+[('discard',g,None) for g in discard_groups]
    for done,(action,remove,index) in enumerate(actions,1):
        if cancelled and cancelled():
            return {'status':'superseded'}
        result=planner.simulate(action,remove,permutations,seed+1,cancelled)
        if result is None:
            return {'status':'superseded'}
        result.update(action=action,indices=[i+1 for i in (evaluator.order(remove) if action=='play' else remove)])
        if action=='play':
            result.update(hand=NAMES[kinds[0,index]],immediate_score=float(scores[0,index]))
            plays.append(result)
        else:
            candidates.append(result)
        if progress:
            progress(done,total_options,snapshot(done,total_options))
    return snapshot(total_options,total_options,True)
