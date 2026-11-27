#!/usr/bin/env python3
"""Read-only readiness diagnostic for content-operations workspace, style assets, and platform credentials."""
from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import sys

REQUIRED_WORKSPACE_FILES = (
    'brand-profile.md',
    'accounts.json',
    'topics/topics.json',
    'calendar.json',
    'publish-log.jsonl',
    'analytics/snapshots.jsonl',
)

PLATFORM_CREDENTIAL_GROUPS = {
    'wechat-official': ('WECHAT_OFFICIAL_APP_ID', 'WECHAT_OFFICIAL_APP_SECRET'),
    'youtube': ('YOUTUBE_ACCESS_TOKEN',),
    'tiktok': ('TIKTOK_ACCESS_TOKEN',),
    'instagram': ('INSTAGRAM_ACCESS_TOKEN', 'INSTAGRAM_USER_ID'),
    'threads': ('THREADS_ACCESS_TOKEN', 'THREADS_USER_ID'),
    'x-twitter': ('X_ACCESS_TOKEN',),
    'linkedin': ('LINKEDIN_ACCESS_TOKEN', 'LINKEDIN_AUTHOR_URN'),
    'facebook': ('FACEBOOK_PAGE_ID', 'FACEBOOK_PAGE_ACCESS_TOKEN'),
    'pinterest': ('PINTEREST_ACCESS_TOKEN',),
    'bilibili': ('BILIBILI_ACCESS_TOKEN',),
    'douyin': ('DOUYIN_ACCESS_TOKEN', 'DOUYIN_OPEN_ID'),
    'kuaishou': ('KUAISHOU_ACCESS_TOKEN',),
}

STYLE_WEIGHTS = {
    'style_profile': 3,
    'style_playbook': 3,
    'exemplars': 2,
    'edit_lessons': 2,
    'corpus_articles': 1,
    'custom_themes': 1,
}


def _check_workspace(ws: Path) -> list[dict]:
    checks: list[dict] = []
    if not ws.is_dir():
        return [{'group': 'workspace', 'name': 'workspace_dir', 'status': 'fail', 'detail': f'Directory not found: {ws}'}]
    checks.append({'group': 'workspace', 'name': 'workspace_dir', 'status': 'pass', 'detail': str(ws)})
    missing = [rel for rel in REQUIRED_WORKSPACE_FILES if not (ws / rel).exists()]
    if missing:
        checks.append({'group': 'workspace', 'name': 'core_files', 'status': 'warn', 'detail': f'Missing: {", ".join(missing)}'})
    else:
        checks.append({'group': 'workspace', 'name': 'core_files', 'status': 'pass', 'detail': f'{len(REQUIRED_WORKSPACE_FILES)} core files present'})
    return checks


def _check_style_readiness(ws: Path) -> tuple[list[dict], int, int]:
    style_dir = ws / 'style'
    checks: list[dict] = []
    score = 0
    max_score = sum(STYLE_WEIGHTS.values())

    def record(name: str, ok: bool, detail: str) -> None:
        nonlocal score
        if ok:
            score += STYLE_WEIGHTS[name]
        checks.append({'group': 'style', 'name': name, 'status': 'pass' if ok else 'missing', 'weight': STYLE_WEIGHTS[name], 'detail': detail})

    profile_path = style_dir / 'style-profile.json'
    record('style_profile', profile_path.is_file(), 'Found style-profile.json' if profile_path.is_file() else 'Run build_playbook.py init-style')

    playbook_path = style_dir / 'style-playbook.md'
    has_playbook = playbook_path.is_file() and bool(playbook_path.read_text(encoding='utf-8', errors='ignore').strip())
    record('style_playbook', has_playbook, 'Found style-playbook.md' if has_playbook else 'Bootstrap via build_playbook.py or promote via learn_edits.py')

    ex_path = style_dir / 'exemplars.json'
    ex_count = 0
    if ex_path.is_file():
        try:
            ex_count = len((json.loads(ex_path.read_text(encoding='utf-8')) or {}).get('exemplars') or [])
        except ValueError:
            ex_count = 0
    record('exemplars', ex_count > 0, f'{ex_count} exemplar fingerprint(s)' if ex_count else 'Optional: extract_exemplar.py from benchmark articles')

    les_path = style_dir / 'lessons.json'
    les_count = 0
    if les_path.is_file():
        try:
            les_count = len((json.loads(les_path.read_text(encoding='utf-8')) or {}).get('lessons') or [])
        except ValueError:
            les_count = 0
    record('edit_lessons', les_count > 0, f'{les_count} recorded edit lesson(s)' if les_count else 'Run learn_edits.py after human edits')

    corpus_dir = style_dir / 'corpus'
    corpus_count = len(list(corpus_dir.glob('*.md')) + list(corpus_dir.glob('*.txt'))) if corpus_dir.is_dir() else 0
    record('corpus_articles', corpus_count > 0, f'{corpus_count} historical article(s) in style/corpus/' if corpus_count else 'Optional: drop historical articles in style/corpus/')

    themes_dir = style_dir / 'themes'
    theme_count = len(list(themes_dir.glob('*.json'))) if themes_dir.is_dir() else 0
    record('custom_themes', theme_count > 0, f'{theme_count} learned theme(s)' if theme_count else 'Optional: learn_theme.py to clone a benchmark publication')

    return checks, score, max_score


def _check_credentials() -> list[dict]:
    """Check presence of official platform env vars without ever exposing secret values."""
    checks: list[dict] = []
    for platform, env_names in PLATFORM_CREDENTIAL_GROUPS.items():
        present = [n for n in env_names if os.environ.get(n, '').strip()]
        if len(present) == len(env_names):
            checks.append({'group': 'credentials', 'name': platform, 'status': 'configured', 'detail': f'{len(present)}/{len(env_names)} env var(s) set'})
        elif present:
            missing = [n for n in env_names if n not in present]
            checks.append({'group': 'credentials', 'name': platform, 'status': 'partial', 'detail': f'Missing: {", ".join(missing)}'})
        else:
            checks.append({'group': 'credentials', 'name': platform, 'status': 'unset', 'detail': 'Use manual/browser fallback or set official env vars'})
    return checks


def _check_runtime() -> list[dict]:
    checks = [{'group': 'runtime', 'name': 'python', 'status': 'pass', 'detail': f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'}]
    try:
        importlib.import_module('PIL')
        checks.append({'group': 'runtime', 'name': 'pillow_optional', 'status': 'pass', 'detail': 'Installed (image_ops.py pixel resize/crop ready)'})
    except ImportError:
        checks.append({'group': 'runtime', 'name': 'pillow_optional', 'status': 'info', 'detail': 'Not installed (optional; only needed for image_ops.py pixel transforms)'})
    return checks


def run_diagnose(workspace: Path) -> dict:
    ws = workspace.expanduser().resolve()
    ws_checks = _check_workspace(ws)
    style_checks, style_score, style_max = _check_style_readiness(ws)
    cred_checks = _check_credentials()
    rt_checks = _check_runtime()
    configured_platforms = [c['name'] for c in cred_checks if c['status'] == 'configured']
    ws_ok = all(c['status'] == 'pass' for c in ws_checks)
    return {
        'ok': ws_ok,
        'workspace': str(ws),
        'styleReadinessScore': style_score,
        'styleReadinessMax': style_max,
        'configuredApiPlatforms': configured_platforms,
        'checks': ws_checks + style_checks + rt_checks + cred_checks,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Diagnose content-operations data directory, style readiness, and platform credential availability.')
    ap.add_argument('--workspace', '--data-dir', dest='workspace', required=True, help='Path to content-ops data directory.')
    ap.add_argument('--json', action='store_true', help='Print structured JSON report.')
    args = ap.parse_args(argv)

    report = run_diagnose(Path(args.workspace))
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f'Workspace: {report["workspace"]} ({"READY" if report["ok"] else "NEEDS_SETUP"})')
        print(f'Style readiness: {report["styleReadinessScore"]}/{report["styleReadinessMax"]}')
        print(f'Configured API platforms ({len(report["configuredApiPlatforms"])}): {", ".join(report["configuredApiPlatforms"]) or "none (browser/manual fallback active)"}')
        for item in report['checks']:
            if item['group'] == 'credentials' and item['status'] == 'unset':
                continue
            print(f'  [{item["status"]:10s}] {item["group"]}.{item["name"]}: {item["detail"]}')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
