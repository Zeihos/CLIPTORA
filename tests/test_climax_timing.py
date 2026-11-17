"""v0.1.14 regression tests for reaction timing and corroborated peak selection."""
import copy
import math
import unittest

from climax_timing import ReactionContext
from engine import generate_candidates


class ReactionTimingTests(unittest.TestCase):
    def test_lingering_reaction_keeps_tail_beyond_old_fixed_cut(self):
        audio = [0.015] * 140
        audio[40:57] = [0.22] + [0.12] * 16  # 20..28 seconds
        context = ReactionContext(70, audio, [], [])
        start, end, reasons = context.window(20)
        self.assertLessEqual(start, 16.5)
        self.assertGreaterEqual(end, 29.0)
        self.assertLessEqual(end-start, 20.0)
        self.assertIn('продолжительная звуковая реакция', reasons)

    def test_reply_is_not_truncated_after_peak(self):
        audio = [0.012] * 120
        dialogue = [
            {'start': 24.0, 'end': 28.4, 'text': 'Смотри сейчас!'},
            {'start': 32.0, 'end': 38.0, 'text': 'Я всё видел, как так получилось?'},
        ]
        context = ReactionContext(60, audio, [], dialogue)
        start, end, reasons = context.window(30)
        self.assertLessEqual(start, 24.0)
        self.assertGreaterEqual(end, 39.0)
        self.assertIn('сохранён ответ после реакции', reasons)

    def test_static_loud_background_does_not_inflate_reaction(self):
        audio = [0.21] * 140
        context = ReactionContext(70, audio, [], [])
        start, end, reasons = context.window(20)
        self.assertGreaterEqual(start, 0)
        self.assertLessEqual(end, 27.0)
        self.assertNotIn('продолжительная звуковая реакция', reasons)

    def test_visual_activity_can_preserve_aftershock(self):
        audio = [0.013] * 140
        motion = [0.012] * 35
        motion[14:17] = [0.13, 0.11, 0.10]  # 28..34 sec activity
        context = ReactionContext(70, audio, motion, [])
        start, end, reasons = context.window(26)
        self.assertGreaterEqual(end, 34.0)
        self.assertIn('продолжение движения в кадре', reasons)

    def test_clamps_file_edges_and_ignores_malformed_segments(self):
        context = ReactionContext(12, [0.02]*24, [], [
            {'start': float('nan'), 'end': 12, 'text': 'bad'},
            {'start': 'invalid', 'end': 8, 'text': 'bad'},
            {'start': 11, 'end': 17, 'text': 'late'},
        ])
        start, end, _ = context.window(11.6)
        self.assertGreaterEqual(start, 0)
        self.assertLessEqual(end, 12)
        self.assertGreater(end-start, 0)

    def test_reaction_candidate_uses_expanded_tail_without_touching_analysis(self):
        audio = [0.012] * 140
        audio[40:57] = [0.23] + [0.11] * 16
        media = {'duration':70.0, 'analysis':{'audio_levels': audio, 'motion_levels':[], 'transcript':[]}}
        snapshot = copy.deepcopy(media)
        candidates = generate_candidates(media)
        reactions = [c for c in candidates if c.get('type') == 'reaction']
        self.assertTrue(reactions, candidates)
        self.assertTrue(any(c['end'] >= 29 and c['start'] < 20 for c in reactions), reactions)
        self.assertEqual(media, snapshot)

    def test_evidence_combination_is_explained_without_claiming_event_recognition(self):
        audio = [0.012] * 140
        audio[40:43] = [0.22, 0.18, 0.13]
        motion = [0.008] * 35
        motion[9:12] = [0.11, 0.10, 0.08]
        media = {'duration':70.0, 'analysis':{'audio_levels': audio, 'motion_levels':motion,
            'transcript':[{'start':18.0,'end':19.2,'text':'Ничего себе!'}]}}
        candidates = generate_candidates(media)
        self.assertTrue(any('совпадение звука, речи и движения' in c.get('reasons', [])
                            for c in candidates), candidates)
        self.assertTrue(all(0 <= c['score'] <= 100 for c in candidates), candidates)


if __name__ == '__main__':
    unittest.main()
