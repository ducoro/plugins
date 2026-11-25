#!/usr/bin/env python3
"""Project customer-support-ops workspace data one-way into shadcn/ui boards."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

SCRIPT_DIR = Path(__file__).resolve().parent
BOARDS_SRC = SCRIPT_DIR.parent / 'assets/boards'
BOARDS = ('triage-sla-board', 'root-cause-board')


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def read_json(path: Path, default: object) -> object:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return default


def build_triage_payload(workspace: Path) -> dict:
    tickets_doc = read_json(workspace / 'tickets/tickets.json', {'tickets': {}})
    queue_doc = read_json(workspace / 'outbound-queue.json', {'drafts': {}})
    report = read_json(workspace / 'sla-report.json', {})
    tickets = list((tickets_doc.get('tickets') or {}).values())
    rank = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}
    tickets.sort(key=lambda t: (rank.get(t.get('priority', 'P3'), 3), -(t.get('ageHours') or 0)))

    drafts_by_ticket = {}
    for d in (queue_doc.get('drafts') or {}).values():
        if isinstance(d, dict) and d.get('ticketId'):
            drafts_by_ticket[d['ticketId']] = d

    open_tickets = [t for t in tickets if t.get('status') in {'open', 'pending_human'}]
    return {
        'generatedAt': utc_now(),
        'summary': {
            'openCount': len(open_tickets),
            'escalationCount': sum(1 for t in open_tickets if t.get('requiresHumanApproval')),
            'slaBreachCount': sum(1 for t in open_tickets if t.get('slaBreached')),
            'pendingDraftCount': sum(1 for d in (queue_doc.get('drafts') or {}).values() if d.get('status') in {'awaiting_approval', 'approved'}),
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
                'status': t.get('status', 'open'),
                'ageHours': t.get('ageHours', 0),
                'slaBreached': bool(t.get('slaBreached')),
                'requiresHumanApproval': bool(t.get('requiresHumanApproval')),
                'escalationReasons': t.get('escalationReasons', []),
                'rootCauseId': t.get('rootCauseId') or '',
                'draftStatus': drafts_by_ticket.get(t.get('ticketId'), {}).get('status', ''),
            }
            for t in tickets[:200]
        ],
    }


def build_root_cause_payload(workspace: Path) -> dict:
    clusters_doc = read_json(workspace / 'issues/root-causes.json', {'clusters': {}})
    tickets_doc = read_json(workspace / 'tickets/tickets.json', {'tickets': {}})
    report = read_json(workspace / 'sla-report.json', {})
    spikes_map = {s['rootCauseId']: s for s in report.get('spikes', []) if isinstance(s, dict)}
    kb_ids = {k['rootCauseId'] for k in report.get('kbDeflectionCandidates', []) if isinstance(k, dict)}
    tickets = list((tickets_doc.get('tickets') or {}).values())

    counts: dict[str, list[dict]] = {}
    for t in tickets:
        rc = t.get('rootCauseId')
        if rc:
            counts.setdefault(rc, []).append(t)

    all_ids = sorted(set(counts.keys()) | set((clusters_doc.get('clusters') or {}).keys()))
    issues = []
    for rc in all_ids:
        meta = (clusters_doc.get('clusters') or {}).get(rc, {})
        linked = counts.get(rc, [])
        unique_customers = len({str(t.get('customer') or t.get('ticketId')).strip().lower() for t in linked})
        spike = spikes_map.get(rc)
        issues.append({
            'rootCauseId': rc,
            'title': meta.get('title', rc),
            'area': meta.get('area', 'general'),
            'totalTickets': len(linked),
            'uniqueCustomers': unique_customers,
            'recent7dCount': spike['recent7dCount'] if spike else len(linked),
            'prior7dCount': spike['prior7dCount'] if spike else 0,
            'spikeRatio': spike['spikeRatio'] if spike else 1.0,
            'isSpiking': bool(spike),
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


def project_board(workspace: Path, board_name: str, board_dir: Path, *, overwrite_templates: bool = False) -> Path:
    if board_name not in BOARDS:
        raise ValueError(f'Unknown board: {board_name}')
    board_dir = board_dir.expanduser().resolve()
    assets_dir = board_dir / 'assets'
    assets_dir.mkdir(parents=True, exist_ok=True)
    src_dir = BOARDS_SRC / board_name
    if overwrite_templates or not (board_dir / 'index.html').is_file():
        shutil.copy2(src_dir / 'index.html', board_dir / 'index.html')
        shutil.copy2(src_dir / 'README.md', board_dir / 'README.md')
        shutil.copy2(BOARDS_SRC / 'shared/board-ui.css', assets_dir / 'board-ui.css')
        shutil.copy2(BOARDS_SRC / 'shared/board-sdk-bridge.js', assets_dir / 'board-sdk-bridge.js')
    payload = build_triage_payload(workspace) if board_name == 'triage-sla-board' else build_root_cause_payload(workspace)
    out = assets_dir / 'data.json'
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description='Project customer-support-ops data to shadcn/ui boards.')
    parser.add_argument('workspace')
    parser.add_argument('--board', choices=BOARDS, default=None)
    parser.add_argument('--board-dir', default=None)
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--overwrite-templates', action='store_true')
    args = parser.parse_args()

    ws = Path(args.workspace).expanduser().resolve()
    outputs = []
    if args.all:
        for b in BOARDS:
            outputs.append(str(project_board(ws, b, ws / 'boards' / b, overwrite_templates=args.overwrite_templates)))
    elif args.board:
        target = Path(args.board_dir) if args.board_dir else (ws / 'boards' / args.board)
        outputs.append(str(project_board(ws, args.board, target, overwrite_templates=args.overwrite_templates)))
    else:
        parser.error('Specify --all or --board')
    print(json.dumps({'projected': outputs}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
