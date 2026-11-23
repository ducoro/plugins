"""Check repository hygiene for staged changes, commit messages, pushes, and tracked files."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

ALLOWED_KEEP_FILES = {
    '.docs/.gitkeep',
    '.plans/.gitkeep',
    '.rules/.gitkeep',
}
BLOCKED_LOCAL_DIRS = ('.docs', '.plans', '.rules')
DEFAULT_CUSTOM_PATTERNS_REL = Path('.rules/hygiene-patterns.txt')
ZERO_SHA = '0' * 40

BUILTIN_PATTERNS = [
    ('private key block', re.compile(r'-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----')),
    ('GitHub personal access token', re.compile(r'\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b')),
    ('GitHub fine-grained token', re.compile(r'\bgithub_pat_[A-Za-z0-9_]{20,}\b')),
    ('API secret key', re.compile(r'\bsk-(?:ant-api\d+-|proj-|live-|test-)?[A-Za-z0-9_-]{20,}\b')),
    ('AWS access key ID', re.compile(r'\b(?:AKIA|ASIA)[0-9A-Z]{16}\b')),
    ('Google API key', re.compile(r'\bAIza[0-9A-Za-z_-]{35}\b')),
    ('Slack token', re.compile(r'\bxox[baprs]-[0-9A-Za-z-]{10,}\b')),
    ('macOS absolute user path', re.compile(r'(?<![A-Za-z0-9_])/Users/[A-Za-z0-9._-]+/')),
    ('Linux absolute user path', re.compile(r'(?<![A-Za-z0-9_])/home/[A-Za-z0-9._-]+/')),
    ('Windows absolute user path', re.compile(r'[A-Za-z]:\\Users\\[A-Za-z0-9._-]+\\')),
    ('local file URI', re.compile(r'file:' + r'///')),
]


def run_git(root, args):
    result = subprocess.run(
        ['git', *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def normalize_rel_path(rel_path):
    norm = rel_path.replace('\\', '/')
    while norm.startswith('./'):
        norm = norm[2:]
    return norm.lstrip('/')


def check_blocked_path(rel_path):
    norm = normalize_rel_path(rel_path)
    parts = norm.split('/')
    if parts[0] in BLOCKED_LOCAL_DIRS and norm not in ALLOWED_KEEP_FILES:
        return f'{norm}: local workspace file must not be committed'
    name = parts[-1]
    if name == '.env' or name.startswith('.env.'):
        return f'{norm}: environment file must not be committed'
    if name == '.DS_Store' or '__pycache__' in parts or name.endswith(('.pyc', '.pyo')):
        return f'{norm}: generated or OS metadata file must not be committed'
    return None


def load_custom_patterns(root, patterns_file=None):
    if patterns_file is not None:
        path = Path(patterns_file)
    else:
        env_path = os.environ.get('HYGIENE_PATTERNS_FILE', '').strip()
        path = Path(env_path) if env_path else (Path(root) / DEFAULT_CUSTOM_PATTERNS_REL)
    if not path.is_file():
        return []

    compiled = []
    for lineno, raw in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
        entry = raw.strip()
        if not entry or entry.startswith('#'):
            continue
        label = f'custom pattern (line {lineno})'
        if entry.startswith('re:'):
            expr = entry[3:].strip()
            if not expr:
                continue
            try:
                regex = re.compile(expr, re.IGNORECASE)
            except re.error as error:
                raise ValueError(f'{path}:{lineno}: invalid regex: {error}') from error
        else:
            regex = re.compile(re.escape(entry), re.IGNORECASE)
        compiled.append((label, regex))
    return compiled


def scan_lines(source_label, numbered_lines, custom_patterns):
    findings = []
    all_patterns = [*BUILTIN_PATTERNS, *custom_patterns]
    for lineno, text in numbered_lines:
        for label, regex in all_patterns:
            if regex.search(text):
                location = f'{source_label}:{lineno}' if lineno is not None else source_label
                findings.append(f'{location}: matched {label}')
    return findings


def extract_added_lines_from_diff(diff_text):
    """Parse unified=0 git diff output into (rel_path, lineno, added_line) tuples."""
    results = []
    current_file = None
    current_line = None
    hunk_re = re.compile(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@')

    for line in diff_text.splitlines():
        if line.startswith('+++ b/'):
            current_file = line[6:]
            current_line = None
            continue
        if line.startswith('+++ /dev/null'):
            current_file = None
            current_line = None
            continue
        if line.startswith('@@ '):
            match = hunk_re.match(line)
            current_line = int(match.group(1)) if match else None
            continue
        if current_file is None or current_line is None:
            continue
        if line.startswith('+') and not line.startswith('+++'):
            results.append((current_file, current_line, line[1:]))
            current_line += 1
    return results


def parse_name_status(output):
    paths = []
    for line in output.splitlines():
        if not line.strip():
            continue
        fields = line.split('\t')
        status = fields[0]
        if status.startswith('D'):
            continue
        if status.startswith(('R', 'C')) and len(fields) >= 3:
            paths.append(fields[2])
        elif len(fields) >= 2:
            paths.append(fields[1])
    return paths


def check_staged(root, custom_patterns):
    findings = []
    status_out = run_git(root, ['diff', '--cached', '--name-status'])
    for rel_path in parse_name_status(status_out):
        blocked = check_blocked_path(rel_path)
        if blocked:
            findings.append(blocked)

    diff_out = run_git(root, ['diff', '--cached', '--unified=0', '--no-color'])
    for rel_path, lineno, text in extract_added_lines_from_diff(diff_out):
        findings.extend(scan_lines(rel_path, [(lineno, text)], custom_patterns))
    return findings


def check_commit_msg_text(message_text, custom_patterns, label='commit message'):
    numbered = [
        (idx, line)
        for idx, line in enumerate(message_text.splitlines(), start=1)
        if not line.lstrip().startswith('#')
    ]
    return scan_lines(label, numbered, custom_patterns)


def check_commit_msg_file(msg_path, custom_patterns):
    text = Path(msg_path).read_text(encoding='utf-8', errors='replace')
    return check_commit_msg_text(text, custom_patterns, label='commit message')


def check_tracked(root, custom_patterns):
    root = Path(root)
    findings = []
    tracked = run_git(root, ['ls-files']).splitlines()
    for rel_path in tracked:
        if not rel_path:
            continue
        blocked = check_blocked_path(rel_path)
        if blocked:
            findings.append(blocked)
        file_path = root / rel_path
        if not file_path.is_file():
            continue
        raw = file_path.read_bytes()
        if b'\x00' in raw:
            continue
        text = raw.decode('utf-8', errors='replace')
        numbered = list(enumerate(text.splitlines(), start=1))
        findings.extend(scan_lines(rel_path, numbered, custom_patterns))
    return findings


def commits_for_push_lines(root, ref_lines):
    commits = []
    seen = set()
    for line in ref_lines:
        parts = line.strip().split()
        if len(parts) != 4:
            continue
        _, local_sha, _, remote_sha = parts
        if local_sha == ZERO_SHA:
            continue
        if remote_sha == ZERO_SHA:
            rev_args = ['rev-list', local_sha, '--not', '--remotes']
        else:
            rev_args = ['rev-list', f'{remote_sha}..{local_sha}']
        out = run_git(root, rev_args)
        for sha in out.splitlines():
            if sha and sha not in seen:
                seen.add(sha)
                commits.append(sha)
    return commits


def check_commits(root, commit_shas, custom_patterns):
    findings = []
    for sha in commit_shas:
        short = sha[:8]
        msg = run_git(root, ['show', '-s', '--format=%B', sha])
        findings.extend(check_commit_msg_text(msg, custom_patterns, label=f'commit {short} message'))

        name_status = run_git(root, ['diff-tree', '--no-commit-id', '--name-status', '-r', '--root', sha])
        for rel_path in parse_name_status(name_status):
            blocked = check_blocked_path(rel_path)
            if blocked:
                findings.append(f'commit {short}: {blocked}')

        diff_out = run_git(root, ['diff-tree', '--no-commit-id', '-p', '--unified=0', '--no-color', '--root', sha])
        for rel_path, lineno, text in extract_added_lines_from_diff(diff_out):
            findings.extend(scan_lines(f'commit {short} {rel_path}', [(lineno, text)], custom_patterns))
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description='Check repository hygiene rules.')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--staged', action='store_true', help='Check staged files and diff.')
    mode.add_argument('--commit-msg', metavar='PATH', help='Check a commit message file.')
    mode.add_argument('--tracked', action='store_true', help='Check all tracked files.')
    mode.add_argument('--pre-push', action='store_true', help='Check commits read from pre-push stdin.')
    parser.add_argument('--root', default=None, help='Repository root directory.')
    parser.add_argument('--patterns-file', default=None, help='Optional custom patterns file.')
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[1]

    try:
        custom_patterns = load_custom_patterns(root, args.patterns_file)
        if args.staged:
            findings = check_staged(root, custom_patterns)
        elif args.commit_msg:
            findings = check_commit_msg_file(args.commit_msg, custom_patterns)
        elif args.tracked:
            findings = check_tracked(root, custom_patterns)
        else:
            ref_lines = sys.stdin.read().splitlines()
            commits = commits_for_push_lines(root, ref_lines)
            findings = check_commits(root, commits, custom_patterns)
    except (OSError, RuntimeError, ValueError) as error:
        print(f'Hygiene check error: {error}', file=sys.stderr)
        return 1

    if findings:
        print('Hygiene check failed:', file=sys.stderr)
        for item in findings:
            print(f'  - {item}', file=sys.stderr)
        return 1

    print('Hygiene check passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
