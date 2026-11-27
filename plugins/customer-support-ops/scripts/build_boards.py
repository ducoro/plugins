#!/usr/bin/env python3
"""Project customer-support-ops data one-way into shadcn/ui boards."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil

SCRIPT_DIR = Path(__file__).resolve().parent
BOARDS_SRC = SCRIPT_DIR.parent / 'assets/boards'
BOARDS = ('triage-sla-board', 'root-cause-board')


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def parse_ts(raw: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def read_json(path: Path, default: object) -> object:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return default


def load_latest_sent_by_ticket(data_dir: Path) -> dict[str, datetime]:
    log_path = data_dir / 'reply-log.jsonl'
    if not log_path.is_file():
        return {}
    latest: dict[str, datetime] = {}
    for line in log_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        tid = row.get('ticketId')
        sent_dt = parse_ts(row.get('sentAt'))
        if tid and sent_dt and (tid not in latest or sent_dt > latest[tid]):
            latest[tid] = sent_dt
    return latest


def derive_ticket_status(ticket: dict, latest_sent: datetime | None) -> str:
    base_status = str(ticket.get('effectiveStatus') or ticket.get('status') or 'open')
    if base_status in {'resolved', 'closed'}:
        return base_status
    if latest_sent is not None:
        inbound_dt = parse_ts(ticket.get('lastInboundAt') or ticket.get('createdAt'))
        if inbound_dt is None or latest_sent >= inbound_dt:
            return 'replied'
    return base_status


def build_triage_payload(data_dir: Path) -> dict:
    tickets_doc = read_json(data_dir / 'tickets/tickets.json', {'tickets': {}})
    queue_doc = read_json(data_dir / 'outbound-queue.json', {'drafts': {}})
    report = read_json(data_dir / 'sla-report.json', {})
    latest_sent_map = load_latest_sent_by_ticket(data_dir)
    tickets = list((tickets_doc.get('tickets') or {}).values())
    rank = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}
    tickets.sort(key=lambda t: (rank.get(t.get('priority', 'P3'), 3), -(t.get('ageHours') or 0)))

    # When a ticket has multiple drafts, keep the most recently staged one (stagedAt descending).
    drafts_by_ticket: dict[str, dict] = {}
    all_drafts = [d for d in (queue_doc.get('drafts') or {}).values() if isinstance(d, dict) and d.get('ticketId')]
    all_drafts.sort(key=lambda d: (str(d.get('stagedAt') or ''), str(d.get('draftId') or '')), reverse=True)
    for d in all_drafts:
        tid = d['ticketId']
        if tid not in drafts_by_ticket:
            drafts_by_ticket[tid] = d

    derived_rows = []
    open_tickets = []
    for t in tickets:
        tid = t.get('ticketId')
        eff_status = derive_ticket_status(t, latest_sent_map.get(tid))
        if eff_status in {'open', 'pending_human'}:
            open_tickets.append(t)
        derived_rows.append((t, eff_status))

    return {
        'generatedAt': utc_now(),
        'summary': {
            'openCount': len(open_tickets),
            'escalationCount': sum(1 for t in open_tickets if t.get('requiresHumanApproval')),
            'slaBreachCount': sum(1 for t in open_tickets if t.get('slaBreached')),
            'pendingDraftCount': sum(
                1
                for d in all_drafts
                if d.get('status') in {'awaiting_approval', 'approved', 'ready_to_send'}
            ),
            'spikeCount': report.get('spikeCount', 0),
        },
        'tickets': [
            {
                'ticketId': t.get('ticketId'),
                'channel': t.get('channel'),
                'customer': t.get('customer'),
                'subject': t.get('subject'),
                'url': t.get('url', ''),
                'priority': t.get('priority', 'P3'),
                'status': eff_status,
                'ageHours': t.get('ageHours', 0),
                'slaBreached': bool(t.get('slaBreached')) if eff_status in {'open', 'pending_human'} else False,
                'requiresHumanApproval': bool(t.get('requiresHumanApproval')),
                'escalationReasons': t.get('escalationReasons', []),
                'rootCauseId': t.get('rootCauseId') or '',
                'draftStatus': drafts_by_ticket.get(t.get('ticketId'), {}).get('status', ''),
            }
            for t, eff_status in derived_rows[:200]
        ],
    }


def _compute_real_cluster_window(linked: list[dict], ref_now: datetime) -> dict:
    recent_cutoff = ref_now - timedelta(days=7)
    prior_cutoff = ref_now - timedelta(days=14)
    recent_items = []
    prior_n = 0
    for t in linked:
        ts = parse_ts(t.get('createdAt'))
        if ts is None:
            continue
        if ts >= recent_cutoff:
            recent_items.append(t)
        elif ts >= prior_cutoff:
            prior_n += 1
    recent_n = len(recent_items)
    if recent_n == 0:
        ratio = 0.0
    elif prior_n == 0:
        ratio = float(recent_n)
    else:
        ratio = round(recent_n / prior_n, 2)
    recent_unique = len({str(t.get('customer') or t.get('ticketId')).strip().lower() for t in recent_items})
    total_unique = len({str(t.get('customer') or t.get('ticketId')).strip().lower() for t in linked})
    return {
        'recent7dCount': recent_n,
        'prior7dCount': prior_n,
        'spikeRatio': ratio,
        'uniqueCustomers': recent_unique if recent_n > 0 else total_unique,
    }


def build_root_cause_payload(data_dir: Path) -> dict:
    clusters_doc = read_json(data_dir / 'issues/root-causes.json', {'clusters': {}})
    tickets_doc = read_json(data_dir / 'tickets/tickets.json', {'tickets': {}})
    report = read_json(data_dir / 'sla-report.json', {})
    spikes_map = {s['rootCauseId']: s for s in report.get('spikes', []) if isinstance(s, dict)}
    cluster_metrics_map = report.get('clusterMetrics') if isinstance(report.get('clusterMetrics'), dict) else {}
    kb_ids = {k['rootCauseId'] for k in report.get('kbDeflectionCandidates', []) if isinstance(k, dict)}
    tickets = list((tickets_doc.get('tickets') or {}).values())
    ref_now = parse_ts(report.get('generatedAt')) or datetime.now(timezone.utc).replace(microsecond=0)

    counts: dict[str, list[dict]] = {}
    for t in tickets:
        rc = t.get('rootCauseId')
        if rc:
            counts.setdefault(rc, []).append(t)

    all_ids = sorted(set(counts.keys()) | set((clusters_doc.get('clusters') or {}).keys()) | set(cluster_metrics_map.keys()))
    issues = []
    for rc in all_ids:
        meta = (clusters_doc.get('clusters') or {}).get(rc, {})
        linked = counts.get(rc, [])
        spike = spikes_map.get(rc)
        metric = cluster_metrics_map.get(rc)
        if isinstance(metric, dict):
            recent_7d = int(metric.get('recent7dCount', 0))
            prior_7d = int(metric.get('prior7dCount', 0))
            spike_ratio = float(metric.get('spikeRatio', 0.0))
            unique_customers = int(metric.get('uniqueCustomers', 0))
            is_spiking = bool(metric.get('isSpiking', bool(spike)))
        elif spike:
            recent_7d = int(spike['recent7dCount'])
            prior_7d = int(spike['prior7dCount'])
            spike_ratio = float(spike['spikeRatio'])
            unique_customers = int(spike['uniqueCustomers'])
            is_spiking = True
        else:
            computed = _compute_real_cluster_window(linked, ref_now)
            recent_7d = computed['recent7dCount']
            prior_7d = computed['prior7dCount']
            spike_ratio = computed['spikeRatio']
            unique_customers = computed['uniqueCustomers']
            is_spiking = False

        issues.append({
            'rootCauseId': rc,
            'title': meta.get('title', rc),
            'area': meta.get('area', 'general'),
            'totalTickets': len(linked),
            'uniqueCustomers': unique_customers,
            'recent7dCount': recent_7d,
            'prior7dCount': prior_7d,
            'spikeRatio': spike_ratio,
            'isSpiking': is_spiking,
            'kbDeflectionCandidate': rc in kb_ids,
            'sampleQuotes': [
                {'ticketId': t.get('ticketId'), 'subject': t.get('subject', ''), 'url': t.get('url', '')}
                for t in linked[:5]
            ],
        })
    issues.sort(key=lambda x: (not x['isSpiking'], -x['recent7dCount'], x['rootCauseId']))
    return {
        'generatedAt': utc_now(),
        'summary': {
            'clusterCount': len(issues),
            'spikeCount': sum(1 for i in issues if i['isSpiking']),
            'linkedTickets': sum(i['totalTickets'] for i in issues),
        },
        'issues': issues,
    }


def project_board(data_dir: Path, board_name: str, board_dir: Path, *, overwrite_templates: bool = False) -> Path:
    if board_name not in BOARDS:
        raise ValueError(f'Unknown board: {board_name}')
    data_dir = data_dir.expanduser().resolve()
    board_dir = board_dir.expanduser().resolve()
    assets_dir = board_dir / 'assets'
    assets_dir.mkdir(parents=True, exist_ok=True)
    src_dir = BOARDS_SRC / board_name
    if overwrite_templates or not (board_dir / 'index.html').is_file():
        shutil.copy2(src_dir / 'index.html', board_dir / 'index.html')
        shutil.copy2(src_dir / 'README.md', board_dir / 'README.md')
        shutil.copy2(BOARDS_SRC / 'shared/board-ui.css', assets_dir / 'board-ui.css')
        shutil.copy2(BOARDS_SRC / 'shared/board-sdk-bridge.js', assets_dir / 'board-sdk-bridge.js')
    payload = build_triage_payload(data_dir) if board_name == 'triage-sla-board' else build_root_cause_payload(data_dir)
    out = assets_dir / 'data.json'
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description='Project customer-support-ops data to shadcn/ui boards.')
    parser.add_argument('data_dir', help='Path to customer-support-ops data directory')
    parser.add_argument('--board', choices=BOARDS, default=None)
    parser.add_argument('--board-dir', default=None, help='Target Space board directory (e.g. <space-work-root>/boards/<id>)')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--overwrite-templates', action='store_true')
    args = parser.parse_args()

    data_dir = Path(args.data_dir).expanduser().resolve()
    outputs = []
    if args.all:
        base_dir = Path(args.board_dir).expanduser().resolve() if args.board_dir else (data_dir / 'boards')
        for b in BOARDS:
            outputs.append(str(project_board(data_dir, b, base_dir / b, overwrite_templates=args.overwrite_templates)))
    elif args.board:
        target = Path(args.board_dir) if args.board_dir else (data_dir / 'boards' / args.board)
        outputs.append(str(project_board(data_dir, args.board, target, overwrite_templates=args.overwrite_templates)))
    else:
        parser.error('Specify --all or --board')
    print(json.dumps({'projected': outputs}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
