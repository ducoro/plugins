"""HTTP roundtrip, fault-injection resume, and firstReply spec tests for LinkedIn & Threads upgrades."""
from __future__ import annotations

import contextlib
import http.server
import importlib.util
import io
import json
import os
from pathlib import Path
import socketserver
import sys
import tempfile
import threading
import unittest
import urllib.parse

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


SPECS_MOD = load_module(SKILLS / 'content-ops-loop' / 'scripts' / 'check_media_specs.py', 'lt_check_specs')
LI_CLIENT = load_module(SKILLS / 'platform-linkedin' / 'scripts' / 'client.py', 'li_client_v2')
TH_CLIENT = load_module(SKILLS / 'platform-threads' / 'scripts' / 'client.py', 'th_client_v2')


class _ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


class LinkedInAndThreadsUpgradesTest(unittest.TestCase):
    def test_linkedin_and_threads_first_reply_spec_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft_dir = Path(tmp) / 'drf-lt-01'
            (draft_dir / 'variants').mkdir(parents=True)

            # 1. LinkedIn root link without firstReply emits non-blocking advisory warning
            li_path = draft_dir / 'variants' / 'linkedin.md'
            li_path.write_text(
                '```json\n{"platform":"linkedin","mode":"text","title":"","topics":[],"media":[],"options":{}}\n```\n'
                'Read the full write-up at https://example.com/report\n',
                encoding='utf-8',
            )
            r_warn = SPECS_MOD.validate_variant(draft_dir, li_path, channel='browser')
            self.assertEqual(r_warn['specStatus'], 'pass')
            self.assertIn('outbound_link_in_root', {w['code'] for w in r_warn['warnings']})

            # Moving link to options.firstReply clears warning; over-3000 firstReply fails hard
            li_path.write_text(
                '```json\n' + json.dumps({
                    'platform': 'linkedin', 'mode': 'text', 'title': '', 'topics': [], 'media': [],
                    'options': {'firstReply': 'Full report: https://example.com/report'},
                }) + '\n```\nClean main post without outbound URL.\n',
                encoding='utf-8',
            )
            r_ok = SPECS_MOD.validate_variant(draft_dir, li_path, channel='browser')
            self.assertEqual(r_ok['specStatus'], 'pass')
            self.assertNotIn('outbound_link_in_root', {w['code'] for w in r_ok['warnings']})

            li_path.write_text(
                '```json\n' + json.dumps({
                    'platform': 'linkedin', 'mode': 'text', 'title': '', 'topics': [], 'media': [],
                    'options': {'firstReply': 'x' * 3001},
                }) + '\n```\nClean main post.\n',
                encoding='utf-8',
            )
            r_big = SPECS_MOD.validate_variant(draft_dir, li_path, channel='browser')
            self.assertEqual(r_big['specStatus'], 'fail')

            # 2. Threads firstReply enforces 500-char limit and placeholder rejection
            th_path = draft_dir / 'variants' / 'threads.md'
            th_path.write_text(
                '```json\n' + json.dumps({
                    'platform': 'threads', 'mode': 'text', 'title': '', 'topics': ['ProductCraft'], 'media': [],
                    'options': {'firstReply': 'y' * 501},
                }) + '\n```\nFirst post\n---\nSecond post\n',
                encoding='utf-8',
            )
            self.assertEqual(SPECS_MOD.validate_variant(draft_dir, th_path, channel='browser')['specStatus'], 'fail')

            th_path.write_text(
                '```json\n' + json.dumps({
                    'platform': 'threads', 'mode': 'text', 'title': '', 'topics': ['ProductCraft'], 'media': [],
                    'options': {'firstReply': 'Reference notes: TODO add link'},
                }) + '\n```\nFirst post\n---\nSecond post\n',
                encoding='utf-8',
            )
            self.assertEqual(SPECS_MOD.validate_variant(draft_dir, th_path, channel='browser')['specStatus'], 'fail')

    def test_linkedin_post_with_first_reply_and_partial_failure_resume(self):
        recorded: list[tuple[str, str, dict | None]] = []
        state = {'fail_comment': False, 'post_count': 0}

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                return

            def do_POST(self):
                length = int(self.headers.get('Content-Length', '0'))
                body = json.loads(self.rfile.read(length).decode('utf-8')) if length else None
                recorded.append(('POST', self.path, body))
                if self.path == '/rest/posts':
                    state['post_count'] += 1
                    self.send_response(201)
                    self.send_header('x-restli-id', f'urn:li:share:700{state["post_count"]}')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                if '/comments' in self.path:
                    if state['fail_comment']:
                        err = b'{"message":"temporary failure"}'
                        self.send_response(500)
                        self.send_header('Content-Length', str(len(err)))
                        self.end_headers()
                        self.wfile.write(err)
                        return
                    raw = json.dumps({'id': 'urn:li:comment:99'}).encode('utf-8')
                    self.send_response(201)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                self.send_response(404)
                self.end_headers()

        server = _ThreadedHTTPServer(('127.0.0.1', 0), Handler)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()

        old_rest = LI_CLIENT.REST_BASE
        old_tok = os.environ.get('LINKEDIN_ACCESS_TOKEN')
        old_urn = os.environ.get('LINKEDIN_AUTHOR_URN')
        try:
            LI_CLIENT.REST_BASE = f'http://127.0.0.1:{port}/rest'
            os.environ['LINKEDIN_ACCESS_TOKEN'] = 'li-test-tok'
            os.environ['LINKEDIN_AUTHOR_URN'] = 'urn:li:person:abc'

            with tempfile.TemporaryDirectory() as tmp:
                vpath = Path(tmp) / 'linkedin.md'
                vpath.write_text(
                    '```json\n{"platform":"linkedin","mode":"text","options":{"firstReply":"Resource link: https://example.com/guide"}}\n```\n'
                    'Three concrete lessons from running file-backed content ops.\n',
                    encoding='utf-8',
                )

                # 1. Happy path
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = LI_CLIENT.main(['post-with-first-reply', '--variant', str(vpath)])
                self.assertEqual(rc, 0)
                out = json.loads(buf.getvalue())
                self.assertTrue(out['ok'])
                self.assertEqual(out['postUrn'], 'urn:li:share:7001')
                self.assertEqual(out['firstReply']['id'], 'urn:li:comment:99')

                # 2. Fault injection: first comment fails -> preserves postUrn and resumes without re-posting
                recorded.clear()
                state['fail_comment'] = True
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = LI_CLIENT.main(['post-with-first-reply', '--variant', str(vpath)])
                self.assertEqual(rc, 1)
                partial = json.loads(buf.getvalue())
                self.assertFalse(partial['ok'])
                self.assertTrue(partial['partial'])
                self.assertEqual(partial['resumePostUrn'], 'urn:li:share:7002')

                state['fail_comment'] = False
                recorded.clear()
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = LI_CLIENT.main([
                        'post-with-first-reply',
                        '--resume-post-urn', partial['resumePostUrn'],
                        '--first-reply', 'Resource link: https://example.com/guide',
                    ])
                self.assertEqual(rc, 0)
                # Confirm root post was NOT called again on resume
                self.assertEqual([p for _, p, _ in recorded], ['/rest/socialActions/urn%3Ali%3Ashare%3A7002/comments'])
        finally:
            LI_CLIENT.REST_BASE = old_rest
            if old_tok is None:
                os.environ.pop('LINKEDIN_ACCESS_TOKEN', None)
            else:
                os.environ['LINKEDIN_ACCESS_TOKEN'] = old_tok
            if old_urn is None:
                os.environ.pop('LINKEDIN_AUTHOR_URN', None)
            else:
                os.environ['LINKEDIN_AUTHOR_URN'] = old_urn
            server.shutdown()
            server.server_close()

    def test_threads_post_thread_chaining_and_partial_failure_resume(self):
        recorded: list[tuple[str, dict[str, str]]] = []
        state = {'create_seq': 0, 'pub_seq': 0, 'fail_create_on': None}

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                return

            def do_POST(self):
                length = int(self.headers.get('Content-Length', '0'))
                raw_body = self.rfile.read(length).decode('utf-8')
                params = {k: v[0] for k, v in urllib.parse.parse_qs(raw_body).items()}
                recorded.append((self.path, params))
                if self.path.endswith('/threads'):
                    state['create_seq'] += 1
                    if state['fail_create_on'] == state['create_seq']:
                        err = b'{"error":{"message":"rate limit"}}'
                        self.send_response(429)
                        self.send_header('Content-Length', str(len(err)))
                        self.end_headers()
                        self.wfile.write(err)
                        return
                    out = json.dumps({'id': f'cnt-{state["create_seq"]}'}).encode('utf-8')
                elif self.path.endswith('/threads_publish'):
                    state['pub_seq'] += 1
                    out = json.dumps({'id': f'post-{state["pub_seq"]}'}).encode('utf-8')
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(out)))
                self.end_headers()
                self.wfile.write(out)

        server = _ThreadedHTTPServer(('127.0.0.1', 0), Handler)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()

        old_base = TH_CLIENT.BASE
        old_tok = os.environ.get('THREADS_ACCESS_TOKEN')
        old_uid = os.environ.get('THREADS_USER_ID')
        try:
            TH_CLIENT.BASE = f'http://127.0.0.1:{port}'
            os.environ['THREADS_ACCESS_TOKEN'] = 'th-test-tok'
            os.environ['THREADS_USER_ID'] = 'u-42'

            with tempfile.TemporaryDirectory() as tmp:
                vpath = Path(tmp) / 'threads.md'
                vpath.write_text(
                    '```json\n{"platform":"threads","mode":"text","topics":["ProductCraft"],"options":{"reply_control":"everyone","firstReply":"Full checklist in reply"}}\n```\n'
                    'Root conversational prompt\n'
                    '---\n'
                    'Follow-up breakdown\n',
                    encoding='utf-8',
                )

                # 1. Happy path: 3 sequential create+publish pairs with topic_tag on root only
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = TH_CLIENT.main(['post-thread', '--variant', str(vpath)])
                self.assertEqual(rc, 0)
                out = json.loads(buf.getvalue())
                self.assertTrue(out['ok'])
                self.assertEqual(len(out['publishedPosts']), 3)
                creates = [p for path, p in recorded if path.endswith('/threads')]
                self.assertEqual(creates[0].get('topic_tag'), 'ProductCraft')
                self.assertNotIn('reply_to_id', creates[0])
                self.assertNotIn('topic_tag', creates[1])
                self.assertEqual(creates[1].get('reply_to_id'), 'post-1')
                self.assertEqual(creates[2].get('reply_to_id'), 'post-2')

                # 2. Fault injection on 2nd create -> preserves root post-1 and resumes cleanly
                recorded.clear()
                state['create_seq'] = 0
                state['pub_seq'] = 0
                state['fail_create_on'] = 2
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = TH_CLIENT.main(['post-thread', '--variant', str(vpath)])
                self.assertEqual(rc, 1)
                partial = json.loads(buf.getvalue())
                self.assertFalse(partial['ok'])
                self.assertTrue(partial['partial'])
                self.assertEqual(partial['failedAtIndex'], 1)
                self.assertEqual(partial['resumeReplyTo'], 'post-1')

                state['fail_create_on'] = None
                recorded.clear()
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = TH_CLIENT.main([
                        'post-thread',
                        '--parts', 'Follow-up breakdown',
                        '--first-reply', 'Full checklist in reply',
                        '--resume-reply-to', partial['resumeReplyTo'],
                    ])
                self.assertEqual(rc, 0)
                resumed_creates = [p for path, p in recorded if path.endswith('/threads')]
                self.assertEqual(resumed_creates[0].get('reply_to_id'), 'post-1')
        finally:
            TH_CLIENT.BASE = old_base
            if old_tok is None:
                os.environ.pop('THREADS_ACCESS_TOKEN', None)
            else:
                os.environ['THREADS_ACCESS_TOKEN'] = old_tok
            if old_uid is None:
                os.environ.pop('THREADS_USER_ID', None)
            else:
                os.environ['THREADS_USER_ID'] = old_uid
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
