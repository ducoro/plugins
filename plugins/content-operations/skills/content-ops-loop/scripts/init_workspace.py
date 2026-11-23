#!/usr/bin/env python3
"""Initialize a file-backed content-ops/ workspace and assemble prebuilt interactive boards."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
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

BRAND_PROFILE_TEMPLATE = """# Brand Profile

## Positioning & Audience
- **Brand / Voice**: Replace with your brand or creator name.
- **Primary Audience**: Who you are speaking to and the problems they care about.
- **Core Angle**: What distinct point of view separates your content from generic advice.

## Voice & Non-Negotiable Facts
- **Tone**: Clear, concrete, evidence-first; avoid hype and unverified claims.
- **Do Not Claim**: List prohibited promises, unshipped features, or restricted topics.
- **Canonical Links**: Primary website, docs, or landing URLs.

## Standing Approvals (Optional)
- **Gate 1 (Topic Commitment)**: Human approval required by default.
- **Gate 2 (Public Publishing)**: Human approval required per slot unless an explicit recurring column rule is listed below.
- **General Praise Replies**: Disabled by default (`false`). Enable only with per-platform daily rate caps.
"""


def write_if_missing(path: Path, content: str, force: bool = False) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    return True


def write_json_if_missing(path: Path, payload: object, force: bool = False) -> bool:
    return write_if_missing(path, json.dumps(payload, indent=2, ensure_ascii=False) + '\n', force=force)


def assemble_board(board_name: str, dest_dir: Path, force: bool = False) -> None:
    src_board = BOARDS_SRC / board_name
    shared_bridge = BOARDS_SRC / 'shared' / 'board-sdk-bridge.js'
    if not src_board.is_dir():
        raise FileNotFoundError(f'Missing board template directory: {src_board}')
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / 'runtime').mkdir(parents=True, exist_ok=True)
    (dest_dir / 'assets').mkdir(parents=True, exist_ok=True)

    for rel in ('index.html', 'README.md'):
        target = dest_dir / rel
        if force or not target.exists():
            shutil.copyfile(src_board / rel, target)

    bridge_target = dest_dir / 'runtime' / 'board-sdk-bridge.js'
    if shared_bridge.is_file() and (force or not bridge_target.exists()):
        shutil.copyfile(shared_bridge, bridge_target)


def init_workspace(target_root: Path, timezone_name: str = 'UTC', force: bool = False) -> Path:
    root = target_root.resolve()
    ws = root if root.name == 'content-ops' else root / 'content-ops'
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    for sub in ('inbox', 'topics/briefs', 'drafts', 'engagement', 'analytics/retros', 'boards'):
        (ws / sub).mkdir(parents=True, exist_ok=True)

    write_if_missing(ws / 'brand-profile.md', BRAND_PROFILE_TEMPLATE, force=force)
    write_json_if_missing(ws / 'accounts.json', {'version': 1, 'accounts': []}, force=force)
    write_json_if_missing(ws / 'topics' / 'topics.json', {'version': 1, 'topics': []}, force=force)
    write_json_if_missing(ws / 'drafts' / 'plans.json', {'version': 1, 'plans': []}, force=force)
    write_json_if_missing(
        ws / 'calendar.json',
        {'version': 1, 'timezone': timezone_name, 'slots': []},
        force=force,
    )
    write_if_missing(ws / 'publish-log.jsonl', '', force=force)
    write_json_if_missing(ws / 'engagement' / 'inbox.json', {'version': 1, 'comments': []}, force=force)
    write_if_missing(ws / 'engagement' / 'action-log.jsonl', '', force=force)
    write_if_missing(ws / 'analytics' / 'snapshots.jsonl', '', force=force)
    write_if_missing(
        ws / 'analytics' / 'retros' / 'README.md',
        f'# Weekly Retrospectives\n\nInitialized at {now}. Add `YYYY-Www.md` files after each weekly review.\n',
        force=force,
    )

    for board_name in BOARD_NAMES:
        assemble_board(board_name, ws / 'boards' / board_name, force=force)

    # Populate initial assets/data.json and inline seed data for all 5 boards so first load never 404s
    import build_boards
    payloads = build_boards.build_payloads(ws)
    for board_name, payload in payloads.items():
        build_boards.sync_board_dir(
            board_name,
            ws / 'boards' / board_name,
            payload,
            overwrite_templates=force,
            embed_inline=True,
        )

    return ws


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Initialize a file-backed content-ops workspace.')
    parser.add_argument('target', help='Target project root or content-ops directory.')
    parser.add_argument('--timezone', default='UTC', help='Default calendar timezone (e.g. Asia/Shanghai, UTC).')
    parser.add_argument('--force', action='store_true', help='Overwrite existing template files.')
    args = parser.parse_args(argv)

    ws = init_workspace(Path(args.target), timezone_name=args.timezone, force=args.force)
    print(f'Initialized content-ops workspace at {ws}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
