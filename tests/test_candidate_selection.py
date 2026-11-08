"""CLIPTORA v0.1.9: ranking and duplicate-resistance of suggested clips."""
import tempfile
import unittest
from pathlib import Path

from candidate_selection import select_best_clips
from engine import Studio


def clip(media_id, start, end, text, score=70, kind='dialogue', reasons=()):
    return {'media_id': media_id, 'start': start, 'end': end,
            'label': text, 'score': score, 'type': kind,
            'reasons': list(reasons), 'source_name': media_id+'.mp4'}


class CandidateSelectionTests(unittest.TestCase):
    def test_full_setup_and_response_beats_one_word_shout_with_same_base_score(self):
        candidates = [
            clip('a', 0, 10, 'Бля!', 79),
            clip('b', 0, 14, 'Подожди, ты же говорил, что здесь никто не придёт! И что теперь делать?', 79,
                 reasons=('сохранена подводка', 'сохранён ответ после реплики')),
        ]
        chosen, report = select_best_clips(candidates, 15)
        self.assertEqual([x['media_id'] for x in chosen], ['b'])
        self.assertGreater(chosen[0]['rank_score'], chosen[0]['score'])
        self.assertEqual(report['considered'], 2)
        self.assertEqual(report['selected'], 1)
        self.assertEqual(candidates[1]['score'], 79, 'candidate input must not be mutated')
        self.assertNotIn('rank_score', candidates[1])

    def test_similar_dialogue_from_different_recordings_is_not_added_twice(self):
        text1 = 'Я вижу противника он бежит справа давай убегать отсюда быстро'
        text2 = 'Я вижу противника, он бежит справа, давай убегать отсюда быстро!'
        candidates = [clip('a', 1, 15, text1, 92), clip('b', 30, 44, text2, 91)]
        chosen, report = select_best_clips(candidates, 60)
        self.assertEqual(len(chosen), 1)
        self.assertEqual(report['duplicates'], 1)
        self.assertEqual(chosen[0]['media_id'], 'a')

    def test_different_punchline_is_not_suppressed_by_shared_setup(self):
        candidates = [
            clip('a', 0, 12, 'Смотри брат, я сейчас зайду в дом и там найду сокровища', 77),
            clip('b', 0, 12, 'Смотри брат, я сейчас зайду в дом и там меня убьют', 77),
        ]
        chosen, report = select_best_clips(candidates, 60)
        self.assertEqual(len(chosen), 2)
        self.assertEqual(report['duplicates'], 0)

    def test_generic_audio_reaction_labels_do_not_de_duplicate_distinct_events(self):
        candidates = [
            clip('a', 4, 14, 'Резкая звуковая реакция (проверь вручную)', 74, 'reaction'),
            clip('a', 54, 64, 'Резкая звуковая реакция (проверь вручную)', 71, 'reaction'),
        ]
        chosen, report = select_best_clips(candidates, 60)
        self.assertEqual(len(chosen), 2)
        self.assertEqual(report['duplicates'], 0)

    def test_same_video_overlap_is_skipped_and_counted(self):
        candidates = [clip('a', 2, 18, 'Я тут нашёл очень странную штуку', 90),
                      clip('a', 12, 22, 'Вот именно поэтому мне страшно', 85)]
        chosen, report = select_best_clips(candidates, 60)
        self.assertEqual(len(chosen), 1)
        self.assertEqual(report['overlaps'], 1)

    def test_short_or_malformed_candidates_are_ignored(self):
        candidates = [clip('a', 1, 1, 'невалидный', 99),
                      clip('a', 0, 8, 'смешной диалог', float('nan')),
                      clip('a', 10, 20, 'Обычная запись без распознавания речи', 60)]
        chosen, report = select_best_clips(candidates, 30)
        self.assertEqual(len(chosen), 1)
        self.assertEqual(report['invalid'], 2)

    def test_existing_project_without_report_can_create_new_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Studio(Path(tmp) / 'state')
            entry = {'id': 'vid', 'name': 'test.mp4', 'duration': 60,
                     'analysis': {'audio_levels': [0.04] * 120,
                                  'motion_levels': [],
                                  'transcript': [{'start': 2, 'end': 7,
                                                  'text': 'Я сейчас попробую этот трюк!', 'humor': 4}]},
                     'analyzed': True, 'analysis_signature': app.analysis_signature()}
            app.project['files'] = [entry]
            app.project.pop('selection_summary', None)
            out = app.plan(target_minutes=1)
            self.assertTrue(out)
            summary = app.status()['selection_summary']
            self.assertEqual(summary['selected'], len(out))
            self.assertGreaterEqual(summary['considered'], len(out))
            reloaded = Studio(Path(tmp) / 'state')
            self.assertEqual(reloaded.status()['selection_summary'], summary)


if __name__ == '__main__':
    unittest.main()
