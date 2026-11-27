#!/usr/bin/env python3
"""Aggregate multi-window snapshots, recall top historical hooks, detect breakout works, and list due snapshots."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from statistics import median
import sys
from urllib.parse import urlparse

WINDOW_HOURS = [('24h', 24), ('72h', 72), ('7d', 168), ('30d', 720)]
FRONT_JSON_RE = re.compile(r'^\s*```json\s*\n.*?\n```\s*\n?', re.S)
YAML_FRONT_RE = re.compile(r'^\s*---\s*\n.*?\n---\s*\n?', re.S)
BREAKOUT_ACTION_TYPES = ('reply', 'repost')


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_iso_utc(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
        return dt.astimezone(timezone.utc) if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _is_http_url(url: object) -> bool:
    if not isinstance(url, str) or not url.strip():
        return False
    parsed = urlparse(url.strip())
    return parsed.scheme in ('http', 'https') and bool(parsed.netloc)


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


def read_json(path: Path, default):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except ValueError:
        return default


def extract_hook_from_text(raw: str, max_chars: int = 220) -> str:
    """Extract the opening 1-2 meaningful lines/sentences from a variant or master draft."""
    body = FRONT_JSON_RE.sub('', raw, count=1)
    body = YAML_FRONT_RE.sub('', body, count=1)
    lines: list[str] = []
    for ln in body.splitlines():
        s = ln.strip()
        if not s:
            if lines:
                break
            continue
        if s.startswith('<!--') and s.endswith('-->'):
            continue
        s = re.sub(r'^#{1,6}\s+', '', s).strip()
        if not s:
            continue
        lines.append(s)
        if len(lines) >= 2 or len(' '.join(lines)) >= max_chars:
            break
    joined = ' '.join(lines).strip()
    if len(joined) > max_chars:
        joined = joined[: max_chars - 1].rstrip() + '…'
    return joined


def load_publish_index(ws: Path) -> dict[tuple[str, str], dict]:
    """Map (platform, workId) to the latest published record in publish-log.jsonl."""
    idx: dict[tuple[str, str], dict] = {}
    for row in iter_jsonl(ws / 'publish-log.jsonl'):
        if row.get('status') != 'published' or not row.get('workId'):
            continue
        plat = str(row.get('platform') or 'unknown')
        wid = str(row['workId'])
        prev = idx.get((plat, wid))
        prev_dt = parse_iso_utc(prev.get('publishedAt')) if prev else None
        cur_dt = parse_iso_utc(row.get('publishedAt'))
        if prev is None or (cur_dt is not None and (prev_dt is None or cur_dt >= prev_dt)):
            idx[(plat, wid)] = row
    return idx


def resolve_work_hook(ws: Path, platform: str, draft_id: str | None, fallback_title: str | None) -> tuple[str, str]:
    """Resolve the opening hook text and source label from variant markdown, master.md, or title fallback."""
    if draft_id:
        draft_dir = ws / 'drafts' / str(draft_id)
        for rel, label in (
            (draft_dir / 'variants' / f'{platform}.md', f'drafts/{draft_id}/variants/{platform}.md'),
            (draft_dir / 'master.md', f'drafts/{draft_id}/master.md'),
        ):
            if rel.is_file():
                hook = extract_hook_from_text(rel.read_text(encoding='utf-8'))
                if hook:
                    return hook, label
    title = str(fallback_title or '').strip()
    return title, ('title_fallback' if title else 'none')


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


def load_breakout_rules(ws: Path) -> dict:
    """Load optional per-workspace breakout rules from engagement/breakout-rules.json."""
    cfg = read_json(ws / 'engagement' / 'breakout-rules.json', {})
    return cfg if isinstance(cfg, dict) else {}


def _load_executed_action_keys(ws: Path) -> set[tuple[str, str, str]]:
    """Return set of (platform, targetId, actionType) that already succeeded in engagement/action-log.jsonl."""
    done: set[tuple[str, str, str]] = set()
    for row in iter_jsonl(ws / 'engagement' / 'action-log.jsonl'):
        if row.get('result', 'ok') != 'ok':
            continue
        plat = str(row.get('platform') or '').strip()
        tid = str(row.get('targetId') or '').strip()
        act = str(row.get('actionType') or '').strip()
        if plat and tid and act:
            done.add((plat, tid, act))
    return done


def _load_queued_action_keys(ws: Path) -> set[tuple[str, str, str]]:
    """Return set of (platform, targetPostId, actionType) already present (not skipped) in outbound-queue.json."""
    doc = read_json(ws / 'engagement' / 'outbound-queue.json', {'version': 1, 'items': []})
    keys: set[tuple[str, str, str]] = set()
    for item in (doc.get('items') if isinstance(doc, dict) else []) or []:
        if not isinstance(item, dict):
            continue
        if item.get('status') == 'skipped':
            continue
        plat = str(item.get('platform') or '').strip()
        tid = str(item.get('targetPostId') or '').strip()
        act = str(item.get('actionType') or '').strip()
        if plat and tid and act:
            keys.add((plat, tid, act))
    return keys


def detect_breakouts(
    ws: Path,
    works: list[dict],
    publish_index: dict[tuple[str, str], dict],
    now: datetime,
    *,
    platform_filter: str | None = None,
    baseline_multiplier: float | None = None,
    min_views: int | None = None,
    min_likes: int | None = None,
    min_interactions: int | None = None,
    max_age_hours: float | None = None,
) -> list[dict]:
    """Identify recently published works outperforming baseline or configured thresholds for human-approved amplification."""
    rules_cfg = load_breakout_rules(ws)
    defaults = rules_cfg.get('defaults') if isinstance(rules_cfg.get('defaults'), dict) else {}
    per_plat = rules_cfg.get('platforms') if isinstance(rules_cfg.get('platforms'), dict) else {}

    executed_keys = _load_executed_action_keys(ws)
    queued_keys = _load_queued_action_keys(ws)

    # Compute per-platform baselines across all evaluated works before filtering.
    views_by_plat: dict[str, list[int]] = defaultdict(list)
    inter_by_plat: dict[str, list[int]] = defaultdict(list)
    for w in works:
        plat = str(w.get('platform') or 'unknown')
        views_by_plat[plat].append(int(w.get('views') or 0))
        inter_by_plat[plat].append(int(w.get('interactions') or 0))

    candidates: list[dict] = []
    for w in works:
        plat = str(w.get('platform') or 'unknown')
        if platform_filter and plat != platform_filter:
            continue
        wid = str(w.get('workId') or '')
        if not wid:
            continue

        pcfg = per_plat.get(plat) if isinstance(per_plat.get(plat), dict) else {}
        mult = baseline_multiplier if baseline_multiplier is not None else float(pcfg.get('baselineMultiplier', defaults.get('baselineMultiplier', 2.0)))
        req_views = min_views if min_views is not None else pcfg.get('minViews', defaults.get('minViews'))
        req_likes = min_likes if min_likes is not None else pcfg.get('minLikes', defaults.get('minLikes'))
        req_inter = min_interactions if min_interactions is not None else pcfg.get('minInteractions', defaults.get('minInteractions'))
        age_cap = max_age_hours if max_age_hours is not None else float(pcfg.get('maxAgeHours', defaults.get('maxAgeHours', 168.0)))

        pub = publish_index.get((plat, wid), {})
        pub_dt = parse_iso_utc(pub.get('publishedAt'))
        age_hours: float | None = None
        if pub_dt is not None:
            age_hours = round((now - pub_dt).total_seconds() / 3600.0, 1)
            if age_cap > 0 and age_hours > age_cap:
                continue

        views = int(w.get('views') or 0)
        likes = int(w.get('likes') or 0)
        inter = int(w.get('interactions') or 0)
        med_views = float(median(views_by_plat[plat])) if views_by_plat[plat] else 0.0
        med_inter = float(median(inter_by_plat[plat])) if inter_by_plat[plat] else 0.0

        reasons: list[str] = []
        has_explicit = any(x is not None for x in (req_views, req_likes, req_inter))
        if has_explicit:
            if req_views is not None and views >= int(req_views):
                reasons.append(f'views {views} >= {int(req_views)}')
            if req_likes is not None and likes >= int(req_likes):
                reasons.append(f'likes {likes} >= {int(req_likes)}')
            if req_inter is not None and inter >= int(req_inter):
                reasons.append(f'interactions {inter} >= {int(req_inter)}')
        else:
            # Neutral relative breakout: >= multiplier x platform median with non-trivial activity floor
            if len(views_by_plat[plat]) >= 2:
                if med_views > 0 and views >= med_views * mult and inter >= 10:
                    reasons.append(f'views {views} >= {mult:.1f}x platform median ({med_views:.0f})')
                if med_inter > 0 and inter >= med_inter * mult and inter >= 10:
                    reasons.append(f'interactions {inter} >= {mult:.1f}x platform median ({med_inter:.0f})')
            elif inter >= 50 or likes >= 30:
                reasons.append(f'early breakout activity (likes={likes}, interactions={inter})')

        if not reasons:
            continue

        suggested_actions: list[str] = []
        for act in BREAKOUT_ACTION_TYPES:
            if (plat, wid, act) not in executed_keys and (plat, wid, act) not in queued_keys:
                suggested_actions.append(act)

        if not suggested_actions:
            continue

        public_url = str(pub.get('publicUrl') or '').strip()
        candidates.append({
            'workId': wid,
            'draftId': pub.get('draftId') or w.get('draftId'),
            'topicId': w.get('topicId'),
            'platform': plat,
            'accountId': pub.get('accountId') or w.get('accountId') or f'{plat}-main',
            'title': w.get('title') or wid,
            'publicUrl': public_url or None,
            'ageHours': age_hours,
            'views': views,
            'likes': likes,
            'interactions': inter,
            'engagementRate': w.get('engagementRate', 0.0),
            'reasons': reasons,
            'suggestedActions': suggested_actions,
            'requiresApproval': True,
        })

    candidates.sort(key=lambda c: (c['interactions'], c['views']), reverse=True)
    return candidates


def stage_breakouts_to_outbound_queue(ws: Path, candidates: list[dict], now: datetime) -> dict:
    """Idempotently append breakout amplification suggestions to engagement/outbound-queue.json (requiresApproval=True)."""
    qpath = ws / 'engagement' / 'outbound-queue.json'
    doc = read_json(qpath, {'version': 1, 'items': []})
    if not isinstance(doc, dict):
        doc = {'version': 1, 'items': []}
    items = doc.get('items')
    if not isinstance(items, list):
        items = []

    existing_ids = {str(it.get('outboundId')) for it in items if isinstance(it, dict) and it.get('outboundId')}
    existing_keys = _load_queued_action_keys(ws)
    executed_keys = _load_executed_action_keys(ws)

    staged: list[dict] = []
    skipped_no_url: list[str] = []
    skipped_existing: list[str] = []

    for cand in candidates:
        plat = str(cand['platform'])
        wid = str(cand['workId'])
        url = cand.get('publicUrl')
        if not _is_http_url(url):
            skipped_no_url.append(f'{plat}:{wid}')
            continue

        # Stage the highest-priority remaining action ('reply' follow-up plug first, else 'repost')
        chosen_action = None
        for act in cand.get('suggestedActions') or []:
            if act not in BREAKOUT_ACTION_TYPES:
                continue
            if (plat, wid, act) in existing_keys or (plat, wid, act) in executed_keys:
                continue
            chosen_action = act
            break

        if not chosen_action:
            skipped_existing.append(f'{plat}:{wid}')
            continue

        digest = hashlib.sha256(f'{plat}:{wid}:{chosen_action}'.encode('utf-8')).hexdigest()[:8]
        oid = f'out-brk-{digest}'
        if oid in existing_ids:
            skipped_existing.append(f'{plat}:{wid}:{chosen_action}')
            continue

        angle = (
            'Breakout follow-up reply: add a useful resource, next step, or CTA while momentum is active.'
            if chosen_action == 'reply'
            else 'Breakout repost boost: resurface this winning post for a second timezone window.'
        )
        reason_text = '; '.join(cand.get('reasons') or [])
        entry = {
            'outboundId': oid,
            'platform': plat,
            'accountId': cand.get('accountId') or f'{plat}-main',
            'kind': 'breakout_amplification',
            'workId': wid,
            'targetHandle': f'@self ({cand.get("title") or wid})',
            'targetPostId': wid,
            'targetUrl': url,
            'targetExcerpt': f'Breakout ({reason_text}) — views={cand["views"]}, likes={cand["likes"]}, interactions={cand["interactions"]}',
            'actionType': chosen_action,
            'angle': angle,
            'draftText': '',
            'status': 'discovered',
            'requiresApproval': True,
            'discoveredAt': iso_utc(now),
        }
        items.append(entry)
        existing_ids.add(oid)
        existing_keys.add((plat, wid, chosen_action))
        staged.append(entry)

    if staged:
        doc['version'] = doc.get('version') or 1
        doc['items'] = items
        qpath.parent.mkdir(parents=True, exist_ok=True)
        tmp = qpath.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        tmp.replace(qpath)

    return {
        'queuePath': str(qpath),
        'stagedCount': len(staged),
        'stagedIds': [s['outboundId'] for s in staged],
        'skippedNoUrl': skipped_no_url,
        'skippedExisting': skipped_existing,
    }


def aggregate(
    ws: Path,
    days: int = 14,
    *,
    now: datetime | None = None,
    platform_filter: str | None = None,
    top_hooks_limit: int = 5,
    baseline_multiplier: float | None = None,
    min_views: int | None = None,
    min_likes: int | None = None,
    min_interactions: int | None = None,
    max_age_hours: float | None = None,
    stage_breakouts: bool = False,
) -> dict:
    now = now or utc_now()
    cutoff = now - timedelta(days=days)
    snap_path = ws / 'analytics' / 'snapshots.jsonl'
    publish_index = load_publish_index(ws)

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
        wid = str(row.get('workId') or '')
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

        pub = publish_index.get((plat, wid), {})
        work_item = {
            'workId': wid,
            'draftId': pub.get('draftId') or row.get('draftId'),
            'topicId': row.get('topicId'),
            'platform': plat,
            'accountId': row.get('accountId') or pub.get('accountId'),
            'title': row.get('title'),
            'window': row.get('window'),
            'views': views,
            'likes': likes,
            'interactions': inter,
            'engagementRate': eng,
            'publicUrl': pub.get('publicUrl'),
        }
        ranked_works.append(work_item)
        if row.get('topicId'):
            by_topic[row['topicId']].append(work_item)

    ranked_works.sort(key=lambda w: (w['views'], w['interactions'], w['engagementRate']), reverse=True)

    # Top historical hooks for next-cycle creative inspiration
    hook_pool = [w for w in ranked_works if not platform_filter or w['platform'] == platform_filter]
    top_hooks: list[dict] = []
    for w in hook_pool[: max(top_hooks_limit, 0)]:
        hook_text, hook_source = resolve_work_hook(ws, w['platform'], w.get('draftId'), w.get('title'))
        if not hook_text:
            continue
        top_hooks.append({
            'workId': w['workId'],
            'draftId': w.get('draftId'),
            'topicId': w.get('topicId'),
            'platform': w['platform'],
            'title': w.get('title'),
            'hook': hook_text,
            'hookSource': hook_source,
            'views': w['views'],
            'interactions': w['interactions'],
            'engagementRate': w['engagementRate'],
            'publicUrl': w.get('publicUrl'),
        })

    breakout_candidates = detect_breakouts(
        ws,
        ranked_works,
        publish_index,
        now,
        platform_filter=platform_filter,
        baseline_multiplier=baseline_multiplier,
        min_views=min_views,
        min_likes=min_likes,
        min_interactions=min_interactions,
        max_age_hours=max_age_hours,
    )

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

    result: dict = {
        'windowDays': days,
        'worksEvaluated': len(latest_by_work),
        'byPlatform': plat_summary,
        'topWorks': ranked_works[:5],
        'bottomWorks': list(reversed(ranked_works[-5:])) if ranked_works else [],
        'topHooks': top_hooks,
        'breakoutCandidates': breakout_candidates,
        'crossPlatformTopics': cross,
        'accountSnapshots': [
            row for _, row in sorted(
                latest_by_account.values(),
                key=lambda x: (str(x[1].get('platform') or ''), str(x[1].get('accountId') or '')),
            )
        ],
        'dueSnapshots': compute_due_snapshots(ws, existing_windows, now),
    }

    if stage_breakouts:
        result['stagedBreakouts'] = stage_breakouts_to_outbound_queue(ws, breakout_candidates, now)

    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Aggregate analytics/snapshots.jsonl, recall top hooks, and detect breakout works.')
    parser.add_argument('workspace', help='Path to the content-ops directory.')
    parser.add_argument('--days', type=int, default=14, help='Lookback window in days (default: 14).')
    parser.add_argument('--platform', default=None, help='Optional platform slug filter for topHooks and breakoutCandidates.')
    parser.add_argument('--top-hooks-limit', type=int, default=5, help='Maximum historical top hooks to return (default: 5).')
    parser.add_argument('--baseline-multiplier', type=float, default=None, help='Relative breakout multiplier vs platform median (default: 2.0).')
    parser.add_argument('--min-views', type=int, default=None, help='Optional explicit views threshold for breakout detection.')
    parser.add_argument('--min-likes', type=int, default=None, help='Optional explicit likes threshold for breakout detection.')
    parser.add_argument('--min-interactions', type=int, default=None, help='Optional explicit interactions threshold for breakout detection.')
    parser.add_argument('--max-age-hours', type=float, default=None, help='Maximum hours since publish for breakout triggers (default: 168).')
    parser.add_argument('--stage-breakouts', action='store_true', help='Idempotently append breakout suggestions to engagement/outbound-queue.json (requiresApproval=true).')
    args = parser.parse_args(argv)

    result = aggregate(
        Path(args.workspace).expanduser().resolve(),
        days=args.days,
        platform_filter=args.platform,
        top_hooks_limit=args.top_hooks_limit,
        baseline_multiplier=args.baseline_multiplier,
        min_views=args.min_views,
        min_likes=args.min_likes,
        min_interactions=args.min_interactions,
        max_age_hours=args.max_age_hours,
        stage_breakouts=args.stage_breakouts,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
