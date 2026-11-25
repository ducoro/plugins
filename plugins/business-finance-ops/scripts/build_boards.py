#!/usr/bin/env python3
"""Project exact Decimal finance-report.json one-way into shadcn/ui boards."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

SCRIPT_DIR = Path(__file__).resolve().parent
BOARDS_SRC = SCRIPT_DIR.parent / 'assets/boards'
BOARDS = ('finance-overview-board', 'anomaly-audit-board')


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def read_json(path: Path, default: object) -> object:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return default


def build_overview_payload(workspace: Path) -> dict:
    report = read_json(workspace / 'finance-report.json', {})
    accounts = read_json(workspace / 'accounts.json', {'baseCurrency': 'USD'})
    base_ccy = report.get('baseCurrency') or accounts.get('baseCurrency', 'USD')
    return {
        'generatedAt': report.get('generatedAt') or utc_now(),
        'month': report.get('month', utc_now()[:7]),
        'baseCurrency': base_ccy,
        'summary': report.get('summary') or {
            'inflowTotal': '0.00',
            'recurringInflow': '0.00',
            'oneTimeInflow': '0.00',
            'outflowTotal': '0.00',
            'grossMarginPct': None,
            'netCashFlow': '0.00',
            'totalCashBalance': '0.00',
            'monthlyNetBurn': '0.00',
            'runwayMonths': None,
            'transactionCount': 0,
            'anomalyCount': 0,
            'highAnomalyCount': 0,
        },
        'scenarios': report.get('scenarios') or {},
        'fluxAnalysis': report.get('fluxAnalysis') or [],
        'budgets': report.get('budgets') or [],
        'transactions': report.get('transactions') or [],
    }


def build_anomaly_payload(workspace: Path) -> dict:
    report = read_json(workspace / 'finance-report.json', {})
    anomalies = report.get('anomalies') or []
    return {
        'generatedAt': report.get('generatedAt') or utc_now(),
        'month': report.get('month', utc_now()[:7]),
        'baseCurrency': report.get('baseCurrency', 'USD'),
        'summary': {
            'totalAlerts': len(anomalies),
            'highCount': sum(1 for a in anomalies if a.get('severity') == 'high'),
            'duplicateCount': sum(1 for a in anomalies if a.get('type') == 'duplicate_charge'),
            'hikeCount': sum(1 for a in anomalies if a.get('type') == 'vendor_price_hike'),
        },
        'anomalies': anomalies,
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
    payload = build_overview_payload(workspace) if board_name == 'finance-overview-board' else build_anomaly_payload(workspace)
    out = assets_dir / 'data.json'
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description='Project business-finance-ops data into shadcn/ui boards.')
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
