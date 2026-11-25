#!/usr/bin/env python3
"""Initialize a shared customer-support-ops workspace and seed board data."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_SLA_POLICY = {
    'schemaVersion': 'customer-support-sla/1',
    'firstResponseHours': {'P0': 1, 'P1': 4, 'P2': 24, 'P3': 72},
    'replyCooldownHours': 24,
    'spikeMinRecentCount': 3,
    'spikeRatioThreshold': 2.0,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def write_json_if_missing(path: Path, payload: object) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return True


def init_workspace(root: Path) -> dict:
    root = root.expanduser().resolve()
    for rel in ('tickets', 'issues', 'kb', 'boards'):
        (root / rel).mkdir(parents=True, exist_ok=True)

    now = utc_now()
    created = []
    if write_json_if_missing(root / 'sla-policy.json', {**DEFAULT_SLA_POLICY, 'updatedAt': now}):
        created.append('sla-policy.json')
    if write_json_if_missing(
        root / 'tickets/tickets.json',
        {'schemaVersion': 'customer-support-tickets/1', 'updatedAt': now, 'tickets': {}},
    ):
        created.append('tickets/tickets.json')
    if write_json_if_missing(
        root / 'issues/root-causes.json',
        {'schemaVersion': 'customer-support-root-causes/1', 'updatedAt': now, 'clusters': {}},
    ):
        created.append('issues/root-causes.json')
    if write_json_if_missing(
        root / 'outbound-queue.json',
        {'schemaVersion': 'customer-support-outbound/1', 'updatedAt': now, 'drafts': {}},
    ):
        created.append('outbound-queue.json')
    log_path = root / 'reply-log.jsonl'
    if not log_path.exists():
        log_path.write_text('', encoding='utf-8')
        created.append('reply-log.jsonl')

    build_script = SCRIPT_DIR / 'build_boards.py'
    if build_script.is_file():
        subprocess.run(
            [sys.executable, str(build_script), str(root), '--all', '--overwrite-templates'],
            check=True,
            stdout=subprocess.DEVNULL,
        )

    return {'workspace': str(root), 'created': created, 'initializedAt': now}


def main() -> int:
    parser = argparse.ArgumentParser(description='Initialize customer-support-ops workspace.')
    parser.add_argument('workspace', help='Target workspace path')
    args = parser.parse_args()
    print(json.dumps(init_workspace(Path(args.workspace)), indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
