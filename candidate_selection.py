"""CLIPTORA first-cut shortlist: text-aware, explainable *heuristic* ranking.

No semantic inference, speech identity or LLM network calls. This stage only uses
already cached clip metadata. It never changes the supplied candidate objects.
"""
import math
import re

_WORDS = re.compile(r'[^\W_]+', re.UNICODE)
# These low-information connectors should not make unrelated moments look alike.
_STOPWORDS = frozenset(('это', 'вот', 'тут', 'там', 'как', 'мне', 'тебе', 'тебя',
                        'меня', 'что', 'где', 'кто', 'для', 'они', 'она', 'его',
                        'уже', 'ещё', 'если', 'или', 'the', 'and', 'you', 'are',
                        'что-то', 'будет', 'сейчас', 'потом', 'только'))


def _tokens(text):
    """Significant lexical units; no embeddings and no claim of understanding."""
    return frozenset(w for w in _WORDS.findall(str(text or '').casefold())
                     if len(w) >= 3 and w not in _STOPWORDS)


def _quality_bonus(candidate):
    """Modest preference for substantial setup/answer dialogue over bare shouts."""
    if candidate.get('type') != 'dialogue':
        return 0, []
    words = _WORDS.findall(str(candidate.get('label') or '').casefold())
    reasons = candidate.get('reasons') or []
    if not isinstance(reasons, (list, tuple)):
        reasons = []
    bonus, notes = 0, []
    if len(words) <= 2:
        bonus -= 11
        notes.append('короткая реплика без контекста')
    elif len(words) >= 8:
        bonus += 4
        notes.append('развёрнутый диалог')
    if 'сохранена подводка' in reasons:
        bonus += 4
        notes.append('есть подводка')
    if 'сохранён ответ после реплики' in reasons:
        bonus += 4
        notes.append('есть ответ')
    return bonus, notes


def _duplicate_dialogue(a, b):
    """Only near-identical *informative* dialogue, not generic event labels."""
    if a.get('type') != 'dialogue' or b.get('type') != 'dialogue':
        return False
    aa, bb = a['_word_set'], b['_word_set']
    if min(len(aa), len(bb)) < 5:
        return False
    da, db = a['end'] - a['start'], b['end'] - b['start']
    if max(da, db) > min(da, db) * 1.65:
        return False
    return len(aa & bb) / len(aa | bb) >= .85


def select_best_clips(candidates, target_seconds, *, max_clips=240):
    """Return (selection, report) without mutating original candidates.

    Low-memory best-first choice, with simple file-diversity penalty. Two
    candidates from a single source cannot overlap; practically identical
    dialogue is deduplicated across sources. A budget is approximate, as in
    the previous implementation: the first strong scene may slightly exceed it.
    """
    pool = []
    report = {'considered': 0, 'selected': 0, 'duplicates': 0, 'overlaps': 0,
              'over_budget': 0, 'invalid': 0, 'selected_seconds': 0.0}
    for c in candidates:
        report['considered'] += 1
        if not isinstance(c, dict) or not c.get('media_id'):
            report['invalid'] += 1
            continue
        try:
            start, end, score = float(c['start']), float(c['end']), float(c['score'])
        except (KeyError, TypeError, ValueError, OverflowError):
            report['invalid'] += 1
            continue
        if not all(math.isfinite(x) for x in (start, end, score)) or start < 0 or end <= start:
            report['invalid'] += 1
            continue
        copy = dict(c)
        copy['start'], copy['end'] = start, end
        bonus, notes = _quality_bonus(copy)
        copy['rank_score'] = round(min(100., max(0., score + bonus)), 1)
        copy['rank_factors'] = notes
        copy['_word_set'] = _tokens(copy.get('label')) if copy.get('type') == 'dialogue' else frozenset()
        pool.append(copy)

    selected, counts, used = [], {}, 0.0
    limit = max(0., float(target_seconds))
    while pool and used < limit and len(selected) < max_clips:
        # Recompute only the small diversity penalty, not the ranking signals.
        best_index = max(range(len(pool)), key=lambda idx:
                         (pool[idx]['rank_score'] - min(18., counts.get(pool[idx]['media_id'], 0) * 1.1),
                          pool[idx]['rank_score'], -idx))
        item = pool.pop(best_index)
        if any(previous['media_id'] == item['media_id'] and
               max(0., min(previous['end'], item['end']) - max(previous['start'], item['start'])) > .3
               for previous in selected):
            report['overlaps'] += 1
            continue
        if any(_duplicate_dialogue(item, previous) for previous in selected):
            report['duplicates'] += 1
            continue
        length = item['end'] - item['start']
        if used + length > limit + 8 and used > limit * .65:
            report['over_budget'] += 1
            continue
        selected.append(item)
        counts[item['media_id']] = counts.get(item['media_id'], 0) + 1
        used += length
    for item in selected:
        item.pop('_word_set', None)
    report['selected'] = len(selected)
    report['selected_seconds'] = round(used, 1)
    return selected, report
