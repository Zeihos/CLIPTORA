"""Deterministic, read-only planning and invalidation for composed MP4 previews."""
import copy
import hashlib
import json
import math


PREVIEW_LIMIT_SECONDS = 120


def preview_segments(clips, limit_seconds=PREVIEW_LIMIT_SECONDS):
    """Return enabled timeline clips clipped to the first `limit_seconds`.

    Does not reorder or mutate the user's manually edited draft. Preview duration
    is explicitly limited, rather than silently promising a complete long movie.
    """
    if type(limit_seconds) not in (int, float) or not math.isfinite(limit_seconds) or limit_seconds <= 0:
        raise ValueError('Неверная длительность предпросмотра')
    selected = []
    total = 0.0
    truncated = False
    for clip in clips:
        if not clip.get('enabled'):
            continue
        try:
            start = float(clip['start'])
            end = float(clip['end'])
        except (KeyError, ValueError, TypeError, OverflowError):
            raise ValueError('Некорректные границы фрагмента') from None
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end):
            raise ValueError('Некорректные границы фрагмента')
        duration = end - start
        remaining = limit_seconds - total
        if remaining <= 0:
            truncated = True
            break
        chosen = copy.deepcopy(clip)
        if duration > remaining:
            chosen['end'] = round(start + remaining, 6)
            duration = remaining
            truncated = True
        selected.append(chosen)
        total += duration
    if not selected:
        raise ValueError('Включите хотя бы один фрагмент для предпросмотра')
    return selected, truncated, round(total, 3)


def preview_signature(clips, files, normalize_audio, fade_ms, pacing='normal'):
    """Stable content key: draft edits, render options and scan's source fingerprint."""
    media = {f['id']: f for f in files}
    selected = [c for c in clips if c.get('enabled')]
    referenced = []
    for media_id in sorted({c['media_id'] for c in selected}):
        f = media.get(media_id, {})
        referenced.append({'id':media_id,'path':f.get('path'), 'size':f.get('size'),
                           'mtime_ns':f.get('mtime_ns'),
                           'analysis_signature':f.get('analysis_signature')})
    payload={'format':'cliptora-preview-v2','limit_seconds':PREVIEW_LIMIT_SECONDS,
             'clips':selected,'media':referenced,'normalize_audio':normalize_audio,
             'fade_ms':fade_ms,'pacing':pacing}
    data=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    return hashlib.sha256(data.encode('utf-8')).hexdigest()
