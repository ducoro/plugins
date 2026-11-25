#!/usr/bin/env python3
"""Project market-intel workspace truth one-way into isolated Board assets/data.json."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

SCRIPT_DIR = Path(__file__).resolve().parent
BOARDS_SRC = SCRIPT_DIR.parent / 'assets/boards'
BOARDS = ('radar-board', 'battlecard-board')


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def read_json(path: Path, default: object) -> object:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return default


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
        except json.JSONDecodeError:
            continue
    return rows


def build_radar_payload(workspace: Path) -> dict:
    watchlist = read_json(workspace / 'watchlist.json', {'entities': []})
    events = read_jsonl(workspace / 'events.jsonl')
    events.sort(key=lambda e: e.get('observedAt', ''), reverse=True)
    entities = watchlist.get('entities', [])
    name_map = {e['slug']: e.get('name', e['slug']) for e in entities if isinstance(e, dict) and e.get('slug')}
    high_count = sum(1 for e in events if e.get('severity') == 'high')
    return {
        'generatedAt': utc_now(),
        'summary': {
            'entityCount': len(entities),
            'eventCount': len(events),
            'highSeverityCount': high_count,
            'sourceCount': sum(len(e.get('sources', [])) for e in entities if isinstance(e, dict)),
        },
        'entities': [
            {'slug': e['slug'], 'name': e.get('name', e['slug']), 'category': e.get('category', 'tracked')}
            for e in entities if isinstance(e, dict) and e.get('slug')
        ],
        'events': [
            {**e, 'entityName': name_map.get(e.get('entitySlug', ''), e.get('entitySlug', ''))}
            for e in events[:200]
        ],
    }


def build_battlecard_payload(workspace: Path) -> dict:
    watchlist = read_json(workspace / 'watchlist.json', {'entities': []})
    events = read_jsonl(workspace / 'events.jsonl')
    cards = []
    for e in watchlist.get('entities', []):
        if not isinstance(e, dict) or not e.get('slug'):
            continue
        slug = e['slug']
        profile = read_json(workspace / 'entities' / slug / 'profile.json', {})
        bc = read_json(workspace / 'battlecards' / f'{slug}.json', {})
        entity_events = [ev for ev in events if ev.get('entitySlug') == slug]
        cards.append({
            'slug': slug,
            'name': e.get('name', slug),
            'category': e.get('category', 'tracked'),
            'threatLevel': bc.get('threatLevel', 'medium'),
            'oneLiner': bc.get('oneLiner', ''),
            'sourceCount': len(e.get('sources', [])),
            'eventCount': len(entity_events),
            'latestEvent': entity_events[-1]['summary'] if entity_events else 'No verified changes yet',
            'pricingSummary': bc.get('pricingSummary') or profile.get('pricingSummary', '—'),
            'latestVersion': bc.get('latestVersion') or profile.get('latestVersion', '—'),
            'hiringSignal': bc.get('hiringSignal') or profile.get('hiringSignal', '—'),
            'whenWeWin': bc.get('whenWeWin', ''),
            'whenWeLose': bc.get('whenWeLose', ''),
            'landmines': bc.get('landmines', []),
            'objectionHandlers': bc.get('objectionHandlers', []),
            'strengths': bc.get('strengths', []),
            'gaps': bc.get('gaps', []),
            'evidenceUrls': bc.get('evidenceUrls', []),
        })
    return {
        'generatedAt': utc_now(),
        'summary': {
            'entityCount': len(cards),
            'battlecardCount': sum(1 for c in cards if c['pricingSummary'] != '—' or c['strengths']),
        },
        'cards': cards,
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

    payload = build_radar_payload(workspace) if board_name == 'radar-board' else build_battlecard_payload(workspace)
    data_path = assets_dir / 'data.json'
    data_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return data_path


def main() -> int:
    parser = argparse.ArgumentParser(description='Project market-intel data to shadcn/ui boards.')
    parser.add_argument('workspace', help='Path to market-intel workspace')
    parser.add_argument('--board', choices=BOARDS, default=None)
    parser.add_argument('--board-dir', default=None, help='Target board directory (for Space board projection)')
    parser.add_argument('--all', action='store_true', help='Project all bundled boards under <workspace>/boards/')
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
        parser.error('Specify --all or --board <name>')

    print(json.dumps({'projected': outputs}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
