"""Tests for signal_gate.py, fuzzy repeat-annotating score_topics.py, and 6-source global / CN envelope pipelines."""
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
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
GLOBAL_SCRIPTS = SKILLS / 'topic-research-global' / 'scripts'
CN_SCRIPTS = SKILLS / 'topic-research-cn' / 'scripts'


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def iso_utc(delta_hours: float = 0.0) -> str:
    dt = datetime.now(timezone.utc) + timedelta(hours=delta_hours)
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


class SignalGateAndPipelineTest(unittest.TestCase):
    def test_ingest_fail_closed_bad_schema_stale_ttl_and_mixed_regions(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            bad_schema = tdir / 'bad.json'
            bad_schema.write_text(json.dumps({'schema': 'wrong/1', 'generatedAt': iso_utc(), 'region': 'global', 'items': []}), encoding='utf-8')
            r1 = subprocess.run(
                [sys.executable, str(LOOP_SCRIPTS / 'signal_gate.py'), 'ingest', '--input', str(bad_schema)],
                capture_output=True, text=True,
            )
            self.assertEqual(r1.returncode, 2)
            self.assertFalse(json.loads(r1.stdout)['ok'])

            stale = tdir / 'stale.json'
            stale.write_text(json.dumps({'schema': 'content-ops-signal-envelope/1', 'generatedAt': iso_utc(-10), 'region': 'global', 'items': []}), encoding='utf-8')
            r2 = subprocess.run(
                [sys.executable, str(LOOP_SCRIPTS / 'signal_gate.py'), 'ingest', '--input', str(stale)],
                capture_output=True, text=True,
            )
            self.assertEqual(r2.returncode, 2)
            self.assertIn('stale envelope', r2.stdout)

            cn_env = tdir / 'cn.json'
            gl_env = tdir / 'gl.json'
            cn_env.write_text(json.dumps({'schema': 'content-ops-signal-envelope/1', 'generatedAt': iso_utc(), 'region': 'cn', 'items': []}), encoding='utf-8')
            gl_env.write_text(json.dumps({'schema': 'content-ops-signal-envelope/1', 'generatedAt': iso_utc(), 'region': 'global', 'items': []}), encoding='utf-8')
            r3 = subprocess.run(
                [sys.executable, str(LOOP_SCRIPTS / 'signal_gate.py'), 'ingest', '--input', str(cn_env), '--input', str(gl_env)],
                capture_output=True, text=True,
            )
            self.assertEqual(r3.returncode, 2)
            self.assertIn('mixed regions', r3.stdout)

    def test_ingest_grounding_keep_richest_dedupe_and_seen_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            ws = tdir / 'content-ops'
            (ws / 'inbox').mkdir(parents=True)

            env1 = tdir / 'env1.json'
            env2 = tdir / 'env2.json'
            env1.write_text(json.dumps({
                'schema': 'content-ops-signal-envelope/1',
                'generatedAt': iso_utc(-0.1),
                'region': 'global',
                'provenance': 'public_api',
                'source': 'hackernews',
                'items': [
                    {
                        'title': 'Major Runtime Release',
                        'url': 'https://Example.com/release/?utm_source=hn&b=2&a=1#top',
                        'publishedAt': iso_utc(-2),
                        'hotNormalized': 72.0,
                        'engagement': {'score': 120, 'comments': 25},
                        'snippet': 'Short summary.',
                        'isSeedListing': True,
                    },
                    {
                        'title': 'Missing URL Row',
                        'url': 'javascript:alert(1)',
                        'publishedAt': iso_utc(-1),
                    },
                    {
                        'title': 'Bad Date Row',
                        'url': 'https://example.com/bad-date',
                        'publishedAt': 'yesterday',
                    },
                    {
                        'title': 'Too Old Row',
                        'url': 'https://example.com/old',
                        'publishedAt': iso_utc(-24 * 45),
                    },
                ],
            }), encoding='utf-8')

            env2.write_text(json.dumps({
                'schema': 'content-ops-signal-envelope/1',
                'generatedAt': iso_utc(-0.1),
                'region': 'global',
                'provenance': 'connector',
                'source': 'x',
                'items': [
                    {
                        'title': 'Major Runtime Release (X thread)',
                        'url': 'https://example.com/release?a=1&b=2&fbclid=xyz',
                        'publishedAt': iso_utc(-1),
                        'hotNormalized': 88.5,
                        'engagement': {'likes': 410, 'comments': 90},
                        'snippet': 'Much richer detailed release thread excerpt with concrete benchmark numbers.',
                        'topComments': [
                            {'author': '@builder', 'text': 'Latency dropped 40% in production.', 'likes': 95},
                        ],
                        'isSeedListing': True,
                    },
                ],
            }), encoding='utf-8')

            pool_path = tdir / 'pool.json'
            run1 = subprocess.run(
                [
                    sys.executable, str(LOOP_SCRIPTS / 'signal_gate.py'), 'ingest',
                    '--input', str(env1), '--input', str(env2),
                    '--workspace', str(ws), '--window-days', '30', '--mark-seen',
                    '--output', str(pool_path),
                ],
                capture_output=True, text=True, check=True,
            )
            pool = json.loads(run1.stdout)
            self.assertTrue(pool['ok'])
            self.assertEqual(pool['stats']['dropped'], 3)
            self.assertEqual(pool['stats']['droppedReasons']['invalid_url'], 1)
            self.assertEqual(pool['stats']['droppedReasons']['invalid_published_at'], 1)
            self.assertEqual(pool['stats']['droppedReasons']['out_of_window'], 1)
            self.assertEqual(pool['stats']['deduped'], 1)
            self.assertEqual(pool['stats']['deltaCount'], 1)

            item = pool['items'][0]
            self.assertEqual(item['canonicalUrl'], 'https://example.com/release?a=1&b=2')
            self.assertEqual(item['sources'], ['hackernews', 'x'])
            self.assertEqual(item['distinctSources'], 2)
            self.assertEqual(item['seedSourceCount'], 2)
            self.assertEqual(item['hotNormalized'], 88.5)
            self.assertEqual(item['engagement']['likes'], 410.0)
            self.assertEqual(item['engagement']['score'], 120.0)
            self.assertEqual(len(item['topComments']), 1)
            self.assertIn('concrete benchmark', item['snippet'])

            # Second run against same workspace must yield empty delta
            run2 = subprocess.run(
                [
                    sys.executable, str(LOOP_SCRIPTS / 'signal_gate.py'), 'ingest',
                    '--input', str(env1), '--workspace', str(ws),
                ],
                capture_output=True, text=True, check=True,
            )
            pool2 = json.loads(run2.stdout)
            self.assertEqual(pool2['stats']['skippedSeen'], 1)
            self.assertEqual(pool2['stats']['deltaCount'], 0)

    def test_gate_enforces_provenance_floor_junk_anti_cheat_and_nothing_solid(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            pool_path = tdir / 'pool.json'
            pool_path.write_text(json.dumps({
                'schema': 'content-ops-signal-pool/1',
                'ok': True,
                'region': 'global',
                'items': [
                    {
                        'canonicalUrl': 'https://example.com/multi',
                        'sources': ['hackernews', 'lobsters'],
                        'seedSources': ['hackernews', 'lobsters'],
                        'isPrimarySource': False,
                        'hotNormalized': 50.0,
                        'engagement': {'score': 45},
                    },
                    {
                        'canonicalUrl': 'https://example.com/paper',
                        'sources': ['arxiv'],
                        'seedSources': ['arxiv'],
                        'isPrimarySource': True,
                        'hotNormalized': 20.0,
                        'engagement': {'score': 0},
                    },
                    {
                        'canonicalUrl': 'https://example.com/junk-single-seed',
                        'sources': ['x', 'reddit'],
                        'seedSources': ['x'],
                        'isPrimarySource': False,
                        'hotNormalized': 99.0,
                        'engagement': {'likes': 900},
                    },
                    {
                        'canonicalUrl': 'https://example.com/weak',
                        'sources': ['devto'],
                        'seedSources': ['devto'],
                        'isPrimarySource': False,
                        'hotNormalized': 30.0,
                        'engagement': {'likes': 4},
                    },
                ],
            }), encoding='utf-8')

            # 1. Mixed batch with hallucinated URL fails strict mode (exit 2)
            cands = tdir / 'cands.json'
            cands.write_text(json.dumps({
                'candidates': [
                    {'title': 'Cross-source win', 'evidenceUrls': ['https://example.com/multi']},
                    {'title': 'Primary paper', 'evidenceUrls': ['https://example.com/paper']},
                    {'title': 'Junk bypass attempt', 'evidenceUrls': ['https://example.com/junk-single-seed'], 'junkShape': True},
                    {'title': 'Weak chatter', 'evidenceUrls': ['https://example.com/weak']},
                    {'title': 'Hallucinated link', 'evidenceUrls': ['https://example.com/never-fetched']},
                ],
            }), encoding='utf-8')
            res = subprocess.run(
                [sys.executable, str(LOOP_SCRIPTS / 'signal_gate.py'), 'gate', '--pool', str(pool_path), '--candidates', str(cands), '--strict'],
                capture_output=True, text=True,
            )
            self.assertEqual(res.returncode, 2)
            rep = json.loads(res.stdout)
            self.assertEqual(rep['counts']['passed'], 2)
            self.assertEqual(rep['counts']['provenanceViolations'], 1)
            rej_by_title = {r['title']: r['rejectionReasons'] for r in rep['rejected']}
            self.assertIn('junk_shape_requires_multi_seed_sources', rej_by_title['Junk bypass attempt'])
            self.assertTrue(any('below_signal_floor' in m for m in rej_by_title['Weak chatter']))
            self.assertTrue(any('ungrounded_urls' in m for m in rej_by_title['Hallucinated link']))

            # 2. Honest empty state when only weak grounded signal exists -> exit 0 + nothing_solid
            weak_only = tdir / 'weak.json'
            weak_only.write_text(json.dumps({
                'candidates': [{'title': 'Weak chatter', 'evidenceUrls': ['https://example.com/weak']}],
            }), encoding='utf-8')
            res_empty = subprocess.run(
                [sys.executable, str(LOOP_SCRIPTS / 'signal_gate.py'), 'gate', '--pool', str(pool_path), '--candidates', str(weak_only), '--strict'],
                capture_output=True, text=True, check=True,
            )
            rep_empty = json.loads(res_empty.stdout)
            self.assertEqual(rep_empty['outcome'], 'nothing_solid')
            self.assertEqual(rep_empty['weakSignal']['title'], 'Weak chatter')

    def test_watchlist_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / 'content-ops'
            ws.mkdir()
            add = subprocess.run(
                [
                    sys.executable, str(LOOP_SCRIPTS / 'signal_gate.py'), 'watchlist', str(ws), 'add',
                    '--id', 'ai-agents', '--query', 'AI agent frameworks', '--region', 'global',
                    '--cadence', 'daily', '--platforms', 'x-twitter,linkedin',
                ],
                capture_output=True, text=True, check=True,
            )
            self.assertTrue(json.loads(add.stdout)['ok'])

            due1 = json.loads(subprocess.run(
                [sys.executable, str(LOOP_SCRIPTS / 'signal_gate.py'), 'watchlist', str(ws), 'due'],
                capture_output=True, text=True, check=True,
            ).stdout)
            self.assertEqual(due1['dueCount'], 1)

            subprocess.run(
                [
                    sys.executable, str(LOOP_SCRIPTS / 'signal_gate.py'), 'watchlist', str(ws), 'mark-run',
                    '--id', 'ai-agents', '--new-signals', '3', '--outcome', 'solid',
                ],
                capture_output=True, text=True, check=True,
            )
            due2 = json.loads(subprocess.run(
                [sys.executable, str(LOOP_SCRIPTS / 'signal_gate.py'), 'watchlist', str(ws), 'due'],
                capture_output=True, text=True, check=True,
            ).stdout)
            self.assertEqual(due2['dueCount'], 0)

            rm = json.loads(subprocess.run(
                [sys.executable, str(LOOP_SCRIPTS / 'signal_gate.py'), 'watchlist', str(ws), 'remove', '--id', 'ai-agents'],
                capture_output=True, text=True, check=True,
            ).stdout)
            self.assertTrue(rm['ok'])

    def test_score_topics_annotate_only_fuzzy_repeat_and_nothing_solid(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / 'content-ops'
            (ws / 'topics').mkdir(parents=True)
            (ws / 'drafts' / 'drf-1').mkdir(parents=True)
            (ws / 'drafts' / 'drf-1' / 'meta.json').write_text(json.dumps({
                'draftId': 'drf-1', 'topicId': 'top-old', 'status': 'published',
            }), encoding='utf-8')
            (ws / 'publish-log.jsonl').write_text(json.dumps({
                'publishId': 'pub-1', 'draftId': 'drf-1', 'status': 'published',
                'publishedAt': '2026-01-10T00:00:00Z', 'publicUrl': 'https://example.com/p/1',
            }) + '\n', encoding='utf-8')

            topics_file = ws / 'topics' / 'topics.json'
            topics_file.write_text(json.dumps({
                'version': 1,
                'topics': [
                    {
                        'topicId': 'top-old',
                        'title': '本地部署开源大模型隐私安全指南',
                        'sourceType': 'platform_trend',
                        'cooldownKey': 'local-llm-old',
                        'scores': {'audiencePain': 5, 'evidenceStrength': 5, 'timeliness': 4, 'brandFit': 5},
                        'status': 'produced',
                        'createdAt': '2026-01-01T00:00:00Z',
                    },
                    {
                        'topicId': 'top-new-cn',
                        'title': '本地部署开源大模型隐私安全实战指南',
                        'sourceType': 'platform_trend',
                        'cooldownKey': 'local-llm-new-key',
                        'scores': {'audiencePain': 5, 'evidenceStrength': 5, 'timeliness': 4, 'brandFit': 5},
                        'status': 'candidate',
                        'createdAt': iso_utc(),
                    },
                ],
            }), encoding='utf-8')

            out = json.loads(subprocess.run(
                [sys.executable, str(LOOP_SCRIPTS / 'score_topics.py'), str(ws)],
                capture_output=True, text=True, check=True,
            ).stdout)
            # Non-destructive: both rows preserved!
            self.assertEqual(out['total'], 2)
            self.assertEqual(out['outcome'], 'solid')
            ann = out['shortlisted'][0]['repeatAnnotation']
            self.assertIsNotNone(ann)
            self.assertEqual(ann['matchedTopicId'], 'top-old')
            self.assertTrue(ann['alreadyCovered'])
            self.assertGreaterEqual(ann['overlap'], 0.6)

            # All weak candidates -> honest nothing_solid outcome
            topics_file.write_text(json.dumps({
                'version': 1,
                'topics': [{
                    'topicId': 'top-weak',
                    'title': 'Low signal rumor',
                    'sourceType': 'platform_trend',
                    'scores': {'audiencePain': 3, 'evidenceStrength': 2, 'timeliness': 4, 'brandFit': 4},
                    'status': 'candidate',
                }],
            }), encoding='utf-8')
            out_weak = json.loads(subprocess.run(
                [sys.executable, str(LOOP_SCRIPTS / 'score_topics.py'), str(ws)],
                capture_output=True, text=True, check=True,
            ).stdout)
            self.assertEqual(out_weak['outcome'], 'nothing_solid')
            self.assertEqual(out_weak['closestCandidate']['topicId'], 'top-weak')

    def test_global_6_sources_and_cn_envelope_pipe_to_signal_gate(self):
        now_ts = int(datetime.now(timezone.utc).timestamp())
        now_iso = iso_utc(-1)

        class MockHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith('/hn/top'):
                    body, ctype = json.dumps([101]).encode(), 'application/json'
                elif self.path.startswith('/hn/item/101'):
                    body, ctype = json.dumps({'id': 101, 'title': 'AI Agent Memory Architecture', 'score': 320, 'descendants': 88, 'by': 'pg', 'time': now_ts, 'url': 'https://example.org/agent-memory'}).encode(), 'application/json'
                elif self.path.startswith('/lobsters'):
                    body, ctype = json.dumps([{'title': 'Zero-dependency Python tooling', 'score': 55, 'comment_count': 12, 'url': 'https://example.org/py-tools', 'tags': ['python'], 'created_at': now_iso, 'submitter_user': {'username': 'alice'}}]).encode(), 'application/json'
                elif self.path.startswith('/github'):
                    body, ctype = json.dumps({'items': [{'full_name': 'org/agent-kit', 'description': 'Fast agent runtime', 'html_url': 'https://github.com/org/agent-kit', 'stargazers_count': 840, 'forks_count': 90, 'pushed_at': now_iso, 'owner': {'login': 'org'}, 'language': 'Python'}]}).encode(), 'application/json'
                elif self.path.startswith('/polymarket'):
                    body, ctype = json.dumps([{'question': 'Will open weights beat frontier by Q4?', 'slug': 'open-weights-q4', 'volume24hr': 125000.5, 'updatedAt': now_iso, 'description': 'Prediction market.'}]).encode(), 'application/json'
                elif self.path.startswith('/devto'):
                    body, ctype = json.dumps([{'title': 'Shipping lean skills', 'url': 'https://dev.to/alice/lean-skills', 'public_reactions_count': 180, 'comments_count': 30, 'published_at': now_iso, 'tag_list': ['ai'], 'user': {'username': 'alice'}}]).encode(), 'application/json'
                elif self.path.startswith('/arxiv'):
                    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
                    <feed xmlns="http://www.w3.org/2005/Atom">
                      <entry>
                        <id>http://arxiv.org/abs/2611.00001v1</id>
                        <published>{now_iso}</published>
                        <title>Deterministic Gates for Agentic Systems</title>
                        <summary>Enforcing hard invariants around LLM reasoning.</summary>
                        <author><name>Jane Doe</name></author>
                      </entry>
                    </feed>'''
                    body, ctype = xml.encode(), 'application/atom+xml'
                elif self.path.startswith('/weibo'):
                    body, ctype = json.dumps({'data': {'realtime': [{'note': '开源AI框架发布', 'num': 990000}]}}).encode(), 'application/json'
                elif self.path.startswith('/toutiao'):
                    body, ctype = json.dumps({'data': [{'Title': '国产模型推理提速', 'HotValue': 850000, 'Url': 'https://www.toutiao.com/trending/1'}]}).encode(), 'application/json'
                elif self.path.startswith('/baidu'):
                    body, ctype = json.dumps({'data': {'cards': [{'content': [{'content': [{'word': '智能体落地案例', 'hotScore': 760000, 'url': 'https://www.baidu.com/s?wd=agent'}]}]}]}}).encode(), 'application/json'
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header('Content-Type', ctype)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                return

        srv = ThreadingHTTPServer(('127.0.0.1', 0), MockHandler)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            gmod = load_module(GLOBAL_SCRIPTS / 'fetch_hotspots_global.py', 'fetch_hotspots_global_test')
            mock_gl = {
                'hackernews': f'http://127.0.0.1:{port}/hn/top',
                'lobsters': f'http://127.0.0.1:{port}/lobsters',
                'github': f'http://127.0.0.1:{port}/github',
                'polymarket': f'http://127.0.0.1:{port}/polymarket',
                'devto': f'http://127.0.0.1:{port}/devto',
                'arxiv': f'http://127.0.0.1:{port}/arxiv',
            }
            with tempfile.TemporaryDirectory() as tmp:
                env_file = Path(tmp) / 'gl-env.json'
                with patch.dict(gmod.ENDPOINTS, mock_gl), patch.object(gmod, 'HN_ITEM_TMPL', f'http://127.0.0.1:{port}/hn/item/{{id}}'):
                    import io
                    buf = io.StringIO()
                    with patch('sys.stdout', buf):
                        rc = gmod.main(['--limit', '20', '--envelope'])
                    self.assertEqual(rc, 0)
                    env_doc = json.loads(buf.getvalue())
                    self.assertEqual(env_doc['schema'], 'content-ops-signal-envelope/1')
                    self.assertEqual(len(env_doc['sourcesOk']), 6)
                    env_file.write_text(json.dumps(env_doc), encoding='utf-8')

                ing = json.loads(subprocess.run(
                    [sys.executable, str(LOOP_SCRIPTS / 'signal_gate.py'), 'ingest', '--input', str(env_file)],
                    capture_output=True, text=True, check=True,
                ).stdout)
                self.assertTrue(ing['ok'])
                self.assertEqual(ing['stats']['deduped'], 6)
                self.assertEqual(ing['stats']['dropped'], 0)

                # CN envelope check
                cmod = load_module(CN_SCRIPTS / 'fetch_hotspots_cn.py', 'fetch_hotspots_cn_test')
                mock_cn = {
                    'weibo': f'http://127.0.0.1:{port}/weibo',
                    'toutiao': f'http://127.0.0.1:{port}/toutiao',
                    'baidu': f'http://127.0.0.1:{port}/baidu',
                }
                cn_file = Path(tmp) / 'cn-env.json'
                with patch.dict(cmod.ENDPOINTS, mock_cn):
                    buf2 = io.StringIO()
                    with patch('sys.stdout', buf2):
                        rc2 = cmod.main(['--limit', '10', '--envelope'])
                    self.assertEqual(rc2, 0)
                    cn_doc = json.loads(buf2.getvalue())
                    self.assertEqual(cn_doc['region'], 'cn')
                    self.assertEqual(len(cn_doc['sourcesOk']), 3)
                    cn_file.write_text(json.dumps(cn_doc), encoding='utf-8')

                ing_cn = json.loads(subprocess.run(
                    [sys.executable, str(LOOP_SCRIPTS / 'signal_gate.py'), 'ingest', '--input', str(cn_file)],
                    capture_output=True, text=True, check=True,
                ).stdout)
                self.assertTrue(ing_cn['ok'])
                self.assertEqual(ing_cn['stats']['deduped'], 3)
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == '__main__':
    unittest.main()
