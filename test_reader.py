import copy
import unittest
import threading
import time
import tempfile
from pathlib import Path
from unittest.mock import patch

from reader import SimulationController, fingerprint
from test_simulator import state, card

class ManualSimulationTests(unittest.TestCase):
    def setUp(self):
        self.data=state([card('A')],[card('2')])
        self.controller=SimulationController(lambda:self.data)

    def test_idle_does_not_start_automatically(self):
        self.assertEqual(self.controller.view()['status'],'idle')
        self.assertIsNone(self.controller.pending)
        self.assertFalse(self.controller.wakeup.is_set())

    def test_submit_captures_input_and_allows_repeat(self):
        first=self.controller.submit(self.data)
        self.assertEqual(self.controller.view()['status'],'running')
        self.assertEqual(self.controller.pending[1]['round']['hands_left'],2)
        self.data['round']['hands_left']=1
        self.assertEqual(self.controller.pending[1]['round']['hands_left'],2)
        second=self.controller.submit(self.data)
        self.assertGreater(second,first)
        self.assertEqual(self.controller.pending[1]['round']['hands_left'],1)

    def test_resource_or_card_change_invalidates_results(self):
        for change in [('hands_left',1),('discards_left',0),('hands_played',2),('chips',50)]:
            self.data=state([card('A')],[card('2')])
            self.controller.submit(self.data)
            self.data['round'][change[0]]=change[1]
            self.assertEqual(self.controller.view()['status'],'stale')
            self.assertNotIn('recommendation',self.controller.view())
        self.controller.submit(self.data)
        self.data['hand']['cards'][0]['value']['rank']='K'
        self.assertEqual(self.controller.view()['status'],'stale')

    def test_highlight_and_recording_do_not_invalidate(self):
        before=fingerprint(self.data)
        self.data['hand']['cards'][0]['state']['highlight']=True
        self.data['registro']={'cambios':23}
        self.assertEqual(before,fingerprint(self.data))

    def test_disconnect_hides_results(self):
        self.controller.submit(self.data)
        self.data=None
        self.assertEqual(self.controller.view()['status'],'waiting')

    def test_animation_objects_and_hand_previews_do_not_invalidate(self):
        self.data['joker_context']={
            'round_resets':{'hands':4,'discards':3,'blind_tag':{'tag_sprite':{
                'role':{'major':{'UIBox':{'overflow_check_timer':1,'hover_offset':{'x':2}}}}}}},
            'current_round':{'current_hand':{'chips':12,'mult':4,'chip_total':48},
                             'most_played_poker_hand':'Pair'}}
        self.data['hands']={'Pair':{'level':2,'chips':25,'mult':3,
                                   'example':{'card':{'VT':{'x':1}}}}}
        self.controller.submit(self.data)
        before=copy.deepcopy(self.data)
        first=fingerprint(self.data)
        self.assertEqual(self.data,before)
        self.data['joker_context']['round_resets']['blind_tag']['tag_sprite']['role']['major']['UIBox'].update(
            overflow_check_timer=2,hover_offset={'x':4})
        self.data['joker_context']['current_round']['current_hand']['chips']=99
        self.data['hands']['Pair']['example']['card']['VT']['x']=5
        self.data['hand']['cards'][0].update(label='Texto de carta',runtime={'hover_timer':10})
        self.data['hand']['cards'][0]['value']['effect']='Otra descripción'
        self.assertEqual(first,fingerprint(self.data))
        self.assertEqual(self.controller.view()['status'],'running')

    def test_rules_inventory_and_history_changes_still_invalidate(self):
        baseline=copy.deepcopy(self.data)
        baseline.update(jokers={'cards':[{'key':'j_joker','ability':{'mult':4}}]},
            consumables={'cards':[]},hands={'Pair':{'level':1,'played':2}},
            active_blind={'key':'bl_eye','hands':{'Pair':True}},used_vouchers={},
            unseen_cards=[card('A')],joker_context={'consumeable_usage_total':{'tarot':2},
                'probabilities':{'normal':1},'round_resets':{'hands':4},
                'current_round':{'idol_card':{'id':14,'suit':'Hearts'}}})
        changes=[
            lambda s:s['jokers']['cards'][0]['ability'].update(mult=5),
            lambda s:s['consumables']['cards'].append({'key':'c_jupiter'}),
            lambda s:s['hands']['Pair'].update(level=2),
            lambda s:s['hands']['Pair'].update(played=3),
            lambda s:s['active_blind']['hands'].update(Pair=False),
            lambda s:s['used_vouchers'].update(v_grabber='description'),
            lambda s:s['unseen_cards'][0]['value'].update(rank='K'),
            lambda s:s['hand']['cards'][0]['modifier'].update(enhancement='GLASS'),
            lambda s:s['joker_context']['consumeable_usage_total'].update(tarot=3),
            lambda s:s['joker_context']['probabilities'].update(normal=2),
            lambda s:s['joker_context']['round_resets'].update(hands=5),
            lambda s:s['joker_context']['current_round']['idol_card'].update(id=13),
        ]
        for i,change in enumerate(changes):
            with self.subTest(change=i):
                self.data=copy.deepcopy(baseline);self.controller.submit(self.data)
                change(self.data)
                self.assertEqual(self.controller.view()['status'],'stale')

    def test_hand_and_joker_order_changes_invalidate_indices(self):
        self.data['hand']['cards'].append(card('K'))
        self.data['jokers']['cards']=[{'key':'j_blueprint'},{'key':'j_joker'}]
        for key in ('hand','jokers'):
            self.controller.submit(self.data)
            self.data[key]['cards'].reverse()
            self.assertEqual(self.controller.view()['status'],'stale')

    def test_worker_finishes_despite_animation_updates(self):
        self.data['joker_context']={'round_resets':{'hands':4,'blind_tag':{'tag_sprite':{'timer':0}}}}
        def calculation(data,progress,cancelled,**kwargs):
            for i in range(4):
                self.data['joker_context']['round_resets']['blind_tag']['tag_sprite']['timer']=i+1
                self.assertFalse(cancelled())
                progress(i+1,4,{'status':'running','completed':i+1,'total':4})
            return {'status':'ready','recommendation':{'win_probability':1}}
        with tempfile.TemporaryDirectory() as folder, patch('reader.RECORDS',Path(folder)), \
                patch('reader.analyze',side_effect=calculation):
            threading.Thread(target=self.controller.run,daemon=True).start()
            self.controller.submit(self.data)
            deadline=time.monotonic()+2
            while self.controller.result['status']=='running' and time.monotonic()<deadline:
                time.sleep(.01)
            self.assertEqual(self.controller.view()['status'],'ready',self.controller.view())
            self.assertTrue((Path(folder)/'recomendacion.json').exists())

    def test_interruption_allows_simulating_again_after_recovery(self):
        original=copy.deepcopy(self.data)
        called=threading.Event()
        def interrupted(*args,**kwargs):
            self.data=None
            called.set()
            return {'status':'superseded'}
        with patch('reader.analyze',side_effect=interrupted):
            threading.Thread(target=self.controller.run,daemon=True).start()
            self.controller.submit(original)
            self.assertTrue(called.wait(1))
            deadline=time.monotonic()+1
            while self.controller.result['status']=='running' and time.monotonic()<deadline:
                time.sleep(.01)
        self.data=original
        self.assertEqual(self.controller.view()['status'],'stale')

if __name__=='__main__': unittest.main()
