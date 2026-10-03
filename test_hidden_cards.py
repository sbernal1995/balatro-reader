import copy
import io
import itertools
import json
import random
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import reader
from hidden_cards import HiddenCardTracker, NORMAL, STONE, solve, sort_value


def card(identity, rank='Q', suit='C', hidden=False, stone=False):
    return {'id': identity, 'value': {'rank': rank, 'suit': suit}, 'state': {'hidden': hidden},
            'modifier': {'enhancement': 'STONE' if stone else 'BASE'}, 'ability': {},
            'key': f'{suit}_{rank}', 'runtime': {'secret': rank + suit}}


def state(cards):
    return {'state': 'SELECTING_HAND', 'ante_num': 1, 'round_num': 1,
            'round': {'hands_left': 3, 'discards_left': 2, 'hands_played': 0, 'chips': 0},
            'hand': {'cards': cards}, 'consumables': {'cards': []}, 'cards': {'cards': []}}


class InferenceTests(unittest.TestCase):
    def setUp(self):
        self.tracker = HiddenCardTracker()
        self.rank_cards = [card(1,'K','S'), card(2,'K','H'), card(3,'Q','H'),
                           card(7, hidden=True), card(4,'J','H'), card(5,'T','H'), card(6,'T','C')]
        self.suit_cards = [self.rank_cards[i] for i in (0,1,2,4,5,3,6)]

    def prepare(self, cards):
        data = state(copy.deepcopy(cards))
        self.tracker.prepare(data)
        return data

    def capture(self, mode):
        return self.tracker.capture(mode, self.tracker.view()['hand_id'])

    def test_two_orders_identify_queen_of_clubs_without_reading_hidden_value(self):
        self.prepare(self.rank_cards)
        first = self.capture('rank')['cards'][0]
        self.assertGreater(len(first['candidates']), 1)
        self.assertFalse(first['identified'])
        self.assertLess(len(first['candidates']), len(first['ranks']) * len(first['suits']))
        self.prepare(self.suit_cards)
        inferred = self.capture('suit')['cards'][0]
        self.assertEqual(inferred['candidates'], [{'rank':'Q','suit':'C'}])
        self.assertTrue(inferred['identified'])
        self.assertFalse(inferred['stone_possible'])
        self.assertEqual(inferred['position'], 6)
        self.assertEqual(inferred['label'], 'A')
        self.assertEqual(first['token'], inferred['token'])

    def test_hidden_secrets_and_bag_do_not_change_deductions_or_epoch(self):
        data = self.prepare(self.rank_cards)
        before = self.capture('rank')
        data['hand']['cards'][3].update(value={'rank':'2','suit':'D'},
                                       modifier={'enhancement':'STONE'}, ability={'extra':999})
        data['unseen_cards'] = [card(90,'A','S')]
        self.tracker.prepare(data)
        self.assertEqual(self.tracker.view(), before)

    def test_multiple_hidden_cards_keep_their_labels_when_swapped(self):
        cards = [card(1,'A','S'), card(2, hidden=True), card(3, hidden=True), card(4,'2','D')]
        data = self.prepare(cards)
        before = self.capture('rank')
        data['hand']['cards'][1:3] = reversed(data['hand']['cards'][1:3])
        self.tracker.prepare(data)
        self.capture('suit')
        after = self.tracker.view()
        self.assertEqual([c['label'] for c in before['cards']], ['A','B'])
        self.assertEqual([c['label'] for c in after['cards']], ['B','A'])
        self.assertEqual(before['hand_id'], after['hand_id'])

    def test_duplicate_cards_remain_possible(self):
        self.prepare([card(1,'J','H'), card(2,hidden=True), card(3,'J','H'), card(4,hidden=True)])
        result = self.capture('rank')['cards']
        self.assertEqual(result[0]['candidates'], [{'rank':'J','suit':'H'}])
        self.assertIn({'rank':'J','suit':'H'}, result[1]['candidates'])

    def test_stone_possible_at_bottom_and_does_not_claim_visible_base_rank(self):
        self.prepare([card(1,'2','D'),card(2,hidden=True)])
        result = self.capture('rank')['cards'][0]
        self.assertTrue(result['stone_possible'])
        self.assertFalse(result['identified'])
        self.assertEqual(result['candidates'], [{'rank':'2','suit':'D'}])
        data = self.prepare([card(1,stone=True),card(2,hidden=True)])
        before = self.capture('rank')
        data['hand']['cards'][0]['value'] = {'rank':'A','suit':'S'}
        self.tracker.prepare(data)
        self.assertEqual(before, self.tracker.view())

    def test_reordering_preserves_observations_but_actions_reset_them(self):
        data = self.prepare(self.rank_cards)
        self.capture('rank')
        data['hand']['cards'].reverse()
        self.tracker.prepare(data)
        self.assertEqual(self.tracker.view()['observations'], ['rank'])
        previous = self.tracker.view()['hand_id']
        data['round']['discards_left'] -= 1
        self.tracker.prepare(data)
        self.assertEqual(self.tracker.view()['observations'], [])
        self.assertNotEqual(previous, self.tracker.view()['hand_id'])
        with self.assertRaises(ValueError): self.tracker.capture('rank', previous)

    def test_new_draw_reveal_consumable_and_phase_clear_observations(self):
        for change in (
            lambda d: d['hand']['cards'].__setitem__(3,card(99,hidden=True)),
            lambda d: d['hand']['cards'][3]['state'].update(hidden=False),
            lambda d: d['consumables']['cards'].append({'id':8,'key':'c_moon'}),
            lambda d: d.update(state='SHOP'),
        ):
            with self.subTest(change=change):
                data = self.prepare(self.rank_cards)
                self.capture('rank')
                change(data)
                self.tracker.prepare(data)
                self.assertEqual(self.tracker.view()['observations'], [])
                self.tracker.reset()

    def test_wrong_sort_is_rejected_without_losing_good_observation(self):
        data = self.prepare(self.rank_cards)
        before = self.capture('rank')
        data['hand']['cards'][0:2] = reversed(data['hand']['cards'][0:2])
        self.tracker.prepare(data)
        with self.assertRaises(ValueError): self.capture('suit')
        self.assertEqual(self.tracker.view(), before)
        data['hand']['cards'].reverse()
        self.tracker.prepare(data)
        with self.assertRaises(ValueError): self.capture('rank')
        self.assertEqual(self.tracker.view()['observations'], ['rank'])

    def test_no_observation_missing_identity_clear_and_unknown_value(self):
        data = self.prepare(self.rank_cards)
        self.assertEqual(len(self.tracker.view()['cards'][0]['candidates']),52)
        self.capture('rank')
        self.tracker.clear(self.tracker.view()['hand_id'])
        self.assertEqual(self.tracker.view()['observations'], [])
        data['hand']['cards'][0]['id'] = None
        self.tracker.prepare(data)
        self.assertIsNotNone(self.tracker.view()['reason'])
        self.assertIsNone(self.tracker.view()['hand_id'])
        data = self.prepare([card(1,'UNKNOWN'), card(2,hidden=True)])
        with self.assertRaises(ValueError): self.capture('rank')

    def test_sort_order_ace_faces_suits_stone_and_ties(self):
        self.assertEqual(sorted(['J','A','T','K','Q'],key=lambda r:sort_value((r,'D',False),'rank'),reverse=True),
                         ['A','K','Q','J','T'])
        self.assertGreater(sort_value(('A','D',False),'rank'),sort_value(('K','S',False),'rank'))
        self.assertGreater(sort_value(('2','S',False),'suit'),sort_value(('A','H',False),'suit'))
        self.assertLess(max(sort_value(c,'rank') for c in STONE),min(sort_value(c,'rank') for c in NORMAL))
        self.assertEqual(sort_value(('A','D',True),'suit'),sort_value(('A','D',True),'rank'))

    def test_order_bounds_never_remove_feasible_joint_assignments(self):
        rng = random.Random(5)
        # Independent exhaustive reference for two hidden cards, including Stones.
        for trial in range(8):
            true = {str(i): rng.choice(NORMAL + STONE) for i in range(4)}
            nodes = {key: {'hidden': True} if key in ('1','2') else
                     {'stone':True} if c[2] else {'rank':c[0],'suit':c[1]} for key,c in true.items()}
            orders = {mode:sorted(true, key=lambda key:sort_value(true[key],mode),reverse=True) for mode in ('rank','suit')}
            domains = solve(nodes,orders)
            for left,right in itertools.product(NORMAL+STONE,repeat=2):
                assignment = dict(true, **{'1':left,'2':right})
                if all(all(sort_value(assignment[a],mode)>=sort_value(assignment[b],mode)
                           for a,b in zip(order,order[1:])) for mode,order in orders.items()):
                    self.assertIn(left,domains['1'],trial)
                    self.assertIn(right,domains['2'],trial)


class ReaderInferenceTests(unittest.TestCase):
    def test_reader_hides_secrets_and_does_not_link_anonymous_bag_to_token(self):
        tracker = HiddenCardTracker()
        raw = state([card(901,'A','S',True),card(902,'K','H')])
        payload = json.dumps({'result':raw}).encode()
        with patch('reader.hidden_tracker',tracker), patch('reader.urlopen',side_effect=lambda *a,**k:io.BytesIO(payload)):
            data = reader.state()
        hidden = data['hand']['cards'][0]
        self.assertIn('tracking_token',hidden)
        for key in ('id','key','value','modifier','ability','runtime'): self.assertNotIn(key,hidden)
        self.assertNotIn('tracking_token',data['unseen_cards'][0])
        self.assertNotIn('id',data['unseen_cards'][0])
        self.assertEqual(len(data['hidden_inference']['cards'][0]['candidates']),52)

    def test_observations_do_not_cancel_simulation_but_hidden_card_order_does(self):
        data = state([{'state':{'hidden':True},'tracking_token':'opaque-a'},
                      {'state':{'hidden':True},'tracking_token':'opaque-b'}])
        before = reader.fingerprint(data)
        data['hidden_inference'] = {'observations':['rank','suit']}
        self.assertEqual(before,reader.fingerprint(data))
        data['hand']['cards'].reverse()
        self.assertNotEqual(before,reader.fingerprint(data))

    def test_local_capture_endpoint_and_clear_do_not_call_game_actions(self):
        tracker = HiddenCardTracker()
        raw = state([card(1,'A','S'),card(2,hidden=True),card(3,'2','D')])
        tracker.prepare(raw)
        raw['hidden_inference'] = tracker.view()
        server = ThreadingHTTPServer(('127.0.0.1',0),reader.Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}'
        def post(body, origin=None):
            headers = {'Content-Type':'application/json'}
            if origin: headers['Origin'] = origin
            payload = json.dumps(body).encode() if body is not None else None
            return urlopen(Request(base+'/hidden-observation',payload,headers,method='POST'),timeout=3)
        try:
            with patch('reader.hidden_tracker',tracker), patch('reader.state',return_value=raw) as read, \
                    patch('reader.cached',None), patch('reader.problem',None), patch.object(reader.simulations,'submit') as simulate:
                for mode in ('rank','clear'):
                    with post({'mode':mode,'hand_id':tracker.view()['hand_id']}) as response:
                        result = json.load(response)
                        self.assertEqual(response.status,200)
                        self.assertEqual(result['inference']['observations'], [] if mode=='clear' else ['rank'])
                with self.assertRaises(HTTPError) as error: post({'mode':'rank','hand_id':'old'})
                self.assertEqual(error.exception.code,409)
                error.exception.close()
                with self.assertRaises(HTTPError) as error: post(None,'https://foreign.example')
                self.assertEqual(error.exception.code,403)
                error.exception.close()
                self.assertEqual(read.call_count,3)
                simulate.assert_not_called()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__': unittest.main()
