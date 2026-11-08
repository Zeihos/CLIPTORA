"""v0.1.8 regressions: keep setup, payoff and response in a bounded clip."""
import unittest
from dialogue_context import build_dialogue_windows
from engine import generate_candidates


def s(start, end, text, humor=0):
    return {'start': start, 'end': end, 'text': text, 'humor': humor}


class DialogueContextTests(unittest.TestCase):
    def test_retains_earlier_setup_and_response_after_payoff(self):
        segs = [s(2, 5, 'Смотри на меня'), s(9, 11, 'Точно получится?'),
                s(14, 16, 'Я упал!', 5), s(18, 19.5, 'Ахаха, видел?', 1)]
        hits = [{'time': 17.5, 'strength': .85, 'reasons': ['звуковой всплеск']}]
        result = build_dialogue_windows(segs, 45, hits)
        self.assertTrue(result)
        chosen = max(result, key=lambda w: w['humor'])
        self.assertLessEqual(chosen['start'], 2)
        self.assertGreaterEqual(chosen['end'], 22)
        self.assertIn('Точно получится?', chosen['text'])
        self.assertIn('Я упал!', chosen['text'])
        self.assertIn('Ахаха, видел?', chosen['text'])
        self.assertIn('подводка', ' '.join(chosen['reasons']))
        self.assertIn('ответ', ' '.join(chosen['reasons']))

    def test_reaction_after_last_sentence_keeps_short_tail(self):
        segs = [s(8, 11, 'Ну всё, победили', 4)]
        hits = [{'time': 12, 'strength': .91, 'reasons': ['звуковой всплеск']}]
        chosen = build_dialogue_windows(segs, 22, hits)[0]
        self.assertGreaterEqual(chosen['end'], 16)
        self.assertLessEqual(chosen['end'], 22)

    def test_long_continuous_dialogue_is_bounded_and_keeps_payoff(self):
        segs = [s(i, i + 1, f'Реплика {i}', 5 if i == 39 else 0)
                for i in range(0, 42, 3)]
        wins = build_dialogue_windows(segs, 60)
        self.assertTrue(wins)
        self.assertTrue(all(3 <= w['end'] - w['start'] <= 36 for w in wins), wins)
        self.assertTrue(any('Реплика 39' in w['text'] for w in wins), wins)
        self.assertTrue(all(w['start'] >= 0 and w['end'] <= 60 for w in wins))

    def test_distant_dialogues_stay_separate(self):
        segs = [s(1, 3, 'Сцена один'), s(7, 9, 'Ответ'), s(40, 43, 'Другая сцена')]
        wins = build_dialogue_windows(segs, 60)
        self.assertEqual(len(wins), 2)
        self.assertLess(wins[0]['end'], wins[1]['start'])

    def test_bad_transcripts_and_duration_boundaries_do_not_create_invalid_clips(self):
        segs = [s(-4, 0.4, 'Начало'), s(2, 5, 'Конец'),
                {'start': None, 'end': 0, 'text': 'Bad'},
                s(25, 26, 'Outside')]
        wins = build_dialogue_windows(segs, 5)
        self.assertTrue(all(0 <= w['start'] < w['end'] <= 5 for w in wins), wins)
        self.assertTrue(all('Outside' not in w['text'] for w in wins))
        self.assertEqual(build_dialogue_windows([], 80), [])
        self.assertEqual(build_dialogue_windows(segs, 0), [])

    def test_engine_consumes_context_windows_not_just_fixed_three_second_padding(self):
        segs = [s(2, 5, 'Подводка'), s(10, 12, 'Вопрос'), s(16, 17, 'Вот это да!', 5),
                s(20, 21, 'Ответ зрителей')]
        item = {'duration': 45, 'analysis': {'audio_levels': [0.02]*90,
                'motion_levels': [], 'transcript': segs}}
        candidates = [c for c in generate_candidates(item) if c['type'] == 'dialogue']
        self.assertTrue(candidates)
        best = max(candidates, key=lambda x: x['score'])
        self.assertLessEqual(best['start'], 2)
        self.assertGreaterEqual(best['end'], 23)
        self.assertIn('подводка', ' '.join(best['reasons']))


if __name__ == '__main__':
    unittest.main()
