"""Conservative dialogue context windows for manual-first video highlights.

Uses only existing transcript timestamps, optional *heuristic* humor scores and
relative audio spikes. Does not infer speakers, jokes, or scene semantics.
"""
from bisect import bisect_left, bisect_right
import math


def _num(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError, OverflowError):
        return None


def build_dialogue_windows(segments, duration, reactions=()):
    """Build bounded, chronological contexts around ranked/reaction-adjacent speech.

    Output is a list of {start, end, text, humor, reasons} dictionaries. Does
    not modify cached transcriptions. In the absence of strong signals, falls
    back to grouped dialogue just as earlier CLIPTORA releases did.
    """
    duration = _num(duration)
    if duration is None or duration < 3:
        return []
    speech = []
    for raw in segments or ():
        if not isinstance(raw, dict):
            continue
        start, end = _num(raw.get('start')), _num(raw.get('end'))
        if start is None or end is None or end <= 0 or start >= duration:
            continue
        start, end = max(0.0, start), min(duration, end)
        if end <= start:
            continue
        content = str(raw.get('text') or '').strip()
        if not content:
            continue
        humor = _num(raw.get('humor'))
        speech.append({'start': start, 'end': end, 'text': content,
                       'humor': min(5., max(0., humor or 0.))})
    if not speech:
        return []
    speech.sort(key=lambda s: (s['start'], s['end']))
    hits = []
    for raw in reactions or ():
        if not isinstance(raw, dict):
            continue
        t, strength = _num(raw.get('time')), _num(raw.get('strength'))
        if t is not None and 0 <= t <= duration and strength is not None:
            hits.append({'time': t, 'strength': min(1.0, max(0.0, strength))})
    hits.sort(key=lambda x: x['time'])
    times = [h['time'] for h in hits]

    scenes, group = [], []
    for seg in speech:
        # A long speech run may span multiple independent comic moments.
        if group and (seg['start'] - group[-1]['end'] > 6.5 or
                      seg['end'] - group[0]['start'] > 34):
            scenes.append(group)
            group = []
        group.append(seg)
    if group:
        scenes.append(group)

    windows = []
    for scene in scenes:
        anchor = None
        anchor_hit = None
        best = 0.0
        for seg in scene:
            lo = bisect_left(times, seg['start'] - 1.5)
            hi = bisect_right(times, seg['end'] + 4)
            hit = max(hits[lo:hi], key=lambda h: h['strength'], default=None)
            strength = hit['strength'] if hit else 0.0
            if seg['humor'] < 3 and strength < .55:
                continue
            priority = seg['humor'] / 5.0 + strength * .75
            if priority > best:
                anchor, anchor_hit, best = seg, hit, priority

        if anchor:
            # Keep the lead-in and follow-up utterances, not just the peak.
            focus = max(anchor['end'], anchor_hit['time'] if anchor_hit else anchor['end'])
            visible = [s for s in scene if s['end'] >= focus - 18 and
                       s['start'] <= focus + 8]
            if not visible:
                visible = [anchor]
            start = max(0, visible[0]['start'] - 2)
            end = min(duration, max(focus + 5, visible[-1]['end'] + 3))
            reasons = []
            if any(s['end'] <= anchor['start'] for s in visible if s is not anchor):
                reasons.append('сохранена подводка')
            if any(s['start'] >= anchor['end'] for s in visible if s is not anchor):
                reasons.append('сохранён ответ после реплики')
            if anchor_hit and anchor_hit['time'] >= anchor['start']:
                reasons.append('запас после звуковой реакции')
            else:
                reasons.append('запас после ключевой реплики')
        else:
            visible = scene
            start, end = max(0, scene[0]['start'] - 2.5), min(duration, scene[-1]['end'] + 2.5)
            reasons = ['группа соседних реплик']
        # Avoid 40+ second candidates that consume a whole short montage.
        if end - start > 36:
            start = end - 36
            visible = [s for s in visible if s['end'] > start]
        if end - start < 3 or not visible:
            continue
        windows.append({'start': round(start, 2), 'end': round(end, 2),
                        'text': ' '.join(s['text'] for s in visible),
                        'humor': max(s['humor'] for s in visible),
                        'reasons': reasons})
    return windows
