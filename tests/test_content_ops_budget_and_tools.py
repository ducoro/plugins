"""Tests for context budget guard, source ledger, 5-dim editorial eval, corpus playbook builder, diagnose, WeChat stats & gallery."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import re
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
MEDIA_SCRIPTS = SKILLS / 'longform-writing' / 'scripts'
WECHAT_SCRIPTS = SKILLS / 'platform-wechat-official' / 'scripts'
ANALYTICS_SCRIPTS = SKILLS / 'engagement-and-analytics' / 'scripts'


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def estimate_tokens(text: str) -> int:
    """Rough tokenizer-agnostic estimate: ~1.5 chars/token for CJK, ~4 chars/token for ASCII."""
    cjk = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', text))
    other = max(0, len(text) - cjk)
    return int(cjk / 1.5 + other / 4.0)


class ContentOpsBudgetAndToolsTest(unittest.TestCase):
    def test_context_budget_guard_keeps_hot_path_lean(self):
        # 1. WeChat long-form hot path
        wechat_hot_path = [
            SKILLS / 'content-ops-loop' / 'SKILL.md',
            SKILLS / 'topic-research-cn' / 'SKILL.md',
            SKILLS / 'longform-writing' / 'SKILL.md',
            SKILLS / 'platform-wechat-official' / 'SKILL.md',
            SKILLS / 'longform-writing' / 'references' / 'editorial-brief-and-rubric.md',
            SKILLS / 'longform-writing' / 'references' / 'writing-personas.md',
        ]
        # 2. X/Twitter short-form hot path (completely isolated from WeChat/long-form)
        x_hot_path = [
            SKILLS / 'content-ops-loop' / 'SKILL.md',
            SKILLS / 'topic-research-global' / 'SKILL.md',
            SKILLS / 'shortform-social' / 'SKILL.md',
            SKILLS / 'platform-x-twitter' / 'SKILL.md',
        ]
        for label, files, ceiling in [
            ('wechat-longform', wechat_hot_path, 12000),
            ('x-shortform', x_hot_path, 6500),
        ]:
            total_tokens = 0
            for fp in files:
                self.assertTrue(fp.is_file(), f'Missing hot-path file: {fp}')
                toks = estimate_tokens(fp.read_text(encoding='utf-8'))
                self.assertLess(toks, 3500, f'Single skill/reference too bloated ({toks} est. tokens): {fp.name}')
                total_tokens += toks
            self.assertLess(total_tokens, ceiling, f'{label} hot-path budget exceeded: {total_tokens} est. tokens')
        # Ensure old monolithic directories are gone
        self.assertFalse((SKILLS / 'topic-research').exists())
        self.assertFalse((SKILLS / 'media-production').exists())

    def test_source_ledger_grounding_and_rejection_of_unverified_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            ledger = tdir / 'sources.json'
            claims = tdir / 'claims.json'

            # Verified source without URL must fail (blocks marking model memory as verified)
            bad = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'source_ledger.py'), 'add',
                 '--ledger', str(ledger), '--title', 'Memory', '--claim', 'Invented stat', '--status', 'verified'],
                capture_output=True, text=True,
            )
            self.assertEqual(bad.returncode, 2)
            self.assertIn('http(s):// URL', bad.stderr)

            # Add one verified source + one user_provided source
            ok1 = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'source_ledger.py'), 'add',
                 '--ledger', str(ledger), '--title', 'Official Release', '--claim', 'Supports 18 themes',
                 '--url', 'https://example.com/release', '--publisher', 'Example', '--status', 'verified'],
                capture_output=True, text=True, check=True,
            )
            s1 = json.loads(ok1.stdout)['id']
            ok2 = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'source_ledger.py'), 'add',
                 '--ledger', str(ledger), '--title', 'Founder Note', '--claim', 'Migrated 3 accounts in Q1',
                 '--status', 'user_provided'],
                capture_output=True, text=True, check=True,
            )
            s2 = json.loads(ok2.stdout)['id']

            # Supports non-web verified provenance (local_file / first_hand_test / publication_or_interview)
            ok_local = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'source_ledger.py'), 'add',
                 '--ledger', str(ledger), '--title', 'Internal Benchmark PDF', '--claim', 'p95 latency 120ms',
                 '--source-type', 'local_file', '--locator', 'reports/q1-bench.pdf#p4', '--status', 'verified'],
                capture_output=True, text=True, check=True,
            )
            s3 = json.loads(ok_local.stdout)['id']
            bad_local = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'source_ledger.py'), 'add',
                 '--ledger', str(ledger), '--title', 'No Locator', '--claim', 'Unanchored',
                 '--source-type', 'first_hand_test', '--status', 'verified'],
                capture_output=True, text=True,
            )
            self.assertEqual(bad_local.returncode, 2)

            # Valid grounded claims pass (web_url + local_file + user_provided + opinion)
            claims.write_text(json.dumps({
                'version': 1,
                'claims': [
                    {'id': 'C1', 'text': 'Supports 18 themes', 'type': 'fact', 'sourceIds': [s1], 'status': 'supported'},
                    {'id': 'C1b', 'text': 'p95 latency 120ms', 'type': 'fact', 'sourceIds': [s3], 'status': 'supported'},
                    {'id': 'C2', 'text': 'We migrated 3 accounts', 'type': 'user_experience', 'sourceIds': [s2], 'status': 'supported'},
                    {'id': 'C3', 'text': 'Consistent loops beat one-offs', 'type': 'opinion', 'sourceIds': [], 'status': 'supported'},
                ],
            }), encoding='utf-8')
            ver_ok = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'source_ledger.py'), 'verify-claims',
                 '--ledger', str(ledger), '--claims', str(claims), '--json'],
                capture_output=True, text=True,
            )
            self.assertEqual(ver_ok.returncode, 0, ver_ok.stdout + ver_ok.stderr)
            self.assertTrue(json.loads(ver_ok.stdout)['ok'])

            # Fact pointing only to user_provided or user_experience with no source fails
            claims.write_text(json.dumps({
                'version': 1,
                'claims': [
                    {'id': 'C1', 'text': 'Market grew 80%', 'type': 'fact', 'sourceIds': [s2], 'status': 'supported'},
                    {'id': 'C2', 'text': 'My friend told me yesterday', 'type': 'user_experience', 'sourceIds': [], 'status': 'supported'},
                ],
            }), encoding='utf-8')
            ver_fail = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'source_ledger.py'), 'verify-claims',
                 '--ledger', str(ledger), '--claims', str(claims), '--json'],
                capture_output=True, text=True,
            )
            self.assertEqual(ver_fail.returncode, 2)
            rep = json.loads(ver_fail.stdout)
            self.assertFalse(rep['ok'])
            self.assertEqual(rep['errors'], 2)

    def test_content_eval_5_dimension_gate_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            draft = tdir / 'draft.md'
            final = tdir / 'final.md'
            assess = tdir / 'assessment.json'
            out_rep = tdir / 'review-report.json'
            draft.write_text('# Title\n\n## Old Section\n\nInitial rough paragraph.\n', encoding='utf-8')
            final.write_text('# Title\n\n## Revised Section\n\nSharper verified paragraph with source.\n', encoding='utf-8')

            # Passing case (avg >= 4.0, min >= 3.0, decision=pass, blockers=[])
            assess.write_text(json.dumps({
                'decision': 'pass',
                'passNumber': 1,
                'dimensions': {'accuracy': 5, 'viewpoint': 4, 'usefulness': 4, 'voice': 4, 'readability': 3},
                'blockers': [],
                'majorIssues': [],
            }), encoding='utf-8')
            ok = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'content_eval.py'),
                 '--draft', str(draft), '--final', str(final), '--assessment', str(assess),
                 '-o', str(out_rep), '--strict', '--json'],
                capture_output=True, text=True,
            )
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            rep = json.loads(ok.stdout)
            self.assertTrue(rep['publishable'])
            self.assertTrue(rep['structureChanged'])
            self.assertGreater(rep['editRatio'], 0.1)

            # Failing case: one dimension < 3 and blocker present
            assess.write_text(json.dumps({
                'decision': 'pass',
                'passNumber': 2,
                'dimensions': {'accuracy': 2, 'viewpoint': 5, 'usefulness': 5, 'voice': 5, 'readability': 5},
                'blockers': ['Unsupported benchmark figure'],
            }), encoding='utf-8')
            fail = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'content_eval.py'),
                 '--draft', str(draft), '--final', str(final), '--assessment', str(assess), '--strict', '--json'],
                capture_output=True, text=True,
            )
            self.assertEqual(fail.returncode, 1)
            frep = json.loads(fail.stdout)
            self.assertFalse(frep['publishable'])
            self.assertEqual(len(frep['failureReasons']), 2)

            # Allows passNumber >= 1 (no arbitrary 2-pass cap) and rejects passNumber=0
            assess.write_text(json.dumps({
                'decision': 'pass',
                'passNumber': 3,
                'dimensions': {'accuracy': 5, 'viewpoint': 5, 'usefulness': 5, 'voice': 5, 'readability': 5},
            }), encoding='utf-8')
            ok_pass3 = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'content_eval.py'),
                 '--draft', str(draft), '--final', str(final), '--assessment', str(assess), '--strict'],
                capture_output=True, text=True,
            )
            self.assertEqual(ok_pass3.returncode, 0, ok_pass3.stderr)

            assess.write_text(json.dumps({
                'decision': 'pass',
                'passNumber': 0,
                'dimensions': {'accuracy': 5, 'viewpoint': 5, 'usefulness': 5, 'voice': 5, 'readability': 5},
            }), encoding='utf-8')
            bad_pass = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'content_eval.py'),
                 '--draft', str(draft), '--final', str(final), '--assessment', str(assess)],
                capture_output=True, text=True,
            )
            self.assertEqual(bad_pass.returncode, 2)

    def test_build_playbook_init_style_corpus_analysis_and_diagnose(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / 'content-ops'
            subprocess.run(
                [sys.executable, str(LOOP_SCRIPTS / 'init_workspace.py'), str(ws), '--timezone', 'Asia/Shanghai'],
                capture_output=True, text=True, check=True,
            )

            # Initialize style profile with automatic tone -> persona mapping
            init_res = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'build_playbook.py'), 'init-style',
                 '--workspace', str(ws), '--name', 'Signal Lab', '--industry', 'AI Engineering',
                 '--topics', 'Agents,Systems,Workflows', '--tone', '严谨数据研究风格', '--theme', 'impeccable'],
                capture_output=True, text=True, check=True,
            )
            profile_out = json.loads(init_res.stdout)
            self.assertEqual(profile_out['profile']['writingPersona'], 'cold-analyst')
            self.assertTrue(Path(profile_out['profilePath']).is_file())

            # Drop historical articles into style/corpus/ and analyze in batches
            corpus_dir = ws / 'style' / 'corpus'
            for idx in range(1, 4):
                (corpus_dir / f'article-0{idx}.md').write_text(
                    f'# Historical Essay {idx}\n\n## Section A\n\nParagraph one.\n\n## Section B\n\nParagraph two.\n',
                    encoding='utf-8',
                )
            an_res = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'build_playbook.py'), 'analyze',
                 '--workspace', str(ws), '--batch-size', '2', '--json'],
                capture_output=True, text=True, check=True,
            )
            an = json.loads(an_res.stdout)
            self.assertTrue(an['ok'])
            self.assertEqual(an['stats']['totalArticles'], 3)
            self.assertEqual(an['batchCount'], 2)

            # Write playbook & run diagnose ensuring secrets are never leaked
            (ws / 'style' / 'style-playbook.md').write_text('# Style Playbook\n- Short sentences.\n', encoding='utf-8')
            env = dict(os.environ)
            fake_secret = 'SUPER_SECRET_NEVER_PRINT_9999'
            env['WECHAT_OFFICIAL_APP_ID'] = 'wx_fake_id'
            env['WECHAT_OFFICIAL_APP_SECRET'] = fake_secret
            diag_res = subprocess.run(
                [sys.executable, str(LOOP_SCRIPTS / 'diagnose.py'), '--workspace', str(ws), '--json'],
                capture_output=True, text=True, env=env, check=True,
            )
            self.assertNotIn(fake_secret, diag_res.stdout)
            diag = json.loads(diag_res.stdout)
            self.assertTrue(diag['ok'])
            self.assertIn('wechat-official', diag['configuredApiPlatforms'])
            self.assertGreaterEqual(diag['styleReadinessScore'], 7)

    def test_wechat_fetch_stats_appends_snapshots_and_feeds_aggregate_metrics_plus_gallery(self):
        client = load_module(WECHAT_SCRIPTS / 'client.py', 'wechat_client_stats_mod')

        class MockWeChatStatsHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def do_POST(self):
                length = int(self.headers.get('Content-Length', '0'))
                _ = self.rfile.read(length)
                if self.path.startswith('/datacube/getarticlesummary'):
                    body = {'list': [{
                        'msgid': '2650001_1',
                        'title': 'File-Backed Content Loops',
                        'ref_date': '2026-11-20',
                        'int_page_read_count': 4200,
                        'ori_page_read_count': 310,
                        'share_count': 180,
                        'add_to_fav_count': 95,
                        'like_count': 240,
                    }]}
                elif self.path.startswith('/datacube/getarticletotal'):
                    body = {'list': [{
                        'msgid': '2650001_1',
                        'title': 'File-Backed Content Loops',
                        'ref_date': '2026-11-20',
                        'details': [{
                            'target_user': 12000,
                            'int_page_read_count': 4500,
                            'ori_page_read_count': 340,
                            'share_count': 195,
                            'add_to_fav_count': 102,
                            'like_count': 260,
                        }],
                    }]}
                else:
                    body = {'errcode': 0, 'list': []}
                raw = json.dumps(body).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        server = ThreadingHTTPServer(('127.0.0.1', 0), MockWeChatStatsHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                ws = Path(tmp) / 'content-ops'
                subprocess.run(
                    [sys.executable, str(LOOP_SCRIPTS / 'init_workspace.py'), str(ws)],
                    capture_output=True, text=True, check=True,
                )
                with patch.object(client, 'BASE', f'http://127.0.0.1:{server.server_port}'), \
                     patch.dict(os.environ, {'WECHAT_OFFICIAL_ACCESS_TOKEN': 'tok_stats_test'}):
                    args = type('Args', (), {
                        'days': 2,
                        'end_date': '2026-11-21',
                        'workspace': str(ws),
                        'account_id': 'acct-wx-main',
                        'window': '7d',
                        'dry_run': False,
                    })()
                    res = client.run_fetch_stats(args, 'tok_stats_test')
                    self.assertTrue(res['ok'])
                    self.assertEqual(res['articleCount'], 1)
                    self.assertEqual(res['articles'][0]['views'], 4500)
                    self.assertEqual(res['snapshotsAppended'], 1)

                # Feed directly into aggregate_metrics.py to verify seamless end-to-end compatibility
                agg = subprocess.run(
                    [sys.executable, str(ANALYTICS_SCRIPTS / 'aggregate_metrics.py'), str(ws), '--days', '14'],
                    capture_output=True, text=True, check=True,
                )
                agg_data = json.loads(agg.stdout)
                self.assertIn('wechat-official', agg_data['byPlatform'])
                self.assertEqual(agg_data['byPlatform']['wechat-official']['views'], 4500)
                self.assertEqual(agg_data['byPlatform']['wechat-official']['avgPlatformMetrics']['openRate'], 37.5)

                # Explicit fallback hints for 48001 (unverified personal account) and 40164 (IP not allowlisted)
                with self.assertRaises(RuntimeError) as ctx_48001:
                    client.check_wechat_error({'errcode': 48001, 'errmsg': 'api unauthorized'})
                self.assertIn('mp.weixin.qq.com', str(ctx_48001.exception))
                with self.assertRaises(RuntimeError) as ctx_40164:
                    client.check_wechat_error({'errcode': 40164, 'errmsg': 'invalid ip'})
                self.assertIn('IP not allowlisted', str(ctx_40164.exception))

                # Gallery rendering across all 18 standalone themes
                themes_dir = SKILLS / 'platform-wechat-official' / 'assets' / 'themes'
                self.assertEqual(len(list(themes_dir.glob('*.json'))), 18)
                self.assertFalse((SKILLS / 'platform-wechat-official' / 'assets' / 'themes.json').exists())
                gallery_path = Path(tmp) / 'gallery.html'
                gal_res = subprocess.run(
                    [sys.executable, str(WECHAT_SCRIPTS / 'render_wechat_html.py'),
                     '--gallery', str(gallery_path), '--json'],
                    capture_output=True, text=True, check=True,
                )
                gal_info = json.loads(gal_res.stdout)
                self.assertEqual(gal_info['themeCount'], 18)
                gal_html = gallery_path.read_text(encoding='utf-8')
                for tname in ('impeccable', 'ink', 'lobster-notes', 'github', 'minimal-gold', 'bytedance'):
                    self.assertIn(f'data-theme="{tname}"', gal_html)
                # Confirm distinct structural typography/H2 layouts actually render (not color-only swaps)
                rwh = load_module(WECHAT_SCRIPTS / 'render_wechat_html.py', 'render_wechat_html_distinct_mod')
                themes = rwh.load_themes()
                md = '# Title\n\n## Core Point\n\nBody text.\n\n> Quoted line.\n'
                h_lobster = rwh.WeChatRenderer(themes['lobster-notes']).convert(md)['html']
                h_ink = rwh.WeChatRenderer(themes['ink']).convert(md)['html']
                h_bauhaus = rwh.WeChatRenderer(themes['bauhaus']).convert(md)['html']
                h_impeccable = rwh.WeChatRenderer(themes['impeccable']).convert(md)['html']
                self.assertIn('background-color: #c8471c', h_lobster)
                self.assertIn('Songti SC', h_ink)
                self.assertIn('text-align: center', h_ink)
                self.assertIn('border-bottom: 4px solid', h_bauhaus)
                self.assertIn('border-left: 4px solid #1a6b5a', h_impeccable)
                self.assertIn('Songti SC', h_impeccable)
        finally:
            server.shutdown()
            server.server_close()

    def test_learn_edits_scope_isolation_time_decay_and_exemplar_ownership_safety(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / 'content-ops'
            draft = Path(tmp) / 'draft.md'
            final = Path(tmp) / 'final.md'
            draft.write_text('# Demo\n\nLong rambling opening paragraph that explains everything at once.\n', encoding='utf-8')
            final.write_text('# Demo\n\nShort punchy tutorial step one.\n\nShort punchy tutorial step two.\n', encoding='utf-8')

            # Record same edit twice under narrow scope content_type:tutorial
            for _ in range(2):
                subprocess.run(
                    [sys.executable, str(MEDIA_SCRIPTS / 'learn_edits.py'), 'record', str(ws),
                     '--draft', str(draft), '--final', str(final),
                     '--scope', 'content_type', '--scope-value', 'tutorial', '--json'],
                    capture_output=True, text=True, check=True,
                )

            # Matching scope sees hard standing rules; unrelated scope must NOT receive them
            tut = json.loads(subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'learn_edits.py'), 'summarize', str(ws),
                 '--content-type', 'tutorial', '--json'],
                capture_output=True, text=True, check=True,
            ).stdout)
            opi = json.loads(subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'learn_edits.py'), 'summarize', str(ws),
                 '--content-type', 'opinion', '--json'],
                capture_output=True, text=True, check=True,
            ).stdout)
            self.assertGreaterEqual(tut['standingCount'], 1)
            self.assertTrue(all(r['hard'] for r in tut['standingRules']))
            self.assertEqual(opi['standingCount'], 0)

            # Far-future evaluation date decays unconfirmed rules below 2.0 into expiredCount
            decayed = json.loads(subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'learn_edits.py'), 'summarize', str(ws),
                 '--content-type', 'tutorial', '--as-of', '2029-12-31', '--json'],
                capture_output=True, text=True, check=True,
            ).stdout)
            self.assertEqual(decayed['standingCount'], 0)
            self.assertGreaterEqual(decayed['expiredCount'], 1)

            # Exemplar ownership isolation: default third_party vs --user-authored, both block reusing personal materials
            ref_a = Path(tmp) / 'third_party.md'
            ref_b = Path(tmp) / 'mine.md'
            ref_a.write_text('# Third Party Essay\n\n## Section\n\nObservations from outside.\n', encoding='utf-8')
            ref_b.write_text('# My Own Essay\n\n## Section\n\nMy own structured essay.\n', encoding='utf-8')
            ex_a = json.loads(subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'extract_exemplar.py'), 'add', str(ws), str(ref_a),
                 '--source', 'External', '--framework', 'opinion', '--json'],
                capture_output=True, text=True, check=True,
            ).stdout)['exemplars'][0]
            ex_b = json.loads(subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'extract_exemplar.py'), 'add', str(ws), str(ref_b),
                 '--source', 'Self', '--framework', 'opinion', '--user-authored', '--json'],
                capture_output=True, text=True, check=True,
            ).stdout)['exemplars'][0]
            self.assertEqual(ex_a['ownership'], 'third_party')
            self.assertEqual(ex_b['ownership'], 'user')
            for ex in (ex_a, ex_b):
                self.assertEqual(ex['allowedUses'], ['style', 'structure'])
                self.assertFalse(ex['personalMaterialsReusable'])


if __name__ == '__main__':
    unittest.main()
