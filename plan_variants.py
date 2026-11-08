"""Generate explainable alternative first-cut plans without editing the current draft.

This is transparent heuristic reweighting, not a learned quality or comedy model.
"""
import copy

from candidate_selection import select_best_clips

PRESET_TITLES = {
    'balanced': 'Баланс',
    'dialogue': 'Диалоги',
    'action': 'Экшен',
}

_PRESET_BONUSES = {
    'balanced': {},
    'dialogue': {'dialogue': 20, 'reaction': -12, 'motion': -12, 'action': -12},
    'action': {'dialogue': -18, 'reaction': 18, 'motion': 18, 'action': 18},
}


def create_variants(candidates, target_seconds, source_order):
    """Return three independent choices from the same cached candidates.

    Original input candidates remain unchanged. Sorting follows source chronology.
    """
    variants = {}
    for preset, bonuses in _PRESET_BONUSES.items():
        weighted = []
        for item in candidates:
            copy_item = dict(item)
            try:
                base_score = float(item['score'])
            except (TypeError, ValueError, KeyError):
                weighted.append(copy_item)
                continue
            bonus = bonuses.get(item.get('type'), 0)
            copy_item['base_score'] = base_score
            copy_item['variant_adjustment'] = bonus
            copy_item['score'] = max(0., min(100., base_score + bonus))
            weighted.append(copy_item)
        chosen, report = select_best_clips(weighted, target_seconds)
        chosen.sort(key=lambda item: (source_order.get(item['media_id'], 10**9), item['start']))
        for i, clip in enumerate(chosen):
            clip.update({'id': f'c{i:05d}', 'enabled': True,
                         'zoom': clip['rank_score'] >= 68})
        variants[preset] = {'title': PRESET_TITLES[preset], 'clips': chosen,
                            'summary': report}
    return variants
