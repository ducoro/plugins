#!/usr/bin/env python3
"""Aggregate multi-window snapshots, rank works, track account snapshots, and list due snapshots."""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

WINDOW_HOURS = [('24h', 24), ('72h', 72), ('7d', 168), ('30d', 720)]


def parse_iso_utc(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
        return dt.astimezone(timezone.utc) if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def iter_jsonl(path: Path):
    if not path.is_file():
        return
    for lineno, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except ValueError as exc:
            print(f'Warning: skipping malformed JSONL line {path.name}:{lineno} ({exc})', file=sys.stderr)
            continue
        if isinstance(row, dict):
            yield row


def compute_due_snapshots(ws: Path, existing_windows: dict[tuple[str, str], set[str]], now: datetime) -> list[dict]:
    pub_path = ws / 'publish-log.jsonl'
    due = []
    for row in iter_jsonl(pub_path):
        if row.get('status') != 'published' or not row.get('workId'):
            continue
        pub_dt = parse_iso_utc(row.get('publishedAt'))
        if not pub_dt:
            continue
        age_hours = (now - pub_dt).total_seconds() / 3600.0
        plat = str(row.get('platform') or 'unknown')
        wid = str(row['workId'])
        captured = existing_windows.get((plat, wid), set())
        missing = [label for label, hrs in WINDOW_HOURS if age_hours >= hrs and label not in captured]
        if missing:
            due.append({
                'workId': wid,
                'platform': row.get('platform'),
                'accountId': row.get('accountId'),
                'publishedAt': row.get('publishedAt'),
                'missingWindows': missing,
            })
    return due


def aggregate(ws: Path, days: int = 14) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    snap_path = ws / 'analytics' / 'snapshots.jsonl'

    latest_by_work: dict[tuple[str, str], tuple[datetime, dict]] = {}
    latest_by_account: dict[str, tuple[datetime, dict]] = {}
    existing_windows: dict[tuple[str, str], set[str]] = defaultdict(set)

    for row in iter_jsonl(snap_path):
        dt = parse_iso_utc(row.get('capturedAt')) or datetime.min.replace(tzinfo=timezone.utc)
        plat_key = str(row.get('platform') or 'unknown')
        if row.get('workId') and row.get('window'):
            existing_windows[(plat_key, str(row['workId']))].add(row['window'])
        if row.get('window') == 'account':
            aid = row.get('accountId') or row.get('platform') or 'unknown'
            if aid and (aid not in latest_by_account or dt >= latest_by_account[aid][0]):
                latest_by_account[aid] = (dt, row)
            continue
        if dt < cutoff:
            continue
        wid = row.get('workId')
        if wid:
            wkey = (plat_key, str(wid))
            if wkey not in latest_by_work or dt >= latest_by_work[wkey][0]:
                latest_by_work[wkey] = (dt, row)

    by_plat = defaultdict(lambda: {
        'works': 0, 'views': 0, 'likes': 0, 'comments': 0, 'shares': 0, 'saves': 0,
        'nativeSums': defaultdict(float), 'nativeCounts': defaultdict(int),
    })
    by_topic = defaultdict(list)
    ranked_works = []

    for _, row in latest_by_work.values():
        plat = str(row.get('platform') or 'unknown')
        m = row.get('metrics') or {}
        views = int(m.get('views', 0) or 0)
        likes = int(m.get('likes', 0) or 0)
        cmts = int(m.get('comments', 0) or 0)
        shares = int(m.get('shares', 0) or 0)
        saves = int(m.get('saves', 0) or 0)
        inter = likes + cmts + shares + saves
        eng = round((inter / views) * 100, 2) if views > 0 else 0.0

        b = by_plat[plat]
        b['works'] += 1
        b['views'] += views
        b['likes'] += likes
        b['comments'] += cmts
        b['shares'] += shares
        b['saves'] += saves
        for k, v in (row.get('platformMetrics') or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                b['nativeSums'][k] += float(v)
                b['nativeCounts'][k] += 1

        work_item = {
            'workId': row.get('workId'),
            'topicId': row.get('topicId'),
            'platform': plat,
            'title': row.get('title'),
            'window': row.get('window'),
            'views': views,
            'interactions': inter,
            'engagementRate': eng,
        }
        ranked_works.append(work_item)
        if row.get('topicId'):
            by_topic[row['topicId']].append(work_item)

    ranked_works.sort(key=lambda w: (w['views'], w['engagementRate']), reverse=True)

    plat_summary = {}
    for plat, b in sorted(by_plat.items()):
        inter = b['likes'] + b['comments'] + b['shares'] + b['saves']
        plat_summary[plat] = {
            'works': b['works'],
            'views': b['views'],
            'likes': b['likes'],
            'comments': b['comments'],
            'shares': b['shares'],
            'saves': b['saves'],
            'avgEngagementRate': round((inter / b['views']) * 100, 2) if b['views'] > 0 else 0.0,
            'avgPlatformMetrics': {
                k: round(b['nativeSums'][k] / b['nativeCounts'][k], 3)
                for k in sorted(b['nativeSums'])
            },
        }

    cross = [
        {'topicId': tid, 'platforms': sorted(entries, key=lambda e: -e['views'])}
        for tid, entries in sorted(by_topic.items())
        if len({e['platform'] for e in entries}) >= 2
    ]

    return {
        'windowDays': days,
        'worksEvaluated': len(latest_by_work),
        'byPlatform': plat_summary,
        'topWorks': ranked_works[:5],
        'bottomWorks': list(reversed(ranked_works[-5:])) if ranked_works else [],
        'crossPlatformTopics': cross,
        'accountSnapshots': [
            row for _, row in sorted(
                latest_by_account.values(),
                key=lambda x: (str(x[1].get('platform') or ''), str(x[1].get('accountId') or '')),
            )
        ],
        'dueSnapshots': compute_due_snapshots(ws, existing_windows, now),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Aggregate analytics/snapshots.jsonl for retrospectives.')
    parser.add_argument('workspace', help='Path to the content-ops directory.')
    parser.add_argument('--days', type=int, default=14, help='Lookback window in days (default: 14).')
    args = parser.parse_args(argv)

    result = aggregate(Path(args.workspace).resolve(), days=args.days)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
