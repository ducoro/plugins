#!/usr/bin/env python3
"""Build and sync board data payloads for all 5 interactive content-ops boards."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

SKILL_DIR = Path(__file__).resolve().parents[1]
BOARDS_SRC = SKILL_DIR / 'assets' / 'boards'
BOARD_NAMES = [
    'calendar-board',
    'pipeline-board',
    'publish-ledger-board',
    'engagement-inbox-board',
    'analytics-retro-board',
]
DEFAULT_DAILY_CAPS = {
    'xiaohongshu': 40,
    'douyin': 40,
    'bilibili': 50,
    'wechat-official': 30,
    'wechat-channels': 40,
    'kuaishou': 40,
    'x-twitter': 80,
    'youtube': 60,
    'tiktok': 50,
    'instagram': 50,
    'facebook': 60,
    'threads': 60,
    'linkedin': 40,
    'pinterest': 50,
}
DEFAULT_FESTIVALS = [
    {'id': 'new-year', 'date': '01-01', 'name': 'New Year', 'region': 'global', 'leadDays': 7},
    {'id': 'spring-festival', 'date': '01-29', 'name': 'Spring Festival Window (check lunar date)', 'region': 'cn', 'leadDays': 14},
    {'id': 'valentines', 'date': '02-14', 'name': "Valentine's Day", 'region': 'global', 'leadDays': 7},
    {'id': 'womens-day', 'date': '03-08', 'name': "International Women's Day", 'region': 'global', 'leadDays': 7},
    {'id': 'labor-day', 'date': '05-01', 'name': 'Labor Day Holiday', 'region': 'cn', 'leadDays': 10},
    {'id': 'midyear-618', 'date': '06-18', 'name': '618 Shopping Festival', 'region': 'cn', 'leadDays': 14},
    {'id': 'q4-planning', 'date': '09-01', 'name': 'Back-to-School / Q4 Planning', 'region': 'global', 'leadDays': 10},
    {'id': 'golden-week', 'date': '10-01', 'name': 'National Day Golden Week', 'region': 'cn', 'leadDays': 14},
    {'id': 'double-11', 'date': '11-11', 'name': 'Double 11 / Singles Day', 'region': 'cn', 'leadDays': 14},
    {'id': 'black-friday', 'date': '11-27', 'name': 'Black Friday / Cyber Week', 'region': 'global', 'leadDays': 14},
    {'id': 'year-end', 'date': '12-25', 'name': 'Year-End & Holiday Wrap', 'region': 'global', 'leadDays': 10},
]
INLINE_DATA_RE = re.compile(
    r'(<script\s+id="board-initial-data"\s+type="application/json">)(.*?)(</script>)',
    re.S,
)


def parse_iso_utc(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
        return dt.astimezone(timezone.utc) if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def read_json(path: Path, default):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
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
            rows.append(row)
    return rows


def collect_drafts(ws: Path) -> list[dict]:
    drafts = []
    drafts_root = ws / 'drafts'
    if not drafts_root.is_dir():
        return drafts
    for entry in sorted(drafts_root.iterdir()):
        meta_path = entry / 'meta.json'
        if entry.is_dir() and meta_path.is_file():
            meta = read_json(meta_path, {})
            meta.setdefault('draftId', entry.name)
            drafts.append(meta)
    return drafts


def parse_latest_retro(ws: Path) -> dict:
    retros_dir = ws / 'analytics' / 'retros'
    if not retros_dir.is_dir():
        return {'file': None, 'title': 'No retrospective recorded yet', 'actions': []}
    files = sorted(p for p in retros_dir.glob('*.md') if p.name.lower() != 'readme.md')
    if not files:
        return {'file': None, 'title': 'No retrospective recorded yet', 'actions': []}
    latest = files[-1]
    lines = latest.read_text(encoding='utf-8').splitlines()
    title = latest.stem
    actions = []
    in_actions_section = False
    saw_actions_heading = False
    for line in lines:
        s = line.strip()
        if s.startswith('# ') and title == latest.stem:
            title = s[2:].strip()
        elif s.startswith('## '):
            heading = s[3:].strip().lower()
            in_actions_section = 'next-cycle action' in heading or 'action' in heading
            if in_actions_section:
                saw_actions_heading = True
        elif in_actions_section and s.startswith(('- [ ] ', '- [x] ', '- [X] ', '- ')):
            text = re.sub(r'^- (?:\[[ xX]\] )?', '', s).strip()
            if text:
                stable_id = 'act-' + hashlib.sha256(text.encode('utf-8')).hexdigest()[:8]
                actions.append({
                    'id': stable_id,
                    'text': text,
                    'done': s.startswith(('- [x] ', '- [X] ')),
                })
    # Fallback only if file has no ## Actions heading at all, restricted strictly to checkbox tasks
    if not saw_actions_heading:
        for line in lines:
            s = line.strip()
            if s.startswith(('- [ ] ', '- [x] ', '- [X] ')):
                text = re.sub(r'^- \[[ xX]\] ', '', s).strip()
                if text:
                    stable_id = 'act-' + hashlib.sha256(text.encode('utf-8')).hexdigest()[:8]
                    actions.append({'id': stable_id, 'text': text, 'done': s.startswith(('- [x] ', '- [X] '))})
    return {'file': f'analytics/retros/{latest.name}', 'title': title, 'actions': actions[:20]}


def build_payloads(ws: Path) -> dict[str, dict]:
    now = datetime.now(timezone.utc)
    generated_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    today_prefix = now.strftime('%Y-%m-%d')

    accounts = read_json(ws / 'accounts.json', {'accounts': []}).get('accounts', [])
    topics = read_json(ws / 'topics' / 'topics.json', {'topics': []}).get('topics', [])
    plans = read_json(ws / 'drafts' / 'plans.json', {'plans': []}).get('plans', [])
    drafts = collect_drafts(ws)
    cal_doc = read_json(ws / 'calendar.json', {'timezone': 'UTC', 'slots': []})
    tz_name = cal_doc.get('timezone', 'UTC')
    slots = cal_doc.get('slots', [])
    publish_log = read_jsonl(ws / 'publish-log.jsonl')
    comments = read_json(ws / 'engagement' / 'inbox.json', {'comments': []}).get('comments', [])
    benchmark_accounts = read_json(ws / 'engagement' / 'benchmark-accounts.json', {'accounts': []}).get('accounts', [])
    outbound_queue = read_json(ws / 'engagement' / 'outbound-queue.json', {'items': []}).get('items', [])
    action_log = read_jsonl(ws / 'engagement' / 'action-log.jsonl')
    snapshots = read_jsonl(ws / 'analytics' / 'snapshots.jsonl')

    platforms = sorted({
        *(a.get('platform') for a in accounts if a.get('platform')),
        *(s.get('platform') for s in slots if s.get('platform')),
        *(p.get('platform') for p in publish_log if p.get('platform')),
        *(c.get('platform') for c in comments if c.get('platform')),
        *(b.get('platform') for b in benchmark_accounts if b.get('platform')),
        *(o.get('platform') for o in outbound_queue if o.get('platform')),
        *(sn.get('platform') for sn in snapshots if sn.get('platform')),
        *(pl for t in topics for pl in t.get('targetPlatforms', []) if pl),
    })

    latest_pub_by_slot = {}
    for row in publish_log:
        sid = row.get('slotId')
        if sid:
            latest_pub_by_slot[sid] = row

    enriched_slots = []
    for slot in slots:
        pub = latest_pub_by_slot.get(slot.get('slotId'), {})
        enriched_slots.append({
            **slot,
            'publicUrl': pub.get('publicUrl'),
            'workId': pub.get('workId'),
            'lastError': pub.get('error'),
        })

    year = now.year
    festivals = [{**f, 'date': f'{year}-{f["date"]}'} for f in DEFAULT_FESTIVALS]

    calendar_payload = {
        'schemaVersion': 1,
        'board': 'calendar-board',
        'generatedAt': generated_at,
        'timezone': tz_name,
        'platforms': platforms,
        'summary': {
            'totalSlots': len(enriched_slots),
            'awaitingApproval': sum(1 for s in enriched_slots if s.get('status') == 'awaiting_approval'),
            'approved': sum(1 for s in enriched_slots if s.get('status') == 'approved'),
            'published': sum(1 for s in enriched_slots if s.get('status') == 'published'),
            'failed': sum(1 for s in enriched_slots if s.get('status') == 'failed'),
        },
        'slots': enriched_slots,
        'festivals': festivals,
    }

    inbox_files = sorted((ws / 'inbox').glob('*.md')) if (ws / 'inbox').is_dir() else []
    columns = {'intake': [], 'approved': [], 'ready': [], 'archive': []}
    spec_alert_count = 0
    for topic in topics:
        item = {
            'itemType': 'topic',
            'id': topic.get('topicId'),
            'title': topic.get('title', 'Untitled topic'),
            'status': topic.get('status', 'candidate'),
            'score': topic.get('weightedScore'),
            'sourceType': topic.get('sourceType'),
            'platforms': topic.get('targetPlatforms', []),
            'planId': topic.get('planId', ''),
            'specAlerts': [],
        }
        st = item['status']
        if st in ('candidate', 'shortlisted'):
            columns['intake'].append(item)
        elif st == 'approved':
            columns['approved'].append(item)
        else:
            columns['archive'].append(item)

    for draft in drafts:
        variants = draft.get('variants', {})
        alerts = []
        for plat, v in variants.items():
            if isinstance(v, dict) and v.get('specStatus') not in ('pass', None):
                alerts.append({'platform': plat, 'issues': v.get('issues', [])})
        spec_alert_count += len(alerts)
        item = {
            'itemType': 'draft',
            'id': draft.get('draftId'),
            'topicId': draft.get('topicId'),
            'title': draft.get('title', 'Untitled draft'),
            'status': draft.get('status', 'drafting'),
            'planId': draft.get('planId', ''),
            'platforms': sorted(variants.keys()),
            'variants': variants,
            'specAlerts': alerts,
        }
        st = item['status']
        if st in ('drafting', 'in_review', 'needs_update'):
            columns['approved'].append(item)
        elif st in ('ready', 'scheduled'):
            columns['ready'].append(item)
        else:
            columns['archive'].append(item)

    pipeline_payload = {
        'schemaVersion': 1,
        'board': 'pipeline-board',
        'generatedAt': generated_at,
        'timezone': tz_name,
        'platforms': platforms,
        'summary': {
            'inboxCount': len(inbox_files),
            'candidateTopics': len(columns['intake']),
            'approvedItems': len(columns['approved']),
            'draftsReady': len(columns['ready']),
            'specAlertCount': spec_alert_count,
        },
        'plans': plans,
        'columns': columns,
    }

    safe_accounts = [
        {k: v for k, v in a.items() if k not in ('token', 'accessToken', 'secret')}
        for a in accounts
    ]
    publish_ledger_payload = {
        'schemaVersion': 1,
        'board': 'publish-ledger-board',
        'generatedAt': generated_at,
        'timezone': tz_name,
        'platforms': platforms,
        'summary': {
            'totalAccounts': len(safe_accounts),
            'healthyAccounts': sum(1 for a in safe_accounts if a.get('status') in ('active', 'manual_browser')),
            'attentionAccounts': sum(1 for a in safe_accounts if a.get('status') in ('expiring', 'expired')),
            'totalPublished': sum(1 for r in publish_log if r.get('status') == 'published'),
            'totalFailed': sum(1 for r in publish_log if r.get('status') == 'failed'),
        },
        'accounts': safe_accounts,
        'records': list(reversed(publish_log)),
    }

    used_today = defaultdict(int)
    for act in action_log:
        dt = parse_iso_utc(act.get('executedAt'))
        if dt and dt.strftime('%Y-%m-%d') == today_prefix and act.get('platform'):
            used_today[act['platform']] += 1
    rate_limits = [
        {'platform': plat, 'usedToday': used_today.get(plat, 0), 'dailyCap': DEFAULT_DAILY_CAPS.get(plat, 50)}
        for plat in platforms
    ]
    engagement_payload = {
        'schemaVersion': 1,
        'board': 'engagement-inbox-board',
        'generatedAt': generated_at,
        'timezone': tz_name,
        'platforms': platforms,
        'summary': {
            'openTotal': sum(1 for c in comments if c.get('status') in ('open', 'drafted', 'escalated')),
            'highIntent': sum(1 for c in comments if c.get('tier') == 'high_intent'),
            'feedback': sum(1 for c in comments if c.get('tier') == 'feedback'),
            'general': sum(1 for c in comments if c.get('tier') == 'general'),
            'spam': sum(1 for c in comments if c.get('tier') == 'spam'),
            'awaitingApproval': sum(1 for c in comments if c.get('requiresApproval') and c.get('status') in ('open', 'drafted')),
            'activeBenchmarks': sum(1 for b in benchmark_accounts if b.get('status') == 'active'),
            'proposedBenchmarks': sum(1 for b in benchmark_accounts if b.get('status') == 'proposed'),
            'outboundOpen': sum(1 for o in outbound_queue if o.get('status') in ('discovered', 'drafted', 'approved')),
            'outboundAwaitingApproval': sum(1 for o in outbound_queue if o.get('requiresApproval', True) and o.get('status') in ('discovered', 'drafted')),
        },
        'rateLimits': rate_limits,
        'comments': comments,
        'benchmarkAccounts': benchmark_accounts,
        'outboundQueue': outbound_queue,
    }

    dt_min = datetime.min.replace(tzinfo=timezone.utc)
    latest_by_work: dict[tuple[str, str], dict] = {}
    latest_by_work_day: dict[tuple[str, str, str], dict] = {}
    latest_by_account: dict[str, dict] = {}
    for snap in snapshots:
        snap_dt = parse_iso_utc(snap.get('capturedAt'))
        cmp_dt = snap_dt or dt_min
        plat_key = str(snap.get('platform') or 'unknown')
        if snap.get('window') == 'account':
            aid = snap.get('accountId') or plat_key
            if aid:
                prev = latest_by_account.get(aid)
                prev_dt = (parse_iso_utc(prev.get('capturedAt')) or dt_min) if prev else dt_min
                if not prev or cmp_dt >= prev_dt:
                    latest_by_account[aid] = snap
            continue
        wid = snap.get('workId')
        if wid:
            wkey = (plat_key, str(wid))
            prev = latest_by_work.get(wkey)
            prev_dt = (parse_iso_utc(prev.get('capturedAt')) or dt_min) if prev else dt_min
            if not prev or cmp_dt >= prev_dt:
                latest_by_work[wkey] = snap
            if snap_dt is not None:
                day = snap_dt.strftime('%Y-%m-%d')
                dkey = (plat_key, str(wid), day)
                prev_day = latest_by_work_day.get(dkey)
                prev_day_dt = (parse_iso_utc(prev_day.get('capturedAt')) or dt_min) if prev_day else dt_min
                if not prev_day or snap_dt >= prev_day_dt:
                    latest_by_work_day[dkey] = snap

    trend_by_plat_day: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {'views': 0, 'interactions': 0}))
    for (plat, _, day), snap in latest_by_work_day.items():
        m = snap.get('metrics', {}) or {}
        v = int(m.get('views', 0) or 0)
        inter = sum(int(m.get(k, 0) or 0) for k in ('likes', 'comments', 'shares', 'saves'))
        for bucket in ('all', plat):
            trend_by_plat_day[bucket][day]['views'] += v
            trend_by_plat_day[bucket][day]['interactions'] += inter

    trend_by_platform = {}
    for bucket, days_map in trend_by_plat_day.items():
        series = []
        for day in sorted(days_map.keys()):
            d = days_map[day]
            rate = round((d['interactions'] / d['views']) * 100, 2) if d['views'] > 0 else 0.0
            series.append({'date': day, 'views': d['views'], 'interactions': d['interactions'], 'engagementRate': rate})
        trend_by_platform[bucket] = series

    works = []
    cross_groups = defaultdict(list)
    total_views = total_likes = total_comments = total_shares = total_saves = 0
    for snap in latest_by_work.values():
        m = snap.get('metrics', {})
        views = int(m.get('views', 0) or 0)
        likes = int(m.get('likes', 0) or 0)
        cmts = int(m.get('comments', 0) or 0)
        shares = int(m.get('shares', 0) or 0)
        saves = int(m.get('saves', 0) or 0)
        interactions = likes + cmts + shares + saves
        eng_rate = round((interactions / views) * 100, 2) if views > 0 else 0.0
        total_views += views
        total_likes += likes
        total_comments += cmts
        total_shares += shares
        total_saves += saves
        work_entry = {
            'workId': snap.get('workId'),
            'topicId': snap.get('topicId'),
            'platform': snap.get('platform'),
            'accountId': snap.get('accountId'),
            'title': snap.get('title', snap.get('workId')),
            'window': snap.get('window'),
            'capturedAt': snap.get('capturedAt'),
            'views': views,
            'likes': likes,
            'comments': cmts,
            'shares': shares,
            'saves': saves,
            'engagementRate': eng_rate,
            'platformMetrics': snap.get('platformMetrics', {}),
        }
        works.append(work_entry)
        if work_entry['topicId']:
            cross_groups[work_entry['topicId']].append(work_entry)

    works.sort(key=lambda w: w['views'], reverse=True)
    cross_platform = [
        {'topicId': tid, 'entries': entries}
        for tid, entries in sorted(cross_groups.items())
        if len({e['platform'] for e in entries}) >= 2
    ]
    total_inter = total_likes + total_comments + total_shares + total_saves
    analytics_payload = {
        'schemaVersion': 1,
        'board': 'analytics-retro-board',
        'generatedAt': generated_at,
        'timezone': tz_name,
        'platforms': platforms,
        'summary': {
            'totalWorks': len(works),
            'totalViews': total_views,
            'totalLikes': total_likes,
            'totalComments': total_comments,
            'totalShares': total_shares,
            'totalSaves': total_saves,
            'avgEngagementRate': round((total_inter / total_views) * 100, 2) if total_views > 0 else 0.0,
        },
        'trend': trend_by_platform.get('all', []),
        'trendByPlatform': trend_by_platform,
        'crossPlatform': cross_platform,
        'works': works,
        'accountSnapshots': list(latest_by_account.values()),
        'retro': parse_latest_retro(ws),
    }

    return {
        'calendar-board': calendar_payload,
        'pipeline-board': pipeline_payload,
        'publish-ledger-board': publish_ledger_payload,
        'engagement-inbox-board': engagement_payload,
        'analytics-retro-board': analytics_payload,
    }


def is_blank_seed_html(path: Path) -> bool:
    if not path.is_file():
        return True
    text = path.read_text(encoding='utf-8', errors='ignore')
    return 'data-sample' in text and 'board-initial-data' not in text


def sync_board_dir(
    board_name: str,
    board_dir: Path,
    payload: dict,
    overwrite_templates: bool = False,
    embed_inline: bool = False,
) -> None:
    src_board = BOARDS_SRC / board_name
    shared_bridge = BOARDS_SRC / 'shared' / 'board-sdk-bridge.js'
    board_dir.mkdir(parents=True, exist_ok=True)
    (board_dir / 'assets').mkdir(parents=True, exist_ok=True)
    (board_dir / 'runtime').mkdir(parents=True, exist_ok=True)

    index_target = board_dir / 'index.html'
    needs_template = overwrite_templates or is_blank_seed_html(index_target)
    shared_dir = BOARDS_SRC / 'shared'
    if needs_template:
        shutil.copyfile(src_board / 'index.html', index_target)
        shutil.copyfile(src_board / 'README.md', board_dir / 'README.md')
        for shared_name in ('board-sdk-bridge.js', 'board-ui.css'):
            src_shared = shared_dir / shared_name
            if src_shared.is_file():
                shutil.copyfile(src_shared, board_dir / 'runtime' / shared_name)
    else:
        if not (board_dir / 'README.md').exists():
            shutil.copyfile(src_board / 'README.md', board_dir / 'README.md')
        for shared_name in ('board-sdk-bridge.js', 'board-ui.css'):
            src_shared = shared_dir / shared_name
            dst_shared = board_dir / 'runtime' / shared_name
            if src_shared.is_file() and not dst_shared.exists():
                shutil.copyfile(src_shared, dst_shared)

    data_json = json.dumps(payload, indent=2, ensure_ascii=False)
    (board_dir / 'assets' / 'data.json').write_text(data_json + '\n', encoding='utf-8')

    # Only rewrite inline JSON inside index.html when assembling fresh templates or explicitly
    # requested (--embed-inline), so live updates touch only assets/data.json and allow in-place
    # ducoro.board.revalidate without forcing a full document reload.
    if (embed_inline or needs_template) and index_target.is_file():
        html = index_target.read_text(encoding='utf-8')
        safe_inline = data_json.replace('</', '<\\/')
        updated, count = INLINE_DATA_RE.subn(lambda m: f'{m.group(1)}\n{safe_inline}\n{m.group(3)}', html, count=1)
        if count == 1:
            index_target.write_text(updated, encoding='utf-8')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Build data payloads for content-ops interactive boards.')
    parser.add_argument('workspace', help='Path to the content-ops directory.')
    parser.add_argument('--board', choices=BOARD_NAMES, help='Update only one specific board.')
    parser.add_argument(
        '--board-dir',
        help='Optional target directory for --board (e.g. a Space boards/<id>/ folder created via ducoro-cli board new).',
    )
    parser.add_argument(
        '--overwrite-templates',
        action='store_true',
        help='Overwrite index.html, README.md, runtime/board-sdk-bridge.js, and runtime/board-ui.css from plugin templates.',
    )
    parser.add_argument(
        '--embed-inline',
        action='store_true',
        help='Also refresh inline JSON inside index.html (for standalone offline HTML sharing; triggers reload in live sessions).',
    )
    args = parser.parse_args(argv)

    ws = Path(args.workspace).expanduser().resolve()
    payloads = build_payloads(ws)

    if args.board:
        dest = Path(args.board_dir).expanduser().resolve() if args.board_dir else (ws / 'boards' / args.board)
        sync_board_dir(
            args.board,
            dest,
            payloads[args.board],
            overwrite_templates=args.overwrite_templates,
            embed_inline=args.embed_inline,
        )
        print(f'Synced {args.board} -> {dest}')
        return 0

    for name in BOARD_NAMES:
        dest = ws / 'boards' / name
        sync_board_dir(
            name,
            dest,
            payloads[name],
            overwrite_templates=args.overwrite_templates,
            embed_inline=args.embed_inline,
        )
    print(f'Synced all 5 boards under {ws / "boards"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
