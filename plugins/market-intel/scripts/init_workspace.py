#!/usr/bin/env python3
"""Initialize a shared market-intel workspace and seed empty board snapshots."""
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


def init_workspace(root: Path) -> dict:
    root = root.expanduser().resolve()
    for rel in ('captures', 'snapshots', 'entities', 'battlecards', 'briefs', 'boards'):
        (root / rel).mkdir(parents=True, exist_ok=True)

    now = utc_now()
    created = []
    if write_json_if_missing(
        root / 'watchlist.json',
        {'schemaVersion': 'market-intel-watchlist/1', 'updatedAt': now, 'entities': []},
    ):
        created.append('watchlist.json')
    if write_json_if_missing(
        root / 'seen-events.json',
        {'schemaVersion': 'market-intel-seen/1', 'updatedAt': now, 'fingerprints': {}},
    ):
        created.append('seen-events.json')
    events_path = root / 'events.jsonl'
    if not events_path.exists():
        events_path.write_text('', encoding='utf-8')
        created.append('events.jsonl')

    build_script = SCRIPT_DIR / 'build_boards.py'
    if build_script.is_file():
        subprocess.run(
            [sys.executable, str(build_script), str(root), '--all', '--overwrite-templates'],
            check=True,
            stdout=subprocess.DEVNULL,
        )

    return {'workspace': str(root), 'created': created, 'initializedAt': now}


def main() -> int:
    parser = argparse.ArgumentParser(description='Initialize a market-intel shared workspace.')
    parser.add_argument('workspace', help='Target workspace directory (e.g. ~/.ducoro/workspaces/market-intel)')
    args = parser.parse_args()
    result = init_workspace(Path(args.workspace))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
