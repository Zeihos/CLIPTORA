"""Adaptive, bounded context around a detected audio reaction.

Uses cached 0.5-second audio, 2-second motion, and optional transcript time
ranges. It does not recognize laughter, game events or humor. The caller
keeps all proposed cuts editable and subject to review.
"""
from bisect import bisect_left, bisect_right
from statistics import median
import math


MAX_WINDOW_SECONDS = 20.0


def _finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


class ReactionContext:
    """Prepare a recording once; look up each audio peak without re-scanning ASR.

    Audio RMS: two buckets per second. Motion: one bucket per two seconds.
    Returns (start, end, evidence labels) without changing the cached inputs.
    """

    def __init__(self, duration, audio_levels=(), motion_levels=(), transcript=()):
        self.duration = max(0.0, _finite(duration) or 0.0)
        self.audio = audio_levels or ()
        self.motion = motion_levels or ()
        valid_audio = [_finite(x) for x in self.audio]
        valid_motion = [_finite(x) for x in self.motion]
        self.audio_floor = median([x for x in valid_audio if x is not None and x >= 0]) if valid_audio and any(x is not None and x >= 0 for x in valid_audio) else 0.0
        self.motion_floor = median([x for x in valid_motion if x is not None and x >= 0]) if valid_motion and any(x is not None and x >= 0 for x in valid_motion) else 0.0
        speech = []
        for entry in transcript or ():
            if not isinstance(entry, dict) or not str(entry.get('text') or '').strip():
                continue
            a, b = _finite(entry.get('start')), _finite(entry.get('end'))
            if a is not None and b is not None and 0 <= a < b <= self.duration:
                speech.append((a, b))
        self.speech = sorted(speech)
        self.starts = [a for a, _ in self.speech]

    def window(self, time):
        """Preserve likely setup, adjacent reply and significant aftershock; cap length."""
        t = _finite(time)
        if t is None or not 0 <= t < self.duration:
            raise ValueError('Время реакции вне границ записи')
        start, end = max(0.0, t - 4.5), min(self.duration, t + 6.5)
        reasons = []

        # A nearby lead-in must finish close to the peak, not an unrelated
        # sentence tens of seconds earlier. Search only the 10 nearest lines.
        before = bisect_right(self.starts, t)
        for a, b in reversed(self.speech[max(0, before-10):before]):
            if a <= t and t - 2.6 <= b <= t + 1 and t - a <= 9.0:
                new_start = max(0.0, a - 1.0)
                if new_start < start:
                    start = new_start
                    reasons.append('сохранена подводка перед реакцией')
                break

        # Include any reply beginning shortly after the peak, including an
        # utterance that happens to overlap the peak.
        for a, b in self.speech[max(0, bisect_left(self.starts, t-1)-1):]:
            if a > t + 5.0:
                break
            if a >= t - 1 and b > t and b <= t + 11:
                new_end = min(self.duration, b + 1.0)
                if new_end > end:
                    end = new_end
                    reasons.append('сохранён ответ после реакции')

        # A reaction's tail should be relative to this video's background,
        # not a blanket extension for continuous loud music.
        audio_threshold = max(0.045, self.audio_floor * 1.9)
        last_audio_time = None
        a = max(0, int(math.floor(t * 2)))
        b = min(len(self.audio), int(math.ceil((t + 9) * 2)))
        for i in range(a, b):
            value = _finite(self.audio[i])
            if value is not None and value > audio_threshold:
                last_audio_time = (i+1) * 0.5
        if last_audio_time is not None:
            new_end = min(self.duration, last_audio_time + 1.75)
            if new_end > end + 0.1:
                end = new_end
                reasons.append('продолжительная звуковая реакция')

        motion_threshold = max(0.05, self.motion_floor * 2.0)
        last_motion_time = None
        for i in range(max(0, int(t // 2)), min(len(self.motion), int(math.ceil((t+8)/2)))):
            value = _finite(self.motion[i])
            if value is not None and value > motion_threshold:
                last_motion_time = (i+1) * 2.0
        if last_motion_time is not None:
            new_end = min(self.duration, last_motion_time + 1.5)
            if new_end > end + 0.1:
                end = new_end
                reasons.append('продолжение движения в кадре')

        end = min(end, self.duration, t + 12.5)
        # If a long reply+aftershock exceeds the budget, favor the peak and
        # response over a distant introduction.
        if end-start > MAX_WINDOW_SECONDS:
            start = end - MAX_WINDOW_SECONDS
        return round(start, 2), round(end, 2), reasons
