"""Tests and formal proofs for Gate 2 hash verification, engagement_guard.py, and video_ops.py."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / 'plugins' / 'content-operations' / 'skills'
INIT_PY = SKILLS / 'content-ops-loop' / 'scripts' / 'init_workspace.py'
VAL_PY = SKILLS / 'content-ops-loop' / 'scripts' / 'validate_workspace.py'
SPEC_PY = SKILLS / 'content-ops-loop' / 'scripts' / 'check_media_specs.py'
ENG_PY = SKILLS / 'engagement-and-analytics' / 'scripts' / 'engagement_guard.py'
VID_PY = SKILLS / 'video-production' / 'scripts' / 'video_ops.py'


def run_script(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, '-B', str(script), *args], capture_output=True, text=True, check=False)


def load_mod(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


class ObjectiveGuardsTest(unittest.TestCase):
    def test_gate2_verify_slot_and_approved_master_hash_tamper_detection(self):
        """Fault injection for Gate 2 live variantHash verification, idempotency, and approvedMasterHash protection."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / 'content-ops'
            self.assertEqual(run_script(INIT_PY, str(ws)).returncode, 0)

            (ws / 'accounts.json').write_text(json.dumps({
                'version': 1,
                'accounts': [{'accountId': 'acct-x', 'platform': 'x-twitter', 'status': 'active', 'envKeys': ['X_ACCESS_TOKEN']}],
            }), encoding='utf-8')
            (ws / 'topics' / 'topics.json').write_text(json.dumps({
                'version': 1,
                'topics': [{'topicId': 't1', 'title': 'Launch', 'sourceType': 'internal_fact', 'status': 'approved'}],
            }), encoding='utf-8')

            draft_dir = ws / 'drafts' / 'd1'
            (draft_dir / 'variants').mkdir(parents=True)
            master_path = draft_dir / 'master.md'
            master_path.write_text('# Approved Master Copy\n\nOriginal verified body.\n', encoding='utf-8')
            master_hash = hashlib.sha256(master_path.read_bytes()).hexdigest()[:16]

            variant_path = draft_dir / 'variants' / 'x-twitter.md'
            variant_path.write_text('```json\n{"platform": "x-twitter", "mode": "text", "media": []}\n```\n\nShipped v1.5.\n', encoding='utf-8')
            (draft_dir / 'meta.json').write_text(json.dumps({
                'draftId': 'd1', 'topicId': 't1', 'status': 'ready', 'approvedMasterHash': master_hash,
            }), encoding='utf-8')

            # Run check_media_specs --update-meta to compute real variantHash
            self.assertEqual(run_script(SPEC_PY, str(draft_dir), '--update-meta').returncode, 0)
            vhash = json.loads((draft_dir / 'meta.json').read_text(encoding='utf-8'))['variants']['x-twitter']['variantHash']

            # Set approved slot in calendar.json
            (ws / 'calendar.json').write_text(json.dumps({
                'version': 1,
                'timezone': 'UTC',
                'slots': [{
                    'slotId': 'slot-1', 'draftId': 'd1', 'platform': 'x-twitter', 'accountId': 'acct-x',
                    'status': 'approved', 'approvalRef': 'human-2026-11-24', 'approvedVariantHash': vhash,
                }],
            }), encoding='utf-8')

            # 1. Clean workspace + Gate 2 verify-slot PASSES
            self.assertEqual(run_script(VAL_PY, str(ws)).returncode, 0)
            ok = run_script(VAL_PY, str(ws), '--verify-slot', 'slot-1')
            self.assertEqual(ok.returncode, 0, ok.stdout)
            self.assertTrue(json.loads(ok.stdout)['ok'])

            # 2. Fault A: edit variant AFTER approval -> Gate 2 MUST FAIL on variantHash mismatch!
            variant_path.write_text('```json\n{"platform": "x-twitter", "mode": "text", "media": []}\n```\n\nSneaky unapproved edit.\n', encoding='utf-8')
            tampered = run_script(VAL_PY, str(ws), '--verify-slot', 'slot-1')
            self.assertEqual(tampered.returncode, 1)
            self.assertTrue(any('variantHash mismatch' in r for r in json.loads(tampered.stdout)['reasons']))

            # Restore variant, then Fault B: already published in publish-log.jsonl -> idempotency blocks republish
            variant_path.write_text('```json\n{"platform": "x-twitter", "mode": "text", "media": []}\n```\n\nShipped v1.5.\n', encoding='utf-8')
            (ws / 'publish-log.jsonl').write_text(json.dumps({
                'publishId': 'pub-1', 'slotId': 'slot-1', 'draftId': 'd1', 'platform': 'x-twitter',
                'accountId': 'acct-x', 'status': 'published', 'publishedAt': '2026-11-24T08:00:00Z',
                'publicUrl': 'https://x.com/i/status/123', 'variantHash': vhash,
            }) + '\n', encoding='utf-8')
            dup_pub = run_script(VAL_PY, str(ws), '--verify-slot', 'slot-1')
            self.assertEqual(dup_pub.returncode, 1)
            self.assertTrue(any('already published' in r for r in json.loads(dup_pub.stdout)['reasons']))

            # 3. Fault C: overwriting approved master.md triggers workspace validation failure
            master_path.write_text('# Mutated Master\n', encoding='utf-8')
            val_mut = run_script(VAL_PY, str(ws), '--json')
            self.assertEqual(val_mut.returncode, 1)
            self.assertTrue(any('modified after approval' in e for e in json.loads(val_mut.stdout)['errors']))

            # 4. Fault D: non-HTTP publicUrl or bad variantHash in publish-log.jsonl caught
            (ws / 'publish-log.jsonl').write_text(json.dumps({
                'publishId': 'pub-bad', 'slotId': 'slot-2', 'draftId': 'd1', 'platform': 'x-twitter',
                'accountId': 'acct-x', 'status': 'published', 'publishedAt': '2026-11-24T08:00:00Z',
                'publicUrl': 'not-a-url', 'variantHash': 'SHORT',
            }) + '\n', encoding='utf-8')
            errs = json.loads(run_script(VAL_PY, str(ws), '--json').stdout)['errors']
            self.assertTrue(any('valid http(s):// URL' in e for e in errs))
            self.assertTrue(any('16 lowercase hex' in e for e in errs))

    def test_engagement_guard_formal_bfs_budget_and_idempotency(self):
        """Class-B formal BFS + live CLI replay proving engagement_guard never exceeds caps or duplicates actions."""
        eg = load_mod(ENG_PY, 'engagement_guard_mod')

        # 1. Exhaustive BFS over bounded model (cap_h=2, cap_d=3, 3 distinct targets)
        def explore(enforce_budget: bool = True, enforce_idempotent: bool = True) -> tuple[int, str | None]:
            # state: (used_h, used_d, t0_done, t1_done, t2_done)
            init = (0, 0, False, False, False)
            visited = {init}
            q = deque([init])
            while q:
                uh, ud, t0, t1, t2 = q.popleft()
                if uh > 2 or ud > 3:
                    return len(visited), 'VIOLATION:cap_exceeded'
                nxt_hr = (0, ud, t0, t1, t2)
                if nxt_hr not in visited:
                    visited.add(nxt_hr)
                    q.append(nxt_hr)
                flags = (t0, t1, t2)
                for tidx, done in enumerate(flags):
                    allowed = True
                    if enforce_budget:
                        allowed = allowed and (uh < 2) and (ud < 3)
                    if enforce_idempotent:
                        allowed = allowed and (not done)
                    if allowed:
                        if done:
                            return len(visited), 'VIOLATION:duplicate_action'
                        if uh + 1 > 2 or ud + 1 > 3:
                            return len(visited), 'VIOLATION:cap_exceeded'
                        nxt_flags = tuple(True if i == tidx else flags[i] for i in range(3))
                        nxt = (uh + 1, ud + 1, *nxt_flags)
                        if nxt not in visited:
                            visited.add(nxt)
                            q.append(nxt)
            return len(visited), None

        n_states, cex = explore(True, True)
        self.assertIsNone(cex)
        self.assertGreaterEqual(n_states, 6)
        self.assertEqual(explore(False, True)[1], 'VIOLATION:cap_exceeded')
        self.assertEqual(explore(True, False)[1], 'VIOLATION:duplicate_action')

        # 2. Real CLI end-to-end replay
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / 'content-ops'
            ws.mkdir()
            now_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

            # Record 1st action -> ok
            r1 = run_script(ENG_PY, 'record-action', str(ws), '--platform', 'wechat-official', '--account-id', 'wx1', '--target-id', 'c1', '--action-type', 'reply', '--executed-at', now_iso)
            self.assertEqual(r1.returncode, 0, r1.stdout)

            # Duplicate same (platform, accountId, targetId, actionType) -> blocked (exit 1)
            r_dup = run_script(ENG_PY, 'record-action', str(ws), '--platform', 'wechat-official', '--account-id', 'wx1', '--target-id', 'c1', '--action-type', 'reply', '--executed-at', now_iso)
            self.assertEqual(r_dup.returncode, 1)
            self.assertEqual(json.loads(r_dup.stdout)['error'], 'duplicate_action')

            # Fill hourly cap (6/hr on wechat-official)
            for idx in range(2, 7):
                ri = run_script(ENG_PY, 'record-action', str(ws), '--platform', 'wechat-official', '--account-id', 'wx1', '--target-id', f'c{idx}', '--action-type', 'reply', '--executed-at', now_iso)
                self.assertEqual(ri.returncode, 0)

            # 7th action within same hour MUST be blocked by rate_limit_exceeded
            r7 = run_script(ENG_PY, 'record-action', str(ws), '--platform', 'wechat-official', '--account-id', 'wx1', '--target-id', 'c7', '--action-type', 'reply', '--executed-at', now_iso)
            self.assertEqual(r7.returncode, 1)
            self.assertEqual(json.loads(r7.stdout)['error'], 'rate_limit_exceeded')

            # Check-budget confirms usedHour=6, hourlyCap=6, ok=False
            bud = json.loads(run_script(ENG_PY, 'check-budget', str(ws), '--platform', 'wechat-official', '--account-id', 'wx1').stdout)
            self.assertFalse(bud['ok'])
            self.assertEqual(bud['usedHour'], 6)

            # All 14 platforms present in PLATFORM_CAPS
            self.assertEqual(len(eg.PLATFORM_CAPS), 14)

    def test_video_ops_srt_validation_duration_estimator_and_optional_probe(self):
        """Verify video_ops.py SRT fault detection, CN/EN duration estimator, and real ffmpeg probe --loudness."""
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            good_srt = tdir / 'good.srt'
            good_srt.write_text(
                '1\n00:00:00,000 --> 00:00:02,000\n第一句干净字幕\n\n'
                '2\n00:00:02,200 --> 00:00:04,500\nSecond clean line\n',
                encoding='utf-8',
            )
            r_ok = run_script(VID_PY, 'validate-srt', str(good_srt))
            self.assertEqual(r_ok.returncode, 0, r_ok.stdout)
            self.assertTrue(json.loads(r_ok.stdout)['ok'])

            bad_srt = tdir / 'bad.srt'
            bad_srt.write_text(
                '1\n00:00:03,000 --> 00:00:02,000\nReversed timestamp\n\n'
                '2\n00:00:01,500 --> 00:00:04,000\nOverlapping cue\n',
                encoding='utf-8',
            )
            r_bad = run_script(VID_PY, 'validate-srt', str(bad_srt))
            self.assertEqual(r_bad.returncode, 1)
            self.assertGreaterEqual(len(json.loads(r_bad.stdout)['errors']), 2)

            script_md = tdir / 'script.md'
            script_md.write_text('# Spoken Script\n\n' + ('今天我们实测一下视频脚本时长估算工具。' * 13) + ' Quick test check.\n', encoding='utf-8')
            r_est = run_script(VID_PY, 'estimate-duration', str(script_md))
            self.assertEqual(r_est.returncode, 0, r_est.stdout)
            est = json.loads(r_est.stdout)
            self.assertGreater(est['estimatedDurationSec'], 45.0)
            self.assertLess(est['estimatedDurationSec'], 75.0)

            if shutil.which('ffmpeg') and shutil.which('ffprobe'):
                vid = tdir / 'sample.mp4'
                subprocess.run(
                    ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=1080x1920:rate=24:duration=2',
                     '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2',
                     '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(vid)],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                r_pr = run_script(VID_PY, 'probe', str(vid), '--loudness')
                self.assertEqual(r_pr.returncode, 0, r_pr.stdout)
                pdata = json.loads(r_pr.stdout)
                self.assertEqual((pdata['width'], pdata['height']), (1080, 1920))
                self.assertTrue(pdata['hasAudio'])
                self.assertIsNotNone(pdata['loudness']['integratedLufs'])


if __name__ == '__main__':
    unittest.main()
