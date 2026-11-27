"""Opt-in live network smoke tests for zero-key public radar scripts.

Skipped during normal offline `unittest` runs so commits stay fast and deterministic.
Run explicitly to verify upstream public websites have not changed schemas or blocked access:

    RUN_LIVE_TESTS=1 python3 -m unittest tests/test_live_public_sources.py -v
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / 'plugins' / 'content-operations' / 'skills'
LOOP_SCRIPTS = SKILLS / 'content-ops-loop' / 'scripts'
GLOBAL_SCRIPTS = SKILLS / 'topic-research-global' / 'scripts'
CN_SCRIPTS = SKILLS / 'topic-research-cn' / 'scripts'

RUN_LIVE = os.environ.get('RUN_LIVE_TESTS') == '1'


@unittest.skipUnless(RUN_LIVE, 'Set RUN_LIVE_TESTS=1 to run live network smoke tests against real public endpoints.')
class LivePublicSourcesSmokeTest(unittest.TestCase):
    def test_live_global_public_radars_and_signal_gate_ingest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            ws = tdir / 'content-ops'
            (ws / 'inbox').mkdir(parents=True)

            proc = subprocess.run(
                [
                    sys.executable, str(GLOBAL_SCRIPTS / 'fetch_hotspots_global.py'),
                    '--sources', 'hackernews,lobsters,github,polymarket,devto,arxiv,gnews',
                    '--limit', '14', '--envelope',
                ],
                capture_output=True, text=True, check=True, timeout=45,
            )
            env = json.loads(proc.stdout)
            self.assertEqual(env['schema'], 'content-ops-signal-envelope/1')
            # Core 6 must succeed; arXiv occasionally returns transient 429 on rapid bursts
            for core_source in ('hackernews', 'lobsters', 'github', 'polymarket', 'devto', 'gnews'):
                self.assertIn(core_source, env['sourcesOk'], f'{core_source} failed: {env["sourcesFailed"]}')
            self.assertGreater(len(env['items']), 0)

            env_path = tdir / 'global-env.json'
            env_path.write_text(proc.stdout, encoding='utf-8')
            ing = json.loads(subprocess.run(
                [
                    sys.executable, str(LOOP_SCRIPTS / 'signal_gate.py'), 'ingest',
                    '--input', str(env_path), '--workspace', str(ws), '--mark-seen',
                ],
                capture_output=True, text=True, check=True,
            ).stdout)
            self.assertTrue(ing['ok'])
            self.assertEqual(ing['stats']['dropped'], 0, f'Unexpected dropped rows: {ing["rejectedRows"]}')
            self.assertEqual(ing['stats']['deltaCount'], len(env['items']))

            # Keyword mode live smoke test (HN Algolia + Google News RSS + GitHub)
            kw_proc = subprocess.run(
                [
                    sys.executable, str(GLOBAL_SCRIPTS / 'fetch_hotspots_global.py'),
                    '--sources', 'hackernews,gnews,github', '--query', 'grok bot',
                    '--window-days', '30', '--limit', '12', '--envelope',
                ],
                capture_output=True, text=True, check=True, timeout=45,
            )
            kw_env = json.loads(kw_proc.stdout)
            for s in ('hackernews', 'gnews', 'github'):
                self.assertIn(s, kw_env['sourcesOk'], f'keyword {s} failed: {kw_env["sourcesFailed"]}')
            kw_path = tdir / 'kw-env.json'
            kw_path.write_text(kw_proc.stdout, encoding='utf-8')
            kw_ing = json.loads(subprocess.run(
                [sys.executable, str(LOOP_SCRIPTS / 'signal_gate.py'), 'ingest', '--input', str(kw_path)],
                capture_output=True, text=True, check=True,
            ).stdout)
            self.assertTrue(kw_ing['ok'])
            self.assertEqual(kw_ing['stats']['dropped'], 0)

    def test_live_cn_public_radars_seo_and_signal_gate_ingest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            ws = tdir / 'content-ops'
            (ws / 'inbox').mkdir(parents=True)

            proc = subprocess.run(
                [sys.executable, str(CN_SCRIPTS / 'fetch_hotspots_cn.py'), '--limit', '12', '--envelope'],
                capture_output=True, text=True, check=True, timeout=30,
            )
            env = json.loads(proc.stdout)
            self.assertEqual(env['schema'], 'content-ops-signal-envelope/1')
            for src in ('weibo', 'toutiao', 'baidu'):
                self.assertIn(src, env['sourcesOk'], f'{src} failed: {env["sourcesFailed"]}')

            env_path = tdir / 'cn-env.json'
            env_path.write_text(proc.stdout, encoding='utf-8')
            ing = json.loads(subprocess.run(
                [
                    sys.executable, str(LOOP_SCRIPTS / 'signal_gate.py'), 'ingest',
                    '--input', str(env_path), '--workspace', str(ws), '--mark-seen',
                ],
                capture_output=True, text=True, check=True,
            ).stdout)
            self.assertTrue(ing['ok'])
            self.assertEqual(ing['stats']['dropped'], 0, f'Unexpected dropped rows: {ing["rejectedRows"]}')

            seo = json.loads(subprocess.run(
                [sys.executable, str(CN_SCRIPTS / 'seo_keywords_cn.py'), 'AI', '--json'],
                capture_output=True, text=True, check=True, timeout=20,
            ).stdout)
            self.assertTrue(isinstance(seo, list) and len(seo) >= 1)
            self.assertGreater(len(seo[0].get('relatedKeywords', [])), 0)

    def test_live_wave1_market_support_and_finance_public_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)

            # 1. market-intel live public sources
            mi_ws = tdir / 'market-intel'
            mi_scripts = ROOT / 'plugins/market-intel/scripts'
            subprocess.run([sys.executable, str(mi_scripts / 'init_workspace.py'), str(mi_ws)], check=True, stdout=subprocess.DEVNULL)
            (mi_ws / 'watchlist.json').write_text(json.dumps({
                'schemaVersion': 'market-intel-watchlist/1',
                'updatedAt': '2026-11-25T00:00:00Z',
                'entities': [{
                    'slug': 'live-check',
                    'name': 'Live Check',
                    'sources': [
                        {'id': 'gh', 'kind': 'github_releases', 'repo': 'openai/codex', 'limit': 1},
                        {'id': 'ios', 'kind': 'appstore_ios', 'appId': '618783545'},
                        {'id': 'npm', 'kind': 'npm', 'package': 'next'},
                        {'id': 'pypi', 'kind': 'pypi', 'package': 'pydantic'},
                        {'id': 'jobs_gh', 'kind': 'greenhouse_jobs', 'boardToken': 'stripe'},
                        {'id': 'jobs_ashby', 'kind': 'ashby_jobs', 'boardSlug': 'linear'},
                        {'id': 'sec', 'kind': 'sec_edgar', 'cik': '0000320193', 'limit': 2},
                        {'id': 'hn', 'kind': 'hn_algolia', 'query': 'stripe', 'limit': 2},
                    ],
                }],
            }), encoding='utf-8')
            mi_cap = json.loads(subprocess.run(
                [sys.executable, str(mi_scripts / 'fetch_sources.py'), str(mi_ws)],
                capture_output=True, text=True, check=True, timeout=60,
            ).stdout)
            self.assertEqual(mi_cap['okCount'], 8, f'Failed sources: {[r for r in mi_cap["records"] if not r["ok"]]}')

            # 2. customer-support-ops live public source (GitHub Issues REST API; tolerates anonymous IP rate-limit)
            cs_ws = tdir / 'customer-support-ops'
            cs_scripts = ROOT / 'plugins/customer-support-ops/scripts'
            subprocess.run([sys.executable, str(cs_scripts / 'init_workspace.py'), str(cs_ws)], check=True, stdout=subprocess.DEVNULL)
            cs_proc = subprocess.run(
                [sys.executable, str(cs_scripts / 'ingest_feedback.py'), str(cs_ws), '--github-repo', 'facebook/react'],
                capture_output=True, text=True, timeout=30,
            )
            if cs_proc.returncode == 0:
                cs_res = json.loads(cs_proc.stdout)
                self.assertGreater(cs_res['added'], 0)
            else:
                self.assertIn('403', cs_proc.stderr, f'Unexpected GitHub Issues failure: {cs_proc.stderr}')

            # 3. business-finance-ops live ECB FX rates
            bf_ws = tdir / 'business-finance-ops'
            bf_scripts = ROOT / 'plugins/business-finance-ops/scripts'
            subprocess.run([sys.executable, str(bf_scripts / 'init_workspace.py'), str(bf_ws)], check=True, stdout=subprocess.DEVNULL)
            fx_res = json.loads(subprocess.run(
                [sys.executable, str(bf_scripts / 'fx_rates.py'), str(bf_ws), '--base', 'USD', '--symbols', 'CNY,EUR'],
                capture_output=True, text=True, check=True, timeout=20,
            ).stdout)
            self.assertIn('CNY', fx_res['rates'])
            self.assertIn('EUR', fx_res['rates'])

            # 4. software-stewardship live keyless OSV.dev batch API check
            ss_repo = tdir / 'ss-live-repo'
            ss_repo.mkdir()
            (ss_repo / 'requirements.txt').write_text('urllib3==1.25.8\n', encoding='utf-8')
            ss_scripts = ROOT / 'plugins/software-stewardship/scripts'
            osv_res = json.loads(subprocess.run(
                [sys.executable, str(ss_scripts / 'supply_chain_check.py'), '--repo', str(ss_repo)],
                capture_output=True, text=True, check=True, timeout=30,
            ).stdout)
            self.assertEqual(osv_res['osvStatus'], 'ok')
            self.assertGreater(osv_res['vulnerabilityCount'], 0)


if __name__ == '__main__':
    unittest.main()
