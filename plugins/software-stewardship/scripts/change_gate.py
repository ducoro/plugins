#!/usr/bin/env python3
"""Deterministic delivery safety gate: objective diff blockers, real command evidence, and SHA/diff-hash approval locks."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

SECRET_PATTERNS = (
    ('aws_access_key', re.compile(r'\bAKIA[0-9A-Z]{16}\b')),
    ('github_token', re.compile(r'\b(?:ghp|gho|ghu|ghs)_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b')),
    ('private_key_block', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ('openai_or_sk_key', re.compile(r'\bsk-(?:proj-|live-|test-)?[A-Za-z0-9]{20,}\b')),
    ('hardcoded_secret_assign', re.compile(r'(?i)(?:api[_-]?key|secret[_-]?key|access[_-]?token|password)\s*[:=]\s*["\'](?!\$\{|<|YOUR_|EXAMPLE_|DUMMY_|TEST_)[A-Za-z0-9_\-/.+=]{16,}["\']')),
)

LOCAL_PATH_RE = re.compile(r'(?:/Users/[A-Za-z0-9._-]+/|/home/[A-Za-z0-9._-]+/|C:\\Users\\[A-Za-z0-9._-]+\\)')

BYPASS_PATTERNS = (
    ('test_skip_added', re.compile(r'\b(?:it|test|describe)\.skip\s*\(|\bx(?:it|test|describe)\s*\(|@unittest\.skip|@pytest\.mark\.skip|t\.Skip\s*\(')),
    ('check_bypass_added', re.compile(r'@ts-ignore\b|@ts-nocheck\b|eslint-disable(?:-next-line)?\b|#\s*noqa\b|#\s*type:\s*ignore\b')),
)

TEST_FILE_RE = re.compile(r'(?:^|/)(?:tests?|__tests__|spec)/|\.(?:test|spec)\.[A-Za-z0-9]+$|_test\.(?:py|go)$', re.I)
CODE_SUFFIXES = {
    '.py', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.go', '.rs', '.java', '.kt',
    '.swift', '.c', '.cc', '.cpp', '.h', '.hpp', '.rb', '.php', '.cs', '.sh', '.sql',
}
ASSERT_RE = re.compile(r'\b(?:assert\w*|expect)\s*\(|\bassert\s+')

EVIDENCE_KINDS = ('verification', 'fault-injection-red', 'formal-check', 'independent-review')
RISK_LEVELS = ('low', 'medium', 'high')
RISK_ORDER = {level: idx for idx, level in enumerate(RISK_LEVELS)}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


GIT_ENV_STRIP = ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR', 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES')


def run_git(repo: Path, *args: str) -> tuple[int, str, str]:
    env = {k: v for k, v in os.environ.items() if k not in GIT_ENV_STRIP}
    proc = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True, env=env, check=False)
    return proc.returncode, proc.stdout, proc.stderr


def resolve_repo_root(repo: Path) -> Path:
    repo = repo.expanduser().resolve()
    rc, out, err = run_git(repo, 'rev-parse', '--show-toplevel')
    if rc != 0:
        raise ValueError(f'{repo}: not a git repository ({err.strip()})')
    return Path(out.strip()).resolve()


def resolve_base(repo: Path, requested: str | None) -> str | None:
    if requested:
        rc, _, _ = run_git(repo, 'rev-parse', '--verify', requested)
        return requested if rc == 0 else None
    rc_u, up_out, _ = run_git(repo, 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}')
    if rc_u == 0 and up_out.strip():
        return up_out.strip()
    _, branch_out, _ = run_git(repo, 'branch', '--show-current')
    current_branch = branch_out.strip()
    candidates = ['origin/main', 'origin/master']
    if current_branch not in ('main', 'master'):
        candidates.extend(['main', 'master'])
    candidates.append('HEAD~1')
    for cand in candidates:
        rc, _, _ = run_git(repo, 'rev-parse', '--verify', cand)
        if rc == 0:
            return cand
    return None


CACHE_NOISE_RE = re.compile(r'(?:^|/)(?:__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache)(?:/|$)|\.pyc$')


def resolve_diff_anchor(repo: Path, resolved_base: str | None) -> str:
    if resolved_base:
        rc, mb, _ = run_git(repo, 'merge-base', resolved_base, 'HEAD')
        if rc == 0 and mb.strip():
            return mb.strip()
    return 'HEAD'


def compute_repo_fingerprint(repo: Path, base: str | None = None) -> dict:
    _, head_out, _ = run_git(repo, 'rev-parse', 'HEAD')
    head_sha = head_out.strip()
    resolved_base = resolve_base(repo, base)
    anchor = resolve_diff_anchor(repo, resolved_base)

    h = hashlib.sha256()
    h.update(f'HEAD:{head_sha}\n'.encode('utf-8'))

    # Single net diff from merge-base (or HEAD) to current working tree so fixed historical lines are not double-counted
    rc_d, combined_diff, _ = run_git(repo, 'diff', '--no-color', anchor)
    if rc_d != 0:
        combined_diff = ''

    _, status_out, _ = run_git(repo, 'status', '--porcelain', '-uall')
    untracked_contents = []
    for line in sorted(status_out.splitlines()):
        rel_check = line[3:].strip().strip('"') if len(line) > 3 else ''
        if line.startswith('?? ') and CACHE_NOISE_RE.search(rel_check):
            continue
        h.update((line + '\n').encode('utf-8'))
        if line.startswith('?? '):
            rel = rel_check
            p = repo / rel
            if p.is_file():
                raw = p.read_bytes()
                h.update(f'UNTRACKED:{rel}:'.encode('utf-8'))
                h.update(hashlib.sha256(raw).digest())
                if b'\x00' not in raw:
                    untracked_contents.append((rel, raw.decode('utf-8', errors='replace')))

    h.update(combined_diff.encode('utf-8'))
    return {
        'headSha': head_sha,
        'baseRef': resolved_base,
        'diffHash': h.hexdigest()[:16],
        'combinedDiff': combined_diff,
        'untrackedContents': untracked_contents,
    }


def scan_diff_blockers(repo: Path, base: str | None = None, *, allow_assertion_pruning: bool = False) -> dict:
    fp = compute_repo_fingerprint(repo, base=base)
    blockers = []
    current_file = ''
    test_assert_added: dict[str, int] = {}
    test_assert_deleted: dict[str, int] = {}

    def check_added_line(file_path: str, text: str) -> None:
        for rule_id, pat in SECRET_PATTERNS:
            if pat.search(text):
                blockers.append({'rule': rule_id, 'file': file_path, 'snippet': text.strip()[:120]})
        if LOCAL_PATH_RE.search(text):
            blockers.append({'rule': 'local_path_leak', 'file': file_path, 'snippet': text.strip()[:120]})
        if Path(file_path).suffix.lower() in CODE_SUFFIXES:
            for rule_id, pat in BYPASS_PATTERNS:
                if pat.search(text):
                    blockers.append({'rule': rule_id, 'file': file_path, 'snippet': text.strip()[:120]})

    for line in fp['combinedDiff'].splitlines():
        if line.startswith('+++ b/'):
            current_file = line[6:].strip()
            continue
        if line.startswith('+++ ') or line.startswith('--- ') or line.startswith('@@'):
            continue
        if line.startswith('+'):
            body = line[1:]
            check_added_line(current_file, body)
            if TEST_FILE_RE.search(current_file) and ASSERT_RE.search(body):
                test_assert_added[current_file] = test_assert_added.get(current_file, 0) + 1
        elif line.startswith('-'):
            body = line[1:]
            if TEST_FILE_RE.search(current_file) and ASSERT_RE.search(body):
                test_assert_deleted[current_file] = test_assert_deleted.get(current_file, 0) + 1

    for rel, content in fp['untrackedContents']:
        for body in content.splitlines():
            check_added_line(rel, body)
            if TEST_FILE_RE.search(rel) and ASSERT_RE.search(body):
                test_assert_added[rel] = test_assert_added.get(rel, 0) + 1

    if not allow_assertion_pruning:
        for tf, deleted_count in sorted(test_assert_deleted.items()):
            added_count = test_assert_added.get(tf, 0)
            if deleted_count > added_count:
                blockers.append({
                    'rule': 'assertions_deleted',
                    'file': tf,
                    'snippet': f'deleted {deleted_count} assertion line(s) while adding only {added_count}',
                })

    return {
        'ok': len(blockers) == 0,
        'checkedAt': utc_now(),
        'headSha': fp['headSha'],
        'baseRef': fp['baseRef'],
        'diffHash': fp['diffHash'],
        'allowAssertionPruning': allow_assertion_pruning,
        'blockerCount': len(blockers),
        'blockers': blockers,
    }


def load_gate_state(state_dir: Path) -> dict:
    path = state_dir / 'gate-state.json'
    if not path.is_file():
        return {'schemaVersion': 'software-stewardship-gate/1', 'evidence': [], 'approvals': {}, 'lastDiffCheck': None}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            data.setdefault('evidence', [])
            data.setdefault('approvals', {})
            return data
    except json.JSONDecodeError:
        pass
    return {'schemaVersion': 'software-stewardship-gate/1', 'evidence': [], 'approvals': {}, 'lastDiffCheck': None}


def save_gate_state(state_dir: Path, data: dict) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / 'gate-state.json'
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return path


def cmd_check_diff(repo: Path, state_dir: Path, base: str | None, *, allow_assertion_pruning: bool = False) -> tuple[int, dict]:
    res = scan_diff_blockers(repo, base=base, allow_assertion_pruning=allow_assertion_pruning)
    state = load_gate_state(state_dir)
    state['lastDiffCheck'] = res
    save_gate_state(state_dir, state)
    return (0 if res['ok'] else 2), res


def cmd_record_evidence(
    repo: Path,
    state_dir: Path,
    command: str,
    *,
    base: str | None = None,
    run_now: bool = False,
    exit_code: int | None = None,
    summary: str = '',
    kind: str = 'verification',
) -> tuple[int, dict]:
    if kind not in EVIDENCE_KINDS:
        raise ValueError(f'Unknown evidence kind: {kind}')
    output_tail = summary
    if run_now:
        proc = subprocess.run(command, cwd=str(repo), shell=True, capture_output=True, text=True, check=False)
        actual_rc = proc.returncode
        combined = (proc.stdout + '\n' + proc.stderr).strip()
        output_tail = combined[-400:] if combined else ''
    else:
        if exit_code is None:
            raise ValueError('Provide --run or explicit --exit-code')
        actual_rc = exit_code

    fp = compute_repo_fingerprint(repo, base=base)
    passed = (actual_rc != 0) if kind == 'fault-injection-red' else (actual_rc == 0)

    entry = {
        'kind': kind,
        'command': command,
        'exitCode': actual_rc,
        'passed': passed,
        'headSha': fp['headSha'],
        'diffHash': fp['diffHash'],
        'recordedAt': utc_now(),
        'summary': output_tail,
    }
    state = load_gate_state(state_dir)
    state['evidence'] = (state.get('evidence', []) + [entry])[-50:]
    save_gate_state(state_dir, state)
    return (0 if entry['passed'] else 2), {'ok': entry['passed'], 'evidence': entry}


def cmd_approve(
    repo: Path,
    state_dir: Path,
    action: str,
    approved_by: str,
    base: str | None,
    *,
    risk: str = 'low',
    allow_assertion_pruning: bool = False,
    waive_review: str = '',
    summary: str = '',
) -> tuple[int, dict]:
    if not approved_by.strip():
        raise ValueError('--approved-by must be non-empty')
    if risk not in RISK_LEVELS:
        raise ValueError(f'Unknown risk level: {risk}')
    diff_res = scan_diff_blockers(repo, base=base, allow_assertion_pruning=allow_assertion_pruning)
    if not diff_res['ok']:
        return 2, {
            'ok': False,
            'reason': 'diff_blockers_present',
            'blockers': diff_res['blockers'],
        }

    record = {
        'action': action,
        'risk': risk,
        'allowAssertionPruning': allow_assertion_pruning,
        'reviewWaiverReason': waive_review.strip(),
        'summary': summary.strip(),
        'approvedBy': approved_by.strip(),
        'approvedAt': utc_now(),
        'headSha': diff_res['headSha'],
        'diffHash': diff_res['diffHash'],
        'baseRef': diff_res['baseRef'],
    }
    state = load_gate_state(state_dir)
    state['lastDiffCheck'] = diff_res
    state['approvals'][action] = record
    save_gate_state(state_dir, state)
    return 0, {'ok': True, 'approval': record}


def cmd_verify_release(
    repo: Path,
    state_dir: Path,
    action: str,
    base: str | None,
    *,
    risk: str = 'low',
    allow_assertion_pruning: bool = False,
    waive_review: str = '',
) -> tuple[int, dict]:
    if risk not in RISK_LEVELS:
        raise ValueError(f'Unknown risk level: {risk}')
    state = load_gate_state(state_dir)
    approval = state.get('approvals', {}).get(action)
    effective_allow_pruning = bool(
        allow_assertion_pruning and isinstance(approval, dict) and approval.get('allowAssertionPruning') is True
    )
    diff_res = scan_diff_blockers(repo, base=base, allow_assertion_pruning=effective_allow_pruning)
    state['lastDiffCheck'] = diff_res
    save_gate_state(state_dir, state)

    reasons = []
    if not diff_res['ok']:
        reasons.append('diff_blockers_present')

    approval_risk = approval.get('risk', 'low') if isinstance(approval, dict) else 'low'
    if approval_risk not in RISK_ORDER:
        approval_risk = 'high'
    effective_risk = risk if RISK_ORDER[risk] >= RISK_ORDER[approval_risk] else approval_risk

    if not approval:
        reasons.append('missing_approval')
    else:
        if approval.get('headSha') != diff_res['headSha'] or approval.get('diffHash') != diff_res['diffHash']:
            reasons.append('tampered_after_approval')

    matching_verification = [
        ev for ev in state.get('evidence', [])
        if ev.get('passed') is True
        and ev.get('kind', 'verification') in ('verification', 'formal-check')
        and ev.get('headSha') == diff_res['headSha']
        and ev.get('diffHash') == diff_res['diffHash']
    ]
    if not matching_verification:
        reasons.append('missing_passing_evidence')

    matching_review = [
        ev for ev in state.get('evidence', [])
        if ev.get('passed') is True
        and ev.get('kind') == 'independent-review'
        and ev.get('headSha') == diff_res['headSha']
        and ev.get('diffHash') == diff_res['diffHash']
    ]
    waived_review = bool(
        waive_review.strip()
        and isinstance(approval, dict)
        and approval.get('reviewWaiverReason', '').strip() == waive_review.strip()
        and approval.get('headSha') == diff_res['headSha']
        and approval.get('diffHash') == diff_res['diffHash']
    )
    if effective_risk in ('medium', 'high') and not matching_review and not waived_review:
        reasons.append('missing_independent_review')

    ok = len(reasons) == 0
    return (0 if ok else 3), {
        'ok': ok,
        'action': action,
        'effectiveRisk': effective_risk,
        'headSha': diff_res['headSha'],
        'diffHash': diff_res['diffHash'],
        'reasons': reasons,
        'blockerCount': diff_res['blockerCount'],
        'blockers': diff_res['blockers'],
        'approval': approval,
        'matchingEvidenceCount': len(matching_verification),
        'matchingReviewCount': len(matching_review),
        'reviewWaived': waived_review,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Deterministic change gate with diff guards, typed evidence, and risk-aware SHA approval locks.')
    parser.add_argument('--repo', required=True)
    parser.add_argument('--state-dir', required=True, help='Space-local state directory (never inside target repo)')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_diff = sub.add_parser('check-diff')
    p_diff.add_argument('--base', default=None)
    p_diff.add_argument('--allow-assertion-pruning', action='store_true')

    p_ev = sub.add_parser('record-evidence')
    p_ev.add_argument('--kind', default='verification', choices=EVIDENCE_KINDS)
    p_ev.add_argument('--command', required=True)
    p_ev.add_argument('--run', action='store_true', dest='run_now')
    p_ev.add_argument('--exit-code', type=int, default=None)
    p_ev.add_argument('--summary', default='')
    p_ev.add_argument('--base', default=None)

    p_app = sub.add_parser('approve')
    p_app.add_argument('--action', required=True, choices=('merge', 'release', 'migrate'))
    p_app.add_argument('--risk', default='low', choices=RISK_LEVELS)
    p_app.add_argument('--approved-by', required=True)
    p_app.add_argument('--summary', default='')
    p_app.add_argument('--base', default=None)
    p_app.add_argument('--allow-assertion-pruning', action='store_true')
    p_app.add_argument('--waive-review', default='', help='Explicit human break-glass reason to waive independent-review (audited)')

    p_ver = sub.add_parser('verify-release')
    p_ver.add_argument('--action', required=True, choices=('merge', 'release', 'migrate'))
    p_ver.add_argument('--risk', default='low', choices=RISK_LEVELS)
    p_ver.add_argument('--base', default=None)
    p_ver.add_argument('--allow-assertion-pruning', action='store_true')
    p_ver.add_argument('--waive-review', default='', help='Must match an explicit human waiver recorded in approve')

    args = parser.parse_args()
    try:
        repo = resolve_repo_root(Path(args.repo))
        state_dir = Path(args.state_dir).expanduser().resolve()
        if args.cmd == 'check-diff':
            rc, payload = cmd_check_diff(repo, state_dir, args.base, allow_assertion_pruning=args.allow_assertion_pruning)
        elif args.cmd == 'record-evidence':
            rc, payload = cmd_record_evidence(
                repo, state_dir, args.command, base=args.base, run_now=args.run_now,
                exit_code=args.exit_code, summary=args.summary, kind=args.kind,
            )
        elif args.cmd == 'approve':
            rc, payload = cmd_approve(
                repo, state_dir, args.action, args.approved_by, args.base,
                risk=args.risk, allow_assertion_pruning=args.allow_assertion_pruning,
                waive_review=args.waive_review, summary=args.summary,
            )
        else:
            rc, payload = cmd_verify_release(
                repo, state_dir, args.action, args.base,
                risk=args.risk, allow_assertion_pruning=args.allow_assertion_pruning,
                waive_review=args.waive_review,
            )
    except ValueError as err:
        print(json.dumps({'ok': False, 'error': str(err)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
