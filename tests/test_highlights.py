"""Regression checks for v0.1.7 relative reaction detection and review hints."""
import unittest
from engine import clip_score, generate_candidates
from highlight_signals import detect_audio_reactions


class HighlightSignalTests(unittest.TestCase):
    def test_short_relative_reaction_beats_constant_loud_background(self):
        quiet = [0.018] * 120
        quiet[20:23] = [0.10, 0.24, 0.13]
        hits = detect_audio_reactions(quiet, 60.0)
        self.assertTrue(any(9 <= h['time'] <= 12 for h in hits), hits)
        self.assertEqual(detect_audio_reactions([0.23]*120, 60.0), [])

    def test_single_sample_glitch_without_context_is_ignored(self):
        levels = [0.015] * 120
        levels[40] = 0.31
        self.assertFalse(detect_audio_reactions(levels, 60.0))

    def test_speech_can_support_short_reaction(self):
        levels = [0.015] * 120
        levels[40] = 0.31
        transcription = [{'start': 19.5, 'end': 21.2, 'text': 'Ой!'}]
        hits = detect_audio_reactions(levels, 60.0, transcript=transcription)
        self.assertTrue(hits)
        self.assertIn('речь', ' '.join(hits[0]['reasons']))

    def test_correlation_with_movement_is_visible_in_review_reasons(self):
        levels = [0.018] * 120
        levels[20:23] = [0.10, 0.24, 0.13]
        motion = [0.01] * 30
        motion[5] = 0.22
        item = {'duration': 60, 'analysis': {'audio_levels': levels,
                'motion_levels': motion, 'transcript': []}}
        hits = generate_candidates(item)
        reactions = [x for x in hits if x['type'] == 'reaction']
        self.assertTrue(reactions, hits)
        self.assertTrue(reactions[0].get('reasons'), reactions)
        self.assertTrue(0 <= reactions[0]['start'] < reactions[0]['end'] <= 60)

    def test_dialogue_reaction_has_higher_score_than_same_dialogue_without_peak(self):
        quiet = [0.018]*120
        reaction = quiet.copy()
        reaction[20:23] = [0.10, 0.24, 0.13]
        transcript = [{'start': 10, 'end': 12, 'text': 'Что за прикол?', 'humor': 1}]
        def file_for(levels):
            return {'duration': 60, 'analysis': {'audio_levels': levels,
                    'motion_levels': [], 'transcript': transcript}}
        low = next(c for c in generate_candidates(file_for(quiet)) if c['type']=='dialogue')
        high = next(c for c in generate_candidates(file_for(reaction)) if c['type']=='dialogue')
        self.assertGreater(high['score'], low['score'])
        self.assertIn('звуковой всплеск', ' '.join(high['reasons']))

    def test_silence_short_files_and_boundaries_have_no_invalid_clips(self):
        self.assertEqual(detect_audio_reactions([], 0), [])
        self.assertEqual(detect_audio_reactions([0]*120, 60), [])
        self.assertFalse([x for x in generate_candidates({'duration': 1, 'analysis': {'audio_levels':[.05,.3], 'motion_levels':[], 'transcript':[]}}) if x['end']<=x['start']])


if __name__ == '__main__':
    unittest.main()

class HighlightReviewUITests(unittest.TestCase):
    def test_review_list_displays_reasons_for_clip_suggestion(self):
        from pathlib import Path
        page = (Path(__file__).resolve().parents[1] / 'web' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('Основание:', page)
        self.assertIn('Звуковая реакция', page)
