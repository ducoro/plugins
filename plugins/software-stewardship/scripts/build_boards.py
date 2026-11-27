#!/usr/bin/env python3
"""Project Space-local software-stewardship state one-way into isolated shadcn/ui Board assets/data.json."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

SCRIPT_DIR = Path(__file__).resolve().parent
BOARDS_SRC = SCRIPT_DIR.parent / 'assets/boards'
BOARDS = ('delivery-board', 'health-board')


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


def build_delivery_payload(state_dir: Path) -> dict:
    audit = read_json(state_dir / 'audit.json', {})
    gate = read_json(state_dir / 'gate-state.json', {})
    pulse = read_json(state_dir / 'pulse.json', {})

    blast = audit.get('blastRadius', {}) if isinstance(audit, dict) else {}
    last_diff = gate.get('lastDiffCheck') or {}
    approvals = gate.get('approvals') or {}
    evidence = gate.get('evidence') or []
    remote = pulse.get('remote') or {}
    prs = remote.get('pullRequests') or []
    ci_runs = remote.get('ciRuns') or []

    head_sha = last_diff.get('headSha') or audit.get('headSha') or (pulse.get('git') or {}).get('headSha') or ''
    diff_hash = last_diff.get('diffHash') or ''

    approval_rows = []
    for action, rec in sorted(approvals.items()):
        if not isinstance(rec, dict):
            continue
        still_valid = bool(head_sha and diff_hash and rec.get('headSha') == head_sha and rec.get('diffHash') == diff_hash)
        approval_rows.append({
            'action': action,
            'risk': rec.get('risk', 'low'),
            'approvedBy': rec.get('approvedBy', ''),
            'approvedAt': rec.get('approvedAt', ''),
            'reviewWaived': bool((rec.get('reviewWaiverReason') or '').strip()),
            'headSha': (rec.get('headSha') or '')[:12],
            'diffHash': rec.get('diffHash', ''),
            'status': 'valid' if still_valid else 'stale_tampered',
        })

    items = []
    for blocker in last_diff.get('blockers', []):
        items.append({
            'id': f'blocker-{blocker.get("rule", "rule")}-{blocker.get("file", "")}',
            'kind': 'blocker',
            'severity': 'high',
            'title': f'{blocker.get("rule", "blocker")}: {blocker.get("file", "working-tree")}',
            'detail': blocker.get('snippet', ''),
            'status': 'blocked',
        })
    for sens in blast.get('sensitivePaths', []):
        items.append({
            'id': f'sensitive-{sens.get("path", "")}',
            'kind': 'sensitive_path',
            'severity': 'medium',
            'title': sens.get('path', ''),
            'detail': ', '.join(sens.get('categories', [])),
            'status': 'review',
        })
    for pr in prs:
        items.append({
            'id': f'pr-{pr.get("number", "")}',
            'kind': 'pull_request',
            'severity': 'low',
            'title': f'#{pr.get("number")} {pr.get("title", "")}',
            'detail': f'Author: {pr.get("author", "unknown")}' + (' (draft)' if pr.get('draft') else ''),
            'status': 'draft' if pr.get('draft') else 'open',
            'url': pr.get('url', ''),
        })
    for run in ci_runs:
        concl = run.get('conclusion', 'pending')
        items.append({
            'id': f'ci-{run.get("id", "")}',
            'kind': 'ci_run',
            'severity': 'high' if concl in ('failure', 'timed_out') else 'low',
            'title': f'{run.get("name", "CI")} ({run.get("branch", "")})',
            'detail': f'Status: {run.get("status", "")} / Conclusion: {concl}',
            'status': concl,
            'url': run.get('url', ''),
        })

    return {
        'generatedAt': utc_now(),
        'repoName': audit.get('repoName') or pulse.get('repoName') or 'Repository',
        'branch': audit.get('branch') or (pulse.get('git') or {}).get('branch') or '—',
        'headSha': head_sha[:12] if head_sha else '—',
        'diffHash': diff_hash or '—',
        'signalFlags': audit.get('signalFlags', []) if isinstance(audit, dict) else [],
        'summary': {
            'changedFiles': blast.get('changedFileCount', 0),
            'changedLines': blast.get('totalChangedLines', 0),
            'netLines': blast.get('netLines', 0),
            'newFiles': blast.get('newFileCount', 0),
            'blockerCount': last_diff.get('blockerCount', 0),
            'failingCiCount': remote.get('failingCiCount', 0),
            'openPrCount': len(prs),
            'passingEvidenceCount': sum(1 for e in evidence if isinstance(e, dict) and e.get('passed')),
            'independentReviewCount': sum(
                1 for e in evidence
                if isinstance(e, dict) and e.get('passed') and e.get('kind') == 'independent-review'
            ),
            'faultInjectionCount': sum(
                1 for e in evidence
                if isinstance(e, dict) and e.get('passed') and e.get('kind') == 'fault-injection-red'
            ),
        },
        'approvals': approval_rows,
        'evidence': evidence[-10:][::-1],
        'items': items,
    }


def build_health_payload(state_dir: Path) -> dict:
    audit = read_json(state_dir / 'audit.json', {})
    supply = read_json(state_dir / 'supply-chain.json', {})
    pulse = read_json(state_dir / 'pulse.json', {})
    history = read_jsonl(state_dir / 'pulse-history.jsonl')

    vulns = supply.get('vulnerabilities', []) if isinstance(supply, dict) else []
    licenses = supply.get('licenseAlerts', []) if isinstance(supply, dict) else []
    hotspots = audit.get('churnHotspots', []) if isinstance(audit, dict) else []
    large_files = audit.get('largeFiles', []) if isinstance(audit, dict) else []
    arch_signals = audit.get('architectureSignals', {}) if isinstance(audit, dict) else {}
    shotgun_commits = arch_signals.get('shotgunCommits', []) if isinstance(arch_signals, dict) else []
    git_stats = pulse.get('git', {}) if isinstance(pulse, dict) else {}

    alerts = []
    for v in vulns:
        alerts.append({
            'id': f'cve-{v.get("id", "")}-{v.get("package", "")}',
            'severity': 'high',
            'category': 'cve',
            'target': f'{v.get("package")}@{v.get("version")} ({v.get("ecosystem")})',
            'detail': f'{v.get("id")} from {v.get("source", "lockfile")}',
            'url': v.get('advisoryUrl', ''),
        })
    for lic in licenses:
        alerts.append({
            'id': f'lic-{lic.get("package", "")}-{lic.get("matched", "")}',
            'severity': 'high',
            'category': 'license',
            'target': lic.get('package', ''),
            'detail': f'{lic.get("matched")} detected in {lic.get("source", "")}',
            'url': '',
        })
    for lf in large_files:
        alerts.append({
            'id': f'large-{lf.get("path", "")}',
            'severity': 'medium',
            'category': 'large_file',
            'target': lf.get('path', ''),
            'detail': f'{lf.get("lines")} lines (limit {lf.get("limit")})',
            'url': '',
        })
    for sc in shotgun_commits[:10]:
        alerts.append({
            'id': f'shotgun-{sc.get("sha", "")}',
            'severity': 'medium',
            'category': 'shotgun_surgery',
            'target': f'{sc.get("sha")} ({sc.get("moduleCount")} modules)',
            'detail': f'{sc.get("subject", "")} — {", ".join(sc.get("modules", [])[:6])}',
            'url': '',
        })

    return {
        'generatedAt': utc_now(),
        'repoName': audit.get('repoName') or supply.get('repoName') or pulse.get('repoName') or 'Repository',
        'osvStatus': supply.get('osvStatus', 'not_run'),
        'remoteStatus': (pulse.get('remote') or {}).get('status', 'not_run'),
        'pulseOutcome': pulse.get('outcome', 'not_run'),
        'summary': {
            'dependencyCount': supply.get('dependencyCount', 0),
            'vulnerabilityCount': len(vulns),
            'licenseAlertCount': len(licenses),
            'hotspotCount': len(hotspots),
            'largeFileCount': len(large_files),
            'shotgunCommitCount': len(shotgun_commits),
            'extraWorktreeCount': audit.get('extraWorktreeCount', 0),
            'commitCount30d': git_stats.get('commitCount30d', 0),
            'revertRatePct': git_stats.get('revertRatePct', 0.0),
        },
        'alerts': alerts,
        'hotspots': hotspots,
        'history': history[-20:][::-1],
    }


def project_board(state_dir: Path, board_name: str, board_dir: Path, *, overwrite_templates: bool = False) -> Path:
    if board_name not in BOARDS:
        raise ValueError(f'Unknown board: {board_name}')
    state_dir = state_dir.expanduser().resolve()
    board_dir = board_dir.expanduser().resolve()
    assets_dir = board_dir / 'assets'
    assets_dir.mkdir(parents=True, exist_ok=True)

    src_dir = BOARDS_SRC / board_name
    if overwrite_templates or not (board_dir / 'index.html').is_file():
        shutil.copy2(src_dir / 'index.html', board_dir / 'index.html')
        shutil.copy2(src_dir / 'README.md', board_dir / 'README.md')
        shutil.copy2(BOARDS_SRC / 'shared/board-ui.css', assets_dir / 'board-ui.css')
        shutil.copy2(BOARDS_SRC / 'shared/board-sdk-bridge.js', assets_dir / 'board-sdk-bridge.js')

    payload = build_delivery_payload(state_dir) if board_name == 'delivery-board' else build_health_payload(state_dir)
    data_path = assets_dir / 'data.json'
    data_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return data_path


def main() -> int:
    parser = argparse.ArgumentParser(description='Project software-stewardship Space state to shadcn/ui boards.')
    parser.add_argument('--state-dir', required=True, help='Path to Space-local stewardship state directory')
    parser.add_argument('--board', choices=BOARDS, default=None)
    parser.add_argument('--board-dir', default=None, help='Target Space board directory')
    parser.add_argument('--all', action='store_true', help='Project both boards under <state-dir>/boards/')
    parser.add_argument('--overwrite-templates', action='store_true')
    args = parser.parse_args()

    sdir = Path(args.state_dir).expanduser().resolve()
    outputs = []
    if args.all:
        for b in BOARDS:
            outputs.append(str(project_board(sdir, b, sdir / 'boards' / b, overwrite_templates=args.overwrite_templates)))
    elif args.board:
        target = Path(args.board_dir) if args.board_dir else (sdir / 'boards' / args.board)
        outputs.append(str(project_board(sdir, args.board, target, overwrite_templates=args.overwrite_templates)))
    else:
        parser.error('Specify --all or --board <name>')

    print(json.dumps({'projected': outputs}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
