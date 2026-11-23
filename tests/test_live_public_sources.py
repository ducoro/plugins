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
                    '--sources', 'hackernews,lobsters,github,polymarket,devto,arxiv',
                    '--limit', '12', '--envelope',
                ],
                capture_output=True, text=True, check=True, timeout=45,
            )
            env = json.loads(proc.stdout)
            self.assertEqual(env['schema'], 'content-ops-signal-envelope/1')
            # Core 5 must succeed; arXiv occasionally returns transient 429 on rapid bursts
            for core_source in ('hackernews', 'lobsters', 'github', 'polymarket', 'devto'):
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


if __name__ == '__main__':
    unittest.main()
