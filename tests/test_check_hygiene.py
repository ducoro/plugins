import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('check_hygiene', ROOT / 'scripts/check_hygiene.py')
hygiene = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hygiene)


def git(cwd, *args, env=None, input_text=None):
    merged_env = os.environ.copy()
    for key in ('ALLOW_PUSH', 'HYGIENE_PATTERNS_FILE'):
        merged_env.pop(key, None)
    merged_env.update({
        'GIT_AUTHOR_NAME': 'Test User',
        'GIT_AUTHOR_EMAIL': 'test@example.com',
        'GIT_COMMITTER_NAME': 'Test User',
        'GIT_COMMITTER_EMAIL': 'test@example.com',
    })
    if env:
        merged_env.update(env)
    return subprocess.run(
        ['git', *args],
        cwd=cwd,
        env=merged_env,
        input=input_text,
        capture_output=True,
        text=True,
        encoding='utf-8',
        check=False,
    )


class HygieneCheckTest(unittest.TestCase):
    def test_current_repo_tracked_is_clean(self):
        findings = hygiene.check_tracked(ROOT, [])
        self.assertEqual(findings, [])

    def test_blocked_paths(self):
        for allowed in ('.docs/.gitkeep', './.rules/.gitkeep', '.plans/.gitkeep', '.rules/.gitkeep', 'plugins/demo/plugin.json'):
            with self.subTest(allowed=allowed):
                self.assertIsNone(hygiene.check_blocked_path(allowed))

        for blocked in (
            '.docs/design.md',
            './.plans/roadmap.md',
            '.plans/roadmap.md',
            '.rules/README.md',
            '.rules/sub/rule.md',
            '.env',
            '.env.local',
            'nested/.env.production',
            '.DS_Store',
            'scripts/__pycache__/validate.cpython-312.pyc',
        ):
            with self.subTest(blocked=blocked):
                self.assertIsNotNone(hygiene.check_blocked_path(blocked))

    def test_builtin_content_patterns(self):
        safe_lines = [
            (1, 'Authorization: Bearer ${SERVICE_API_TOKEN}'),
            (2, 'path: ./plugins/starter-template'),
            (3, 'https://example.com/docs/users/guide'),
        ]
        self.assertEqual(hygiene.scan_lines('sample.md', safe_lines, []), [])

        bad_samples = [
            '-----BEGIN ' + 'RSA PRIVATE KEY-----',
            'ghp_' + 'A' * 24,
            'github_pat_' + 'a' * 24,
            'sk-' + 'live-' + 'a' * 24,
            'AKIA' + '1234567890ABCDEF',
            'AIza' + 'a' * 35,
            'xoxb-' + '1234567890-abcdef',
            '/Users/' + 'alice/workspace/repo',
            '/home/' + 'bob/project',
            'C:\\Users\\' + 'carol\\repo',
            'file://' + '/tmp/local.md',
        ]
        for sample in bad_samples:
            with self.subTest(sample=sample[:16]):
                findings = hygiene.scan_lines('sample.md', [(1, sample)], [])
                self.assertTrue(findings, f'expected violation for {sample}')

    def test_custom_patterns_file_and_redaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(hygiene.load_custom_patterns(root), [])

            patterns_path = root / '.rules/hygiene-patterns.txt'
            patterns_path.parent.mkdir(parents=True)
            secret_word = 'Project' + 'Falcon99'
            patterns_path.write_text(
                f'# comment\n\n{secret_word}\nre:alpha-\\d{{3}}\n',
                encoding='utf-8',
            )
            custom = hygiene.load_custom_patterns(root)
            self.assertEqual(len(custom), 2)

            findings = hygiene.scan_lines(
                'doc.md',
                [(4, f'mentions {secret_word.lower()} here'), (9, 'code ALPHA-404')],
                custom,
            )
            self.assertEqual(len(findings), 2)
            joined = '\n'.join(findings)
            self.assertIn('custom pattern (line 3)', joined)
            self.assertIn('custom pattern (line 4)', joined)
            self.assertNotIn(secret_word.lower(), joined.lower())
            self.assertNotIn('alpha-404', joined.lower())

    def test_git_staged_commit_msg_and_pre_push_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            remote = tmp_path / 'remote.git'
            repo = tmp_path / 'repo'
            self.assertEqual(git(tmp_path, 'init', '--bare', str(remote)).returncode, 0)
            self.assertEqual(git(tmp_path, 'init', str(repo)).returncode, 0)
            self.assertEqual(git(repo, 'remote', 'add', 'origin', str(remote)).returncode, 0)

            # Copy minimal repository files needed by scripts/validate.py and hooks.
            for name in ['marketplace.json', 'README.md', 'README.zh-CN.md', 'LICENSE', '.gitignore']:
                shutil.copy2(ROOT / name, repo / name)
            for directory in ['plugins', 'scripts', '.githooks']:
                shutil.copytree(ROOT / directory, repo / directory)
            for placeholder in ['.docs/.gitkeep', '.plans/.gitkeep', '.rules/.gitkeep']:
                target = repo / placeholder
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('', encoding='utf-8')
            smoke_test = repo / 'tests/test_smoke.py'
            smoke_test.parent.mkdir(parents=True, exist_ok=True)
            smoke_test.write_text(
                'import unittest\n\nclass Smoke(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n',
                encoding='utf-8',
            )

            self.assertEqual(git(repo, 'add', '.').returncode, 0)
            self.assertEqual(git(repo, 'commit', '-m', 'chore: initial commit').returncode, 0)

            # 1. Staged check blocks force-added local workspace file.
            draft = repo / '.plans/draft.md'
            draft.write_text('local note\n', encoding='utf-8')
            self.assertEqual(git(repo, 'add', '-f', '.plans/draft.md').returncode, 0)
            self.assertTrue(hygiene.check_staged(repo, []))
            self.assertEqual(git(repo, 'reset', 'HEAD', '.plans/draft.md').returncode, 0)

            # 2. Staged check blocks absolute user path in a tracked file.
            note = repo / 'README.md'
            original_readme = note.read_text(encoding='utf-8')
            note.write_text(original_readme + '\nSee /Users/' + 'alice/private\n', encoding='utf-8')
            self.assertEqual(git(repo, 'add', 'README.md').returncode, 0)
            self.assertTrue(hygiene.check_staged(repo, []))
            note.write_text(original_readme, encoding='utf-8')
            self.assertEqual(git(repo, 'reset', 'HEAD', 'README.md').returncode, 0)

            # 3. Commit message check blocks custom pattern and allows clean message.
            patterns_file = repo / '.rules/hygiene-patterns.txt'
            patterns_file.write_text('Codename' + 'Zephyr\n', encoding='utf-8')
            custom = hygiene.load_custom_patterns(repo)
            bad_msg = repo / 'bad_msg.txt'
            bad_msg.write_text('docs: mention Codename' + 'Zephyr\n# comment\n', encoding='utf-8')
            self.assertTrue(hygiene.check_commit_msg_file(bad_msg, custom))
            good_msg = repo / 'good_msg.txt'
            good_msg.write_text('docs: update catalog notes\n# Codename' + 'Zephyr in comment\n', encoding='utf-8')
            self.assertEqual(hygiene.check_commit_msg_file(good_msg, custom), [])
            bad_msg.unlink()
            good_msg.unlink()

            # 4. Pre-push hook blocks non-interactive push without ALLOW_PUSH=1, allows with ALLOW_PUSH=1.
            self.assertEqual(git(repo, 'config', 'core.hooksPath', '.githooks').returncode, 0)
            branch = git(repo, 'rev-parse', '--abbrev-ref', 'HEAD').stdout.strip()
            blocked_push = git(repo, 'push', 'origin', branch)
            self.assertNotEqual(blocked_push.returncode, 0)
            self.assertIn('ALLOW_PUSH=1', blocked_push.stderr)

            allowed_push = git(repo, 'push', 'origin', branch, env={'ALLOW_PUSH': '1'})
            self.assertEqual(allowed_push.returncode, 0, allowed_push.stderr)

            # 5. Pre-push check still blocks commits containing violations even with ALLOW_PUSH=1.
            note.write_text(original_readme + '\nRef: Codename' + 'Zephyr\n', encoding='utf-8')
            self.assertEqual(git(repo, 'add', 'README.md').returncode, 0)
            self.assertEqual(git(repo, 'commit', '--no-verify', '-m', 'docs: add ref').returncode, 0)
            blocked_dirty_push = git(repo, 'push', 'origin', branch, env={'ALLOW_PUSH': '1'})
            self.assertNotEqual(blocked_dirty_push.returncode, 0)
            self.assertIn('Hygiene check failed', blocked_dirty_push.stderr)


if __name__ == '__main__':
    unittest.main()
