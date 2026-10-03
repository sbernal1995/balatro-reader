"""Exercise the installed Lua exporter against BalatroBot's JSON encoder."""
import json
from pathlib import Path
import unittest

from lupa.luajit21 import LuaRuntime


ROOT = Path(__file__).resolve().parent


class LuaSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.codec = self.lua.execute((ROOT / 'tests/vendor/json.lua').read_text(encoding='utf-8'))
        self.exporter = self.lua.execute((ROOT / 'integrations/gamestate.lua').read_text(encoding='utf-8'))
        self.lua.execute('G = {STATE = 1, STATES = {SELECTING_HAND = 1}, GAME = {}}')

    def export(self):
        return json.loads(self.codec.encode(self.exporter.get_gamestate()))

    def context(self, expression):
        self.lua.execute('G.GAME.round_scores = ' + expression)
        return self.export()['joker_context']['round_scores']

    def test_mixed_keys_keep_named_fields_and_indices(self):
        self.assertEqual(self.context('{[1] = 4, [2] = 8, amt = 12}'),
                         {'1': 4, '2': 8, 'amt': 12})
        self.assertEqual(self.lua.eval('G.GAME.round_scores[1]'), 4)
        self.assertIsNone(self.lua.eval('G.GAME.round_scores["1"]'))

    def test_dense_arrays_keep_order_and_nested_objects(self):
        self.assertEqual(self.context('{4, {chips = 8}, false}'), [4, {'chips': 8}, False])

    def test_sparse_zero_negative_and_fractional_keys(self):
        for expression, expected in [
            ('{[1] = 4, [3] = 8}', {'1': 4, '3': 8}),
            ('{[0] = 4, [2] = 8}', {'0': 4, '2': 8}),
            ('{[-1] = 4, [1.5] = 8}', {'-1': 4, '1.5': 8}),
        ]:
            with self.subTest(expression=expression):
                self.assertEqual(self.context(expression), expected)

    def test_numeric_string_collisions_preserve_both_values(self):
        self.assertEqual(self.context('{[1] = 4, ["1"] = false, ["[number] 1"] = 8}'),
                         {'1': False, '[number] 1': 8, '[number] 1#': 4})

    def test_unsupported_values_do_not_leave_sparse_arrays(self):
        self.assertEqual(self.context('{4, function() end, 8, math.huge, 0/0}'),
                         {'1': 4, '3': 8})

    def test_circular_references_and_shared_tables(self):
        self.lua.execute('local a = {amt = 9}; a.self = a; G.GAME.round_scores = {a, a}')
        self.assertEqual(self.export()['joker_context']['round_scores'], [{'amt': 9}, {'amt': 9}])

    def test_hand_examples_are_sanitized_outside_context(self):
        self.lua.execute('''G.GAME.hands = {Pair = {level = 3, played = 7,
            example = {{[1] = "S_A", highlighted = true}}}}''')
        hand = self.export()['hands']['Pair']
        self.assertEqual(hand['example'], [{'1': 'S_A', 'highlighted': True}])
        self.assertEqual((hand['level'], hand['played']), (3, 7))

    def test_nested_metadata_and_counters_survive(self):
        self.lua.execute('''G.GAME.current_round = {hands_left = 4, discards_left = 2,
            metadata = {[1] = "first", amt = 11}};
            G.GAME.consumeable_usage_total = {tarot = 5, planet = 3, spectral = 1}''')
        state = self.export()
        self.assertEqual(state['round'], {'hands_left': 4, 'discards_left': 2})
        context = state['joker_context']
        self.assertEqual(context['current_round']['metadata'], {'1': 'first', 'amt': 11})
        self.assertEqual(context['consumeable_usage_total']['tarot'], 5)

    def test_menu_without_game_is_serializable(self):
        self.lua.execute('G = nil')
        self.assertEqual(self.export()['state'], 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
