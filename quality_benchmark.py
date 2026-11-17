"""Compare human-marked highlight windows to candidate clips without altering footage.

This is interval agreement against user labels, NOT a measure of actual humour.
A pairing is counted only if it has intersection-over-union >= 0.30.
"""

from collections import defaultdict
import math

MIN_IOU = 0.30
MAX_REFERENCES = 500


def _valid_interval(item):
    """Reject corrupted legacy project entries instead of counting fake matches."""
    try:
        start, end = float(item['start']), float(item['end'])
        return (bool(item.get('media_id')) and math.isfinite(start) and
                math.isfinite(end) and 0 <= start < end)
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def _iou(left, right):
    intersection = max(0.0, min(float(left['end']), float(right['end'])) -
                       max(float(left['start']), float(right['start'])))
    if not intersection:
        return 0.0
    union = (float(left['end']) - float(left['start'])) + (
        float(right['end']) - float(right['start'])) - intersection
    return intersection / union if union else 0.0


def evaluate_quality(references, clips):
    """Compute one-to-one clip/window matching, with no network and no AI call.

    Max-cardinality augmenting matching ensures one loose clip cannot satisfy
    multiple ground-truth moments and avoids global greedy matching mistakes.
    """
    refs = [r for r in references if _valid_interval(r)][:MAX_REFERENCES]
    annotated_media = {r['media_id'] for r in refs}
    # Unreviewed videos cannot supply meaningful false positives. Scope metrics
    # to videos with at least one human label and disclose the excluded count.
    all_selected = [c for c in clips if c.get('enabled', True) and _valid_interval(c)]
    selected = [c for c in all_selected if c['media_id'] in annotated_media]
    output = {
        'ready': bool(refs), 'threshold_iou': MIN_IOU,
        'references': len(refs), 'predictions': len(selected), 'matched': 0,
        'excluded_unlabelled_clips': len(all_selected) - len(selected),
        'precision': None, 'recall': None, 'f1': None, 'mean_iou': None,
        'matches': [], 'missed_references': [], 'unmatched_clips': [],
    }
    if not refs:
        return output
    grouped = defaultdict(list)
    for j, clip in enumerate(selected):
        grouped[clip['media_id']].append(j)

    # Highest overlap first; stable tie-breaking allows reproducible results.
    edges = []
    for ref in refs:
        options = []
        for j in grouped.get(ref['media_id'], []):
            overlap = _iou(ref, selected[j])
            if overlap + 1e-12 >= MIN_IOU:
                options.append((j, overlap))
        options.sort(key=lambda item: (-item[1], item[0]))
        edges.append(options)

    matched_clip_to_ref = {}

    def assign(ref_index, visited):
        for clip_index, _overlap in edges[ref_index]:
            if clip_index in visited:
                continue
            visited.add(clip_index)
            if clip_index not in matched_clip_to_ref or assign(matched_clip_to_ref[clip_index], visited):
                matched_clip_to_ref[clip_index] = ref_index
                return True
        return False

    for i in range(len(refs)):
        assign(i, set())

    matches = []
    matched_refs = set(matched_clip_to_ref.values())
    for clip_index, ref_index in sorted(matched_clip_to_ref.items()):
        ref, clip = refs[ref_index], selected[clip_index]
        matches.append({'reference_id': ref.get('id', ''), 'clip_id': clip.get('id', ''),
                        'media_id': ref['media_id'], 'iou': round(_iou(ref, clip), 4)})
    hits = len(matches)
    precision = hits / len(selected) if selected else 0.0
    recall = hits / len(refs)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    output.update({
        'matched': hits, 'precision': round(precision, 4),
        'recall': round(recall, 4), 'f1': round(f1, 4),
        'mean_iou': round(sum(m['iou'] for m in matches) / hits, 4) if hits else None,
        'matches': matches[:50],
        'missed_references': [r for i, r in enumerate(refs) if i not in matched_refs][:50],
        'unmatched_clips': [c for j, c in enumerate(selected) if j not in matched_clip_to_ref][:50],
    })
    return output
