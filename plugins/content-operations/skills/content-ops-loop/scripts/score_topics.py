#!/usr/bin/env python3
"""Score, rank, cooldown-check, import gated topics, and annotate fuzzy repeats in topics/topics.json."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys

DEFAULT_WEIGHTS = {
    'audiencePain': 0.35,
    'evidenceStrength': 0.30,
    'timeliness': 0.15,
    'brandFit': 0.20,
}
WEIGHTS = DEFAULT_WEIGHTS  # Backward-compatible export

REPEAT_OVERLAP_THRESHOLD = 0.6
STOPWORDS = {
    'a', 'an', 'the', 'and', 'or', 'for', 'of', 'to', 'in', 'on', 'with',
    'by', 'is', 'are', 'how', 'why', 'what', 'when', 'from', 'vs', 'into',
}


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_weights(spec: str | None) -> dict[str, float]:
    if not spec:
        return dict(DEFAULT_WEIGHTS)
    parsed: dict[str, float] = {}
    for pair in spec.split(','):
        if '=' not in pair:
            continue
        k, v = pair.split('=', 1)
        k = k.strip()
        if k in DEFAULT_WEIGHTS:
            parsed[k] = max(0.0, float(v.strip()))
    total = sum(parsed.values())
    if not parsed or total <= 0:
        raise ValueError('Invalid --weights specification; expected e.g. audiencePain=0.4,evidenceStrength=0.3,timeliness=0.1,brandFit=0.2')
    return {k: parsed.get(k, 0.0) / total for k in DEFAULT_WEIGHTS}


def compute_score(scores: dict, weights: dict[str, float] | None = None) -> float:
    w = weights or DEFAULT_WEIGHTS
    total = 0.0
    for key, weight in w.items():
        val = float((scores or {}).get(key) or 0)
        val = max(0.0, min(5.0, val))
        total += val * weight
    return round(total, 2)


def title_tokens(title: str | None) -> set[str]:
    """Tokenize EN words + CJK character bigrams for annotate-only fuzzy repeat detection."""
    text = str(title or '').strip().lower()
    if not text:
        return set()
    tokens: set[str] = set()
    for word in re.findall(r'[a-z0-9]+', text):
        if len(word) >= 2 and word not in STOPWORDS:
            tokens.add(word)
    for run in re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]+', text):
        if len(run) == 1:
            tokens.add(run)
        else:
            for i in range(len(run) - 1):
                tokens.add(run[i:i + 2])
    return tokens


def token_overlap(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def published_topic_ids(ws: Path, cutoff: datetime | None = None) -> set[str]:
    pub_path = ws / 'publish-log.jsonl'
    if not pub_path.is_file():
        return set()
    draft_to_topic: dict[str, str] = {}
    drafts_dir = ws / 'drafts'
    if drafts_dir.is_dir():
        for entry in drafts_dir.iterdir():
            mp = entry / 'meta.json'
            if entry.is_dir() and mp.is_file():
                try:
                    meta = json.loads(mp.read_text(encoding='utf-8'))
                    if meta.get('draftId') and meta.get('topicId'):
                        draft_to_topic[meta['draftId']] = meta['topicId']
                except (OSError, ValueError):
                    pass
    published: set[str] = set()
    for line in pub_path.read_text(encoding='utf-8').splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            row = json.loads(s)
        except ValueError:
            continue
        if row.get('status') != 'published':
            continue
        if cutoff is not None:
            ts = parse_iso(row.get('publishedAt'))
            if ts and ts < cutoff:
                continue
        tid = draft_to_topic.get(row.get('draftId', ''))
        if tid:
            published.add(tid)
    return published


def recent_published_topic_ids(ws: Path, cutoff: datetime) -> set[str]:
    return published_topic_ids(ws, cutoff=cutoff)


def _annotate_fuzzy_repeats(topics: list[dict], all_published_tids: set[str]) -> list[dict]:
    """Annotate fuzzy title overlap (>= 0.6) without ever merging or deleting rows."""
    tokenized = [(t, title_tokens(t.get('title'))) for t in topics]
    annotations: list[dict] = []

    for idx, (item, toks) in enumerate(tokenized):
        if item.get('status', 'candidate') not in ('candidate', 'shortlisted'):
            continue
        tid = item.get('topicId')
        best_match = None
        best_overlap = 0.0
        surfaced_count = 1
        any_covered = False

        for jdx, (other, other_toks) in enumerate(tokenized):
            if idx == jdx:
                continue
            ov = token_overlap(toks, other_toks)
            if ov < REPEAT_OVERLAP_THRESHOLD:
                continue
            surfaced_count += 1
            other_tid = other.get('topicId')
            other_covered = (
                other.get('status') == 'produced'
                or (other_tid in all_published_tids)
                or bool((other.get('repeatAnnotation') or {}).get('alreadyCovered'))
            )
            if other_covered:
                any_covered = True
            if (
                best_match is None
                or (other_covered and not best_match[2])
                or (other_covered == best_match[2] and ov > best_overlap)
            ):
                best_match = (other, ov, other_covered)
                best_overlap = ov

        if best_match is not None:
            matched_item, ov, _ = best_match
            ann = {
                'matchedTopicId': matched_item.get('topicId'),
                'matchedTitle': matched_item.get('title'),
                'overlap': round(ov, 2),
                'surfacedCount': surfaced_count,
                'alreadyCovered': any_covered,
            }
            item['repeatAnnotation'] = ann
            annotations.append({'topicId': tid, **ann})
        else:
            item.pop('repeatAnnotation', None)

    return annotations


def import_gated_topics(ws: Path, gate_report_path: Path, write: bool = True) -> dict:
    """Deterministically merge signal_gate.py `gate` passed candidates into topics/topics.json."""
    topics_path = ws / 'topics' / 'topics.json'
    doc = json.loads(topics_path.read_text(encoding='utf-8')) if topics_path.is_file() else {'version': 1, 'topics': []}
    topics: list[dict] = doc.setdefault('topics', [])
    gate_doc = json.loads(gate_report_path.expanduser().resolve().read_text(encoding='utf-8'))
    passed = gate_doc.get('passed') if isinstance(gate_doc, dict) else None
    if not isinstance(passed, list):
        raise ValueError('Gate report must be a JSON object with a "passed" list.')

    existing_ids = {str(t.get('topicId')) for t in topics if t.get('topicId')}
    existing_urls = {u for t in topics for u in (t.get('evidenceUrls') or [])}
    now_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    date_tag = datetime.now(timezone.utc).strftime('%Y%m%d')
    seq = len(existing_ids) + 1
    added, skipped = [], []

    for cand in passed:
        if not isinstance(cand, dict):
            continue
        title = str(cand.get('title') or '').strip()
        urls = [str(u).strip() for u in (cand.get('evidenceUrls') or []) if str(u).strip()]
        if not title:
            continue
        if urls and all(u in existing_urls for u in urls):
            skipped.append({'title': title, 'reason': 'duplicate_evidence_urls'})
            continue
        tid = str(cand.get('topicId') or '').strip()
        while not tid or tid in existing_ids:
            tid = f'top-{date_tag}-{seq:03d}'
            seq += 1
        existing_ids.add(tid)
        existing_urls.update(urls)
        slug = re.sub(r'[^a-z0-9\u4e00-\u9fff]+', '-', title.lower()).strip('-')[:48] or tid
        row = {
            'topicId': tid,
            'title': title,
            'sourceType': cand.get('sourceType', 'platform_trend'),
            'cooldownKey': cand.get('cooldownKey') or slug,
            'evidenceUrls': urls,
            'targetPlatforms': cand.get('targetPlatforms') or [],
            'scores': cand.get('scores') or {'audiencePain': 4, 'evidenceStrength': 4, 'timeliness': 4, 'brandFit': 4},
            'status': 'candidate',
            'createdAt': now_iso,
        }
        topics.append(row)
        added.append({'topicId': tid, 'title': title})

    if write:
        topics_path.parent.mkdir(parents=True, exist_ok=True)
        topics_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return {'ok': True, 'addedCount': len(added), 'skippedCount': len(skipped), 'added': added, 'skipped': skipped}


def score_topics(
    ws: Path,
    cooldown_days: int = 14,
    write: bool = True,
    weights: dict[str, float] | None = None,
    shortlist_min: float = 3.8,
    auto_archive_below: float | None = None,
) -> dict:
    topics_path = ws / 'topics' / 'topics.json'
    if not topics_path.is_file():
        raise FileNotFoundError(f'Missing {topics_path}')

    doc = json.loads(topics_path.read_text(encoding='utf-8'))
    topics = doc.get('topics', [])
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=cooldown_days)
    recent_pub_tids = published_topic_ids(ws, cutoff=cutoff)
    all_pub_tids = published_topic_ids(ws, cutoff=None)

    recent_keys: dict[str, str] = {}
    for item in topics:
        ck = item.get('cooldownKey')
        tid = item.get('topicId', 'existing')
        if not ck:
            continue
        ts = parse_iso(item.get('updatedAt') or item.get('createdAt'))
        if item.get('status') in ('approved', 'produced') and (ts is None or ts >= cutoff):
            recent_keys[ck] = tid
        elif tid in recent_pub_tids:
            recent_keys[ck] = tid

    eff_weights = weights or DEFAULT_WEIGHTS
    for item in topics:
        item['weightedScore'] = compute_score(item.get('scores', {}), eff_weights)

    repeat_annotations = _annotate_fuzzy_repeats(topics, all_pub_tids)

    candidates = [t for t in topics if t.get('status', 'candidate') in ('candidate', 'shortlisted')]
    candidates.sort(key=lambda t: -(t.get('weightedScore') or 0.0))

    seen_batch_keys: dict[str, str] = {}
    shortlisted = []
    conflicts = []
    for item in candidates:
        scores = item.get('scores', {})
        weighted = item['weightedScore']
        tid = item.get('topicId')
        ck = item.get('cooldownKey')
        override_reason = str(item.get('cooldownOverrideReason') or '').strip()

        conflict_ref = None
        if ck:
            if ck in recent_keys and recent_keys[ck] != tid:
                conflict_ref = recent_keys[ck]
            elif ck in seen_batch_keys and seen_batch_keys[ck] != tid:
                conflict_ref = f'batch:{seen_batch_keys[ck]}'
            else:
                seen_batch_keys[ck] = tid or 'candidate'

        item['cooldownConflict'] = bool(conflict_ref)
        if conflict_ref:
            item['cooldownConflictWith'] = conflict_ref
            conflicts.append((tid, conflict_ref))
        else:
            item.pop('cooldownConflictWith', None)

        veto = float((scores or {}).get('evidenceStrength') or 0) <= 2 or float((scores or {}).get('brandFit') or 0) <= 2
        blocked_by_cooldown = item['cooldownConflict'] and not override_reason

        if weighted >= shortlist_min and not veto and not blocked_by_cooldown:
            item['status'] = 'shortlisted'
            item.pop('archiveReason', None)
            shortlisted.append(item)
        elif auto_archive_below is not None and weighted < auto_archive_below:
            item['status'] = 'archived'
            item.setdefault('archiveReason', f'weightedScore below {auto_archive_below:g} threshold')
        else:
            item['status'] = 'candidate'

    topics.sort(key=lambda t: (t.get('status') != 'shortlisted', -(t.get('weightedScore') or 0.0)))
    doc['topics'] = topics
    if write:
        topics_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    outcome = 'solid' if shortlisted else 'nothing_solid'
    closest = None
    if not shortlisted and candidates:
        top = candidates[0]
        closest = {
            'topicId': top.get('topicId'),
            'title': top.get('title'),
            'weightedScore': top.get('weightedScore'),
            'cooldownConflict': bool(top.get('cooldownConflict')),
            'repeatAnnotation': top.get('repeatAnnotation'),
        }

    return {
        'outcome': outcome,
        'total': len(topics),
        'weights': eff_weights,
        'shortlistMin': shortlist_min,
        'shortlisted': [
            {
                'topicId': t.get('topicId'),
                'title': t.get('title'),
                'weightedScore': t.get('weightedScore'),
                'targetPlatforms': t.get('targetPlatforms', []),
                'cooldownOverridden': bool(t.get('cooldownConflict') and t.get('cooldownOverrideReason')),
                'repeatAnnotation': t.get('repeatAnnotation'),
            }
            for t in shortlisted
        ],
        'cooldownConflicts': conflicts,
        'repeatAnnotations': repeat_annotations,
        'closestCandidate': closest,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Score, rank, import gated topics, and annotate repeats in topics/topics.json.')
    parser.add_argument('workspace', help='Path to the content-ops directory.')
    parser.add_argument('--cooldown-days', type=int, default=14, help='Deduplication cooldown window in days.')
    parser.add_argument('--weights', default='', help='Custom weights e.g. audiencePain=0.4,evidenceStrength=0.3,timeliness=0.1,brandFit=0.2.')
    parser.add_argument('--shortlist-min', type=float, default=3.8, help='Minimum weightedScore for shortlist status (default 3.8).')
    parser.add_argument('--auto-archive-below', type=float, default=None, help='Optional weightedScore below which candidates are archived (off by default).')
    parser.add_argument('--import-gated', default='', help='Optional path to signal_gate.py gate JSON report to merge before scoring.')
    parser.add_argument('--dry-run', action='store_true', help='Print scoring summary without writing topics.json.')
    args = parser.parse_args(argv)

    ws = Path(args.workspace).resolve()
    import_res = None
    if args.import_gated:
        import_res = import_gated_topics(ws, Path(args.import_gated), write=not args.dry_run)

    weights = parse_weights(args.weights) if args.weights else None
    result = score_topics(
        ws,
        cooldown_days=args.cooldown_days,
        write=not args.dry_run,
        weights=weights,
        shortlist_min=args.shortlist_min,
        auto_archive_below=args.auto_archive_below,
    )
    if import_res is not None:
        result['imported'] = import_res
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
