"""Lightweight, explainable audio reaction heuristics for existing 0.5s RMS data.

This does not identify jokes, speakers, game events, or sound categories. It looks for
sudden *changes* relative to a local baseline with an extra plausibility check.
No external dependencies and no raw audio retained in memory.
"""
from bisect import bisect_left, insort
from statistics import median


def detect_audio_reactions(levels, duration, transcript=(), motion=()):
    """Return deduplicated reaction candidates at 0.5-second resolution.

    Each result contains: time, strength in [0,1] and human-readable reasons.
    A one-frame anomaly without speech or motion corroboration is discarded.
    """
    if not levels or duration <= 0 or len(levels) < 8:
        return []
    floor = median(levels)
    motion_base = median(motion) if motion else 0.0
    proposed = []
    speech = sorted((float(s.get('start', 0)), float(s.get('end', 0)))
                    for s in transcript if s.get('start') is not None and s.get('end') is not None)
    speech_index = 0
    for i in range(4, len(levels)-2):
        peak = levels[i]
        if peak < max(0.035, floor * 1.8):
            continue
        if peak < max(levels[i-2:i+3]):
            continue
        history = levels[max(0, i-14):i-2]
        if len(history) < 2:
            continue
        baseline = median(history)
        contrast = peak / max(0.012, baseline)
        if contrast < 2.6:
            continue
        time = i * 0.5
        if time >= duration:
            continue
        # Transcripts are chronological; advance monotonically instead of scanning
        # every recognized sentence for every half-second of a long recording.
        while speech_index < len(speech) and speech[speech_index][1] < time - 2:
            speech_index += 1
        speech_near = (speech_index < len(speech) and speech[speech_index][0] <= time + 2)
        near_motion = motion[max(0,int((time-2)/2)): min(len(motion),int((time+3)/2)+1)] if motion else ()
        motion_near = bool(near_motion and max(near_motion) >= max(0.05, motion_base*1.7))
        # A sustained change may be an exclamation, a sound effect or a gunshot burst.
        # Reject a lone anomalous RMS bucket unless a second channel corroborates it.
        sustained = (levels[i-1] >= max(0.025, peak*.3) or
                     levels[i+1] >= max(0.025, peak*.3))
        if not (sustained or speech_near or motion_near):
            continue
        reasons = ['звуковой всплеск']
        if speech_near:
            reasons.append('речь рядом')
        if motion_near:
            reasons.append('движение в кадре')
        strength = min(1.0, max(0.0, (contrast-2.6)/7) + .25 +
                       (.20 if speech_near else 0) + (.15 if motion_near else 0))
        proposed.append({'time': round(time, 2), 'strength': round(strength, 3),
                         'reasons': reasons})
    proposed.sort(key=lambda x: (-x['strength'], x['time']))
    selected = []
    selected_times = []
    for hit in proposed:
        t = hit['time']
        idx = bisect_left(selected_times, t)
        if ((idx == 0 or t - selected_times[idx-1] >= 8) and
            (idx == len(selected_times) or selected_times[idx] - t >= 8)):
            insort(selected_times, t)
            selected.append(hit)
            if len(selected) >= max(12, int(duration//35)):
                break
    return sorted(selected, key=lambda x: x['time'])
