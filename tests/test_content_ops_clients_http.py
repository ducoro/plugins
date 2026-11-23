"""Real local HTTP round-trip contract tests for all 12 platform client.py scripts."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / 'plugins' / 'content-operations' / 'skills'


def load_client(platform_slug: str):
    path = SKILLS / platform_slug / 'scripts' / 'client.py'
    spec = importlib.util.spec_from_file_location(f'client_{platform_slug.replace("-", "_")}', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class MockGatewayState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.requests: list[dict] = []
        self.next_status = 200
        self.next_body: bytes | None = b'{"ok": true, "data": {"id": "mock-id"}}'
        self.next_headers: dict[str, str] = {}
        self.response_queue: list[tuple[int, bytes, dict[str, str]]] = []


class PlatformClientsHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = MockGatewayState()
        state = cls.state

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def _handle(self):
                length = int(self.headers.get('Content-Length', '0') or '0')
                raw = self.rfile.read(length) if length > 0 else b''
                state.requests.append({
                    'method': self.command,
                    'path': self.path,
                    'headers': {k.lower(): v for k, v in self.headers.items()},
                    'body': raw,
                })
                if state.response_queue:
                    status, body, hdrs = state.response_queue.pop(0)
                else:
                    status, body, hdrs = state.next_status, state.next_body or b'', state.next_headers
                self.send_response(status)
                for k, v in hdrs.items():
                    self.send_header(k, v)
                if body:
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                if body:
                    self.wfile.write(body)

            do_GET = _handle
            do_POST = _handle
            do_PUT = _handle
            do_PATCH = _handle
            do_DELETE = _handle

        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.base_url = f'http://127.0.0.1:{cls.server.server_port}'
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.state.reset()

    def call_main(self, mod, argv: list[str], env: dict[str, str]) -> tuple[int, str, str]:
        out = io.StringIO()
        err = io.StringIO()
        with patch.dict(os.environ, env, clear=False):
            with patch.object(sys, 'stdout', out), patch.object(sys, 'stderr', err):
                rc = mod.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_linkedin_active_version_and_comment_object_and_post_urn(self):
        mod = load_client('platform-linkedin')
        self.state.next_status = 201
        self.state.next_body = b''
        self.state.next_headers = {'x-restli-id': 'urn:li:share:999'}
        with patch.object(mod, 'REST_BASE', f'{self.base_url}/rest'):
            rc, stdout, _ = self.call_main(
                mod,
                ['post', '--text', 'Shipped'],
                {'LINKEDIN_ACCESS_TOKEN': 'tok', 'LINKEDIN_AUTHOR_URN': 'urn:li:person:1'},
            )
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(stdout)['postUrn'], 'urn:li:share:999')
            self.assertGreaterEqual(self.state.requests[-1]['headers']['linkedin-version'], '202601')

            self.state.next_status = 200
            self.state.next_body = b'{"id": "c1"}'
            rc2, _, _ = self.call_main(
                mod,
                ['comment', '--post-urn', 'urn:li:share:999', '--text', 'Nice!'],
                {'LINKEDIN_ACCESS_TOKEN': 'tok', 'LINKEDIN_AUTHOR_URN': 'urn:li:person:1'},
            )
            self.assertEqual(rc2, 0)
            body = json.loads(self.state.requests[-1]['body'].decode('utf-8'))
            self.assertEqual(body['object'], 'urn:li:share:999')

    def test_douyin_get_fans_query_videos_and_business_error(self):
        mod = load_client('platform-douyin')
        with patch.object(mod, 'BASE_URL', self.base_url):
            rc, _, _ = self.call_main(
                mod,
                ['get-fans', '--date-type', '15'],
                {'DOUYIN_ACCESS_TOKEN': 'tok', 'DOUYIN_OPEN_ID': 'oid-1'},
            )
            self.assertEqual(rc, 0)
            req = self.state.requests[-1]
            self.assertEqual(req['method'], 'GET')
            self.assertIn('open_id=oid-1', req['path'])
            self.assertIn('date_type=15', req['path'])

            rc2, _, _ = self.call_main(
                mod,
                ['--app-type', 'miniapp', 'query-videos', '--item-ids', 'v1', 'v2'],
                {'DOUYIN_ACCESS_TOKEN': 'tok', 'DOUYIN_OPEN_ID': 'oid-1'},
            )
            self.assertEqual(rc2, 0)
            req2 = self.state.requests[-1]
            self.assertIn('/api/apps/v1/video/query/?open_id=oid-1', req2['path'])
            self.assertEqual(json.loads(req2['body'].decode('utf-8')), {'item_ids': ['v1', 'v2']})

            # HTTP 200 with non-zero business error_code must exit non-zero
            self.state.next_body = b'{"data": {"error_code": 2190008, "description": "token expired"}}'
            rc3, _, err3 = self.call_main(
                mod,
                ['get-fans'],
                {'DOUYIN_ACCESS_TOKEN': 'tok', 'DOUYIN_OPEN_ID': 'oid-1'},
            )
            self.assertEqual(rc3, 1)
            self.assertIn('2190008', err3)

            # Whitespace-only DOUYIN_OPEN_ID must fail
            rc4, _, _ = self.call_main(mod, ['get-fans'], {'DOUYIN_ACCESS_TOKEN': 'tok', 'DOUYIN_OPEN_ID': '   '})
            self.assertEqual(rc4, 1)

    def test_meta_clients_204_empty_body_updated_metrics_and_threads_carousel(self):
        ig = load_client('platform-instagram')
        fb = load_client('platform-facebook')
        th = load_client('platform-threads')

        with patch.object(ig, 'BASE', self.base_url):
            self.state.next_status = 204
            self.state.next_body = b''
            rc, stdout, _ = self.call_main(
                ig,
                ['delete-comment', '--comment-id', 'cm1'],
                {'INSTAGRAM_ACCESS_TOKEN': 'tok', 'INSTAGRAM_USER_ID': 'ig1'},
            )
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(stdout), {'ok': True})

            self.state.next_status = 200
            self.state.next_body = b'{"data": []}'
            rc2, _, _ = self.call_main(
                ig,
                ['account-insights'],
                {'INSTAGRAM_ACCESS_TOKEN': 'tok', 'INSTAGRAM_USER_ID': 'ig1'},
            )
            self.assertEqual(rc2, 0)
            self.assertNotIn('profile_views', self.state.requests[-1]['path'])
            self.assertIn('metric_type=total_value', self.state.requests[-1]['path'])

            # Carousel VIDEO child item
            rc3, _, _ = self.call_main(
                ig,
                ['create-container', '--media-type', 'VIDEO', '--media-url', 'https://example.com/v.mp4', '--is-carousel-item'],
                {'INSTAGRAM_ACCESS_TOKEN': 'tok', 'INSTAGRAM_USER_ID': 'ig1'},
            )
            self.assertEqual(rc3, 0)
            self.assertIn(b'media_type=VIDEO', self.state.requests[-1]['body'])
            self.assertIn(b'is_carousel_item=true', self.state.requests[-1]['body'])

        with patch.object(fb, 'BASE', self.base_url):
            rc, _, _ = self.call_main(
                fb,
                ['post-insights', '--post-id', 'p1'],
                {'FACEBOOK_PAGE_ACCESS_TOKEN': 'tok', 'FACEBOOK_PAGE_ID': 'pg1'},
            )
            self.assertEqual(rc, 0)
            self.assertNotIn('post_engaged_users', self.state.requests[-1]['path'])
            self.assertIn('post_media_view', self.state.requests[-1]['path'])

        with patch.object(th, 'BASE', self.base_url):
            # IMAGE without --media-url must fail
            rc_bad, _, _ = self.call_main(
                th,
                ['create-container', '--media-type', 'IMAGE'],
                {'THREADS_ACCESS_TOKEN': 'tok', 'THREADS_USER_ID': 'u1'},
            )
            self.assertEqual(rc_bad, 1)

            # Carousel parent container
            rc_car, _, _ = self.call_main(
                th,
                ['create-carousel', '--children-ids', 'c1,c2', '--text', 'Look'],
                {'THREADS_ACCESS_TOKEN': 'tok', 'THREADS_USER_ID': 'u1'},
            )
            self.assertEqual(rc_car, 0)
            self.assertIn(b'media_type=CAROUSEL', self.state.requests[-1]['body'])

    def test_business_error_codes_fail_closed_across_wechat_bilibili_tiktok_kuaishou(self):
        wx = load_client('platform-wechat-official')
        bili = load_client('platform-bilibili')
        tt = load_client('platform-tiktok')
        ks = load_client('platform-kuaishou')

        with patch.object(wx, 'BASE', self.base_url):
            self.state.next_body = b'{"errcode": 40001, "errmsg": "invalid credential"}'
            rc, _, _ = self.call_main(wx, ['poll-publish', '--publish-id', 'p1'], {'WECHAT_OFFICIAL_ACCESS_TOKEN': 'tok'})
            self.assertEqual(rc, 1)

            # Multipart upload-thumb + get-token happy path
            self.state.next_body = b'{"media_id": "thumb-123"}'
            with tempfile.NamedTemporaryFile(suffix='.jpg') as fh:
                fh.write(b'\xff\xd8\xff\xd9')
                fh.flush()
                rc_up, out_up, _ = self.call_main(wx, ['upload-thumb', '--file', fh.name], {'WECHAT_OFFICIAL_ACCESS_TOKEN': 'tok'})
                self.assertEqual(rc_up, 0)
                self.assertEqual(json.loads(out_up)['media_id'], 'thumb-123')
                self.assertIn('multipart/form-data', self.state.requests[-1]['headers']['content-type'])

        with patch.object(bili, 'BASE', self.base_url):
            self.state.next_body = b'{"code": -101, "message": "not logged in"}'
            rc, _, _ = self.call_main(
                bili,
                ['list-categories'],
                {'BILIBILI_CLIENT_ID': 'cid', 'BILIBILI_ACCESS_TOKEN': 'tok', 'BILIBILI_CLIENT_SECRET': 'sec'},
            )
            self.assertEqual(rc, 1)
            # Confirm v2 HMAC signature headers were attached
            hdrs = self.state.requests[-1]['headers']
            self.assertEqual(hdrs.get('x-bili-signature-version'), '2.0')
            self.assertEqual(hdrs.get('x-bili-signature-method'), 'HMAC-SHA256')
            self.assertTrue(hdrs.get('authorization'))

        with patch.object(tt, 'BASE', self.base_url):
            self.state.next_body = b'{"error": {"code": "access_token_invalid", "message": "bad token"}}'
            rc, _, _ = self.call_main(tt, ['creator-info'], {'TIKTOK_ACCESS_TOKEN': 'tok'})
            self.assertEqual(rc, 1)

        with patch.object(ks, 'BASE', self.base_url):
            self.state.next_body = b'{"result": 100200100, "error_msg": "invalid token"}'
            rc, _, _ = self.call_main(ks, ['start-upload'], {'KUAISHOU_APP_ID': 'aid', 'KUAISHOU_ACCESS_TOKEN': 'tok'})
            self.assertEqual(rc, 1)

    def test_x_refresh_and_chunked_upload_and_youtube_put_upload_and_pinterest_204(self):
        xmod = load_client('platform-x-twitter')
        yt = load_client('platform-youtube')
        pin = load_client('platform-pinterest')

        with patch.object(xmod, 'BASE', self.base_url):
            # Whitespace X_USER_ID must fail
            rc_bad, _, _ = self.call_main(
                xmod,
                ['engage', '--action', 'like', '--tweet-id', '1'],
                {'X_ACCESS_TOKEN': 'tok', 'X_USER_ID': '   '},
            )
            self.assertEqual(rc_bad, 1)

            # refresh-token
            self.state.next_body = b'{"access_token": "new-tok", "expires_in": 7200}'
            rc_ref, out_ref, _ = self.call_main(
                xmod,
                ['refresh-token'],
                {'X_CLIENT_ID': 'cid', 'X_REFRESH_TOKEN': 'rtok', 'X_CLIENT_SECRET': 'csec'},
            )
            self.assertEqual(rc_ref, 0)
            self.assertEqual(json.loads(out_ref)['access_token'], 'new-tok')

            # 3-step v2 chunked media upload (initialize -> append -> finalize)
            self.state.response_queue = [
                (200, b'{"data": {"id": "mid-77"}}', {}),
                (204, b'', {}),
                (200, b'{"data": {"id": "mid-77", "processing_info": {"state": "succeeded"}}}', {}),
            ]
            with tempfile.NamedTemporaryFile(suffix='.png') as fh:
                fh.write(b'\x89PNG\r\n\x1a\n1234')
                fh.flush()
                rc_up, out_up, _ = self.call_main(xmod, ['upload-media', '--file', fh.name], {'X_ACCESS_TOKEN': 'tok'})
                self.assertEqual(rc_up, 0)
                self.assertEqual(json.loads(out_up)['media_id'], 'mid-77')
                self.assertTrue(self.state.requests[-1]['path'].endswith('/2/media/upload/mid-77/finalize'))

        with patch.object(yt, 'BASE', self.base_url), patch.object(yt, 'UPLOAD_BASE', self.base_url):
            self.state.next_body = b'{"id": "vid-99"}'
            with tempfile.NamedTemporaryFile(suffix='.mp4') as fh:
                fh.write(b'\x00\x00\x00\x18ftypmp42')
                fh.flush()
                rc_put, out_put, _ = self.call_main(
                    yt,
                    ['upload-video', '--upload-url', f'{self.base_url}/upload/session/1', '--file', fh.name],
                    {'YOUTUBE_ACCESS_TOKEN': 'tok'},
                )
                self.assertEqual(rc_put, 0)
                self.assertEqual(json.loads(out_put)['id'], 'vid-99')
                self.assertEqual(self.state.requests[-1]['method'], 'PUT')

        with patch.object(pin, 'BASE', self.base_url):
            self.state.next_status = 204
            self.state.next_body = b''
            rc_pin, out_pin, _ = self.call_main(pin, ['get-pin', '--pin-id', 'p1'], {'PINTEREST_ACCESS_TOKEN': 'tok'})
            self.assertEqual(rc_pin, 0)
            self.assertEqual(json.loads(out_pin), {'ok': True})

    def test_youtube_tiktok_refresh_token_tiktok_file_upload_and_linkedin_image_upload(self):
        yt = load_client('platform-youtube')
        tt = load_client('platform-tiktok')
        li = load_client('platform-linkedin')

        with patch.object(yt, 'OAUTH_TOKEN_URL', f'{self.base_url}/token'):
            self.state.next_body = b'{"access_token": "yt-new", "expires_in": 3600}'
            rc, out, _ = self.call_main(
                yt,
                ['refresh-token'],
                {'YOUTUBE_CLIENT_ID': 'cid', 'YOUTUBE_CLIENT_SECRET': 'csec', 'YOUTUBE_REFRESH_TOKEN': 'rtok'},
            )
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(out)['access_token'], 'yt-new')

        with patch.object(tt, 'BASE', self.base_url):
            self.state.next_body = b'{"access_token": "tt-new", "expires_in": 86400}'
            rc_r, out_r, _ = self.call_main(
                tt,
                ['refresh-token'],
                {'TIKTOK_CLIENT_KEY': 'ck', 'TIKTOK_CLIENT_SECRET': 'cs', 'TIKTOK_REFRESH_TOKEN': 'rt'},
            )
            self.assertEqual(rc_r, 0)
            self.assertEqual(json.loads(out_r)['access_token'], 'tt-new')

            with tempfile.NamedTemporaryFile(suffix='.mp4') as fh:
                fh.write(b'\x00\x00\x00\x18ftypmp42' + b'\x00' * 100)
                fh.flush()
                self.state.next_body = json.dumps({'data': {'publish_id': 'pub1', 'upload_url': f'{self.base_url}/tt-put'}, 'error': {'code': 'ok'}}).encode('utf-8')
                rc_fi, out_fi, _ = self.call_main(
                    tt,
                    ['init-video-file', '--title', 'Clip', '--file', fh.name],
                    {'TIKTOK_ACCESS_TOKEN': 'tok'},
                )
                self.assertEqual(rc_fi, 0)
                init_body = json.loads(self.state.requests[-1]['body'].decode('utf-8'))
                self.assertEqual(init_body['source_info']['source'], 'FILE_UPLOAD')

                self.state.next_status = 201
                self.state.next_body = b''
                rc_fp, _, _ = self.call_main(
                    tt,
                    ['upload-video-file', '--upload-url', f'{self.base_url}/tt-put', '--file', fh.name],
                    {},
                )
                self.assertEqual(rc_fp, 0)
                self.assertEqual(self.state.requests[-1]['method'], 'PUT')
                self.assertTrue(self.state.requests[-1]['headers']['content-range'].startswith('bytes 0-'))

        with patch.object(li, 'REST_BASE', f'{self.base_url}/rest'):
            self.state.response_queue = [
                (200, json.dumps({'value': {'uploadUrl': f'{self.base_url}/li-put', 'image': 'urn:li:image:555'}}).encode('utf-8'), {}),
                (201, b'', {}),
                (201, b'', {'x-restli-id': 'urn:li:share:555'}),
            ]
            with tempfile.NamedTemporaryFile(suffix='.jpg') as fh:
                fh.write(b'\xff\xd8\xff\xd9')
                fh.flush()
                rc_up, out_up, _ = self.call_main(
                    li,
                    ['upload-image', '--file', fh.name],
                    {'LINKEDIN_ACCESS_TOKEN': 'tok', 'LINKEDIN_AUTHOR_URN': 'urn:li:person:1'},
                )
                self.assertEqual(rc_up, 0)
                urn = json.loads(out_up)['imageUrn']
                self.assertEqual(urn, 'urn:li:image:555')

                rc_p, out_p, _ = self.call_main(
                    li,
                    ['post', '--text', 'With image', '--image-urn', urn, '--alt-text', 'Diagram'],
                    {'LINKEDIN_ACCESS_TOKEN': 'tok', 'LINKEDIN_AUTHOR_URN': 'urn:li:person:1'},
                )
                self.assertEqual(rc_p, 0)
                self.assertEqual(json.loads(out_p)['postUrn'], 'urn:li:share:555')
                post_body = json.loads(self.state.requests[-1]['body'].decode('utf-8'))
                self.assertEqual(post_body['content']['media']['id'], 'urn:li:image:555')


if __name__ == '__main__':
    unittest.main()
