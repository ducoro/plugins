#!/usr/bin/env python3
"""Project exact Decimal finance-report.json one-way into shadcn/ui boards."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile

SCRIPT_DIR = Path(__file__).resolve().parent
BOARDS_SRC = SCRIPT_DIR.parent / 'assets/boards'
BOARDS = ('finance-overview-board', 'anomaly-audit-board')


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def read_json(path: Path, default: object) -> object:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return default


def build_overview_payload(data_dir: Path) -> dict:
    report = read_json(data_dir / 'finance-report.json', {})
    accounts = read_json(data_dir / 'accounts.json', {'baseCurrency': 'USD'})
    base_ccy = report.get('baseCurrency') or accounts.get('baseCurrency', 'USD')
    report_thresholds = report.get('thresholds') if isinstance(report.get('thresholds'), dict) else {}
    acct_thresholds = accounts.get('thresholds') if isinstance(accounts.get('thresholds'), dict) else {}
    thresholds = {
        'minRunwayMonths': str(
            report_thresholds.get('minRunwayMonths')
            or acct_thresholds.get('minRunwayMonths')
            or '6'
        ),
        **acct_thresholds,
        **report_thresholds,
    }
    return {
        'generatedAt': report.get('generatedAt') or utc_now(),
        'month': report.get('month', utc_now()[:7]),
        'baseCurrency': base_ccy,
        'thresholds': thresholds,
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


def build_anomaly_payload(data_dir: Path) -> dict:
    report = read_json(data_dir / 'finance-report.json', {})
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
    payload = build_overview_payload(data_dir) if board_name == 'finance-overview-board' else build_anomaly_payload(data_dir)
    out = assets_dir / 'data.json'
    _atomic_write_text(out, json.dumps(payload, indent=2, ensure_ascii=False) + '\n')
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Project business-finance-ops report data one-way into Ducoro Space boards (or local preview).'
    )
    parser.add_argument('data_dir', metavar='data-dir', help='Active finance data directory')
    parser.add_argument('--board', choices=BOARDS, default=None, help='Board template to project into --board-dir')
    parser.add_argument('--board-dir', default=None, help='Target Space board directory (<space-work-root>/boards/<id>)')
    parser.add_argument('--all', action='store_true', help='Local preview only: project all boards under --boards-root')
    parser.add_argument('--boards-root', default=None, help='Output root for local preview (--all); defaults to <data-dir>/boards')
    parser.add_argument('--overwrite-templates', action='store_true')
    args = parser.parse_args()

    data_dir = Path(args.data_dir).expanduser().resolve()
    outputs = []
    if args.all:
        preview_root = Path(args.boards_root).expanduser().resolve() if args.boards_root else (data_dir / 'boards')
        for b in BOARDS:
            outputs.append(str(project_board(data_dir, b, preview_root / b, overwrite_templates=args.overwrite_templates)))
    elif args.board:
        if args.board_dir:
            target = Path(args.board_dir)
        else:
            preview_root = Path(args.boards_root).expanduser().resolve() if args.boards_root else (data_dir / 'boards')
            target = preview_root / args.board
        outputs.append(str(project_board(data_dir, args.board, target, overwrite_templates=args.overwrite_templates)))
    else:
        parser.error('Specify --board with --board-dir (Ducoro Space) or --all (local preview only)')
    print(json.dumps({'projected': outputs}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
