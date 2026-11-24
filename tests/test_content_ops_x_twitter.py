"""Unit, HTTP roundtrip, and Class-A/B formal verification tests for X (Twitter) capabilities."""
from __future__ import annotations

import contextlib
import http.server
import importlib.util
import io
import itertools
import json
import os
from pathlib import Path
import socketserver
import sys
import tempfile
import threading
import unittest

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins' / 'content-operations'
SKILLS = PLUGIN / 'skills'
LOOP_SCRIPTS = str(SKILLS / 'content-ops-loop' / 'scripts')
if LOOP_SCRIPTS not in sys.path:
    sys.path.insert(0, LOOP_SCRIPTS)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


SPECS_MOD = load_module(SKILLS / 'content-ops-loop' / 'scripts' / 'check_media_specs.py', 'x_check_specs')
INIT_MOD = load_module(SKILLS / 'content-ops-loop' / 'scripts' / 'init_workspace.py', 'x_init_ws')
VAL_MOD = load_module(SKILLS / 'content-ops-loop' / 'scripts' / 'validate_workspace.py', 'x_val_ws')
BUILD_MOD = load_module(SKILLS / 'content-ops-loop' / 'scripts' / 'build_boards.py', 'x_build_boards')
GUARD_MOD = load_module(SKILLS / 'engagement-and-analytics' / 'scripts' / 'engagement_guard.py', 'x_eng_guard')
X_CLIENT = load_module(SKILLS / 'platform-x-twitter' / 'scripts' / 'client.py', 'x_client_v2')


class _ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


class XTwitterCapabilitiesTest(unittest.TestCase):
    def test_formal_exhaustive_first_reply_and_root_link_advisory(self):
        """Class-A formal proof: every combination of long_post x firstReply x root_has_url satisfies hard invariants."""
        first_reply_cases = [
            ('none', None, True, False),
            ('ok_280', 'a' * 280, True, False),
            ('over_281', 'a' * 281, False, True),
            ('ok_cjk_140', '中' * 140, True, False),
            ('over_cjk_141', '中' * 141, False, True),
            ('tco_shortened_ok', 'Read more: https://example.com/' + ('segment/' * 20) + ' ' + ('b' * 245), True, False),
            ('placeholder', 'Link here: TODO replace URL', False, False),
            ('non_string', 12345, False, False),
        ]
        checked = 0
        with tempfile.TemporaryDirectory() as tmp:
            draft_dir = Path(tmp) / 'drf-x-01'
            (draft_dir / 'variants').mkdir(parents=True)
            for long_post, (case_name, fr_val, ok_std, ok_if_long), root_has_url in itertools.product(
                (False, True),
                first_reply_cases,
                (False, True),
            ):
                checked += 1
                opts = {'long_post': long_post}
                if fr_val is not None:
                    opts['firstReply'] = fr_val
                meta = {'platform': 'x-twitter', 'mode': 'text', 'title': '', 'topics': [], 'media': [], 'options': opts}
                body = 'Sharp take https://example.com/post' if root_has_url else 'Sharp take without outbound link'
                vpath = draft_dir / 'variants' / 'x-twitter.md'
                vpath.write_text(f'```json\n{json.dumps(meta)}\n```\n{body}\n', encoding='utf-8')
                res = SPECS_MOD.validate_variant(draft_dir, vpath, channel='browser')

                expected_ok = ok_std or (long_post and ok_if_long)
                if expected_ok:
                    self.assertEqual(res['specStatus'], 'pass', f'Expected pass for ({long_post}, {case_name}, {root_has_url}): {res}')
                else:
                    self.assertEqual(res['specStatus'], 'fail', f'Expected fail for ({long_post}, {case_name}, {root_has_url}): {res}')

                warn_codes = {w['code'] for w in res['warnings']}
                expect_link_warn = (not long_post) and root_has_url and (fr_val is None)
                if expect_link_warn:
                    self.assertIn('outbound_link_in_root', warn_codes)
                else:
                    self.assertNotIn('outbound_link_in_root', warn_codes)

        self.assertEqual(checked, 32)

    def test_formal_exhaustive_benchmark_approval_and_outbound_invariants(self):
        """Class-A formal proof: active benchmarks require human approvedBy; sent outbound requires executedActionId & valid FK/URL."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / 'content-ops'
            sys.path.insert(0, str(SKILLS / 'content-ops-loop' / 'scripts'))
            try:
                INIT_MOD.init_workspace(ws)
            finally:
                sys.path.pop(0)

            self.assertTrue((ws / 'engagement' / 'benchmark-accounts.json').is_file())
            self.assertTrue((ws / 'engagement' / 'outbound-queue.json').is_file())
            self.assertEqual(VAL_MOD.validate_workspace(ws), [])

            # 1. Exhaustive benchmark-accounts sovereignty check
            bench_checked = 0
            for status, approved_by, prof_url in itertools.product(
                ('proposed', 'active', 'paused', 'bogus'),
                ('', 'human:2026-11-24'),
                ('', 'https://x.com/peer_one', 'ftp://invalid.example'),
            ):
                bench_checked += 1
                (ws / 'engagement' / 'benchmark-accounts.json').write_text(
                    json.dumps({
                        'version': 1,
                        'accounts': [{
                            'watchId': 'bench-x-01',
                            'platform': 'x-twitter',
                            'handle': '@peer_one',
                            'profileUrl': prof_url,
                            'status': status,
                            'approvedBy': approved_by,
                        }],
                    }),
                    encoding='utf-8',
                )
                errs = VAL_MOD.validate_workspace(ws)
                valid_status = status in {'proposed', 'active', 'paused'}
                valid_approval = (status != 'active') or bool(approved_by)
                valid_url = (prof_url == '') or prof_url.startswith('https://')
                if valid_status and valid_approval and valid_url:
                    self.assertEqual(errs, [], f'Unexpected errors for {(status, approved_by, prof_url)}: {errs}')
                else:
                    self.assertTrue(errs, f'Expected validation failure for {(status, approved_by, prof_url)}')
            self.assertEqual(bench_checked, 24)

            # Reset benchmark to valid active account, then exhaustively verify outbound-queue invariants
            (ws / 'engagement' / 'benchmark-accounts.json').write_text(
                json.dumps({
                    'version': 1,
                    'accounts': [{
                        'watchId': 'bench-x-01',
                        'platform': 'x-twitter',
                        'handle': '@peer_one',
                        'profileUrl': 'https://x.com/peer_one',
                        'status': 'active',
                        'approvedBy': 'human:2026-11-24',
                    }],
                }),
                encoding='utf-8',
            )
            ob_checked = 0
            for ob_status, exec_id, watch_id, target_url, action_type in itertools.product(
                ('drafted', 'sent'),
                ('', 'act-001'),
                ('bench-x-01', 'bench-missing'),
                ('https://x.com/peer_one/status/123', 'not-a-url'),
                ('reply', 'quote', 'spam_dm'),
            ):
                ob_checked += 1
                (ws / 'engagement' / 'outbound-queue.json').write_text(
                    json.dumps({
                        'version': 1,
                        'items': [{
                            'outboundId': 'out-01',
                            'platform': 'x-twitter',
                            'accountId': 'acct-x-main',
                            'watchId': watch_id,
                            'targetHandle': '@peer_one',
                            'targetPostId': '123',
                            'targetUrl': target_url,
                            'actionType': action_type,
                            'status': ob_status,
                            'executedActionId': exec_id or None,
                        }],
                    }),
                    encoding='utf-8',
                )
                errs = VAL_MOD.validate_workspace(ws)
                expected_valid = (
                    (ob_status != 'sent' or bool(exec_id))
                    and watch_id == 'bench-x-01'
                    and target_url.startswith('https://')
                    and action_type in {'reply', 'quote'}
                )
                if expected_valid:
                    self.assertEqual(errs, [], f'Unexpected errors for {(ob_status, exec_id, watch_id, target_url, action_type)}: {errs}')
                else:
                    self.assertTrue(errs, f'Expected failure for {(ob_status, exec_id, watch_id, target_url, action_type)}')
            self.assertEqual(ob_checked, 48)

    def test_client_post_thread_partial_failure_resume_and_user_tweets_over_http(self):
        """Real local HTTP roundtrip: post-thread chaining, mid-thread failure preservation, resume, and user-tweets."""
        recorded: list[tuple[str, str, dict | None]] = []
        state = {'fail_on_call': None, 'seq': 0}

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                return

            def do_GET(self):
                recorded.append(('GET', self.path, None))
                if self.path.startswith('/2/users/by/username/peer_creator'):
                    payload = {'data': {'id': '9001', 'username': 'peer_creator', 'name': 'Peer Creator'}}
                elif self.path.startswith('/2/users/9001/tweets'):
                    payload = {'data': [{'id': '555', 'text': 'Live X insight'}], 'meta': {'newest_id': '555'}}
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

            def do_POST(self):
                length = int(self.headers.get('Content-Length', '0'))
                body = json.loads(self.rfile.read(length).decode('utf-8')) if length else None
                recorded.append(('POST', self.path, body))
                state['seq'] += 1
                if state['fail_on_call'] == state['seq']:
                    err = json.dumps({'title': 'Too Many Requests', 'status': 429}).encode('utf-8')
                    self.send_response(429)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(err)))
                    self.end_headers()
                    self.wfile.write(err)
                    return
                tid = str(1000 + state['seq'])
                raw = json.dumps({'data': {'id': tid, 'text': (body or {}).get('text', '')}}).encode('utf-8')
                self.send_response(201)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        server = _ThreadedHTTPServer(('127.0.0.1', 0), Handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        old_base = X_CLIENT.BASE
        old_token = os.environ.get('X_ACCESS_TOKEN')
        try:
            X_CLIENT.BASE = f'http://127.0.0.1:{port}'
            os.environ['X_ACCESS_TOKEN'] = 'test-x-token'

            with tempfile.TemporaryDirectory() as tmp:
                variant_path = Path(tmp) / 'x-twitter.md'
                variant_path.write_text(
                    '```json\n'
                    '{"platform":"x-twitter","mode":"text","options":{"firstReply":"Full notes: https://example.com/notes"}}\n'
                    '```\n'
                    'Root insight without link\n'
                    '---\n'
                    'Second thread point with proof\n',
                    encoding='utf-8',
                )

                # 1. Full happy-path thread + firstReply + media_ids on root only
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = X_CLIENT.main(['post-thread', '--variant', str(variant_path), '--media-ids', 'm-1'])
                self.assertEqual(rc, 0)
                out = json.loads(buf.getvalue())
                self.assertTrue(out['ok'])
                self.assertEqual(len(out['publishedTweets']), 3)
                self.assertEqual([t['kind'] for t in out['publishedTweets']], ['post', 'post', 'firstReply'])

                posts = [b for m, p, b in recorded if m == 'POST' and p == '/2/tweets']
                self.assertEqual(posts[0]['media'], {'media_ids': ['m-1']})
                self.assertNotIn('reply', posts[0])
                self.assertEqual(posts[1]['reply'], {'in_reply_to_tweet_id': '1001'})
                self.assertNotIn('media', posts[1])
                self.assertEqual(posts[2]['reply'], {'in_reply_to_tweet_id': '1002'})
                self.assertIn('https://example.com/notes', posts[2]['text'])

                # 2. Fault injection: fail on 2nd tweet, verify non-zero exit + preserved partial state + safe resume
                recorded.clear()
                state['seq'] = 0
                state['fail_on_call'] = 2
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = X_CLIENT.main(['post-thread', '--variant', str(variant_path)])
                self.assertEqual(rc, 1)
                partial = json.loads(buf.getvalue())
                self.assertFalse(partial['ok'])
                self.assertTrue(partial['partial'])
                self.assertEqual(partial['failedAtIndex'], 1)
                self.assertEqual(partial['resumeReplyTo'], '1001')
                self.assertEqual(len(partial['publishedTweets']), 1)

                state['fail_on_call'] = None
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = X_CLIENT.main([
                        'post-thread',
                        '--parts', 'Second thread point with proof',
                        '--first-reply', 'Full notes: https://example.com/notes',
                        '--resume-reply-to', partial['resumeReplyTo'],
                    ])
                self.assertEqual(rc, 0)
                resumed = json.loads(buf.getvalue())
                self.assertTrue(resumed['ok'])
                self.assertEqual(recorded[-2][2]['reply'], {'in_reply_to_tweet_id': '1001'})

                # 3. Benchmark account polling via user-tweets --username --since-id
                recorded.clear()
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = X_CLIENT.main(['user-tweets', '--username', '@peer_creator', '--since-id', '400'])
                self.assertEqual(rc, 0)
                ut = json.loads(buf.getvalue())
                self.assertEqual(ut['userId'], '9001')
                self.assertEqual(ut['tweets'][0]['id'], '555')
                self.assertTrue(any('/2/users/9001/tweets?' in p and 'since_id=400' in p and 'exclude=retweets' in p for m, p, _ in recorded if m == 'GET'))
        finally:
            X_CLIENT.BASE = old_base
            if old_token is None:
                os.environ.pop('X_ACCESS_TOKEN', None)
            else:
                os.environ['X_ACCESS_TOKEN'] = old_token
            server.shutdown()
            server.server_close()

    def test_shared_rate_cap_across_inbound_and_outbound_plus_board_payload(self):
        """Inbound replies and outbound quotes share one engagement_guard budget and project into engagement-inbox-board."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / 'content-ops'
            sys.path.insert(0, str(SKILLS / 'content-ops-loop' / 'scripts'))
            try:
                INIT_MOD.init_workspace(ws)
            finally:
                sys.path.pop(0)

            ts = '2026-11-24T10:00:00Z'
            # Interleave inbound reply + outbound quote under tight shared hourly cap (15 on X)
            for i in range(10):
                r1 = GUARD_MOD.record_action(ws, platform='x-twitter', account_id='acct-x-main', target_id=f'in-{i}', action_type='reply', executed_at=ts)
                self.assertTrue(r1['ok'])
            for i in range(5):
                r2 = GUARD_MOD.record_action(ws, platform='x-twitter', account_id='acct-x-main', target_id=f'out-{i}', action_type='quote', executed_at=ts)
                self.assertTrue(r2['ok'])
            # 16th combined action in the same hour MUST be blocked
            blocked = GUARD_MOD.record_action(ws, platform='x-twitter', account_id='acct-x-main', target_id='out-5', action_type='reply', executed_at=ts)
            self.assertFalse(blocked['ok'])
            self.assertEqual(blocked['error'], 'rate_limit_exceeded')
            # Duplicate outbound target MUST be blocked by idempotency even before cap
            dup = GUARD_MOD.check_idempotent(ws, 'x-twitter', 'acct-x-main', 'out-0', 'quote')
            self.assertFalse(dup['ok'])

            # Populate benchmark + outbound queue and verify build_boards projection
            (ws / 'engagement' / 'benchmark-accounts.json').write_text(
                json.dumps({
                    'version': 1,
                    'accounts': [
                        {'watchId': 'bench-1', 'platform': 'x-twitter', 'handle': '@peer_a', 'profileUrl': 'https://x.com/peer_a', 'status': 'active', 'approvedBy': 'human:2026-11-24'},
                        {'watchId': 'bench-2', 'platform': 'x-twitter', 'handle': '@peer_b', 'profileUrl': 'https://x.com/peer_b', 'status': 'proposed', 'approvedBy': ''},
                    ],
                }),
                encoding='utf-8',
            )
            (ws / 'engagement' / 'outbound-queue.json').write_text(
                json.dumps({
                    'version': 1,
                    'items': [{
                        'outboundId': 'out-cand-1',
                        'platform': 'x-twitter',
                        'accountId': 'acct-x-main',
                        'watchId': 'bench-1',
                        'targetHandle': '@peer_a',
                        'targetPostId': '999',
                        'targetUrl': 'https://x.com/peer_a/status/999',
                        'actionType': 'quote',
                        'status': 'drafted',
                        'requiresApproval': True,
                        'draftText': 'Concrete field observation here.',
                    }],
                }),
                encoding='utf-8',
            )
            self.assertEqual(VAL_MOD.validate_workspace(ws), [])
            payload = BUILD_MOD.build_payloads(ws)['engagement-inbox-board']
            self.assertIn('x-twitter', payload['platforms'])
            self.assertEqual(payload['summary']['activeBenchmarks'], 1)
            self.assertEqual(payload['summary']['proposedBenchmarks'], 1)
            self.assertEqual(payload['summary']['outboundOpen'], 1)
            self.assertEqual(payload['summary']['outboundAwaitingApproval'], 1)
            self.assertEqual(len(payload['benchmarkAccounts']), 2)
            self.assertEqual(len(payload['outboundQueue']), 1)


if __name__ == '__main__':
    unittest.main()
