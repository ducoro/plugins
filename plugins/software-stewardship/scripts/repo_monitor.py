#!/usr/bin/env python3
"""Quiet repository pulse monitor: combines local Git stats, optional GitHub PR/CI state, and honest no_material_change deltas."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def run_git(repo: Path, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True, check=False)
    return proc.returncode, proc.stdout, proc.stderr


def read_json(path: Path, default: object) -> object:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return default


def fetch_github_json(url: str, token: str | None = None, timeout: int = 15) -> object:
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'ducoro-software-stewardship/1.0'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def collect_remote_pulse(
    *,
    github_json: Path | None = None,
    github_repo: str | None = None,
    api_base: str = 'https://api.github.com',
) -> tuple[list[dict], list[dict], str | None]:
    if github_json:
        raw = read_json(github_json.expanduser().resolve(), {})
        if isinstance(raw, dict):
            return list(raw.get('pullRequests', [])), list(raw.get('ciRuns', [])), None
        return [], [], None

    if not github_repo:
        return [], [], None

    token = os.environ.get('GITHUB_TOKEN')
    base = api_base.rstrip('/')
    prs = []
    runs = []
    try:
        pr_data = fetch_github_json(f'{base}/repos/{github_repo}/pulls?state=open&per_page=20', token=token)
        if isinstance(pr_data, list):
            for p in pr_data:
                prs.append({
                    'number': p.get('number'),
                    'title': p.get('title', ''),
                    'author': (p.get('user') or {}).get('login', ''),
                    'draft': bool(p.get('draft')),
                    'url': p.get('html_url', ''),
                    'updatedAt': p.get('updated_at', ''),
                })
        run_data = fetch_github_json(f'{base}/repos/{github_repo}/actions/runs?per_page=10', token=token)
        if isinstance(run_data, dict):
            for r in run_data.get('workflow_runs', [])[:10]:
                runs.append({
                    'id': r.get('id'),
                    'name': r.get('name', ''),
                    'status': r.get('status', ''),
                    'conclusion': r.get('conclusion') or 'pending',
                    'branch': r.get('head_branch', ''),
                    'url': r.get('html_url', ''),
                    'updatedAt': r.get('updated_at', ''),
                })
        return prs, runs, None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as err:
        return [], [], str(err)


def monitor_repo(
    repo: Path,
    state_dir: Path,
    *,
    days: int = 30,
    github_json: Path | None = None,
    github_repo: str | None = None,
    api_base: str = 'https://api.github.com',
) -> dict:
    repo = repo.expanduser().resolve()
    rc, top, err = run_git(repo, 'rev-parse', '--show-toplevel')
    if rc != 0:
        raise ValueError(f'{repo}: not a git repository ({err.strip()})')
    repo = Path(top.strip()).resolve()
    state_dir = state_dir.expanduser().resolve()
    state_dir.mkdir(parents=True, exist_ok=True)

    _, head_out, _ = run_git(repo, 'rev-parse', 'HEAD')
    head_sha = head_out.strip()
    _, branch_out, _ = run_git(repo, 'branch', '--show-current')
    branch = branch_out.strip() or 'HEAD'
    _, log_out, _ = run_git(repo, 'log', f'--since={days} days ago', '--pretty=format:%h\t%s')
    commits = [line for line in log_out.splitlines() if line.strip()]
    reverts = [c for c in commits if 'revert' in c.lower()]
    revert_rate_pct = round((len(reverts) / len(commits)) * 100.0, 2) if commits else 0.0

    prs, ci_runs, remote_error = collect_remote_pulse(
        github_json=github_json, github_repo=github_repo, api_base=api_base,
    )
    failing_ci = [r for r in ci_runs if r.get('conclusion') in ('failure', 'timed_out', 'cancelled')]

    audit = read_json(state_dir / 'audit.json', {})
    supply = read_json(state_dir / 'supply-chain.json', {})
    gate = read_json(state_dir / 'gate-state.json', {})

    material_state = {
        'branch': branch,
        'headSha': head_sha,
        'commitCount30d': len(commits),
        'revertCount30d': len(reverts),
        'openPrNumbers': sorted(p.get('number') for p in prs if p.get('number') is not None),
        'failingCiIds': sorted(r.get('id') for r in failing_ci if r.get('id') is not None),
        'vulnerabilityIds': sorted(v.get('id') for v in supply.get('vulnerabilities', []) if v.get('id')),
        'licenseAlertCount': supply.get('licenseAlertCount', 0),
        'diffBlockerCount': (gate.get('lastDiffCheck') or {}).get('blockerCount', 0),
        'signalFlags': sorted(audit.get('signalFlags', [])) if isinstance(audit, dict) else [],
    }
    fingerprint = hashlib.sha256(json.dumps(material_state, sort_keys=True).encode('utf-8')).hexdigest()[:16]

    prev = read_json(state_dir / 'pulse.json', {})
    prev_fp = prev.get('fingerprint') if isinstance(prev, dict) else None
    prev_state = prev.get('materialState', {}) if isinstance(prev, dict) else {}

    changes = []
    if prev_fp and prev_fp != fingerprint:
        for key, new_val in material_state.items():
            old_val = prev_state.get(key)
            if old_val != new_val:
                changes.append({'field': key, 'before': old_val, 'after': new_val})
        outcome = 'material_change'
    elif prev_fp == fingerprint:
        outcome = 'no_material_change'
    else:
        outcome = 'initial_baseline'

    pulse = {
        'schemaVersion': 'software-stewardship-pulse/1',
        'generatedAt': utc_now(),
        'repoName': repo.name,
        'outcome': outcome,
        'fingerprint': fingerprint,
        'materialState': material_state,
        'changes': changes,
        'git': {
            'branch': branch,
            'headSha': head_sha,
            'commitCount30d': len(commits),
            'revertCount30d': len(reverts),
            'revertRatePct': revert_rate_pct,
        },
        'remote': {
            'pullRequests': prs,
            'ciRuns': ci_runs,
            'failingCiCount': len(failing_ci),
            'error': remote_error,
        },
    }

    (state_dir / 'pulse.json').write_text(json.dumps(pulse, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    if outcome in ('initial_baseline', 'material_change'):
        history_row = {
            'observedAt': pulse['generatedAt'],
            'outcome': outcome,
            'fingerprint': fingerprint,
            'headSha': head_sha,
            'changes': changes,
            'failingCiCount': len(failing_ci),
            'vulnerabilityCount': len(material_state['vulnerabilityIds']),
        }
        with (state_dir / 'pulse-history.jsonl').open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(history_row, ensure_ascii=False) + '\n')

    return pulse


def main() -> int:
    parser = argparse.ArgumentParser(description='Monitor repository pulse with honest no_material_change detection.')
    parser.add_argument('--repo', required=True)
    parser.add_argument('--state-dir', required=True)
    parser.add_argument('--days', type=int, default=30)
    parser.add_argument('--github-json', default=None, help='Optional PR/CI JSON exported from GitHub Connector')
    parser.add_argument('--github-repo', default=None, help='Optional owner/repo for read-only GitHub REST API check')
    parser.add_argument('--api-base', default='https://api.github.com')
    args = parser.parse_args()

    try:
        pulse = monitor_repo(
            Path(args.repo),
            Path(args.state_dir),
            days=args.days,
            github_json=Path(args.github_json) if args.github_json else None,
            github_repo=args.github_repo,
            api_base=args.api_base,
        )
    except ValueError as err:
        print(json.dumps({'ok': False, 'error': str(err)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(pulse, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
