"""Conservative deductions from public cards and two user-confirmed sort orders.

Hidden rank, suit, enhancement and the anonymous draw bag are never inspected.
Opaque per-hand tokens only track which physical card moved when sorting.
"""
import copy
import json
import secrets
import threading

RANKS = tuple('AKQJT98765432')
SUITS = tuple('SHCD')
MODES = ('rank', 'suit')
# Integer bands preserve the base game's order; equal cards may appear either way.
RANK_VALUE = dict(zip('23456789TJQKA', (200, 300, 400, 500, 600, 700, 800,
                                                900, 1000, 1010, 1020, 1030, 1140)))
SUIT_VALUE = dict(zip('DCHS', (1, 2, 3, 4)))
NORMAL = tuple((rank, suit, False) for rank in RANKS for suit in SUITS)
STONE = tuple((rank, suit, True) for rank in RANKS for suit in SUITS)


def sort_value(candidate, mode):
    rank, suit, stone = candidate
    weight = -1000 if stone else 1000 if mode == 'suit' else 1
    return RANK_VALUE[rank] + SUIT_VALUE[suit] * weight


def is_stone(card):
    return str((card.get('modifier') or {}).get('enhancement', '')).upper() in ('STONE', 'M_STONE')


def public_node(card):
    if (card.get('state') or {}).get('hidden'):
        return {'hidden': True}
    # Stone fronts do not reveal the underlying rank and suit used for sorting.
    if is_stone(card):
        return {'stone': True}
    value = card.get('value') or {}
    return {'rank': value.get('rank'), 'suit': value.get('suit')}


def solve(nodes, observations):
    """Enforce order bounds to a fixed point, keeping every feasible assignment.

    Duplicate cards are allowed in Balatro. Pairwise consistency can retain extra
    possibilities; it never promises uniqueness or assigns invented probabilities.
    """
    domains = {}
    for token, node in nodes.items():
        if node.get('hidden'):
            domains[token] = set(NORMAL + STONE)
        elif node.get('stone'):
            domains[token] = set(STONE)
        elif node.get('rank') in RANKS and node.get('suit') in SUITS:
            domains[token] = {(node['rank'], node['suit'], False)}
        else:
            raise ValueError('Hay cartas visibles con valores o palos que el orden estándar no reconoce.')
    edges = [(left, right, mode) for mode, order in observations.items()
             for left, right in zip(order, order[1:])]
    changed = True
    while changed:
        changed = False
        for left, right, mode in edges:
            if not domains[left] or not domains[right]:
                raise ValueError('Los órdenes registrados se contradicen. Volvé a ordenar en Balatro y registralos de nuevo.')
            right_min = min(sort_value(c, mode) for c in domains[right])
            left_max = max(sort_value(c, mode) for c in domains[left])
            kept_left = {c for c in domains[left] if sort_value(c, mode) >= right_min}
            kept_right = {c for c in domains[right] if sort_value(c, mode) <= left_max}
            if not kept_left or not kept_right:
                raise ValueError('El orden no coincide con el estándar de Balatro. Pulsá el botón de ordenar del juego antes de registrar.')
            if kept_left != domains[left] or kept_right != domains[right]:
                changed = True
                domains[left], domains[right] = kept_left, kept_right
    return domains


class HiddenCardTracker:
    def __init__(self):
        self.lock = threading.RLock()
        self.signature = None
        self.hand_id = None
        self.tokens = {}
        self.nodes = {}
        self.order = []
        self.observations = {}
        self.labels = {}
        self.reason = None

    def reset(self):
        with self.lock:
            self.signature = None
            self.hand_id = None
            self.tokens = {}
            self.nodes = {}
            self.order = []
            self.observations = {}
            self.labels = {}
            self.reason = None

    def prepare(self, data):
        """Attach tracking tokens before the reader removes hidden identities."""
        with self.lock:
            cards = (data.get('hand') or {}).get('cards', [])
            if data.get('state') != 'SELECTING_HAND' or not cards:
                self.reset()
                return
            identities = [card.get('id') for card in cards]
            if any(not isinstance(i, (int, str)) or isinstance(i, bool) for i in identities) or len(set(identities)) != len(cards):
                self.reset()
                self.reason = 'No se puede seguir cada carta al cambiar el orden: faltan identificadores únicos en la lectura.'
                return
            # Only public changes reset observations. Never include hidden values.
            public = [(str(card['id']), public_node(card)) for card in cards]
            signature = json.dumps({
                'cards': sorted(public, key=lambda c: c[0]),
                'ante': data.get('ante_num'), 'round': data.get('round_num'),
                'resources': {key: (data.get('round') or {}).get(key) for key in
                              ('hands_left', 'discards_left', 'hands_played', 'discards_used', 'chips')},
                'money': data.get('money'),
                'consumables': [(c.get('id'), c.get('key')) for c in
                                (data.get('consumables') or {}).get('cards', [])],
                'usage': (data.get('joker_context') or {}).get('consumeable_usage_total'),
            }, sort_keys=True)
            if signature != self.signature:
                self.reset()
                self.signature = signature
                self.hand_id = secrets.token_urlsafe(12)
                self.tokens = {identity: secrets.token_urlsafe(12) for identity in identities}
                for card in cards:
                    if (card.get('state') or {}).get('hidden'):
                        number, label = len(self.labels) + 1, ''
                        while number:
                            number, remainder = divmod(number - 1, 26)
                            label = chr(65 + remainder) + label
                        self.labels[self.tokens[card['id']]] = label
            self.order = [self.tokens[i] for i in identities]
            self.nodes = {self.tokens[c['id']]: public_node(c) for c in cards}
            for card, token in zip(cards, self.order):
                card['tracking_token'] = token

    def capture(self, mode, hand_id):
        with self.lock:
            if mode not in MODES:
                raise ValueError('Elegí Categoría o Palo para registrar el orden.')
            if not self.hand_id or hand_id != self.hand_id:
                raise ValueError('La mano cambió. Esperá a que se actualice el panel y registrá el nuevo orden.')
            if not any(node.get('hidden') for node in self.nodes.values()):
                raise ValueError('Esta mano no tiene cartas dadas vuelta.')
            proposed = dict(self.observations, **{mode: list(self.order)})
            solve(self.nodes, proposed)
            self.observations = proposed
            return self.view()

    def clear(self, hand_id):
        with self.lock:
            if not self.hand_id or hand_id != self.hand_id:
                raise ValueError('La mano cambió. Esperá a que se actualice el panel.')
            self.observations = {}
            return self.view()

    def view(self):
        with self.lock:
            result = {'hand_id': self.hand_id, 'observations': list(self.observations), 'cards': [],
                      'reason': self.reason, 'method': 'public_sort_bounds'}
            if not self.nodes or not any(n.get('hidden') for n in self.nodes.values()):
                return result
            try:
                domains = solve(self.nodes, self.observations)
            except ValueError as exc:
                result['reason'] = str(exc)
                return result
            for index, token in enumerate(self.order, 1):
                if not self.nodes[token].get('hidden'):
                    continue
                normal = [c for c in NORMAL if c in domains[token]]
                result['cards'].append({
                    'token': token, 'position': index, 'label': self.labels[token],
                    'ranks': [r for r in RANKS if any(c[0] == r for c in normal)],
                    'suits': [s for s in SUITS if any(c[1] == s for c in normal)],
                    'candidates': [{'rank': r, 'suit': s} for r, s, _ in normal],
                    'stone_possible': any(c[2] for c in domains[token]),
                    'identified': len(normal) == 1 and not any(c[2] for c in domains[token]),
                })
            return copy.deepcopy(result)
