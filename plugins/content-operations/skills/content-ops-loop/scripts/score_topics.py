#!/usr/bin/env python3
"""Score, rank, and cooldown-check topics in content-ops/topics/topics.json."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

WEIGHTS = {
    'audiencePain': 0.35,
    'evidenceStrength': 0.30,
    'timeliness': 0.15,
    'brandFit': 0.20,
}


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def compute_score(scores: dict) -> float:
    total = 0.0
    for key, weight in WEIGHTS.items():
        val = float((scores or {}).get(key) or 0)
        val = max(0.0, min(5.0, val))
        total += val * weight
    return round(total, 2)


def recent_published_topic_ids(ws: Path, cutoff: datetime) -> set[str]:
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
    published_topics: set[str] = set()
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
        ts = parse_iso(row.get('publishedAt'))
        if ts and ts < cutoff:
            continue
        tid = draft_to_topic.get(row.get('draftId', ''))
        if tid:
            published_topics.add(tid)
    return published_topics


def score_topics(ws: Path, cooldown_days: int = 14, write: bool = True) -> dict:
    topics_path = ws / 'topics' / 'topics.json'
    if not topics_path.is_file():
        raise FileNotFoundError(f'Missing {topics_path}')

    doc = json.loads(topics_path.read_text(encoding='utf-8'))
    topics = doc.get('topics', [])
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=cooldown_days)
    recent_pub_tids = recent_published_topic_ids(ws, cutoff)

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

    # Compute weighted scores first so in-batch duplicate cooldownKeys favor the highest-scoring item
    for item in topics:
        item['weightedScore'] = compute_score(item.get('scores', {}))

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

        if weighted >= 3.8 and not veto and not blocked_by_cooldown:
            item['status'] = 'shortlisted'
            item.pop('archiveReason', None)
            shortlisted.append(item)
        elif weighted < 3.0:
            item['status'] = 'archived'
            item.setdefault('archiveReason', 'weightedScore below 3.0 threshold')
        else:
            item['status'] = 'candidate'

    topics.sort(key=lambda t: (t.get('status') != 'shortlisted', -(t.get('weightedScore') or 0.0)))
    doc['topics'] = topics
    if write:
        topics_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    return {
        'total': len(topics),
        'shortlisted': [
            {
                'topicId': t.get('topicId'),
                'title': t.get('title'),
                'weightedScore': t.get('weightedScore'),
                'targetPlatforms': t.get('targetPlatforms', []),
                'cooldownOverridden': bool(t.get('cooldownConflict') and t.get('cooldownOverrideReason')),
            }
            for t in shortlisted
        ],
        'cooldownConflicts': conflicts,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Score and rank topics in topics/topics.json.')
    parser.add_argument('workspace', help='Path to the content-ops directory.')
    parser.add_argument('--cooldown-days', type=int, default=14, help='Deduplication cooldown window in days.')
    parser.add_argument('--dry-run', action='store_true', help='Print scoring summary without writing topics.json.')
    args = parser.parse_args(argv)

    result = score_topics(Path(args.workspace).resolve(), cooldown_days=args.cooldown_days, write=not args.dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
