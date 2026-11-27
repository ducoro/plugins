#!/usr/bin/env python3
"""Deterministic Git repository audit: blast radius, sensitive paths, churn hotspots, large files, and worktrees."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

SENSITIVE_PATH_RULES = (
    ('auth_or_security', re.compile(r'(^|/)(auth|oauth|rbac|acl|security|crypto|jwt|session|permission)', re.I)),
    ('database_migration', re.compile(r'(^|/)(migrations?|schema\.sql|drizzle|prisma|alembic)', re.I)),
    ('ci_or_release', re.compile(r'(^|/)(\.github/workflows/|\.gitlab-ci|Dockerfile|docker-compose|release|entitlements)', re.I)),
    ('dependency_lockfile', re.compile(r'(^|/)(package-lock\.json|pnpm-lock\.yaml|bun\.lock|yarn\.lock|Cargo\.lock|go\.sum|poetry\.lock|uv\.lock|requirements\.txt)$')),
    ('env_or_secrets_config', re.compile(r'(^|/)(\.env(\.|$)|wrangler\.toml|vercel\.json|fly\.toml)', re.I)),
)

SKIP_DIRS = {'.git', 'node_modules', 'dist', 'build', '.next', '.venv', 'venv', '__pycache__', 'target', 'vendor'}
CONTAINER_ROOTS = {'src', 'packages', 'apps', 'plugins', 'services', 'libs', 'internal', 'cmd', 'crates'}
DEP_MANIFEST_RE = re.compile(r'(^|/)(package\.json|pyproject\.toml|requirements\.txt|Cargo\.toml|go\.mod)$')
CODE_EXTENSIONS = {
    '.py', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.go', '.rs', '.java', '.kt',
    '.swift', '.c', '.cc', '.cpp', '.h', '.hpp', '.rb', '.php', '.cs', '.sh', '.sql',
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def run_git(repo: Path, *args: str, check: bool = False) -> tuple[int, str, str]:
    proc = subprocess.run(
        ['git', '-C', str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f'git {" ".join(args)} failed: {proc.stderr.strip()}')
    return proc.returncode, proc.stdout, proc.stderr


def resolve_base_ref(repo: Path, requested: str | None) -> str | None:
    if requested:
        rc, _, _ = run_git(repo, 'rev-parse', '--verify', requested)
        if rc == 0:
            return requested
        return None
    for candidate in ('origin/main', 'main', 'master', 'HEAD~1'):
        rc, _, _ = run_git(repo, 'rev-parse', '--verify', candidate)
        if rc == 0:
            return candidate
    return None


def parse_numstat(output: str) -> dict[str, tuple[int, int]]:
    stats: dict[str, tuple[int, int]] = {}
    for line in output.splitlines():
        parts = line.split('\t')
        if len(parts) < 3:
            continue
        add_s, del_s, path = parts[0], parts[1], parts[-1].strip()
        added = int(add_s) if add_s.isdigit() else 0
        deleted = int(del_s) if del_s.isdigit() else 0
        prev_a, prev_d = stats.get(path, (0, 0))
        stats[path] = (prev_a + added, prev_d + deleted)
    return stats


def scan_large_files(repo: Path, max_file_lines: int) -> list[dict]:
    large = []
    for path in sorted(repo.rglob('*')):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(repo)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.suffix.lower() not in CODE_EXTENSIONS:
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if b'\x00' in raw:
            continue
        lines = raw.count(b'\n') + (1 if raw and not raw.endswith(b'\n') else 0)
        if lines > max_file_lines:
            large.append({'path': rel.as_posix(), 'lines': lines, 'limit': max_file_lines})
    large.sort(key=lambda item: item['lines'], reverse=True)
    return large[:30]


def scan_churn_hotspots(repo: Path, days: int, min_touches: int) -> list[dict]:
    rc, out, _ = run_git(repo, 'log', f'--since={days} days ago', '--name-only', '--pretty=format:')
    if rc != 0:
        return []
    counts = Counter(line.strip() for line in out.splitlines() if line.strip())
    hotspots = [
        {'path': path, 'touches': count, 'windowDays': days}
        for path, count in counts.most_common(25)
        if count >= min_touches
    ]
    return hotspots


def module_bucket(rel_path: str) -> str:
    parts = Path(rel_path).parts
    if len(parts) <= 1:
        return '.'
    if parts[0] in CONTAINER_ROOTS and len(parts) >= 3:
        return f'{parts[0]}/{parts[1]}'
    return parts[0]


def scan_shotgun_commits(repo: Path, days: int, min_buckets: int = 4) -> list[dict]:
    rc, out, _ = run_git(repo, 'log', f'--since={days} days ago', '--pretty=format:===COMMIT:%H:%s', '--name-only')
    if rc != 0:
        return []
    shotgun = []
    cur_sha = ''
    cur_msg = ''
    cur_buckets: set[str] = set()
    cur_files = 0

    def flush() -> None:
        if cur_sha and len(cur_buckets) >= min_buckets:
            shotgun.append({
                'sha': cur_sha[:12],
                'subject': cur_msg[:100],
                'moduleCount': len(cur_buckets),
                'modules': sorted(cur_buckets),
                'fileCount': cur_files,
            })

    for line in out.splitlines():
        if line.startswith('===COMMIT:'):
            flush()
            rest = line[len('===COMMIT:'):]
            sha, _, msg = rest.partition(':')
            cur_sha, cur_msg, cur_buckets, cur_files = sha.strip(), msg.strip(), set(), 0
        elif line.strip():
            cur_files += 1
            cur_buckets.add(module_bucket(line.strip()))
    flush()
    return shotgun[:20]


def list_worktrees(repo: Path) -> list[dict]:
    rc, out, _ = run_git(repo, 'worktree', 'list', '--porcelain')
    if rc != 0:
        return []
    items = []
    current: dict[str, object] = {}
    for line in out.splitlines():
        if not line.strip():
            if current:
                items.append(current)
                current = {}
            continue
        if line.startswith('worktree '):
            current['path'] = line.split(' ', 1)[1].strip()
        elif line.startswith('HEAD '):
            current['head'] = line.split(' ', 1)[1].strip()[:12]
        elif line.startswith('branch '):
            current['branch'] = line.split(' ', 1)[1].strip().removeprefix('refs/heads/')
        elif line.strip() == 'detached':
            current['detached'] = True
        elif line.startswith('prunable'):
            current['prunable'] = True
    if current:
        items.append(current)
    return items


def audit_repo(
    repo: Path,
    *,
    base_ref: str | None = None,
    churn_days: int = 30,
    min_churn_touches: int = 3,
    max_pr_lines: int = 400,
    max_pr_files: int = 15,
    max_file_lines: int = 500,
) -> dict:
    repo = repo.expanduser().resolve()
    rc, top, err = run_git(repo, 'rev-parse', '--show-toplevel')
    if rc != 0:
        raise ValueError(f'{repo}: not a git repository ({err.strip()})')
    repo = Path(top.strip()).resolve()

    _, head_sha_out, _ = run_git(repo, 'rev-parse', 'HEAD')
    head_sha = head_sha_out.strip()
    _, branch_out, _ = run_git(repo, 'branch', '--show-current')
    branch = branch_out.strip() or 'HEAD'

    resolved_base = resolve_base_ref(repo, base_ref)
    anchor = 'HEAD'
    if resolved_base:
        rc_mb, mb_out, _ = run_git(repo, 'merge-base', resolved_base, 'HEAD')
        if rc_mb == 0 and mb_out.strip():
            anchor = mb_out.strip()

    # Single net numstat from merge-base (or HEAD) to working tree avoids double-counting lines
    stats: dict[str, tuple[int, int]] = {}
    rc_ns, out_ns, _ = run_git(repo, 'diff', '--numstat', anchor)
    if rc_ns == 0:
        stats.update(parse_numstat(out_ns))

    _, status_out, _ = run_git(repo, 'status', '--porcelain')
    untracked = []
    dirty_count = 0
    for line in status_out.splitlines():
        if not line.strip():
            continue
        dirty_count += 1
        if line.startswith('?? '):
            rel_path = line[3:].strip()
            untracked.append(rel_path)
            if rel_path not in stats:
                full = repo / rel_path
                line_count = 0
                if full.is_file():
                    raw = full.read_bytes()
                    if b'\x00' not in raw:
                        line_count = raw.count(b'\n') + (1 if raw and not raw.endswith(b'\n') else 0)
                stats[rel_path] = (line_count, 0)

    changed_files = sorted(stats.keys())
    added_lines = sum(v[0] for v in stats.values())
    deleted_lines = sum(v[1] for v in stats.values())
    total_lines = added_lines + deleted_lines
    net_lines = added_lines - deleted_lines

    new_files_set: set[str] = set(untracked)
    rc_a, out_a, _ = run_git(repo, 'diff', '--name-only', '--diff-filter=A', anchor)
    if rc_a == 0:
        new_files_set.update(p.strip() for p in out_a.splitlines() if p.strip())
    new_files = sorted(new_files_set)
    dep_manifest_touches = [p for p in changed_files if DEP_MANIFEST_RE.search(p) and stats[p][0] > 0]

    sensitive_hits = []
    for rel_path in changed_files:
        matched_cats = [cat for cat, pat in SENSITIVE_PATH_RULES if pat.search(rel_path)]
        if matched_cats:
            sensitive_hits.append({'path': rel_path, 'categories': matched_cats})

    exceeds_narrow = total_lines > max_pr_lines or len(changed_files) > max_pr_files
    large_files = scan_large_files(repo, max_file_lines)
    hotspots = scan_churn_hotspots(repo, churn_days, min_churn_touches)
    shotgun_commits = scan_shotgun_commits(repo, churn_days)
    worktrees = list_worktrees(repo)
    extra_worktrees = max(0, len(worktrees) - 1)

    # Objective factual signals only; risk tiering belongs to the human/agent judging semantic impact
    signal_flags = []
    if sensitive_hits:
        signal_flags.append('sensitive_paths_touched')
    if exceeds_narrow:
        signal_flags.append('wide_diff')
    if dep_manifest_touches:
        signal_flags.append('dependency_manifest_touched')
    if shotgun_commits:
        signal_flags.append('shotgun_history_present')
    if large_files:
        signal_flags.append('large_files_present')
    if hotspots:
        signal_flags.append('churn_hotspots_present')

    return {
        'schemaVersion': 'software-stewardship-audit/1',
        'generatedAt': utc_now(),
        'repoName': repo.name,
        'branch': branch,
        'headSha': head_sha,
        'baseRef': resolved_base,
        'signalFlags': signal_flags,
        'blastRadius': {
            'changedFileCount': len(changed_files),
            'addedLines': added_lines,
            'deletedLines': deleted_lines,
            'netLines': net_lines,
            'totalChangedLines': total_lines,
            'newFileCount': len(new_files),
            'newFiles': new_files,
            'dependencyManifestTouches': dep_manifest_touches,
            'dirtyEntries': dirty_count,
            'untrackedFiles': untracked,
            'exceedsNarrowLimit': exceeds_narrow,
            'limits': {'maxLines': max_pr_lines, 'maxFiles': max_pr_files},
            'files': [
                {'path': p, 'added': stats[p][0], 'deleted': stats[p][1]}
                for p in changed_files
            ],
            'sensitivePaths': sensitive_hits,
        },
        'architectureSignals': {
            'shotgunCommitCount': len(shotgun_commits),
            'shotgunCommits': shotgun_commits,
        },
        'largeFiles': large_files,
        'churnHotspots': hotspots,
        'worktrees': worktrees,
        'extraWorktreeCount': extra_worktrees,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Audit a Git repository for blast radius, hotspots, and hygiene.')
    parser.add_argument('--repo', required=True, help='Path to target Git repository')
    parser.add_argument('--base', default=None, help='Base git ref for diff comparison')
    parser.add_argument('--churn-days', type=int, default=30)
    parser.add_argument('--min-churn-touches', type=int, default=3)
    parser.add_argument('--max-pr-lines', type=int, default=400)
    parser.add_argument('--max-pr-files', type=int, default=15)
    parser.add_argument('--max-file-lines', type=int, default=500)
    parser.add_argument('--out', default=None, help='Optional output JSON path inside Space files/')
    args = parser.parse_args()

    try:
        result = audit_repo(
            Path(args.repo),
            base_ref=args.base,
            churn_days=args.churn_days,
            min_churn_touches=args.min_churn_touches,
            max_pr_lines=args.max_pr_lines,
            max_pr_files=args.max_pr_files,
            max_file_lines=args.max_file_lines,
        )
    except ValueError as err:
        print(json.dumps({'ok': False, 'error': str(err)}, indent=2), file=sys.stderr)
        return 1

    rendered = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding='utf-8')
    print(rendered, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
