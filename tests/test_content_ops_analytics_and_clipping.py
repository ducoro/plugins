"""Contract, HTTP round-trip, and formal-verification tests for YouTube/LinkedIn analytics, breakout triggers/hook recall, and line-indexed video clipping."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / 'plugins' / 'content-operations' / 'skills'
LOOP_SCRIPTS = SKILLS / 'content-ops-loop' / 'scripts'
if str(LOOP_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(LOOP_SCRIPTS))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class _MockServerState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.requests: list[dict] = []
        self.queue: list[tuple[int, bytes, dict[str, str]]] = []


class AnalyticsHttpRoundTripTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = _MockServerState()
        state = cls.state

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
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
                status, body, hdrs = state.queue.pop(0) if state.queue else (200, b'{}', {})
                self.send_response(status)
                for k, v in hdrs.items():
                    self.send_header(k, v)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = _handle
            do_POST = _handle

        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.base_url = f'http://127.0.0.1:{cls.server.server_port}'
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

        cls.yt = load_module(SKILLS / 'platform-youtube' / 'scripts' / 'client.py', 'yt_analytics_client')
        cls.li = load_module(SKILLS / 'platform-linkedin' / 'scripts' / 'client.py', 'li_analytics_client')
        cls.init_ws = load_module(SKILLS / 'content-ops-loop' / 'scripts' / 'init_workspace.py', 'init_ws_ac')
        cls.val_ws = load_module(SKILLS / 'content-ops-loop' / 'scripts' / 'validate_workspace.py', 'val_ws_ac')

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.state.reset()

    def _run(self, mod, argv: list[str], env: dict[str, str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, env, clear=False):
            with patch.object(sys, 'stdout', out), patch.object(sys, 'stderr', err):
                rc = mod.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_youtube_channel_and_video_analytics_append_valid_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / 'content-ops'
            self.init_ws.init_workspace(ws)

            channel_report = {
                'columnHeaders': [
                    {'name': 'day'}, {'name': 'views'}, {'name': 'estimatedMinutesWatched'},
                    {'name': 'averageViewDuration'}, {'name': 'averageViewPercentage'},
                    {'name': 'subscribersGained'}, {'name': 'subscribersLost'}, {'name': 'likes'},
                ],
                'rows': [
                    ['2026-11-20', 1000, 3200, 190, 52.0, 40, 5, 90],
                    ['2026-11-21', 1500, 4800, 210, 58.0, 60, 10, 140],
                ],
            }
            video_report = {
                'columnHeaders': [
                    {'name': 'day'}, {'name': 'views'}, {'name': 'estimatedMinutesWatched'},
                    {'name': 'averageViewDuration'}, {'name': 'averageViewPercentage'},
                    {'name': 'likes'}, {'name': 'comments'}, {'name': 'shares'}, {'name': 'subscribersGained'},
                ],
                'rows': [
                    ['2026-11-21', 800, 2400, 180, 61.5, 70, 12, 15, 22],
                ],
            }
            video_stats = {
                'items': [{
                    'id': 'ytVid001',
                    'snippet': {'title': 'Deep Dive Walkthrough'},
                    'statistics': {'viewCount': '950', 'likeCount': '85', 'commentCount': '14'},
                }],
            }
            self.state.queue = [
                (200, json.dumps(channel_report).encode(), {}),
                (200, json.dumps(video_report).encode(), {}),
                (200, json.dumps(video_stats).encode(), {}),
            ]

            with patch.object(self.yt, 'ANALYTICS_BASE', self.base_url), patch.object(self.yt, 'BASE', self.base_url):
                rc1, out1, err1 = self._run(
                    self.yt,
                    ['channel-analytics', '--start-date', '2026-11-20', '--end-date', '2026-11-21', '--workspace', str(ws), '--account-id', 'yt-main'],
                    {'YOUTUBE_ACCESS_TOKEN': 'tok-yt'},
                )
                self.assertEqual(rc1, 0, err1)
                d1 = json.loads(out1)
                self.assertEqual(d1['totals']['views'], 2500)
                self.assertEqual(d1['totals']['estimatedMinutesWatched'], 8000)
                self.assertEqual(d1['platformMetrics']['avgViewDurationSec'], 200.0)
                self.assertEqual(d1['platformMetrics']['avgViewPct'], 55.0)

                rc2, out2, err2 = self._run(
                    self.yt,
                    ['video-analytics', '--video-id', 'ytVid001', '--start-date', '2026-11-20', '--end-date', '2026-11-21',
                     '--with-stats', '--workspace', str(ws), '--window', '7d', '--account-id', 'yt-main', '--topic-id', 'top-1'],
                    {'YOUTUBE_ACCESS_TOKEN': 'tok-yt'},
                )
                self.assertEqual(rc2, 0, err2)
                d2 = json.loads(out2)
                self.assertEqual(d2['title'], 'Deep Dive Walkthrough')
                self.assertEqual(d2['platformMetrics']['avgViewPct'], 61.5)

            self.assertIn('ids=channel%3D%3DMINE', self.state.requests[0]['path'])
            self.assertIn('filters=video%3D%3DytVid001', self.state.requests[1]['path'])
            self.assertIn('/videos?', self.state.requests[2]['path'])

            lines = [json.loads(ln) for ln in (ws / 'analytics' / 'snapshots.jsonl').read_text(encoding='utf-8').splitlines() if ln.strip()]
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0]['window'], 'account')
            self.assertEqual(lines[1]['workId'], 'ytVid001')
            self.assertEqual(lines[1]['metrics']['views'], 950)
            self.assertEqual(lines[1]['platformMetrics']['avgViewDurationSec'], 180.0)

            errors = self.val_ws.validate_workspace(ws)
            self.assertEqual(errors, [])

    def test_linkedin_org_and_post_analytics_restli_and_member_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / 'content-ops'
            self.init_ws.init_workspace(ws)

            org_share_resp = {
                'elements': [
                    {
                        'timeRange': {'start': 1763596800000},
                        'totalShareStatistics': {
                            'impressionCount': 2000, 'uniqueImpressionsCount': 1600,
                            'clickCount': 120, 'likeCount': 60, 'commentCount': 14, 'shareCount': 6,
                        },
                    },
                    {
                        'timeRange': {'start': 1763683200000},
                        'totalShareStatistics': {
                            'impressionCount': 1000, 'uniqueImpressionsCount': 850,
                            'clickCount': 50, 'likeCount': 30, 'commentCount': 6, 'shareCount': 4,
                        },
                    },
                ],
            }
            follower_resp = {
                'elements': [{'followerGains': {'organicFollowerGain': 35, 'paidFollowerGain': 5}}],
            }
            post_org_resp = {
                'elements': [{
                    'totalShareStatistics': {
                        'impressionCount': 4200, 'uniqueImpressionsCount': 3100,
                        'clickCount': 210, 'likeCount': 95, 'commentCount': 24, 'shareCount': 11,
                    },
                }],
            }
            member_social_resp = {
                'likesSummary': {'totalLikes': 42},
                'commentsSummary': {'totalFirstLevelComments': 9},
            }
            self.state.queue = [
                (200, json.dumps(org_share_resp).encode(), {}),
                (200, json.dumps(follower_resp).encode(), {}),
                (200, json.dumps(post_org_resp).encode(), {}),
                (200, json.dumps(member_social_resp).encode(), {}),
            ]

            with patch.object(self.li, 'REST_BASE', self.base_url):
                rc1, out1, err1 = self._run(
                    self.li,
                    ['org-analytics', '--org-urn', 'urn:li:organization:12345', '--start-ms', '1763596800000',
                     '--end-ms', '1763769600000', '--with-followers', '--workspace', str(ws)],
                    {'LINKEDIN_ACCESS_TOKEN': 'tok-li'},
                )
                self.assertEqual(rc1, 0, err1)
                d1 = json.loads(out1)
                self.assertEqual(d1['totals']['impressionCount'], 3000)
                self.assertEqual(d1['followerGains']['total'], 40)

                rc2, out2, err2 = self._run(
                    self.li,
                    ['post-analytics', '--post-urn', 'urn:li:ugcPost:999', '--org-urn', 'urn:li:organization:12345',
                     '--workspace', str(ws), '--window', '72h'],
                    {'LINKEDIN_ACCESS_TOKEN': 'tok-li'},
                )
                self.assertEqual(rc2, 0, err2)
                d2 = json.loads(out2)
                self.assertEqual(d2['scope'], 'organization_share_statistics')
                self.assertEqual(d2['totals']['impressionCount'], 4200)

                rc3, out3, err3 = self._run(
                    self.li,
                    ['post-analytics', '--post-urn', 'urn:li:share:777', '--workspace', str(ws), '--window', '24h'],
                    {'LINKEDIN_ACCESS_TOKEN': 'tok-li'},
                )
                self.assertEqual(rc3, 0, err3)
                d3 = json.loads(out3)
                self.assertEqual(d3['scope'], 'member_public_actions')
                self.assertEqual(d3['totals']['likeCount'], 42)
                self.assertEqual(d3['totals']['commentCount'], 9)

            self.assertIn('timeIntervals=(timeRange:(start:1763596800000,end:1763769600000),timeGranularityType:DAY)', self.state.requests[0]['path'])
            self.assertIn('ugcPosts=List(urn%3Ali%3AugcPost%3A999)', self.state.requests[2]['path'])
            self.assertIn('/socialActions/urn%3Ali%3Ashare%3A777', self.state.requests[3]['path'])
            self.assertEqual(self.state.requests[0]['headers'].get('x-restli-protocol-version'), '2.0.0')

            errors = self.val_ws.validate_workspace(ws)
            self.assertEqual(errors, [])


class BreakoutAndHookRecallFormalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agg = load_module(SKILLS / 'engagement-and-analytics' / 'scripts' / 'aggregate_metrics.py', 'agg_a2')
        cls.init_ws = load_module(SKILLS / 'content-ops-loop' / 'scripts' / 'init_workspace.py', 'init_ws_a2')
        cls.val_ws = load_module(SKILLS / 'content-ops-loop' / 'scripts' / 'validate_workspace.py', 'val_ws_a2')

    def test_top_hooks_extracted_from_variant_master_and_title_fallback(self):
        now = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / 'content-ops'
            self.init_ws.init_workspace(ws)

            d1 = ws / 'drafts' / 'd-1'
            (d1 / 'variants').mkdir(parents=True, exist_ok=True)
            (d1 / 'variants' / 'x-twitter.md').write_text(
                '```json\n{"platform":"x-twitter","title":"T1"}\n```\n'
                'Most teams waste 80% of video editing time guessing timestamps.\n'
                'Here is the 3-step line-index method instead.\n\nMore details below.',
                encoding='utf-8',
            )
            d2 = ws / 'drafts' / 'd-2'
            d2.mkdir(parents=True, exist_ok=True)
            (d2 / 'master.md').write_text('# Why short feedback loops beat huge launches\n\nBody paragraph.', encoding='utf-8')

            pubs = [
                {'workId': 'w-1', 'draftId': 'd-1', 'platform': 'x-twitter', 'accountId': 'x-1', 'status': 'published',
                 'publishedAt': iso_utc(now - timedelta(hours=10)), 'publicUrl': 'https://x.com/u/status/1'},
                {'workId': 'w-2', 'draftId': 'd-2', 'platform': 'linkedin', 'accountId': 'li-1', 'status': 'published',
                 'publishedAt': iso_utc(now - timedelta(hours=20)), 'publicUrl': 'https://www.linkedin.com/feed/update/urn:li:share:2'},
                {'workId': 'w-3', 'platform': 'x-twitter', 'accountId': 'x-1', 'status': 'published',
                 'publishedAt': iso_utc(now - timedelta(hours=30)), 'publicUrl': 'https://x.com/u/status/3'},
            ]
            (ws / 'publish-log.jsonl').write_text('\n'.join(json.dumps(p) for p in pubs) + '\n', encoding='utf-8')

            snaps = [
                {'capturedAt': iso_utc(now - timedelta(hours=1)), 'platform': 'x-twitter', 'accountId': 'x-1',
                 'workId': 'w-1', 'window': '24h', 'title': 'T1', 'metrics': {'views': 12000, 'likes': 400, 'comments': 30, 'shares': 50, 'saves': 120}},
                {'capturedAt': iso_utc(now - timedelta(hours=2)), 'platform': 'linkedin', 'accountId': 'li-1',
                 'workId': 'w-2', 'window': '24h', 'title': 'T2', 'metrics': {'views': 5000, 'likes': 100, 'comments': 25, 'shares': 10, 'saves': 20}},
                {'capturedAt': iso_utc(now - timedelta(hours=3)), 'platform': 'x-twitter', 'accountId': 'x-1',
                 'workId': 'w-3', 'window': '24h', 'title': 'Fallback Title Hook', 'metrics': {'views': 1000, 'likes': 20, 'comments': 2, 'shares': 1, 'saves': 2}},
            ]
            (ws / 'analytics' / 'snapshots.jsonl').write_text('\n'.join(json.dumps(s) for s in snaps) + '\n', encoding='utf-8')

            res = self.agg.aggregate(ws, days=14, now=now)
            hooks = {h['workId']: h for h in res['topHooks']}
            self.assertIn('Most teams waste 80%', hooks['w-1']['hook'])
            self.assertEqual(hooks['w-1']['hookSource'], 'drafts/d-1/variants/x-twitter.md')
            self.assertEqual(hooks['w-2']['hook'], 'Why short feedback loops beat huge launches')
            self.assertEqual(hooks['w-2']['hookSource'], 'drafts/d-2/master.md')
            self.assertEqual(hooks['w-3']['hook'], 'Fallback Title Hook')
            self.assertEqual(hooks['w-3']['hookSource'], 'title_fallback')

            x_only = self.agg.aggregate(ws, days=14, now=now, platform_filter='x-twitter')
            self.assertTrue(all(h['platform'] == 'x-twitter' for h in x_only['topHooks']))

    def test_exhaustive_breakout_trigger_invariants_and_idempotency(self):
        """Class A formal verification: enumerate all 2^5 combinations of threshold, age, URL, executed, and queued states."""
        now = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)
        checked = 0
        for exceeds in (False, True):
            for within_age in (False, True):
                for has_url in (False, True):
                    for already_exec in (False, True):
                        for already_queued in (False, True):
                            checked += 1
                            with tempfile.TemporaryDirectory() as tmp:
                                ws = Path(tmp) / 'content-ops'
                                self.init_ws.init_workspace(ws)

                                pub_dt = now - timedelta(hours=12 if within_age else 240)
                                pub_row = {
                                    'workId': 'w-target',
                                    'platform': 'x-twitter',
                                    'accountId': 'x-main',
                                    'status': 'published',
                                    'publishedAt': iso_utc(pub_dt),
                                    'publicUrl': 'https://x.com/acct/status/9001' if has_url else '',
                                }
                                (ws / 'publish-log.jsonl').write_text(json.dumps(pub_row) + '\n', encoding='utf-8')

                                snap = {
                                    'capturedAt': iso_utc(now - timedelta(hours=1)),
                                    'platform': 'x-twitter',
                                    'accountId': 'x-main',
                                    'workId': 'w-target',
                                    'window': '24h',
                                    'title': 'Target Post',
                                    'metrics': {
                                        'views': 8000 if exceeds else 100,
                                        'likes': 120 if exceeds else 3,
                                        'comments': 15 if exceeds else 0,
                                        'shares': 10 if exceeds else 0,
                                        'saves': 20 if exceeds else 0,
                                    },
                                }
                                (ws / 'analytics' / 'snapshots.jsonl').write_text(json.dumps(snap) + '\n', encoding='utf-8')

                                if already_exec:
                                    # Mark both reply and repost executed
                                    actions = [
                                        {'actionId': 'act-1', 'executedAt': iso_utc(now - timedelta(hours=2)),
                                         'platform': 'x-twitter', 'accountId': 'x-main', 'targetId': 'w-target',
                                         'actionType': 'reply', 'result': 'ok'},
                                        {'actionId': 'act-2', 'executedAt': iso_utc(now - timedelta(hours=2)),
                                         'platform': 'x-twitter', 'accountId': 'x-main', 'targetId': 'w-target',
                                         'actionType': 'repost', 'result': 'ok'},
                                    ]
                                    (ws / 'engagement' / 'action-log.jsonl').write_text(
                                        '\n'.join(json.dumps(a) for a in actions) + '\n', encoding='utf-8'
                                    )

                                if already_queued:
                                    qdoc = {
                                        'version': 1,
                                        'items': [
                                            {'outboundId': 'out-existing-1', 'platform': 'x-twitter', 'accountId': 'x-main',
                                             'targetPostId': 'w-target', 'targetUrl': 'https://x.com/acct/status/9001',
                                             'actionType': 'reply', 'status': 'drafted', 'requiresApproval': True},
                                            {'outboundId': 'out-existing-2', 'platform': 'x-twitter', 'accountId': 'x-main',
                                             'targetPostId': 'w-target', 'targetUrl': 'https://x.com/acct/status/9001',
                                             'actionType': 'repost', 'status': 'drafted', 'requiresApproval': True},
                                        ],
                                    }
                                    (ws / 'engagement' / 'outbound-queue.json').write_text(json.dumps(qdoc), encoding='utf-8')

                                res1 = self.agg.aggregate(
                                    ws, days=14, now=now, min_likes=50, max_age_hours=168, stage_breakouts=True
                                )
                                should_detect = exceeds and within_age and (not already_exec) and (not already_queued)
                                should_stage = should_detect and has_url

                                self.assertEqual(len(res1['breakoutCandidates']) > 0, should_detect)
                                self.assertEqual(res1['stagedBreakouts']['stagedCount'], 1 if should_stage else 0)
                                if should_detect and not has_url:
                                    self.assertEqual(res1['stagedBreakouts']['skippedNoUrl'], ['x-twitter:w-target'])

                                # Re-running --stage-breakouts must be strictly idempotent (never duplicate reply)
                                if should_stage:
                                    q_after_1 = json.loads((ws / 'engagement' / 'outbound-queue.json').read_text(encoding='utf-8'))
                                    self.assertEqual(len(q_after_1['items']), 1)
                                    self.assertTrue(q_after_1['items'][0]['requiresApproval'])
                                    self.assertEqual(q_after_1['items'][0]['status'], 'discovered')
                                    self.assertEqual(q_after_1['items'][0]['actionType'], 'reply')

                                    # Workspace must remain 100% schema-valid after staging
                                    errors = self.val_ws.validate_workspace(ws)
                                    self.assertEqual(errors, [])

                                    # Second pass stages the remaining 'repost' action, third pass stages 0 (fixed point)
                                    res2 = self.agg.aggregate(ws, days=14, now=now, min_likes=50, max_age_hours=168, stage_breakouts=True)
                                    self.assertEqual(res2['stagedBreakouts']['stagedCount'], 1)
                                    res3 = self.agg.aggregate(ws, days=14, now=now, min_likes=50, max_age_hours=168, stage_breakouts=True)
                                    self.assertEqual(res3['stagedBreakouts']['stagedCount'], 0)
                                    self.assertEqual(res3['breakoutCandidates'], [])

        self.assertEqual(checked, 32)

    def test_mutation_check_invalid_staged_url_caught_by_validator(self):
        """Mutation self-check: injecting a non-HTTP targetUrl into outbound-queue must fail validate_workspace."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / 'content-ops'
            self.init_ws.init_workspace(ws)
            bad_queue = {
                'version': 1,
                'items': [{
                    'outboundId': 'out-bad-1',
                    'platform': 'x-twitter',
                    'targetPostId': 'w-bad',
                    'targetUrl': 'not-a-url',
                    'actionType': 'reply',
                    'status': 'discovered',
                    'requiresApproval': True,
                }],
            }
            (ws / 'engagement' / 'outbound-queue.json').write_text(json.dumps(bad_queue), encoding='utf-8')
            errors = self.val_ws.validate_workspace(ws)
            self.assertTrue(any('targetUrl' in e for e in errors))


class VideoLineIndexedClippingFormalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vops = load_module(SKILLS / 'video-production' / 'scripts' / 'video_ops.py', 'video_ops_a3')

    def _write_sample_srt(self, path: Path, count: int = 6, step_sec: int = 10) -> Path:
        blocks = []
        for i in range(count):
            s = i * step_sec
            e = s + step_sec
            blocks.append(f'{i + 1}\n00:00:{s:02d},000 --> 00:00:{e:02d},000\nLine number {i} spoken sentence.')
        path.write_text('\n\n'.join(blocks) + '\n', encoding='utf-8')
        return path

    def test_index_transcript_supports_srt_and_vtt(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            srt = self._write_sample_srt(tdir / 'talk.srt', count=4, step_sec=10)
            res_srt = self.vops.index_transcript(srt)
            self.assertTrue(res_srt['ok'])
            self.assertEqual(res_srt['format'], 'srt')
            self.assertEqual(res_srt['cueCount'], 4)
            self.assertEqual(res_srt['formattedLines'][0], '0 [0.0 - 10.0] Line number 0 spoken sentence.')

            vtt = tdir / 'talk.vtt'
            vtt.write_text(
                'WEBVTT\n\nNOTE metadata comment\n\n'
                '00:00.000 --> 00:12.500 align:center\n<b>Opening</b> hook line.\n\n'
                '00:12.500 --> 00:25.000\nSecond point completed.\n',
                encoding='utf-8',
            )
            res_vtt = self.vops.index_transcript(vtt)
            self.assertTrue(res_vtt['ok'])
            self.assertEqual(res_vtt['format'], 'vtt')
            self.assertEqual(res_vtt['cueCount'], 2)
            self.assertEqual(res_vtt['cues'][0]['text'], 'Opening hook line.')
            self.assertEqual(res_vtt['cues'][1]['endMs'], 25000)

    def test_exhaustive_plan_clips_two_clip_bounds_duration_and_non_overlap(self):
        """Class A formal verification: exhaustively enumerate 2-clip cue index ranges and verify all hard invariants."""
        with tempfile.TemporaryDirectory() as tmp:
            srt = self._write_sample_srt(Path(tmp) / 'six.srt', count=6, step_sec=10)
            # Cues 0..5, each 10s -> [0..60s]. Allowed duration [20s, 30s] means span of 2 or 3 cues.
            total_checked = 0
            valid_count = 0
            for f1 in range(-1, 7):
                for t1 in range(0, 6):
                    for f2 in range(0, 6):
                        for t2 in range(0, 6):
                            total_checked += 1
                            plan = [
                                {'from': f1, 'to': t1, 'title': 'Clip One'},
                                {'from': f2, 'to': t2, 'title': 'Clip Two'},
                            ]
                            res = self.vops.plan_clips(srt, plan, min_sec=20.0, max_sec=30.0, max_clips=4)

                            in_bounds = (0 <= f1 <= t1 < 6) and (0 <= f2 <= t2 < 6)
                            d1_ok = in_bounds and (20.0 <= ((t1 - f1 + 1) * 10.0) <= 30.0)
                            d2_ok = in_bounds and (20.0 <= ((t2 - f2 + 1) * 10.0) <= 30.0)
                            non_overlap = in_bounds and (t1 < f2 or t2 < f1)
                            expected_ok = in_bounds and d1_ok and d2_ok and non_overlap

                            self.assertEqual(res['ok'], expected_ok, f'Mismatch for [{f1}..{t1}] & [{f2}..{t2}]: {res}')
                            if expected_ok:
                                valid_count += 1
                                self.assertEqual(len(res['validClips']), 2)
                                c1, c2 = sorted(res['validClips'], key=lambda c: c['from'])
                                self.assertLess(c1['to'], c2['from'])
                                self.assertLessEqual(c1['endMs'], c2['startMs'])
                            else:
                                self.assertEqual(res['validClips'], [])
                                self.assertTrue(len(res['errors']) >= 1)

            self.assertGreater(total_checked, 1000)
            self.assertGreater(valid_count, 0)

    def test_slice_clips_rebased_srt_and_optional_real_ffmpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            srt = self._write_sample_srt(tdir / 'source.srt', count=6, step_sec=5)
            # 6 cues * 5s = 30s total. Pick [1..2] (10s) and [4..5] (10s) with min_sec=10, max_sec=15.
            raw_clips = [
                {'from': 1, 'to': 2, 'title': 'Hook Arc', 'caption': 'Clip 1 caption'},
                {'from': 4, 'to': 5, 'title': 'Closing Takeaway', 'caption': 'Clip 2 caption'},
            ]

            # Dry-run checks command construction and rebased SRT validity without requiring video file
            dry = self.vops.slice_clips(
                tdir / 'dummy.mp4', srt, raw_clips, tdir / 'out_dry',
                min_sec=10.0, max_sec=15.0, aspect='9:16', burn_subtitles=True, dry_run=True,
            )
            self.assertTrue(dry['ok'])
            self.assertEqual(dry['clipCount'], 2)
            self.assertIn('scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920', ' '.join(dry['sliced'][0]['ffmpegCommand']))

            _, cues = self.vops.parse_subtitle_cues(srt)
            rebased = self.vops.render_rebased_srt(cues, 1, 2)
            rebased_path = tdir / 'rebased.srt'
            rebased_path.write_text(rebased, encoding='utf-8')
            self.assertTrue(rebased.startswith('1\n00:00:00,000 --> 00:00:05,000\n'))
            val = self.vops.validate_srt(rebased_path)
            self.assertTrue(val['ok'], val)

            # Mutation check: overlapping clips must fail slice_clips and write zero files
            bad = self.vops.slice_clips(
                tdir / 'dummy.mp4', srt,
                [{'from': 0, 'to': 2, 'title': 'A'}, {'from': 2, 'to': 4, 'title': 'B'}],
                tdir / 'out_bad', min_sec=10.0, max_sec=20.0, dry_run=True,
            )
            self.assertFalse(bad['ok'])
            self.assertEqual(bad['sliced'], [])

            # If local ffmpeg is installed, run a real end-to-end 30s synthetic MP4 slice and probe output
            if shutil.which('ffmpeg') and shutil.which('ffprobe'):
                src_mp4 = tdir / 'real_source.mp4'
                gen = subprocess.run(
                    [
                        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                        '-f', 'lavfi', '-i', 'color=c=blue:s=320x180:d=30:r=10',
                        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=30',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                        str(src_mp4),
                    ],
                    capture_output=True, text=True, check=False, timeout=60,
                )
                if gen.returncode == 0:
                    real_out = tdir / 'out_real'
                    real = self.vops.slice_clips(
                        src_mp4, srt, raw_clips, real_out,
                        min_sec=10.0, max_sec=15.0, aspect='9:16', burn_subtitles=False, dry_run=False,
                    )
                    self.assertTrue(real['ok'])
                    self.assertTrue(Path(real['manifestPath']).is_file())
                    first_clip = Path(real['sliced'][0]['videoPath'])
                    first_srt = Path(real['sliced'][0]['srtPath'])
                    self.assertTrue(first_clip.is_file())
                    self.assertTrue(first_srt.is_file())
                    probed = self.vops.probe_video(first_clip)
                    self.assertEqual(probed['width'], 1080)
                    self.assertEqual(probed['height'], 1920)
                    self.assertAlmostEqual(probed['durationSec'], 10.0, delta=0.6)
                    self.assertTrue(self.vops.validate_srt(first_srt)['ok'])

                    # Verify --burn-subtitles either renders cleanly (when libass is present) or fails with an actionable hint
                    burn_out = tdir / 'out_burn'
                    if self.vops.ffmpeg_has_filter('subtitles'):
                        burned = self.vops.slice_clips(
                            src_mp4, srt, raw_clips[:1], burn_out,
                            min_sec=10.0, max_sec=15.0, aspect='9:16', burn_subtitles=True, dry_run=False,
                        )
                        self.assertTrue(burned['ok'])
                        self.assertTrue(Path(burned['sliced'][0]['videoPath']).is_file())
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'libass'):
                            self.vops.slice_clips(
                                src_mp4, srt, raw_clips[:1], burn_out,
                                min_sec=10.0, max_sec=15.0, aspect='9:16', burn_subtitles=True, dry_run=False,
                            )


if __name__ == '__main__':
    unittest.main()
