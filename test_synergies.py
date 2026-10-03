import copy
import io
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen
from unittest.mock import patch

import reader
from native_engine import executable, request
from synergies import LIBRARY, JOKERS, evaluate, purchase
from test_simulator import card


def joker(key, **modifier):
    return {'key': key, 'label': JOKERS.get(key, {}).get('name', key),
            'value': {}, 'modifier': modifier, 'ability': {}, 'state': {}, 'cost': {'buy': 6}}


def shop(owned=None, offers=None, deck=None):
    return {'state':'SHOP', 'money':20, 'round':{'hands_left':0, 'discards_left':0},
            'jokers':{'cards':owned or [], 'limit':5}, 'consumables':{'cards':[], 'limit':2},
            'collection':{'cards':deck if deck is not None else [card(r) for r in '23456789TJQKA']},
            'shop':{'cards':offers or []}, 'hands':{'Pair':{'level':1, 'played':0}}}


class SynergyTests(unittest.TestCase):
    @unittest.skipUnless(executable().is_file(), 'Build the native engine to check consumable identities')
    def test_build_consumables_exist_in_the_rules_registry(self):
        catalog = set(request({'op':'catalog'})['consumables'])
        for build in LIBRARY['builds']:
            for key in build['tarots'] + build['planets']:
                self.assertIn(key, catalog, build['id'])

    def test_library_keys_sources_and_catalog_are_valid(self):
        self.assertEqual(len(JOKERS),150)
        self.assertEqual(len(LIBRARY['builds']),12)
        self.assertEqual(len({b['id'] for b in LIBRARY['builds']}),12)
        for b in LIBRARY['builds']:
            self.assertTrue(b['core'])
            for k in b['core'] + b['support']: self.assertIn(k,JOKERS)
            for source in b['sources']: self.assertTrue(LIBRARY['sources'][source]['url'].startswith('https://'))

    def test_owned_partner_increases_affinity(self):
        offer=joker('j_hanging_chad')
        alone=evaluate(shop(offers=[offer]))['shop'][0]
        paired=evaluate(shop([joker('j_photograph')],[offer]))['shop'][0]
        self.assertGreater(paired['percent'],alone['percent'])
        self.assertIn('j_photograph',paired['partners'])
        self.assertEqual(paired['build_id'],'photochad')

    def test_deck_composition_matters(self):
        owned,offers=[joker('j_mime')],[joker('j_baron')]
        low=evaluate(shop(owned,offers,[card('2')]*20))['shop'][0]['percent']
        high=evaluate(shop(owned,offers,[card('K')]*20))['shop'][0]['percent']
        self.assertGreater(high,low)
        self.assertLessEqual(low,30)

    def test_steel_does_not_turn_non_kings_into_baron_triggers(self):
        offer=joker('j_baron')
        x=evaluate(shop([joker('j_mime')],[offer],[card('Q',enhancement='STEEL')]*10))['shop'][0]
        self.assertIn('0 de 10',x['reasons'][1])

    def test_steel_joker_without_steel_has_low_fit(self):
        x=evaluate(shop([joker('j_baron'),joker('j_mime')],[joker('j_steel_joker')],[card('K')]*10))['shop'][0]
        self.assertLessEqual(x['percent'],30)
        self.assertIn('No hay acero',' '.join(x['reasons']))

    def test_smeared_expands_effective_hearts(self):
        s=shop([joker('j_bloodstone')],[joker('j_oops')],[card('2','D')]*10)
        before=evaluate(s)['shop'][0]['percent']
        s['jokers']['cards'].append(joker('j_smeared'))
        after=evaluate(s)['shop'][0]
        self.assertGreater(after['percent'],before)
        self.assertIn('10 de 10',after['reasons'][1])

    def test_hand_levels_and_plays_increase_development(self):
        s=shop([joker('j_photograph')],[joker('j_hanging_chad')])
        before=evaluate(s)['shop'][0]['percent']
        s['hands']['Pair']={'level':10,'played':20}
        self.assertEqual(evaluate(s)['shop'][0]['percent']-before,15)

    def test_target_is_not_an_imaginary_owned_partner(self):
        s=shop(offers=[joker('j_baron')])
        actual=evaluate(s)
        goal=evaluate(s,'baron-mime')
        self.assertEqual(actual['shop'][0]['percent'],goal['shop'][0]['percent'])
        self.assertEqual(goal['selected_id'],'baron-mime')
        self.assertTrue(goal['shop'][0]['target_piece'])
        self.assertIsNone(actual['detected_id'])

    def test_unknown_or_unprofiled_joker_has_no_invented_score(self):
        for key in ['j_joker','j_modded_unknown']:
            item=evaluate(shop(offers=[joker(key)]))['shop'][0]
            self.assertIsNone(item['percent'])
            self.assertIn('Sin relación revisada',item['reasons'][0])

    def test_blueprint_respects_compatibility(self):
        s=shop([joker('j_four_fingers'),joker('j_shortcut')],[joker('j_blueprint')])
        self.assertIsNone(evaluate(s)['shop'][0]['percent'])
        s['jokers']['cards'].append(joker('j_runner'))
        item=evaluate(s)['shop'][0]
        self.assertIsNotNone(item['percent'])
        self.assertEqual(item['partners'],['j_runner'])

    def test_conflict_both_purchase_directions(self):
        for existing,new in [('j_pareidolia','j_ride_the_bus'),('j_ride_the_bus','j_pareidolia')]:
            item=evaluate(shop([joker(existing)],[joker(new)]))['shop'][0]
            self.assertEqual(item['penalty'],45)
            self.assertTrue(any('reinicia' in x for x in item['warnings']))

    def test_vampire_warns_lucky_enhancement_consumption(self):
        s=shop([joker('j_lucky_cat'),joker('j_midas_mask')],[joker('j_vampire')])
        item=evaluate(s)['shop'][0]
        self.assertEqual(item['penalty'],20)
        self.assertTrue(item['warnings'])

    def test_price_and_capacity_do_not_change_affinity(self):
        s=shop([joker('j_photograph')],[joker('j_hanging_chad')])
        first=evaluate(s)['shop'][0]
        s['money']=0;s['jokers']['limit']=1
        second=evaluate(s)['shop'][0]
        self.assertEqual(first['percent'],second['percent'])
        self.assertFalse(second['purchase']['can_buy_now'])
        self.assertFalse(second['purchase']['affordable'])
        self.assertFalse(second['purchase']['space_available'])

    def test_credit_and_negative_joker_capacity(self):
        s=shop([joker('j_credit_card')]);s['money']=-10;s['jokers']['limit']=1
        self.assertTrue(purchase(s,joker('j_photograph',edition='NEGATIVE'))['can_buy_now'])
        self.assertFalse(purchase(s,joker('j_photograph'))['can_buy_now'])

    def test_full_eternal_slots_and_rental_expiry(self):
        s=shop([joker('j_photograph',eternal=True)]);s['jokers']['limit']=1
        offer=joker('j_hanging_chad',rental=True,perishable=2)
        notes=' '.join(purchase(s,offer)['notes'])
        self.assertIn('sin cartas visibles',notes)
        self.assertIn('$3',notes)
        self.assertIn('2 rondas',notes)

    def test_missing_collection_is_not_replaced_by_draw_pile(self):
        s=shop([joker('j_photograph')],[joker('j_hanging_chad')]);s.pop('collection')
        s['draw_pool']={'cards':[card('K')]*40}
        item=evaluate(s)['shop'][0]
        self.assertIsNone(item['percent'])
        self.assertIn('Falta la baraja completa',' '.join(item['reasons']))

    def test_hidden_collection_without_anonymous_composition_blocks_percent(self):
        s=shop([joker('j_mime')],[joker('j_baron')])
        s['collection']['cards'][0]['state']['hidden']=True
        self.assertIsNone(evaluate(s)['shop'][0]['percent'])

    def test_reader_provides_whole_deck_counts_without_hidden_slot_identity(self):
        s=shop([joker('j_mime')],[joker('j_baron')],[card('K')]*4+[card('2')]*8)
        s=copy.deepcopy(s)
        for i,c in enumerate(s['collection']['cards']):
            c['id']=i+100;c['state']['hidden']=True
        raw=json.dumps({'result':s}).encode()
        with patch('reader.urlopen',return_value=io.BytesIO(raw)):
            normalized=reader.state()
        self.assertTrue(all('id' not in c and 'rank' not in c.get('value',{}) for c in normalized['collection']['cards']))
        composition=normalized['deck_composition']['cards']
        self.assertEqual(len(composition),12)
        self.assertTrue(all('id' not in c and 'runtime' not in c for c in composition))
        item=evaluate(normalized)['shop'][0]
        self.assertIsNotNone(item['percent'])
        self.assertIn('4 de 12',' '.join(item['reasons']))

    def test_hidden_joker_is_not_a_partner(self):
        hidden=joker('j_photograph');hidden['state']['hidden']=True
        s=shop([hidden],[joker('j_hanging_chad')])
        result=evaluate(s)
        self.assertFalse(result['shop'][0]['partners'])
        self.assertIsNone(result['detected_id'])
        self.assertTrue(result['warnings'])

    def test_hidden_shop_card_has_no_identity_or_score(self):
        hidden=joker('j_hanging_chad');hidden['state']['hidden']=True
        item=evaluate(shop([joker('j_photograph')],[hidden]))['shop'][0]
        self.assertIsNone(item['percent'])
        self.assertFalse(item['matches'])
        self.assertNotIn('key',item['card'])

    def test_stale_shop_inventory_outside_shop_is_hidden(self):
        s=shop([joker('j_photograph')],[joker('j_hanging_chad')]);s['state']='SELECTING_HAND'
        self.assertFalse(evaluate(s)['shop'])

    def test_consumables_follow_existing_build(self):
        s=shop([joker('j_baron')],[{'key':'c_chariot','cost':{'buy':3}}])
        item=evaluate(s)['shop'][0]
        self.assertEqual(item['build_id'],'baron-mime')
        self.assertIsNotNone(item['percent'])
        self.assertIsNone(evaluate(shop(offers=s['shop']['cards']))['shop'][0]['percent'])

    def test_analysis_is_readonly_and_bounded(self):
        s=shop([joker('j_photograph'),joker('j_baron')],[joker(k) for k in JOKERS])
        before=copy.deepcopy(s);signature=reader.fingerprint(s)
        result=evaluate(s)
        self.assertEqual(s,before);self.assertEqual(reader.fingerprint(s),signature)
        for item in result['shop']:
            if item['percent'] is not None: self.assertTrue(0<=item['percent']<=100)

    def test_invalid_build_rejected(self):
        with self.assertRaises(ValueError): evaluate(shop(),'https://example.com')


class SynergyHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),reader.Handler)
        cls.base='http://127.0.0.1:'+str(cls.server.server_port)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def test_library_and_assets_available_without_game(self):
        with patch.object(reader,'problem','offline'):
            for route in ['/builds','/synergies.js','/synergies.css']:
                with urlopen(self.base+route) as response: self.assertEqual(response.status,200)

    def test_offline_no_old_shop_recommendations(self):
        with patch.object(reader,'problem','offline'),patch.object(reader,'cached',shop()):
            with self.assertRaises(HTTPError) as error: urlopen(self.base+'/synergies')
            self.assertEqual(error.exception.code,503)

    def test_live_shop_and_query_validation(self):
        with patch.object(reader,'problem',None),patch.object(reader,'cached',shop([joker('j_photograph')],[joker('j_hanging_chad')])):
            with urlopen(self.base+'/synergies?build=photochad') as response:
                data=json.load(response);self.assertEqual(data['selected_id'],'photochad');self.assertTrue(data['shop'])
            with self.assertRaises(HTTPError) as error: urlopen(self.base+'/synergies?build=invalid')
            self.assertEqual(error.exception.code,400)


if __name__ == '__main__': unittest.main()
