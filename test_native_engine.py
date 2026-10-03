"""Live-state adapter checks. All actions run in the isolated engine."""
import copy
import io
import json
import unittest
from unittest.mock import patch

from native_engine import request, analyze, executable
from test_simulator import state, card
import reader


def joker(key, **ability):
    return {'key': key, 'ability': ability, 'modifier': {}, 'state': {}}


def consumable(key):
    return {'key': key, 'modifier': {}, 'ability': {}, 'state': {}}


def fixture(cards=None, jokers=None, boss=None):
    s = state(cards or [card('A'), card('K'), card('Q'), card('J'), card('T')],
              [card('2'), card('3'), card('4')], jokers)
    s['hand']['limit'] = len(s['hand']['cards'])
    s['round'].update(hands_left=4, discards_left=3)
    s['blinds']['small']['score'] = 100000
    s['money'] = 20
    s['consumables'] = {'cards': [], 'limit': 2}
    s['joker_context'] = {'probabilities': {'normal': 1}, 'last_tarot_planet': 'c_pluto'}
    if boss:
        s['blinds'] = {'boss': {'status': 'CURRENT', 'type': 'BOSS', 'score': 100000}}
        s['active_blind'] = {'key': boss, 'chips': 100000}
    return s


@unittest.skipUnless(executable().is_file(), 'Build the native engine before running these tests')
class NativeEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = request({'op': 'catalog'})

    def invoke(self, s, move=None):
        payload = {'op': 'step' if move else 'import', 'state': s}
        if move:
            payload['move'] = move
        result = request(payload)
        self.assertNotEqual(result.get('status'), 'blocked', result)
        return result

    def play(self, s, indices=None):
        return self.invoke(s, {'action': 'play', 'indices': indices or list(range(len(s['hand']['cards'])))})

    def test_complete_registry_and_every_joker_imports_and_scores(self):
        self.assertEqual(len(set(self.catalog['jokers'])), 150)
        self.assertEqual(len(set(self.catalog['bosses'])), 28)
        self.assertEqual(len(set(self.catalog['consumables'])), 52)
        for key in self.catalog['jokers']:
            with self.subTest(key=key):
                result = self.play(fixture(jokers=[joker(key)]))
                self.assertIn('last_play', result)

    def test_every_boss_imports_and_applies(self):
        for key in self.catalog['bosses']:
            with self.subTest(key=key):
                result = self.play(fixture(boss=key))
                self.assertEqual(result['active_blind']['proto'], key)

    def test_every_consumable_has_a_legal_executable_effect(self):
        for key in self.catalog['consumables']:
            with self.subTest(key=key):
                s = fixture(jokers=[joker('j_joker'), joker('j_green_joker')])
                s['consumables']['cards'] = [consumable(key)]
                moves = request({'op': 'moves', 'state': s})
                uses = [m for m in moves if m['action'] == 'use']
                self.assertTrue(uses, key)
                self.invoke(s, uses[0])
                self.assertEqual(len({json.dumps(m, sort_keys=True) for m in moves}), len(moves))

    def test_blueprint_brainstorm_and_current_accumulators(self):
        s = fixture([card('A')], [joker('j_blueprint'), joker('j_green_joker', mult=9), joker('j_brainstorm')])
        r = self.play(s)
        self.assertEqual(r['last_play']['score'], 16 * 31)
        self.assertEqual(r['jokers'][1]['state']['mult'], 10)
        s = fixture([card('2')], [joker('j_wee', extra={'chips': 80})])
        self.assertEqual(self.play(s)['last_play']['score'], 7 + 88)

    def test_all_enhancements_editions_and_seals_and_plasma(self):
        for enhancement in ['BONUS','MULT','WILD','GLASS','STEEL','STONE','GOLD','LUCKY']:
            for seal in ['RED','BLUE','PURPLE','GOLD']:
                with self.subTest(enhancement=enhancement, seal=seal):
                    self.play(fixture([card('A', enhancement=enhancement, seal=seal)]))
        for edition in ['FOIL','HOLO','POLYCHROME']:
            self.play(fixture([card('A', edition=edition)]))
        s = fixture([card('A')]); s['deck'] = 'PLASMA'
        self.assertEqual(self.play(s)['last_play']['score'], 72)

    def test_boss_hand_history_debuffs_and_sale(self):
        for boss, extra in [('bl_eye', {'hands': {'High Card': True}}), ('bl_mouth', {'only_hand': 'Pair'})]:
            s = fixture([card('A')], boss=boss); s['active_blind'].update(extra)
            self.assertEqual(self.play(s)['last_play']['score'], 0)
        s = fixture([card('A')], [joker('j_joker')], 'bl_final_leaf')
        self.assertTrue(self.invoke(s)['hand'][0]['debuff'])
        sold = self.invoke(s, {'action':'sell_joker','indices':[],'slot':0})
        self.assertTrue(sold['active_blind']['disabled'])
        self.assertFalse(sold['hand'][0]['debuff'])
        s['jokers']['cards'][0]['ability']['eternal'] = True
        moves = request({'op':'moves','state':s})
        self.assertFalse(any(m['action']=='sell_joker' for m in moves))

    def test_ankh_hex_preserve_eternal_and_death_copies_both_directions(self):
        for key in ['c_ankh','c_hex']:
            s=fixture(jokers=[joker('j_joker',eternal=True),joker('j_green_joker',eternal=True)])
            s['consumables']['cards']=[consumable(key)]
            r=self.invoke(s,{'action':'use','indices':[],'slot':0})
            self.assertGreaterEqual(len(r['jokers']),2)
        s=fixture([card('2'),card('A',seal='RED')]);s['consumables']['cards']=[consumable('c_death')]
        for order,rank in [([0,1],14),([1,0],2)]:
            r=self.invoke(s,{'action':'use','indices':order,'slot':0})
            self.assertEqual([c['rank'] for c in r['hand']],[rank,rank])

    def test_tarots_levels_probability_resources_and_starting_deck_import(self):
        s=fixture([card('A')],[joker('j_fortune_teller')])
        s['joker_context'].update(consumeable_usage_total={'tarot':12},starting_deck_size=40,edition_rate=4)
        s['hands']={'High Card': {'level':3,'chips':25,'mult':3,'played':10,'played_this_round':2}}
        r=self.play(s)
        self.assertEqual(r['last_play']['score'],36*15)
        self.assertEqual(r['hands_table']['rows'][0]['played'],11)
        self.assertEqual(r['reader_starting_deck_size'],40)
        self.assertEqual(r['edition_rate'],4)

    def test_hidden_identity_and_draw_order_do_not_affect_results(self):
        s=fixture([{'state':{'hidden':True}}]);s['unseen_cards']=[card('2'),card('A'),card('K'),card('3')]
        s['round'].update(hands_left=1,discards_left=0)
        s['blinds']['small']['score']=16
        r=analyze(s,1000)
        t=copy.deepcopy(s);t['draw_pool']['cards'].reverse()
        r2=analyze(t,1000)
        self.assertEqual(r['plays'],r2['plays'])
        self.assertGreater(r['plays'][0]['win_probability'],0)
        self.assertLess(r['plays'][0]['win_probability'],1)
        s=fixture([card('2')]);s['round'].update(hands_left=1,discards_left=2)
        s['blinds']['small']['score']=16
        r=analyze(s,100);t=copy.deepcopy(s);t['draw_pool']['cards'].reverse()
        self.assertEqual(r['discards'],analyze(t,100)['discards'])

    def test_random_creation_respects_locked_profile(self):
        s=fixture();s['consumables']['cards']=[consumable('c_judgement')]
        s['excluded_jokers']=[key for key in self.catalog['jokers'] if key!='j_joker']
        r=self.invoke(s,{'action':'use','indices':[],'slot':0})
        self.assertEqual(r['jokers'][0]['id'],'Joker')

    def test_equal_wins_do_not_add_an_unnecessary_sale(self):
        s=fixture([card('A'),card('K'),card('Q'),card('9'),card('2')],[joker('j_dna')])
        s['round'].update(hands_left=1,discards_left=0)
        s['blinds']['small']['score']=400
        s['consumables']['cards']=[consumable('c_jupiter')]
        r=analyze(s,100)
        self.assertEqual(r['recommendation']['action'],'use')
        self.assertEqual(r['recommendation']['expected_inventory_spent'],1)

    def test_rental_prices_fees_and_perishable_expiry(self):
        s=fixture([card('A')],[joker('j_swashbuckler'),joker('j_baron',rental=True)])
        self.assertEqual(self.play(s)['last_play']['score'],32)
        sold=self.invoke(s,{'action':'sell_joker','indices':[],'slot':1})
        self.assertEqual(sold['dollars'],21)
        s=fixture([card('A')],[joker('j_joker',rental=True,perishable=True,perish_tally=1)])
        s['blinds']['small']['score']=16
        s['joker_context']['rental_rate']=4
        r=self.play(s)
        self.assertEqual(r['dollars'],16)
        self.assertEqual(r['jokers'][0]['perish_tally'],0)
        self.assertTrue(r['jokers'][0]['debuffed'])

    def test_spectral_copies_keep_rental_and_perishable_stickers(self):
        s=fixture(jokers=[joker('j_joker',rental=True,perishable=True,perish_tally=3)])
        s['consumables']['cards']=[consumable('c_ankh')]
        r=self.invoke(s,{'action':'use','indices':[],'slot':0})
        self.assertEqual(len(r['jokers']),2)
        self.assertTrue(all(j['rental'] and j['perish_tally']==3 for j in r['jokers']))

    def test_full_round_1000_trials_partials_and_discard_chain(self):
        s=fixture([card('2')]);s['draw_pool']['cards']=[card('3'),card('A')]
        s['round'].update(hands_left=1,discards_left=2);s['blinds']['small']['score']=16
        partials=[]
        r=analyze(s,1000,progress=lambda *args:partials.append(args[2]))
        self.assertEqual(r['recommendation']['action'],'discard')
        self.assertEqual(r['recommendation']['win_probability'],1)
        self.assertEqual(r['recommendation']['trials'],1000)
        self.assertTrue(any(p.get('recommendation') for p in partials))
        self.assertEqual(analyze(s,1000,cancelled=lambda:True)['status'],'superseded')

    def test_unknown_modded_content_is_explained(self):
        s=fixture(jokers=[joker('j_fake_mod')]);r=analyze(s,1)
        self.assertEqual(r['status'],'blocked')
        self.assertIn('j_fake_mod',r['reason'])


class ReaderNormalizationTests(unittest.TestCase):
    def capture(self,data):
        encoded=json.dumps({'result':data}).encode()
        with patch('reader.urlopen',return_value=io.BytesIO(encoded)):
            return reader.state()

    def test_empty_lua_arrays_are_normalized(self):
        r=self.capture({'hand':[],'cards':[],'jokers':[],'consumables':[]})
        self.assertEqual(r['hand']['cards'],[])
        self.assertEqual(r['draw_pool']['cards'],[])

    def test_hidden_composition_is_anonymous_and_forced_slot_retained(self):
        hidden=card('A');hidden.update(id=99,ability={'forced_selection':True});hidden['state']['hidden']=True
        r=self.capture({'hand':{'cards':[hidden]},'cards':{'cards':[card('2')]}})
        self.assertNotIn('value',r['hand']['cards'][0])
        self.assertTrue(r['hand']['cards'][0]['state']['forced_selection'])
        self.assertEqual(len(r['unseen_cards']),2)
        self.assertFalse(any('id' in c or 'state' in c for c in r['unseen_cards']))


if __name__=='__main__':
    unittest.main()
