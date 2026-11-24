"""Regression tests for content-operations core workspace, scoring, analytics, and board scripts."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / 'plugins' / 'content-operations' / 'skills'
INIT_PY = SKILLS / 'content-ops-loop' / 'scripts' / 'init_workspace.py'
VAL_PY = SKILLS / 'content-ops-loop' / 'scripts' / 'validate_workspace.py'
BUILD_PY = SKILLS / 'content-ops-loop' / 'scripts' / 'build_boards.py'
SCORE_PY = SKILLS / 'content-ops-loop' / 'scripts' / 'score_topics.py'
AGG_PY = SKILLS / 'engagement-and-analytics' / 'scripts' / 'aggregate_metrics.py'

BOARDS = [
    'calendar-board',
    'pipeline-board',
    'publish-ledger-board',
    'engagement-inbox-board',
    'analytics-retro-board',
]


def run_script(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, '-B', str(script), *args],
        capture_output=True,
        text=True,
        check=False,
    )


class ContentOpsCoreScriptsTest(unittest.TestCase):
    def test_init_populates_data_json_for_all_boards_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / 'content-ops'
            res = run_script(INIT_PY, str(ws), '--timezone', 'Asia/Shanghai')
            self.assertEqual(res.returncode, 0, res.stderr)

            # Every board must have assets/data.json immediately after init (no first-load 404)
            for board in BOARDS:
                data_path = ws / 'boards' / board / 'assets' / 'data.json'
                self.assertTrue(data_path.is_file(), f'Missing initial data.json for {board}')
                payload = json.loads(data_path.read_text(encoding='utf-8'))
                self.assertEqual(payload['board'], board)
                self.assertEqual(payload['timezone'], 'Asia/Shanghai')

            # Idempotent re-init preserves custom brand-profile.md unless --force is passed
            profile = ws / 'brand-profile.md'
            profile.write_text('# Custom Brand\n', encoding='utf-8')
            self.assertEqual(run_script(INIT_PY, str(ws)).returncode, 0)
            self.assertEqual(profile.read_text(encoding='utf-8'), '# Custom Brand\n')

            # Fresh initialized workspace passes validate_workspace.py
            val = run_script(VAL_PY, str(ws))
            self.assertEqual(val.returncode, 0, val.stderr)

    def test_validate_catches_dangling_refs_on_empty_tables_nonlist_envkeys_and_dupes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / 'content-ops'
            self.assertEqual(run_script(INIT_PY, str(ws)).returncode, 0)

            # Non-list envKeys
            (ws / 'accounts.json').write_text(json.dumps({
                'version': 1,
                'accounts': [{'accountId': 'a1', 'platform': 'x-twitter', 'status': 'active', 'envKeys': 'X_ACCESS_TOKEN'}],
            }), encoding='utf-8')

            # Draft referencing nonexistent topicId & planId while topics/plans tables are empty
            for folder in ('d1', 'd2'):
                ddir = ws / 'drafts' / folder
                ddir.mkdir(parents=True)
                (ddir / 'meta.json').write_text(json.dumps({
                    'draftId': 'dup-draft',
                    'topicId': 'missing-topic',
                    'planId': 'missing-plan',
                    'status': 'drafting',
                }), encoding='utf-8')

            # Duplicate slotId & unknown draftId/accountId
            (ws / 'calendar.json').write_text(json.dumps({
                'version': 1,
                'timezone': 'UTC',
                'slots': [
                    {'slotId': 's1', 'status': 'planned', 'accountId': 'ghost-acct', 'draftId': 'ghost-draft'},
                    {'slotId': 's1', 'status': 'planned'},
                ],
            }), encoding='utf-8')

            res = run_script(VAL_PY, str(ws))
            self.assertNotEqual(res.returncode, 0)
            self.assertIn('"envKeys" must be a list', res.stderr)
            self.assertIn('unknown topicId "missing-topic"', res.stderr)
            self.assertIn('unknown planId "missing-plan"', res.stderr)
            self.assertIn('duplicate draftId "dup-draft"', res.stderr)
            self.assertIn('duplicate slotId "s1"', res.stderr)
            self.assertIn('unknown accountId "ghost-acct"', res.stderr)
            self.assertIn('unknown draftId "ghost-draft"', res.stderr)

    def test_score_topics_handles_null_scores_cooldown_and_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / 'content-ops'
            self.assertEqual(run_script(INIT_PY, str(ws)).returncode, 0)

            (ws / 'topics' / 'topics.json').write_text(json.dumps({
                'version': 1,
                'topics': [
                    {
                        'topicId': 't-null',
                        'title': 'Null score resilience',
                        'sourceType': 'internal_fact',
                        'status': 'candidate',
                        'scores': {'audiencePain': None, 'evidenceStrength': 1, 'timeliness': None, 'brandFit': 2},
                    },
                    {
                        'topicId': 't-win',
                        'title': 'Top winner',
                        'sourceType': 'platform_trend',
                        'cooldownKey': 'ck-1',
                        'status': 'candidate',
                        'scores': {'audiencePain': 5, 'evidenceStrength': 5, 'timeliness': 4, 'brandFit': 5},
                    },
                    {
                        'topicId': 't-dup',
                        'title': 'Batch duplicate',
                        'sourceType': 'platform_trend',
                        'cooldownKey': 'ck-1',
                        'status': 'candidate',
                        'scores': {'audiencePain': 4, 'evidenceStrength': 4, 'timeliness': 4, 'brandFit': 4},
                    },
                    {
                        'topicId': 't-ovr',
                        'title': 'Override batch duplicate',
                        'sourceType': 'internal_fact',
                        'cooldownKey': 'ck-1',
                        'cooldownOverrideReason': 'Major v2 launch',
                        'status': 'candidate',
                        'scores': {'audiencePain': 5, 'evidenceStrength': 4, 'timeliness': 4, 'brandFit': 4},
                    },
                ],
            }), encoding='utf-8')

            res = run_script(SCORE_PY, str(ws))
            self.assertEqual(res.returncode, 0, res.stderr)
            scored = {t['topicId']: t for t in json.loads((ws / 'topics' / 'topics.json').read_text(encoding='utf-8'))['topics']}
            # Default preserves low-scoring candidates without silent archiving
            self.assertEqual(scored['t-null']['status'], 'candidate')
            self.assertEqual(scored['t-win']['status'], 'shortlisted')
            self.assertTrue(scored['t-dup']['cooldownConflict'])
            self.assertEqual(scored['t-dup']['status'], 'candidate')
            self.assertEqual(scored['t-ovr']['status'], 'shortlisted')

            # Explicit --auto-archive-below 3.0 archives low-scoring candidates on demand
            res_arch = run_script(SCORE_PY, str(ws), '--auto-archive-below', '3.0')
            self.assertEqual(res_arch.returncode, 0, res_arch.stderr)
            scored2 = {t['topicId']: t for t in json.loads((ws / 'topics' / 'topics.json').read_text(encoding='utf-8'))['topics']}
            self.assertEqual(scored2['t-null']['status'], 'archived')

            # Deterministic --import-gated merges passed candidates without duplicating URLs
            gated = Path(tmp) / 'gated.json'
            gated.write_text(json.dumps({
                'passed': [{'title': 'Fresh Gated Signal', 'evidenceUrls': ['https://example.com/sig-1'], 'targetPlatforms': ['x-twitter']}],
            }), encoding='utf-8')
            imp1 = json.loads(run_script(SCORE_PY, str(ws), '--import-gated', str(gated)).stdout)
            self.assertEqual(imp1['imported']['addedCount'], 1)
            imp2 = json.loads(run_script(SCORE_PY, str(ws), '--import-gated', str(gated)).stdout)
            self.assertEqual(imp2['imported']['addedCount'], 0)
            self.assertEqual(imp2['imported']['skippedCount'], 1)

    def test_build_boards_and_aggregate_handle_malformed_jsonl_timezones_and_edge_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / 'content-ops'
            self.assertEqual(run_script(INIT_PY, str(ws)).returncode, 0)

            now = datetime.now(timezone.utc)
            pub_old = (now - timedelta(hours=36)).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
            # Same workId across two different platforms; only x-twitter has 24h snapshot -> bilibili must still be due!
            (ws / 'publish-log.jsonl').write_text(
                json.dumps({'workId': 'w-shared', 'platform': 'x-twitter', 'accountId': 'ax', 'status': 'published', 'publishedAt': pub_old, 'publicUrl': 'https://x.com/i/status/1'}) + '\n'
                + json.dumps({'workId': 'w-shared', 'platform': 'bilibili', 'accountId': 'ab', 'status': 'published', 'publishedAt': pub_old, 'publicUrl': 'https://www.bilibili.com/video/BV1'}) + '\n'
                + '{corrupted json line\n',
                encoding='utf-8',
            )

            # Action with non-Z timezone offset that falls on today's UTC date
            utc_midnight = now.replace(hour=1, minute=0, second=0, microsecond=0)
            offset_ts = utc_midnight.astimezone(timezone(timedelta(hours=-8))).isoformat()
            (ws / 'engagement' / 'action-log.jsonl').write_text(
                json.dumps({'actionId': 'act-1', 'platform': 'x-twitter', 'accountId': 'ax', 'actionType': 'reply', 'targetId': 'c1', 'executedAt': offset_ts}) + '\n',
                encoding='utf-8',
            )

            # Snapshots: boolean platformMetrics, null platform on account snapshot, missing capturedAt (must NOT yield 0001-01-01)
            ts_recent = (now - timedelta(hours=2)).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
            (ws / 'analytics' / 'snapshots.jsonl').write_text(
                json.dumps({'workId': 'w-shared', 'platform': 'x-twitter', 'window': '24h', 'capturedAt': ts_recent, 'metrics': {'views': 500, 'likes': 25}, 'platformMetrics': {'isBoosted': True, 'bookmarkRate': 0.05}}) + '\n'
                + json.dumps({'workId': 'w-nodate', 'platform': 'instagram', 'window': '24h', 'metrics': {'views': 100}}) + '\n'
                + json.dumps({'workId': 'account', 'platform': None, 'accountId': 'acct-null', 'window': 'account', 'capturedAt': ts_recent, 'metrics': {'followers': 42}}) + '\n'
                + 'not-json\n',
                encoding='utf-8',
            )

            agg_res = run_script(AGG_PY, str(ws))
            self.assertEqual(agg_res.returncode, 0, agg_res.stderr)
            agg = json.loads(agg_res.stdout)
            # Boolean isBoosted must NOT enter avgPlatformMetrics
            self.assertNotIn('isBoosted', agg['byPlatform']['x-twitter']['avgPlatformMetrics'])
            self.assertIn('bookmarkRate', agg['byPlatform']['x-twitter']['avgPlatformMetrics'])
            # bilibili w-shared must still appear in dueSnapshots despite x-twitter w-shared having 24h
            self.assertTrue(any(d['platform'] == 'bilibili' and d['workId'] == 'w-shared' for d in agg['dueSnapshots']))
            self.assertEqual(len(agg['accountSnapshots']), 1)

            build_res = run_script(BUILD_PY, str(ws))
            self.assertEqual(build_res.returncode, 0, build_res.stderr)
            eng_data = json.loads((ws / 'boards' / 'engagement-inbox-board' / 'assets' / 'data.json').read_text(encoding='utf-8'))
            x_cap = next(r for r in eng_data['rateLimits'] if r['platform'] == 'x-twitter')
            self.assertEqual(x_cap['usedToday'], 1)

            ana_data = json.loads((ws / 'boards' / 'analytics-retro-board' / 'assets' / 'data.json').read_text(encoding='utf-8'))
            self.assertTrue(all(pt['date'] != '0001-01-01' for pt in ana_data['trend']))


if __name__ == '__main__':
    unittest.main()
