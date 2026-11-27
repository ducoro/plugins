"""Formal verification (Class A exhaustive + Class B BFS state machine + real Git/HTTP roundtrip)
for the software-stewardship plugin."""
from __future__ import annotations

from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'plugins/software-stewardship/scripts'


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


repo_audit = load_module('ss_repo_audit', SCRIPTS / 'repo_audit.py')
supply_chain = load_module('ss_supply_chain', SCRIPTS / 'supply_chain_check.py')
change_gate = load_module('ss_change_gate', SCRIPTS / 'change_gate.py')
repo_monitor = load_module('ss_repo_monitor', SCRIPTS / 'repo_monitor.py')
build_boards = load_module('ss_build_boards', SCRIPTS / 'build_boards.py')


GIT_ENV_STRIP = ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR', 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES')


def git(repo: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if k not in GIT_ENV_STRIP}
    proc = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True, env=env, check=True)
    return proc.stdout.strip()


def init_sample_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, 'init', '-b', 'main')
    git(repo, 'config', 'user.email', 'steward@example.com')
    git(repo, 'config', 'user.name', 'Steward Bot')
    (repo / 'src').mkdir()
    (repo / 'tests').mkdir()
    (repo / 'src/app.py').write_text('def add(a, b):\n    return a + b\n', encoding='utf-8')
    (repo / 'tests/test_app.py').write_text(
        'from src.app import add\n\ndef test_add():\n    assert add(1, 2) == 3\n',
        encoding='utf-8',
    )
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'chore: initial commit')


class _MockExternalHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002
        return

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get('Content-Length', '0'))
        body = json.loads(self.rfile.read(length).decode('utf-8'))
        results = []
        for q in body.get('queries', []):
            pkg = (q.get('package') or {}).get('name', '')
            ver = q.get('version', '')
            if pkg == 'lodash' and ver == '4.17.15':
                results.append({'vulns': [{'id': 'GHSA-jf85-cpcp-j695', 'modified': '2026-01-01T00:00:00Z'}]})
            elif pkg == 'urllib3' and ver == '1.25.8':
                results.append({'vulns': [{'id': 'PYSEC-2021-108', 'modified': '2026-01-01T00:00:00Z'}]})
            else:
                results.append({})
        raw = json.dumps({'results': results}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):  # noqa: N802
        if self.path.startswith('/repos/acme/demo/pulls'):
            payload = [{'number': 17, 'title': 'Fix token refresh', 'user': {'login': 'dev1'}, 'draft': False, 'html_url': 'https://github.com/acme/demo/pull/17', 'updated_at': '2026-11-27T01:00:00Z'}]
        elif self.path.startswith('/repos/acme/demo/actions/runs'):
            payload = {'workflow_runs': [{'id': 901, 'name': 'CI', 'status': 'completed', 'conclusion': 'failure', 'head_branch': 'main', 'html_url': 'https://github.com/acme/demo/actions/runs/901', 'updated_at': '2026-11-27T01:05:00Z'}]}
        else:
            self.send_response(404)
            self.end_headers()
            return
        raw = json.dumps(payload).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class SoftwareStewardshipFormalTest(unittest.TestCase):
    def test_real_git_audit_supply_chain_monitor_and_boards_end_to_end(self):
        """Real Git repository + local HTTP OSV/GitHub roundtrip + clean target repo + board projection."""
        server = ThreadingHTTPServer(('127.0.0.1', 0), _MockExternalHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tdir = Path(tmp)
                repo = tdir / 'demo-repo'
                state_dir = tdir / 'space-files/stewardship'
                init_sample_repo(repo)

                # Create 30-day churn hotspot + revert commit + large file
                for idx in range(3):
                    (repo / 'src/app.py').write_text(f'def add(a, b):\n    # touch {idx}\n    return a + b\n', encoding='utf-8')
                    git(repo, 'commit', '-am', f'feat: refine add {idx}')
                (repo / 'src/app.py').write_text('def add(a, b):\n    return a + b\n', encoding='utf-8')
                git(repo, 'commit', '-am', 'revert: roll back touch')

                # Add real multi-ecosystem lockfiles + copyleft dependency
                (repo / 'package-lock.json').write_text(json.dumps({
                    'name': 'demo',
                    'lockfileVersion': 3,
                    'packages': {
                        '': {'name': 'demo', 'version': '1.0.0'},
                        'node_modules/lodash': {'version': '4.17.15', 'license': 'MIT'},
                        'node_modules/gpl-lib': {'version': '2.0.0', 'license': 'AGPL-3.0'},
                    },
                }), encoding='utf-8')
                (repo / 'requirements.txt').write_text('urllib3==1.25.8\n', encoding='utf-8')
                (repo / 'Cargo.lock').write_text('[[package]]\nname = "serde"\nversion = "1.0.200"\n', encoding='utf-8')
                (repo / 'go.mod').write_text('module example.com/demo\n\nrequire (\n\tgolang.org/x/net v0.25.0\n)\n', encoding='utf-8')
                (repo / 'src/big.py').write_text('\n'.join(f'x_{i} = {i}' for i in range(520)) + '\n', encoding='utf-8')
                git(repo, 'add', '.')
                git(repo, 'commit', '-m', 'chore: add lockfiles and big file')

                # Create a cross-module shotgun commit touching 4 distinct module buckets
                for mod in ('auth', 'billing', 'ui', 'storage'):
                    (repo / 'src' / mod).mkdir(parents=True, exist_ok=True)
                    (repo / 'src' / mod / 'mod.py').write_text(f'MOD = "{mod}"\n', encoding='utf-8')
                git(repo, 'add', '.')
                git(repo, 'commit', '-m', 'feat: cross-layer shotgun change')

                # Feature branch with sensitive auth change + new file + dependency manifest touch
                git(repo, 'checkout', '-b', 'feat/auth-hardening')
                (repo / 'src/auth').mkdir(parents=True, exist_ok=True)
                (repo / 'src/auth/jwt.py').write_text('def verify_token(t):\n    return bool(t)\n', encoding='utf-8')
                (repo / 'requirements.txt').write_text('urllib3==1.25.8\nrequests==2.32.3\n', encoding='utf-8')
                git(repo, 'add', '.')
                git(repo, 'commit', '-m', 'feat(auth): add token verifier')

                # 1. Real Git audit
                audit = repo_audit.audit_repo(repo, base_ref='main', max_file_lines=500)
                state_dir.mkdir(parents=True, exist_ok=True)
                (state_dir / 'audit.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
                self.assertIn('sensitive_paths_touched', audit['signalFlags'])
                self.assertIn('dependency_manifest_touched', audit['signalFlags'])
                self.assertIn('shotgun_history_present', audit['signalFlags'])
                self.assertNotIn('riskLevel', audit)
                self.assertTrue(any(s['path'] == 'src/auth/jwt.py' for s in audit['blastRadius']['sensitivePaths']))
                self.assertIn('src/auth/jwt.py', audit['blastRadius']['newFiles'])
                self.assertGreater(audit['blastRadius']['netLines'], 0)
                self.assertIn('requirements.txt', audit['blastRadius']['dependencyManifestTouches'])
                self.assertGreaterEqual(audit['architectureSignals']['shotgunCommitCount'], 1)
                self.assertTrue(any(f['path'] == 'src/big.py' for f in audit['largeFiles']))
                self.assertTrue(any(h['path'] == 'src/app.py' and h['touches'] >= 4 for h in audit['churnHotspots']))

                # 2. Supply chain check (live mock OSV + offline honest check)
                sc_live = supply_chain.run_supply_chain_check(repo, osv_url=f'http://127.0.0.1:{port}/v1/querybatch')
                (state_dir / 'supply-chain.json').write_text(json.dumps(sc_live, indent=2), encoding='utf-8')
                self.assertEqual(sc_live['osvStatus'], 'ok')
                self.assertEqual(sc_live['dependencyCount'], 6)
                self.assertEqual(sc_live['vulnerabilityCount'], 2)
                self.assertEqual(sc_live['licenseAlertCount'], 1)

                sc_off = supply_chain.run_supply_chain_check(repo, offline=True)
                self.assertEqual(sc_off['osvStatus'], 'skipped_offline')
                self.assertEqual(sc_off['vulnerabilityCount'], 0)

                # 3. Record real passing evidence + approve + verify release
                rc_ev, ev_payload = change_gate.cmd_record_evidence(
                    repo, state_dir, f'{sys.executable} -c "import src.app; assert src.app.add(1,2)==3"',
                    base='main', run_now=True,
                )
                self.assertEqual(rc_ev, 0, ev_payload)
                rc_app, _ = change_gate.cmd_approve(repo, state_dir, 'release', 'commander', 'main')
                self.assertEqual(rc_app, 0)
                rc_ver, ver_payload = change_gate.cmd_verify_release(repo, state_dir, 'release', 'main')
                self.assertEqual(rc_ver, 0, ver_payload)

                # 4. Quiet pulse monitor (initial -> no_material_change -> material_change)
                p1 = repo_monitor.monitor_repo(repo, state_dir, github_repo='acme/demo', api_base=f'http://127.0.0.1:{port}')
                self.assertEqual(p1['outcome'], 'initial_baseline')
                self.assertEqual(p1['remote']['failingCiCount'], 1)
                self.assertEqual(len(p1['remote']['pullRequests']), 1)

                p2 = repo_monitor.monitor_repo(repo, state_dir, github_repo='acme/demo', api_base=f'http://127.0.0.1:{port}')
                self.assertEqual(p2['outcome'], 'no_material_change')

                # Mutating repo creates a material change and invalidates approval lock
                (repo / 'src/auth/jwt.py').write_text('def verify_token(t):\n    return len(t) > 5\n', encoding='utf-8')
                rc_ver_after, ver_after = change_gate.cmd_verify_release(repo, state_dir, 'release', 'main')
                self.assertNotEqual(rc_ver_after, 0)
                self.assertIn('tampered_after_approval', ver_after['reasons'])

                # 5. Project both boards and verify target repo stayed 100% free of plugin state files
                d_data = build_boards.project_board(state_dir, 'delivery-board', tdir / 'boards/delivery', overwrite_templates=True)
                h_data = build_boards.project_board(state_dir, 'health-board', tdir / 'boards/health', overwrite_templates=True)
                delivery = json.loads(d_data.read_text(encoding='utf-8'))
                health = json.loads(h_data.read_text(encoding='utf-8'))
                self.assertEqual(delivery['approvals'][0]['status'], 'stale_tampered')
                self.assertEqual(health['summary']['vulnerabilityCount'], 2)
                self.assertEqual(health['summary']['licenseAlertCount'], 1)
                self.assertGreaterEqual(health['summary']['shotgunCommitCount'], 1)
                self.assertTrue(any(a['category'] == 'shotgun_surgery' for a in health['alerts']))
                self.assertFalse((repo / 'stewardship').exists())
                self.assertFalse((repo / 'gate-state.json').exists())
        finally:
            server.shutdown()
            server.server_close()

    def test_class_a_exhaustive_diff_blocker_combinations(self):
        """Class A formal proof: enumerate all 2^5 = 32 combinations of objective diff blockers."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            init_sample_repo(repo)
            git(repo, 'checkout', '-b', 'feat/matrix')
            checked = 0

            for secret, local_path, skip_test, bypass_chk, del_assert in itertools.product([False, True], repeat=5):
                checked += 1
                git(repo, 'reset', '--hard', 'main')
                git(repo, 'clean', '-fd')

                lines = ['def add(a, b):']
                if secret:
                    fake_gh = 'ghp' + '_' + '1234567890abcdefghij1234567890abcd'
                    lines.append(f'    tok = "{fake_gh}"')
                if local_path:
                    fake_home = '/Us' + 'ers/alice/private/key.pem'
                    lines.append(f'    p = "{fake_home}"')
                if bypass_chk:
                    lines.append('    x = 1  # noqa')
                lines.append('    return a + b')
                (repo / 'src/app.py').write_text('\n'.join(lines) + '\n', encoding='utf-8')

                test_lines = ['from src.app import add', '']
                if skip_test:
                    test_lines.append('@unittest.skip("temp")')
                test_lines.append('def test_add():')
                if del_assert:
                    test_lines.append('    add(1, 2)')
                else:
                    test_lines.append('    assert add(1, 2) == 3')
                (repo / 'tests/test_app.py').write_text('\n'.join(test_lines) + '\n', encoding='utf-8')

                res = change_gate.scan_diff_blockers(repo, base='main')
                expected_ok = not (secret or local_path or skip_test or bypass_chk or del_assert)
                self.assertEqual(res['ok'], expected_ok, f'Mismatch for {(secret, local_path, skip_test, bypass_chk, del_assert)}: {res}')

                found_rules = {b['rule'] for b in res['blockers']}
                if secret:
                    self.assertIn('github_token', found_rules)
                if local_path:
                    self.assertIn('local_path_leak', found_rules)
                if skip_test:
                    self.assertIn('test_skip_added', found_rules)
                if bypass_chk:
                    self.assertIn('check_bypass_added', found_rules)
                if del_assert:
                    self.assertIn('assertions_deleted', found_rules)

            self.assertEqual(checked, 32)

    def test_class_b_bfs_release_gate_state_machine_and_fault_injection(self):
        """Class B formal proof: BFS-explore release gate transitions on a real Git repo and prove zero unsafe releases."""
        # Abstract state: (code_ver: 0|1, has_blocker: bool, ev_ver: -1|0|1, app_ver: -1|0|1)
        # Every transition executes the real change_gate functions and checks the invariant:
        # verify_release() == ok  IFF  (not has_blocker) and (ev_ver == code_ver) and (app_ver == code_ver)
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            state_dir = Path(tmp) / 'state'
            init_sample_repo(repo)
            git(repo, 'checkout', '-b', 'feat/bfs')

            def apply_repo_state(code_ver: int, has_blocker: bool) -> None:
                body = f'def add(a, b):\n    return a + b + {code_ver}\n'
                if has_blocker:
                    fake_aws = 'AKIA' + 'IOSFODNN7EXAMPLE'
                    body += f'token = "{fake_aws}"\n'
                (repo / 'src/app.py').write_text(body, encoding='utf-8')

            def reset_gate_to(code_ver: int, has_blocker: bool, ev_ver: int, app_ver: int) -> None:
                if (state_dir / 'gate-state.json').exists():
                    (state_dir / 'gate-state.json').unlink()
                if ev_ver != -1:
                    apply_repo_state(ev_ver, False)
                    change_gate.cmd_record_evidence(repo, state_dir, 'pytest', base='main', exit_code=0)
                if app_ver != -1:
                    apply_repo_state(app_ver, False)
                    rc, _ = change_gate.cmd_approve(repo, state_dir, 'release', 'human', 'main')
                    self.assertEqual(rc, 0)
                apply_repo_state(code_ver, has_blocker)

            start = (0, False, -1, -1)
            visited = {start}
            queue = deque([start])
            transitions_checked = 0

            while queue:
                st = queue.popleft()
                code_ver, has_blocker, ev_ver, app_ver = st
                reset_gate_to(*st)

                # Invariant check at every reachable state
                rc, payload = change_gate.cmd_verify_release(repo, state_dir, 'release', 'main')
                expected_pass = (not has_blocker) and (ev_ver == code_ver) and (app_ver == code_ver)
                self.assertEqual(rc == 0, expected_pass, f'State {st} violated invariant: {payload}')
                self.assertEqual(payload['ok'], expected_pass)

                # Enumerate actions
                next_states = []
                # 1. Record passing evidence on current clean state
                if not has_blocker:
                    next_states.append((code_ver, has_blocker, code_ver, app_ver))
                # 2. Approve on current state (succeeds only if not has_blocker)
                if not has_blocker:
                    next_states.append((code_ver, has_blocker, ev_ver, code_ver))
                # 3. Edit code (flips code_ver 0 <-> 1)
                next_states.append((1 - code_ver, has_blocker, ev_ver, app_ver))
                # 4. Toggle blocker
                next_states.append((code_ver, not has_blocker, ev_ver, app_ver))

                for nxt in next_states:
                    transitions_checked += 1
                    if nxt not in visited:
                        visited.add(nxt)
                        queue.append(nxt)

            self.assertEqual(len(visited), 36)
            self.assertGreater(transitions_checked, 100)

            # Fault injection: tampering approval diffHash directly in state file must immediately fail verify_release
            reset_gate_to(0, False, 0, 0)
            rc_ok, _ = change_gate.cmd_verify_release(repo, state_dir, 'release', 'main')
            self.assertEqual(rc_ok, 0)
            st_file = state_dir / 'gate-state.json'
            corrupted = json.loads(st_file.read_text(encoding='utf-8'))
            corrupted['approvals']['release']['diffHash'] = '0000000000000000'
            st_file.write_text(json.dumps(corrupted), encoding='utf-8')
            rc_bad, bad_payload = change_gate.cmd_verify_release(repo, state_dir, 'release', 'main')
            self.assertNotEqual(rc_bad, 0)
            self.assertIn('tampered_after_approval', bad_payload['reasons'])

    def test_typed_evidence_fault_injection_red_and_risk_tiered_review_gate(self):
        """Prove fault-injection-red requires non-zero exit and medium/high risk enforces independent-review clearance."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            state_dir = Path(tmp) / 'state'
            init_sample_repo(repo)
            git(repo, 'checkout', '-b', 'feat/risk-gate')
            (repo / 'src/app.py').write_text('def add(a, b):\n    return a + b\n# hardened\n', encoding='utf-8')

            # Fault injection: exit 0 means the broken variant was NOT caught -> must fail (rc != 0, passed=False)
            rc_fake_red, fake_red = change_gate.cmd_record_evidence(
                repo, state_dir, 'pytest', base='main', exit_code=0, kind='fault-injection-red',
            )
            self.assertNotEqual(rc_fake_red, 0)
            self.assertFalse(fake_red['evidence']['passed'])

            # Fault injection: non-zero exit proves the guard actually fails red -> passes (rc == 0, passed=True)
            rc_real_red, real_red = change_gate.cmd_record_evidence(
                repo, state_dir, 'pytest', base='main', exit_code=1, kind='fault-injection-red',
            )
            self.assertEqual(rc_real_red, 0)
            self.assertTrue(real_red['evidence']['passed'])

            # Fault-injection-red alone must NOT satisfy verification evidence requirement
            rc_app, _ = change_gate.cmd_approve(repo, state_dir, 'release', 'human', 'main', risk='high')
            self.assertEqual(rc_app, 0)
            rc_v1, v1 = change_gate.cmd_verify_release(repo, state_dir, 'release', 'main', risk='low')
            self.assertNotEqual(rc_v1, 0)
            # Attempting to downgrade high approval to low at verify time must keep effectiveRisk == high
            self.assertEqual(v1['effectiveRisk'], 'high')
            self.assertIn('missing_passing_evidence', v1['reasons'])
            self.assertIn('missing_independent_review', v1['reasons'])

            # Adding verification alone still fails high-risk gate without independent-review
            rc_ev, _ = change_gate.cmd_record_evidence(
                repo, state_dir, 'pytest', base='main', exit_code=0, kind='verification',
            )
            self.assertEqual(rc_ev, 0)
            rc_v2, v2 = change_gate.cmd_verify_release(repo, state_dir, 'release', 'main', risk='high')
            self.assertNotEqual(rc_v2, 0)
            self.assertEqual(v2['reasons'], ['missing_independent_review'])

            # Recording independent-review clearance unlocks release
            rc_rev, _ = change_gate.cmd_record_evidence(
                repo, state_dir, 'blind-review:6-lenses', base='main', exit_code=0, kind='independent-review',
            )
            self.assertEqual(rc_rev, 0)
            rc_v3, v3 = change_gate.cmd_verify_release(repo, state_dir, 'release', 'main', risk='high')
            self.assertEqual(rc_v3, 0, v3)
            self.assertEqual(v3['matchingReviewCount'], 1)

            # Mutating one byte invalidates both approval and independent-review clearance
            (repo / 'src/app.py').write_text('def add(a, b):\n    return a + b\n# sneaky edit\n', encoding='utf-8')
            rc_v4, v4 = change_gate.cmd_verify_release(repo, state_dir, 'release', 'main', risk='high')
            self.assertNotEqual(rc_v4, 0)
            self.assertIn('tampered_after_approval', v4['reasons'])
            self.assertIn('missing_independent_review', v4['reasons'])

            # Intentional dead-guard pruning requires explicit opt-in at BOTH approve and verify-release
            (repo / 'tests/test_app.py').write_text('from src.app import add\n\ndef test_add():\n    add(1, 2)\n', encoding='utf-8')
            rc_prune_blocked, _ = change_gate.cmd_approve(repo, state_dir, 'release', 'human', 'main', risk='low')
            self.assertNotEqual(rc_prune_blocked, 0)
            rc_ev2, _ = change_gate.cmd_record_evidence(repo, state_dir, 'pytest', base='main', exit_code=0, kind='formal-check')
            self.assertEqual(rc_ev2, 0)
            rc_prune_app, _ = change_gate.cmd_approve(
                repo, state_dir, 'release', 'human', 'main', risk='low', allow_assertion_pruning=True,
            )
            self.assertEqual(rc_prune_app, 0)
            # Without --allow-assertion-pruning at verify time, still blocked
            rc_prune_v_no, _ = change_gate.cmd_verify_release(repo, state_dir, 'release', 'main', risk='low')
            self.assertNotEqual(rc_prune_v_no, 0)
            # With explicit opt-in matching human approval, succeeds
            rc_prune_v_ok, v_ok = change_gate.cmd_verify_release(
                repo, state_dir, 'release', 'main', risk='low', allow_assertion_pruning=True,
            )
            self.assertEqual(rc_prune_v_ok, 0, v_ok)

            # Audited break-glass waiver unlocks high-risk release only when passed at BOTH approve and verify-release
            (repo / 'tests/test_app.py').write_text(
                'from src.app import add\n\ndef test_add():\n    assert add(1, 2) == 3\n', encoding='utf-8',
            )
            rc_ev3, _ = change_gate.cmd_record_evidence(repo, state_dir, 'pytest', base='main', exit_code=0, kind='verification')
            self.assertEqual(rc_ev3, 0)
            rc_waive_app, waive_app = change_gate.cmd_approve(
                repo, state_dir, 'release', 'human', 'main', risk='high',
                waive_review='P0 outage hotfix', summary='emergency patch',
            )
            self.assertEqual(rc_waive_app, 0, waive_app)
            self.assertEqual(waive_app['approval']['reviewWaiverReason'], 'P0 outage hotfix')
            # Without --waive-review at verify time, still blocked
            rc_waive_no, _ = change_gate.cmd_verify_release(repo, state_dir, 'release', 'main', risk='high')
            self.assertNotEqual(rc_waive_no, 0)
            # With a mismatched --waive-review reason, must stay blocked
            rc_waive_mismatch, _ = change_gate.cmd_verify_release(
                repo, state_dir, 'release', 'main', risk='high', waive_review='different reason',
            )
            self.assertNotEqual(rc_waive_mismatch, 0)
            # With exact matching waiver at verify time, passes and records reviewWaived=True
            rc_waive_ok, waive_ok = change_gate.cmd_verify_release(
                repo, state_dir, 'release', 'main', risk='high', waive_review='P0 outage hotfix',
            )
            self.assertEqual(rc_waive_ok, 0, waive_ok)
            self.assertTrue(waive_ok['reviewWaived'])

            # Net diff from merge-base: fixing a committed @ts-ignore in working tree must NOT keep blocking,
            # and mentioning @ts-ignore in Markdown docs must NOT trigger code bypass blockers
            (repo / 'src/bad.ts').write_text('// @ts-ignore\nexport const x = 1;\n', encoding='utf-8')
            git(repo, 'add', 'src/bad.ts')
            git(repo, 'commit', '-m', 'chore: accidental ts-ignore')
            self.assertFalse(change_gate.scan_diff_blockers(repo, base='main')['ok'])
            # Fix it in working tree before committing -> net diff is now clean
            (repo / 'src/bad.ts').write_text('export const x: number = 1;\n', encoding='utf-8')
            (repo / 'README.md').write_text('Never add `@ts-ignore` or `eslint-disable` in source files.\n', encoding='utf-8')
            clean_res = change_gate.scan_diff_blockers(repo, base='main')
            self.assertTrue(clean_res['ok'], clean_res)

    def test_v1_1_regressions_untracked_dirs_lockfiles_trunk_base_monitor_and_board(self):
        """Prove v1.1.0 fixes: nested untracked dir secrets, bun/yarn/uv/poetry locks, trunk main base, CI recovery, outages, revert regex, and board headSha fallback."""
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            repo = tdir / 'trunk-repo'
            state_dir = tdir / 'state'
            init_sample_repo(repo)

            # 1. Local trunk-only `main` (no origin/main) must auto-resolve to HEAD~1 rather than empty diff against `main`
            (repo / 'src/feature.py').write_text('def revert_button():\n    return True\n', encoding='utf-8')
            (repo / 'generated').mkdir()
            (repo / 'generated/bundle.ts').write_text('\n'.join(f'export const v{i} = {i};' for i in range(600)) + '\n', encoding='utf-8')
            git(repo, 'add', '.')
            git(repo, 'commit', '-m', 'feat: add revert button in UI')
            trunk_audit = repo_audit.audit_repo(repo)
            self.assertEqual(trunk_audit['baseRef'], 'HEAD~1')
            self.assertIn('src/feature.py', [f['path'] for f in trunk_audit['blastRadius']['files']])
            # Generated output directories must not drown handwritten largeFiles
            self.assertFalse(any(f['path'].startswith('generated/') for f in trunk_audit['largeFiles']))

            # 2. Nested untracked directory containing a leaked secret MUST be caught by change_gate and counted by repo_audit
            nested_dir = repo / 'brand_new_dir/sub'
            nested_dir.mkdir(parents=True)
            fake_aws = 'AKIA' + 'IOSFODNN7EXAMPLE'
            (nested_dir / 'leak.py').write_text(f'KEY = "{fake_aws}"\n', encoding='utf-8')
            diff_nested = change_gate.scan_diff_blockers(repo)
            self.assertFalse(diff_nested['ok'])
            self.assertTrue(any(b['rule'] == 'aws_access_key' and 'brand_new_dir/sub/leak.py' in b['file'] for b in diff_nested['blockers']))
            audit_nested = repo_audit.audit_repo(repo)
            self.assertIn('brand_new_dir/sub/leak.py', audit_nested['blastRadius']['untrackedFiles'])
            (nested_dir / 'leak.py').unlink()

            # 3. Board approval status must stay valid using gate-state.json alone (without audit.json or pulse.json)
            rc_ev, _ = change_gate.cmd_record_evidence(repo, state_dir, 'true', exit_code=0)
            self.assertEqual(rc_ev, 0)
            rc_app, _ = change_gate.cmd_approve(repo, state_dir, 'release', 'commander', None, risk='low')
            self.assertEqual(rc_app, 0)
            delivery_only_gate = build_boards.build_delivery_payload(state_dir)
            self.assertEqual(delivery_only_gate['approvals'][0]['status'], 'valid')
            self.assertEqual(delivery_only_gate['approvals'][0]['risk'], 'low')

            # 4. Multi-ecosystem lockfile parsers: bun.lock (JSONC + workspace skip), yarn.lock (v1+Berry), uv.lock (virtual skip), poetry.lock
            (repo / 'bun.lock').write_text(
                '{\n'
                '  // Bun 1.2+ text lockfile with trailing commas\n'
                '  "lockfileVersion": 1,\n'
                '  "packages": {\n'
                '    "lodash": ["lodash@4.17.21", "", {}, "sha512-abc"],\n'
                '    "@scope/pkg": ["@scope/pkg@2.3.4", "", {}, "sha512-def"],\n'
                '    "@internal/app": ["@internal/app@workspace:apps/web", "", {}],\n'
                '  },\n'
                '}\n',
                encoding='utf-8',
            )
            (repo / 'yarn.lock').write_text(
                '"chalk@^5.0.0":\n  version "5.3.0"\n\n'
                '"@types/node@npm:^22.0.0":\n  version: 22.10.0\n',
                encoding='utf-8',
            )
            (repo / 'uv.lock').write_text(
                '[[package]]\nname = "demo-local"\nversion = "0.1.0"\nsource = { virtual = "." }\n\n'
                '[[package]]\nname = "httpx"\nversion = "0.28.1"\nsource = { registry = "https://pypi.org/simple" }\n',
                encoding='utf-8',
            )
            (repo / 'poetry.lock').write_text(
                '[[package]]\nname = "pydantic"\nversion = "2.10.0"\n',
                encoding='utf-8',
            )
            sc = supply_chain.run_supply_chain_check(repo, offline=True)
            self.assertEqual(set(sc['lockfilesFound']), {'bun.lock', 'yarn.lock', 'uv.lock', 'poetry.lock'})
            self.assertEqual(sc['dependencyCount'], 6)

            # 5. repo_monitor: revert regex ignores "feat: add revert button"; latest-per-(workflow,branch) clears fixed CI;
            #    network failure preserves last-known failingCiIds and returns CLI exit code 2
            gh_json = tdir / 'gh.json'
            gh_json.write_text(json.dumps({
                'pullRequests': [{'number': 12, 'title': 'WIP', 'author': 'dev', 'draft': False}],
                'ciRuns': [
                    {'id': 100, 'name': 'CI', 'branch': 'main', 'status': 'completed', 'conclusion': 'failure', 'updatedAt': '2026-11-27T01:00:00Z'},
                    {'id': 101, 'name': 'CI', 'branch': 'main', 'status': 'completed', 'conclusion': 'success', 'updatedAt': '2026-11-27T02:00:00Z'},
                    {'id': 200, 'name': 'Lint', 'branch': 'main', 'status': 'completed', 'conclusion': 'failure', 'updatedAt': '2026-11-27T02:05:00Z'},
                ],
            }), encoding='utf-8')
            p_ok = repo_monitor.monitor_repo(repo, state_dir, github_json=gh_json)
            self.assertEqual(p_ok['git']['revertCount30d'], 0)
            self.assertEqual(p_ok['remote']['status'], 'ok')
            self.assertEqual(p_ok['remote']['failingCiCount'], 1)
            self.assertEqual(p_ok['materialState']['failingCiIds'], [200])

            # Simulated outage against closed localhost port -> preserves failingCiIds=[200] & CLI exits 2
            proc_fail = subprocess.run(
                [
                    sys.executable, str(SCRIPTS / 'repo_monitor.py'),
                    '--repo', str(repo), '--state-dir', str(state_dir),
                    '--github-repo', 'acme/demo', '--api-base', 'http://127.0.0.1:1',
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc_fail.returncode, 2, proc_fail.stderr)
            p_fail = json.loads(proc_fail.stdout)
            self.assertEqual(p_fail['remote']['status'], 'query_failed')
            self.assertEqual(p_fail['materialState']['failingCiIds'], [200])
            self.assertEqual(p_fail['materialState']['openPrNumbers'], [12])


if __name__ == '__main__':
    unittest.main()
