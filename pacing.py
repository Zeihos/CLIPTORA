"""Conservative, non-destructive shortening of transcript-backed silent gaps.

Only the export timeline is split. Manual editor clips, their labels, and
source files are never changed. This is NOT voice-activity detection: it needs
an existing transcript plus 0.5 s audio-envelope data and optionally a
0.5 FPS motion envelope. Without those inputs it leaves the cut alone.
"""
import copy
import math
from statistics import median


MODES = {
    'normal': None,
    # Required uncut speech gap (seconds), speech padding (seconds), minimum removed section
    'dynamic': (2.0, 0.4, 1.0),
    'fast': (1.1, 0.25, 0.6),
}
MAX_CUTS_PER_CLIP = 24


def validate_pacing(mode):
    if type(mode) is not str or mode not in MODES:
        raise ValueError('Темп монтажа: normal, dynamic или fast.')
    return mode


def _finite(value):
    try:
        f = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return f if math.isfinite(f) else None


def _safe_segments(items, clip_start, clip_end):
    segments = []
    for entry in items:
        if not isinstance(entry, dict) or not str(entry.get('text', '')).strip():
            continue
        start, end = _finite(entry.get('start')), _finite(entry.get('end'))
        if start is None or end is None or not (clip_start <= start < end <= clip_end):
            continue
        segments.append((start, end))
    segments.sort()
    # Whisper sometimes emits overlapping sentences; merge their time spans.
    merged = []
    for start, end in segments:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def _silent_and_still(audio, motion, start, end, threshold, motion_threshold):
    # Sample buckets wholly inside the cut; boundary buckets may contain speech.
    left = max(0, math.ceil(start * 2))
    right = min(len(audio), math.floor(end * 2))
    if right <= left or max(audio[left:right], default=math.inf) > threshold:
        return False
    if motion:
        # Each value describes a 2-second interval. Protect any active gameplay
        # overlapping the proposed deletion, including its boundary windows.
        m_start = max(0, math.floor(start / 2))
        m_end = min(len(motion), math.ceil(end / 2))
        if m_end <= m_start or max(motion[m_start:m_end], default=math.inf) > motion_threshold:
            return False
    return True


def plan_pacing(clips, media_by_id, mode='normal'):
    """Return independent export pieces and a factual removal summary.

    Calls never modify `clips` or `media_by_id`. Repeated clip IDs in the result
    are intentional: pieces share their source editor clip and are for FFmpeg/SRT
    export only, not for inserting back into the editor.
    """
    mode = validate_pacing(mode)
    original = copy.deepcopy(clips)
    if mode == 'normal':
        return original, {'mode': mode, 'cuts': 0, 'removed_seconds': 0.0}

    gap_min, pad, min_removed = MODES[mode]
    result, cuts, removed = [], 0, 0.0
    cache = {}
    for clip in original:
        media = media_by_id.get(clip.get('media_id'), {})
        analysis = media.get('analysis') or {}
        audio = analysis.get('audio_levels') or []
        transcript = analysis.get('transcript') or []
        motion = analysis.get('motion_levels') or []
        start, end = _finite(clip.get('start')), _finite(clip.get('end'))
        if (start is None or end is None or start >= end or
                not audio or not transcript or len(audio) < 4):
            result.append(clip)
            continue
        media_id = clip.get('media_id')
        if media_id not in cache:
            # A quiet window must be both absolutely quiet and quieter than
            # the file's ordinary background sound (music is not silence).
            baseline = median(audio)
            audio_threshold = min(0.025, max(0.006, baseline * 0.7))
            motion_threshold = max(0.015, median(motion) * 1.5) if motion else 0
            cache[media_id] = audio_threshold, motion_threshold
        audio_threshold, motion_threshold = cache[media_id]
        speech = _safe_segments(transcript, start, end)
        if len(speech) < 2:
            result.append(clip)
            continue
        cursor = start
        clip_cuts = 0
        for (_, prior_end), (next_start, _) in zip(speech, speech[1:]):
            if clip_cuts >= MAX_CUTS_PER_CLIP:
                break
            gap = next_start - prior_end
            if gap < gap_min:
                continue
            a, b = round(prior_end + pad, 3), round(next_start - pad, 3)
            if b-a < min_removed or a-cursor < 0.5 or end-b < 0.5:
                continue
            if not _silent_and_still(audio, motion, a, b, audio_threshold, motion_threshold):
                continue
            part = copy.deepcopy(clip)
            part['start'], part['end'] = round(cursor, 3), a
            result.append(part)
            cursor = b
            cuts += 1
            clip_cuts += 1
            removed += b-a
        tail = copy.deepcopy(clip)
        tail['start'], tail['end'] = round(cursor, 3), round(end, 3)
        result.append(tail)
    return result, {'mode': mode, 'cuts': cuts, 'removed_seconds': round(removed, 3)}
