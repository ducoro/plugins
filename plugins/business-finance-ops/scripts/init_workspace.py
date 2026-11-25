#!/usr/bin/env python3
"""Initialize a shared business-finance-ops workspace and seed board data."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

SCRIPT_DIR = Path(__file__).resolve().parent


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def write_json_if_missing(path: Path, payload: object) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return True


def init_workspace(root: Path, *, base_currency: str = 'USD') -> dict:
    root = root.expanduser().resolve()
    base_ccy = base_currency.strip().upper()
    for rel in ('raw-statements', 'invoices', 'reports', 'boards'):
        (root / rel).mkdir(parents=True, exist_ok=True)

    now = utc_now()
    created = []
    if write_json_if_missing(
        root / 'accounts.json',
        {
            'schemaVersion': 'business-finance-accounts/1',
            'updatedAt': now,
            'baseCurrency': base_ccy,
            'cashBalances': {base_ccy: '0.00'},
            'thresholds': {
                'duplicateWindowHours': 72,
                'vendorHikePct': '20',
                'budgetWarnPct': '80',
                'minRunwayMonths': '6',
            },
        },
    ):
        created.append('accounts.json')
    if write_json_if_missing(
        root / 'budgets.json',
        {
            'schemaVersion': 'business-finance-budgets/1',
            'updatedAt': now,
            'baseCurrency': base_ccy,
            'monthlyBudgets': {},
        },
    ):
        created.append('budgets.json')
    if write_json_if_missing(
        root / 'category-rules.json',
        {
            'schemaVersion': 'business-finance-category-rules/1',
            'rules': [
                {'pattern': r'aws|amazon web services|cloudflare|vercel|google cloud|aliyun|tencent cloud', 'category': 'cloud_infra'},
                {'pattern': r'openai|anthropic|github|linear|figma|notion|slack|zoom', 'category': 'software_saas'},
                {'pattern': r'stripe fee|processing fee|bank fee|wire fee', 'category': 'payment_fees'},
                {'pattern': r'google ads|meta ads|x ads|linkedin ads', 'category': 'marketing'},
            ],
        },
    ):
        created.append('category-rules.json')
    if write_json_if_missing(
        root / 'fx-cache.json',
        {'schemaVersion': 'business-finance-fx/1', 'updatedAt': now, 'snapshots': {}},
    ):
        created.append('fx-cache.json')
    ledger_path = root / 'ledger.jsonl'
    if not ledger_path.exists():
        ledger_path.write_text('', encoding='utf-8')
        created.append('ledger.jsonl')

    build_script = SCRIPT_DIR / 'build_boards.py'
    if build_script.is_file():
        subprocess.run(
            [sys.executable, str(build_script), str(root), '--all', '--overwrite-templates'],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    return {'workspace': str(root), 'baseCurrency': base_ccy, 'created': created, 'initializedAt': now}


def main() -> int:
    parser = argparse.ArgumentParser(description='Initialize business-finance-ops workspace.')
    parser.add_argument('workspace')
    parser.add_argument('--base-currency', default='USD')
    args = parser.parse_args()
    print(json.dumps(init_workspace(Path(args.workspace), base_currency=args.base_currency), indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
