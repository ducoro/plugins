#!/usr/bin/env python3
"""Initialize a customer-support-ops data directory (without creating boards inside it)."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

DEFAULT_SLA_POLICY = {
    'schemaVersion': 'customer-support-sla/1',
    'firstResponseHours': {'P0': 1, 'P1': 4, 'P2': 24, 'P3': 72},
    'replyCooldownHours': 24,
    'spikeMinRecentCount': 3,
    'spikeMinUniqueCustomers': 2,
    'spikeRatioThreshold': 2.0,
    'requireApprovalForRoutine': False,
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
    for rel in ('tickets', 'issues', 'kb'):
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

    return {'dataDir': str(root), 'created': created, 'initializedAt': now}


def main() -> int:
    parser = argparse.ArgumentParser(description='Initialize a customer-support-ops data directory.')
    parser.add_argument('data_dir', help='Target data directory path (existing folder, Space files/, or shared folder)')
    args = parser.parse_args()
    print(json.dumps(init_workspace(Path(args.data_dir)), indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
