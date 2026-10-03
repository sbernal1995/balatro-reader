import copy
import itertools
import unittest

import numpy as np

from simulator import Evaluator, analyze
from round_planner import RoundPlanner

def card(rank, suit='H', **modifier):
    return {'value':{'rank':rank,'suit':suit},'modifier':modifier,'state':{}}

def state(cards, pool=None, jokers=None):
    return {'state':'SELECTING_HAND','hand':{'cards':cards,'highlighted_limit':5},
            'draw_pool':{'cards':pool or []},'jokers':{'cards':jokers or []},
            'round':{'hands_left':2,'discards_left':1,'chips':0},
            'blinds':{'small':{'status':'CURRENT','type':'SMALL','score':100}},
            'money':0}

def score(cards,jokers=None):
    s=state(cards,jokers=jokers)
    ev=Evaluator(s,cards)
    values,kinds,groups=ev.scores(np.arange(len(cards))[None,:],1,0)
    i=groups.index(tuple(range(len(cards))))
    return values[0,i],kinds[0,i]

class ScoringTests(unittest.TestCase):
    def test_poker_categories(self):
        examples=[('A',None,16,0),('AAK',None,64,1),('AA22K',None,92,2),
                  ('AAA2',None,189,3),('23456','HDCHD',200,4),
                  ('23479',None,240,5),('AAA22','HDCHD',308,6),
                  ('AAAA2','HDCHD',728,7),('23456',None,960,8),
                  ('AAAAA','HDCHD',2100,9),('AAA22',None,2478,10),
                  ('AAAAA',None,3440,11)]
        for ranks,suits,expected,category in examples:
            # Prevent incidental flushes in pair/trips examples shorter than 5.
            suits=suits or 'H'*len(ranks)
            if ranks=='AA22K': suits='HDCHD'
            with self.subTest(ranks=ranks,category=category):
                self.assertEqual(score([card(r,s) for r,s in zip(ranks,suits)]),(expected,category))

    def test_wheel_and_wild_flush(self):
        self.assertEqual(score([card(r,s) for r,s in zip('A2345','HDCHD')])[0],220)
        self.assertEqual(score([card(r) for r in '2347']+[card('9','S',enhancement='WILD')])[0],240)

    def test_enhancements_and_retriggers(self):
        self.assertEqual(score([card('A',enhancement='GLASS')])[0],32)
        self.assertEqual(score([card('A',enhancement='MULT')])[0],80)
        self.assertEqual(score([card('A',enhancement='MULT',seal='RED')])[0],243)
        self.assertEqual(score([card('2'),card('A',enhancement='STONE')])[0],57)

    def test_held_steel(self):
        cards=[card('2'),card('A',enhancement='STEEL')]
        ev=Evaluator(state(cards),cards)
        values,_,groups=ev.scores(np.array([[0,1]]),1,0)
        self.assertEqual(values[0,groups.index((0,))],10)

    def test_order_optimization(self):
        cards=[card('A',enhancement='GLASS'),card('A','S',enhancement='MULT')]
        self.assertEqual(score(cards)[0],384)
        self.assertEqual(Evaluator(state(cards),cards).order([0,1]),[1,0])

    def test_fast_path_matches_generic_path(self):
        cards=[card(r,s) for r,s in zip('AA234TJK','HDSCHDSC')]
        ev=Evaluator(state(cards),cards)
        fast=ev.scores(np.arange(8)[None,:],2,33)[0]
        ev.simple=False
        np.testing.assert_array_equal(fast,ev.scores(np.arange(8)[None,:],2,33)[0])

    def test_joker_order_and_editions(self):
        cards=[card('A')]
        joker={'key':'j_joker','ability':{'mult':4}}
        self.assertEqual(score(cards,[joker])[0],80)
        banana={'key':'j_cavendish','ability':{'extra':{'Xmult':3}},'modifier':{'edition':'HOLO'}}
        self.assertEqual(score(cards,[banana])[0],528)

    def test_fullhouse_contains_two_pair(self):
        cards=[card(r,s) for r,s in zip('AAA22','HDCHD')]
        self.assertEqual(score(cards,[{'key':'j_mad','ability':{'t_mult':10}}])[0],1078)

    def test_debuff_and_levels(self):
        c=card('A');c['state']['debuff']=True
        self.assertEqual(score([c])[0],5)
        s=state([card('A')]);s['hands']={'High Card':{'chips':15,'mult':2}}
        self.assertEqual(Evaluator(s,s['hand']['cards']).best(np.array([[0]]),1,0)[0][0],52)

class MonteCarloTests(unittest.TestCase):
    def test_accumulates_score_over_three_hands(self):
        s=state([card('A')],[card('K'),card('Q')])
        s['round'].update(hands_left=3,discards_left=0)
        s['blinds']['small']['score']=46
        r=analyze(s)['recommendation']
        self.assertEqual(r['win_probability'],1)
        self.assertEqual(r['score'],46)
        self.assertEqual(r['expected_hands_to_win'],3)
        self.assertEqual(r['win_by_hands'],[0,0,1])
        s['round']['hands_left']=2
        self.assertEqual(analyze(s)['recommendation']['win_probability'],0)

    def test_same_win_chance_prefers_fewer_hands(self):
        s=state([card('2')],[card('A')])
        s['blinds']['small']['score']=16
        r=analyze(s)
        self.assertEqual(r['plays'][0]['win_probability'],1)
        self.assertEqual(r['plays'][0]['expected_hands_to_win'],2)
        self.assertEqual(r['recommendation']['action'],'discard')
        self.assertEqual(r['recommendation']['win_probability'],1)
        self.assertEqual(r['recommendation']['expected_hands_to_win'],1)

    def test_uses_chained_discards_to_raise_round_win_chance(self):
        s=state([card('2')],[card('3'),card('A')])
        s['round'].update(hands_left=1,discards_left=2)
        s['blinds']['small']['score']=16
        r=analyze(s)['recommendation']
        self.assertEqual(r['action'],'discard')
        self.assertEqual(r['win_probability'],1)
        self.assertGreater(r['expected_discards_used'],1.4)
        s['round']['discards_left']=1
        p=analyze(s)['recommendation']['win_probability']
        self.assertGreater(p,.45)
        self.assertLess(p,.55)

    def test_green_joker_discard_penalty_prefers_playing(self):
        j={'key':'j_green_joker','ability':{'mult':4,'extra':{'hand_add':1,'discard_sub':1}}}
        s=state([card('A')],[card('K')],jokers=[j])
        s['round']['hands_left']=1
        s['blinds']['small']['score']=90
        r=analyze(s)
        self.assertEqual(r['recommendation']['action'],'play')
        self.assertEqual(r['plays'][0]['immediate_score'],96)
        self.assertEqual(r['plays'][0]['win_probability'],1)
        self.assertEqual(r['discards'][0]['win_probability'],0)

    def test_green_joker_grows_on_every_play_and_clamps_after_discard(self):
        j={'key':'j_green_joker','ability':{'mult':2,'extra':{'hand_add':1,'discard_sub':5}}}
        s=state([card('2')],[card('A')],jokers=[j])
        s['round'].update(hands_left=2,discards_left=0)
        s['blinds']['small']['score']=105
        r=analyze(s)['recommendation']
        self.assertEqual(r['score'],108)
        self.assertEqual(r['win_probability'],1)
        s['round'].update(hands_left=1,discards_left=1)
        r=analyze(s)['discards'][0]
        self.assertEqual(r['score'],32) # Mult clamps to 0, then gains 1 before scoring.

    def test_banner_cost_is_applied_after_each_discard(self):
        j={'key':'j_banner','ability':{'extra':30}}
        s=state([card('A')],[card('K')],jokers=[j])
        s['round']['hands_left']=1
        s['blinds']['small']['score']=40
        r=analyze(s)
        self.assertEqual(r['plays'][0]['win_probability'],1)
        self.assertEqual(r['discards'][0]['win_probability'],0)

    def test_adaptive_policy_does_not_inspect_future_draw_order(self):
        cards=[card(r,s) for r,s in zip('2346789TJKQA','HDCSHDCSHDCS')]
        s=state(cards[:3],cards[3:])
        planner=RoundPlanner(Evaluator(s,cards),3,9,3,2,150)
        self.assertFalse(planner.exact)
        seen=[]
        for permutation in [[0,1,2,3,4,5,6,7,8],[0,8,7,6,5,4,3,2,1]]:
            events=[]
            planner.simulate('discard',(0,),np.array([permutation]),5,
                             trace=lambda step,rows,hand,mask,discard:events.append((hand,mask,discard)))
            seen.append(events[1]) # Same observed draw, different unknown future order.
        for left,right in zip(seen[0],seen[1]):
            np.testing.assert_array_equal(left,right)

    def test_intervals_and_resource_limits_for_large_round(self):
        cards=[card(r,s) for r in '23456789TJQKA' for s in 'HDCS']
        s=state(cards[:8],cards[8:])
        planner=RoundPlanner(Evaluator(s,cards),8,44,4,3,5000)
        events=[]
        r=planner.simulate('discard',(0,1,2,3,4),
                           np.argsort(np.random.default_rng(5).random((24,44)),axis=1),6,
                           trace=lambda step,rows,hand,mask,discard:events.append((rows,discard)))
        h=np.zeros(24);d=np.zeros(24)
        for rows,discard in events:
            h[rows]+=~discard;d[rows]+=discard
        self.assertTrue(np.all(h<=4))
        self.assertTrue(np.all(d<=3))
        self.assertEqual(r['win_probability'],0)
        self.assertGreater(r['win_interval_95'][1],0)

    def test_discard_can_activate_mystic_summit_without_draw_cards(self):
        cards=[card(r,s) for r,s in zip('AKJ97532','HDCSHDCS')]
        j={'key':'j_mystic_summit','ability':{'extra':{'mult':15,'d_remaining':0}}}
        s=state(cards,jokers=[j])
        planner=RoundPlanner(Evaluator(s,cards),8,0,1,2,250)
        self.assertFalse(planner.exact)
        r=planner.simulate('discard',(7,),np.empty((16,0),int),7)
        self.assertEqual(r['win_probability'],1)
        self.assertEqual(r['expected_discards_used'],2)
        self.assertEqual(r['expected_hands_to_win'],1)

    def test_all_options_and_reproducibility(self):
        s=state([card('2'),card('A')],[card('3'),card('4'),card('A','S')])
        s['round']['hands_left']=1
        r=analyze(s,1000)
        self.assertEqual(r['discard_options'],3)
        self.assertTrue(all(c['trials']==1000 for c in r['discards']))
        self.assertEqual(r['recommendation'],analyze(s,1000)['recommendation'])
        # All three ways of drawing two physical cards are legal and equally likely.
        ev=Evaluator(s,s['hand']['cards']+s['draw_pool']['cards'])
        exact=ev.best(np.array(list(itertools.combinations([2,3,4],2))),0,1)[0].mean()
        estimate=next(c for c in r['discards'] if c['indices']==[1,2])['score']
        self.assertLess(abs(exact-estimate),3)

    def test_win_now_preserves_discard(self):
        s=state([card('A')],[card('2')]);s['blinds']['small']['score']=15
        self.assertEqual(analyze(s,1000)['recommendation']['action'],'play')

    def test_no_discards(self):
        s=state([card('A')],[card('2')]);s['round']['discards_left']=0
        self.assertEqual(analyze(s)['discard_options'],0)

    def test_depleted_draw_pool(self):
        s=state([card('2'),card('3'),card('4')],[card('A')])
        self.assertEqual(analyze(s)['discard_options'],7)

    def test_unsupported_rules_block(self):
        s=state([card('A')],jokers=[{'key':'j_blueprint'}])
        self.assertEqual(analyze(s)['status'],'blocked')
        s=state([card('A',enhancement='LUCKY')])
        with self.assertRaisesRegex(ValueError,'Mejora'):
            analyze(s)
        s=state([card('A')]);s['blinds']['small']['type']='BOSS'
        self.assertEqual(analyze(s)['status'],'blocked')

    def test_no_state_mutation(self):
        s=state([card('A')],[card('2')]);original=copy.deepcopy(s)
        analyze(s)
        self.assertEqual(s,original)

    def test_cancellation(self):
        s=state([card('A')],[card('2')])
        self.assertEqual(analyze(s,cancelled=lambda:True)['status'],'superseded')

    def test_partial_results_before_completion(self):
        s=state([card('2'),card('A')],[card('3'),card('4'),card('A','S')])
        partial=[]
        result=analyze(s,1000,progress=lambda done,total,value:partial.append(value))
        self.assertEqual([p['completed'] for p in partial],list(range(7)))
        self.assertTrue(all(p['status']=='running' and p['partial'] for p in partial))
        self.assertFalse(partial[0]['plays'])
        self.assertTrue(partial[1]['plays'])
        self.assertEqual(partial[-1]['recommendation'],result['recommendation'])
        self.assertFalse(result['partial'])

    def test_second_third_and_last_hand_resources(self):
        for played,left,discards in [(0,4,3),(1,3,2),(2,2,1),(3,1,0)]:
            s=state([card('A')],[card('2')])
            s['round'].update(hands_played=played,hands_left=left,discards_left=discards,chips=40)
            result=analyze(s,1000)
            self.assertEqual(result['hand_number'],played+1)
            self.assertEqual(result['hands_left'],left)
            self.assertEqual(result['hands_after_next_play'],left-1)
            self.assertEqual(result['discards_left'],discards)
            self.assertEqual(result['target'],60)
        s['round']['hands_left']=0
        self.assertEqual(analyze(s)['status'],'waiting')

if __name__=='__main__': unittest.main()
