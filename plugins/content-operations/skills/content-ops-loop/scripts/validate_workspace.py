#!/usr/bin/env python3
"""Validate a file-backed content-ops/ workspace and enforce Gate 2 tamper-proof hash checks."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse

ACCOUNT_STATUSES = {'active', 'expiring', 'expired', 'manual_browser', 'paused'}
TOPIC_STATUSES = {'candidate', 'shortlisted', 'approved', 'produced', 'archived'}
SOURCE_TYPES = {
    'internal_fact',
    'platform_trend',
    'comment_feedback',
    'seasonal_evergreen',
    'cross_platform_repurpose',
}
DRAFT_STATUSES = {'drafting', 'in_review', 'ready', 'scheduled', 'published', 'needs_update', 'archived'}
SLOT_STATUSES = {'planned', 'awaiting_approval', 'approved', 'published', 'failed', 'cancelled'}
PUBLISH_STATUSES = {'published', 'draft_saved', 'failed'}
COMMENT_TIERS = {'high_intent', 'feedback', 'general', 'spam'}
COMMENT_STATUSES = {'open', 'drafted', 'replied', 'escalated', 'ignored'}
SNAPSHOT_WINDOWS = {'24h', '72h', '7d', '30d', 'account'}
SECRET_PATTERNS = [
    re.compile(r'-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----'),
    re.compile(r'\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b'),
    re.compile(r'\bsk-(?:ant-api\d+-|proj-|live-|test-)?[A-Za-z0-9_-]{20,}\b'),
    re.compile(r'\bAIza[0-9A-Za-z_-]{35}\b'),
]
ENV_VAR_NAME = re.compile(r'^[A-Z][A-Z0-9_]*$')
HEX16_RE = re.compile(r'^[0-9a-f]{16}$')


def sha256_prefix16(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _is_http_url(url: object) -> bool:
    if not isinstance(url, str) or not url.strip():
        return False
    p = urlparse(url.strip())
    return p.scheme in ('http', 'https') and bool(p.netloc)


def _is_iso_ts(val: object) -> bool:
    if not isinstance(val, str) or not val.strip():
        return False
    try:
        datetime.fromisoformat(val.strip().replace('Z', '+00:00'))
        return True
    except ValueError:
        return False


def load_json(path: Path, errors: list[str]):
    if not path.is_file():
        errors.append(f'{path.name}: missing required file ({path})')
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        errors.append(f'{path}: invalid JSON ({exc})')
        return None


def load_jsonl(path: Path, errors: list[str]) -> list[tuple[int, dict]]:
    if not path.is_file():
        errors.append(f'{path.name}: missing required file ({path})')
        return []
    rows = []
    for idx, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except ValueError as exc:
            errors.append(f'{path}:{idx}: invalid JSONL line ({exc})')
            continue
        if not isinstance(obj, dict):
            errors.append(f'{path}:{idx}: JSONL row must be an object')
            continue
        rows.append((idx, obj))
    return rows


def scan_secrets(ws: Path, errors: list[str]) -> None:
    for path in sorted(ws.rglob('*')):
        if not path.is_file() or 'boards' in path.relative_to(ws).parts:
            continue
        if path.suffix not in {'.json', '.jsonl', '.md', '.txt'}:
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f'{path.relative_to(ws)}: potential raw secret detected; store only env var names')
                break


def verify_publish_slot(ws: Path, slot_id: str) -> dict:
    """Deterministic Gate 2 pre-publish verification: approvalRef, draft status, specStatus, live variantHash, idempotency."""
    ws = ws.expanduser().resolve()
    reasons: list[str] = []
    cal_path = ws / 'calendar.json'
    if not cal_path.is_file():
        return {'ok': False, 'slotId': slot_id, 'reasons': ['missing calendar.json']}
    cal = json.loads(cal_path.read_text(encoding='utf-8'))
    slot = next((s for s in (cal.get('slots') or []) if isinstance(s, dict) and s.get('slotId') == slot_id), None)
    if not slot:
        return {'ok': False, 'slotId': slot_id, 'reasons': [f'slot "{slot_id}" not found in calendar.json']}

    if slot.get('status') != 'approved':
        reasons.append(f'slot status is "{slot.get("status")}" (must be "approved")')
    if not str(slot.get('approvalRef') or '').strip():
        reasons.append('slot missing non-empty approvalRef')

    approved_hash = str(slot.get('approvedVariantHash') or '').strip()
    if not HEX16_RE.fullmatch(approved_hash):
        reasons.append('slot missing valid 16-hex approvedVariantHash')

    draft_id = str(slot.get('draftId') or '').strip()
    platform = str(slot.get('platform') or '').strip()
    draft_dir = ws / 'drafts' / draft_id if draft_id else None
    meta_path = (draft_dir / 'meta.json') if draft_dir else None
    if not meta_path or not meta_path.is_file():
        reasons.append(f'missing draft meta.json for draftId "{draft_id}"')
        live_hash = None
    else:
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        if meta.get('status') == 'needs_update':
            reasons.append('draft status is "needs_update"; re-check and re-approve before publishing')
        vinfo = (meta.get('variants') or {}).get(platform) or {}
        if vinfo.get('specStatus') != 'pass':
            reasons.append(f'variant "{platform}" specStatus is "{vinfo.get("specStatus")}" (must be "pass")')
        vrel = vinfo.get('file') or f'variants/{platform}.md'
        vpath = draft_dir / vrel
        if not vpath.is_file():
            reasons.append(f'missing variant file: {vrel}')
            live_hash = None
        else:
            live_hash = sha256_prefix16(vpath)
            if HEX16_RE.fullmatch(approved_hash) and live_hash != approved_hash:
                reasons.append(f'variantHash mismatch: live={live_hash} != approved={approved_hash} (edited after approval)')

    # Idempotency check against publish-log.jsonl
    pub_path = ws / 'publish-log.jsonl'
    if pub_path.is_file():
        for line in pub_path.read_text(encoding='utf-8').splitlines():
            s = line.strip()
            if not s:
                continue
            try:
                row = json.loads(s)
            except ValueError:
                continue
            if row.get('slotId') == slot_id and row.get('status') == 'published':
                reasons.append(f'slot "{slot_id}" already published in publish-log.jsonl ({row.get("publicUrl")})')
                break

    return {
        'ok': not reasons,
        'slotId': slot_id,
        'draftId': draft_id,
        'platform': platform,
        'approvedVariantHash': approved_hash or None,
        'liveVariantHash': live_hash,
        'reasons': reasons,
    }


def validate_workspace(ws: Path) -> list[str]:
    errors: list[str] = []
    ws = ws.expanduser().resolve()
    if not ws.is_dir():
        return [f'{ws}: workspace directory does not exist']

    if not (ws / 'brand-profile.md').is_file():
        errors.append('brand-profile.md: missing required brand profile')

    scan_secrets(ws, errors)

    account_ids: set[str] = set()
    accounts_data = load_json(ws / 'accounts.json', errors)
    if isinstance(accounts_data, dict):
        accounts = accounts_data.get('accounts')
        if not isinstance(accounts, list):
            errors.append('accounts.json: "accounts" must be a list')
        else:
            for i, acct in enumerate(accounts):
                if not isinstance(acct, dict):
                    errors.append(f'accounts.json[{i}]: must be an object')
                    continue
                aid = acct.get('accountId')
                if not isinstance(aid, str) or not aid.strip():
                    errors.append(f'accounts.json[{i}]: missing accountId')
                elif aid in account_ids:
                    errors.append(f'accounts.json[{i}]: duplicate accountId "{aid}"')
                else:
                    account_ids.add(aid)
                if acct.get('status') not in ACCOUNT_STATUSES:
                    errors.append(f'accounts.json[{i}]: invalid status "{acct.get("status")}"')
                env_keys = acct.get('envKeys', [])
                if not isinstance(env_keys, list):
                    errors.append(f'accounts.json[{i}]: "envKeys" must be a list of UPPER_SNAKE_CASE env var names')
                else:
                    for key in env_keys:
                        if not isinstance(key, str) or not ENV_VAR_NAME.fullmatch(key):
                            errors.append(f'accounts.json[{i}]: envKeys entry "{key}" must be an UPPER_SNAKE_CASE env var name')

    topic_ids: set[str] = set()
    topics_data = load_json(ws / 'topics' / 'topics.json', errors)
    if isinstance(topics_data, dict):
        topics = topics_data.get('topics')
        if not isinstance(topics, list):
            errors.append('topics/topics.json: "topics" must be a list')
        else:
            for i, item in enumerate(topics):
                if not isinstance(item, dict):
                    errors.append(f'topics/topics.json[{i}]: must be an object')
                    continue
                tid = item.get('topicId')
                if not isinstance(tid, str) or not tid.strip():
                    errors.append(f'topics/topics.json[{i}]: missing topicId')
                elif tid in topic_ids:
                    errors.append(f'topics/topics.json[{i}]: duplicate topicId "{tid}"')
                else:
                    topic_ids.add(tid)
                if item.get('status') not in TOPIC_STATUSES:
                    errors.append(f'topics/topics.json[{i}]: invalid status "{item.get("status")}"')
                if item.get('sourceType') not in SOURCE_TYPES:
                    errors.append(f'topics/topics.json[{i}]: invalid sourceType "{item.get("sourceType")}"')

    plan_ids: set[str] = set()
    plans_data = load_json(ws / 'drafts' / 'plans.json', errors)
    if isinstance(plans_data, dict):
        plans = plans_data.get('plans')
        if not isinstance(plans, list):
            errors.append('drafts/plans.json: "plans" must be a list')
        else:
            for i, plan in enumerate(plans):
                pid = plan.get('planId') if isinstance(plan, dict) else None
                if not isinstance(pid, str) or not pid.strip():
                    errors.append(f'drafts/plans.json[{i}]: missing planId')
                elif pid in plan_ids:
                    errors.append(f'drafts/plans.json[{i}]: duplicate planId "{pid}"')
                else:
                    plan_ids.add(pid)

    draft_ids: set[str] = set()
    drafts_root = ws / 'drafts'
    if drafts_root.is_dir():
        for entry in sorted(drafts_root.iterdir()):
            if not entry.is_dir():
                continue
            meta = load_json(entry / 'meta.json', errors)
            if not isinstance(meta, dict):
                continue
            did = meta.get('draftId')
            if not isinstance(did, str) or not did.strip():
                errors.append(f'drafts/{entry.name}/meta.json: missing draftId')
            elif did in draft_ids:
                errors.append(f'drafts/{entry.name}/meta.json: duplicate draftId "{did}"')
            else:
                draft_ids.add(did)
            if meta.get('status') not in DRAFT_STATUSES:
                errors.append(f'drafts/{entry.name}/meta.json: invalid status "{meta.get("status")}"')
            tid = meta.get('topicId')
            if tid and tid not in topic_ids:
                errors.append(f'drafts/{entry.name}/meta.json: unknown topicId "{tid}"')
            pid = meta.get('planId')
            if pid and pid not in plan_ids:
                errors.append(f'drafts/{entry.name}/meta.json: unknown planId "{pid}"')
            # Protect approved master.md from silent overwrite when approvedMasterHash is recorded
            approved_master = meta.get('approvedMasterHash')
            if approved_master:
                master_md = entry / 'master.md'
                if not master_md.is_file():
                    errors.append(f'drafts/{entry.name}/meta.json: approvedMasterHash set but master.md is missing')
                elif sha256_prefix16(master_md) != str(approved_master):
                    errors.append(f'drafts/{entry.name}/master.md: modified after approval (expected {approved_master}); use illustrated.md for visual edits')

    slot_ids: set[str] = set()
    cal_data = load_json(ws / 'calendar.json', errors)
    if isinstance(cal_data, dict):
        slots = cal_data.get('slots')
        if not isinstance(slots, list):
            errors.append('calendar.json: "slots" must be a list')
        else:
            for i, slot in enumerate(slots):
                if not isinstance(slot, dict):
                    errors.append(f'calendar.json[{i}]: must be an object')
                    continue
                sid = slot.get('slotId')
                if not isinstance(sid, str) or not sid.strip():
                    errors.append(f'calendar.json[{i}]: missing slotId')
                elif sid in slot_ids:
                    errors.append(f'calendar.json[{i}]: duplicate slotId "{sid}"')
                else:
                    slot_ids.add(sid)
                if slot.get('status') not in SLOT_STATUSES:
                    errors.append(f'calendar.json[{i}]: invalid status "{slot.get("status")}"')
                aid = slot.get('accountId')
                if aid and aid not in account_ids:
                    errors.append(f'calendar.json[{i}]: unknown accountId "{aid}"')
                did = slot.get('draftId')
                if did and did not in draft_ids:
                    errors.append(f'calendar.json[{i}]: unknown draftId "{did}"')

    for lineno, row in load_jsonl(ws / 'publish-log.jsonl', errors):
        status = row.get('status')
        if status not in PUBLISH_STATUSES:
            errors.append(f'publish-log.jsonl:{lineno}: invalid status "{status}"')
        if status == 'published':
            if not row.get('publicUrl'):
                errors.append(f'publish-log.jsonl:{lineno}: status "published" requires verified publicUrl')
            elif not _is_http_url(row.get('publicUrl')):
                errors.append(f'publish-log.jsonl:{lineno}: publicUrl must be a valid http(s):// URL')
        vhash = row.get('variantHash')
        if vhash is not None and not HEX16_RE.fullmatch(str(vhash)):
            errors.append(f'publish-log.jsonl:{lineno}: variantHash "{vhash}" must be 16 lowercase hex chars')

    inbox_data = load_json(ws / 'engagement' / 'inbox.json', errors)
    if isinstance(inbox_data, dict):
        comments = inbox_data.get('comments')
        if not isinstance(comments, list):
            errors.append('engagement/inbox.json: "comments" must be a list')
        else:
            for i, item in enumerate(comments):
                if not isinstance(item, dict):
                    errors.append(f'engagement/inbox.json[{i}]: must be an object')
                    continue
                if item.get('tier') not in COMMENT_TIERS:
                    errors.append(f'engagement/inbox.json[{i}]: invalid tier "{item.get("tier")}"')
                if item.get('status') not in COMMENT_STATUSES:
                    errors.append(f'engagement/inbox.json[{i}]: invalid status "{item.get("status")}"')

    for lineno, row in load_jsonl(ws / 'engagement' / 'action-log.jsonl', errors):
        for req_key in ('actionId', 'executedAt', 'platform', 'accountId', 'targetId', 'actionType'):
            if not row.get(req_key):
                errors.append(f'engagement/action-log.jsonl:{lineno}: missing required field "{req_key}"')
        if row.get('executedAt') and not _is_iso_ts(row.get('executedAt')):
            errors.append(f'engagement/action-log.jsonl:{lineno}: invalid ISO executedAt "{row.get("executedAt")}"')

    for lineno, row in load_jsonl(ws / 'analytics' / 'snapshots.jsonl', errors):
        if row.get('window') not in SNAPSHOT_WINDOWS:
            errors.append(f'analytics/snapshots.jsonl:{lineno}: invalid window "{row.get("window")}"')
        if row.get('capturedAt') and not _is_iso_ts(row.get('capturedAt')):
            errors.append(f'analytics/snapshots.jsonl:{lineno}: invalid ISO capturedAt "{row.get("capturedAt")}"')
        metrics = row.get('metrics')
        if not isinstance(metrics, dict):
            errors.append(f'analytics/snapshots.jsonl:{lineno}: missing metrics object')
        else:
            for mk, mv in metrics.items():
                if isinstance(mv, (int, float)) and not isinstance(mv, bool) and mv < 0:
                    errors.append(f'analytics/snapshots.jsonl:{lineno}: negative metric "{mk}={mv}"')

    wl_path = ws / 'watchlist.json'
    if wl_path.is_file():
        wl_data = load_json(wl_path, errors)
        if isinstance(wl_data, dict):
            tracks = wl_data.get('tracks')
            if not isinstance(tracks, list):
                errors.append('watchlist.json: "tracks" must be a list')
            else:
                seen_wl_ids: set[str] = set()
                for i, tr in enumerate(tracks):
                    if not isinstance(tr, dict):
                        errors.append(f'watchlist.json[{i}]: must be an object')
                        continue
                    wid = tr.get('id')
                    if not isinstance(wid, str) or not wid.strip():
                        errors.append(f'watchlist.json[{i}]: missing track id')
                    elif wid in seen_wl_ids:
                        errors.append(f'watchlist.json[{i}]: duplicate track id "{wid}"')
                    else:
                        seen_wl_ids.add(wid)
                    if not str(tr.get('query') or '').strip():
                        errors.append(f'watchlist.json[{i}]: missing query')
                    if tr.get('region') not in {'cn', 'global'}:
                        errors.append(f'watchlist.json[{i}]: invalid region "{tr.get("region")}"')

    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Validate a content-ops workspace or verify Gate 2 publish approval.')
    parser.add_argument('workspace', help='Path to the content-ops directory.')
    parser.add_argument('--verify-slot', default='', help='Verify Gate 2 tamper-proof approval, live variantHash, and idempotency for a slotId.')
    parser.add_argument('--json', action='store_true', help='Output JSON report (always JSON for --verify-slot).')
    args = parser.parse_args(argv)

    ws = Path(args.workspace)
    if args.verify_slot:
        rep = verify_publish_slot(ws, args.verify_slot)
        print(json.dumps(rep, indent=2, ensure_ascii=False))
        return 0 if rep['ok'] else 1

    errors = validate_workspace(ws)
    if args.json:
        print(json.dumps({'ok': not errors, 'workspace': str(ws.expanduser().resolve()), 'errors': errors}, indent=2, ensure_ascii=False))
        return 0 if not errors else 1
    if errors:
        print('Workspace validation failed:', file=sys.stderr)
        for err in errors:
            print(f'  - {err}', file=sys.stderr)
        return 1
    print(f'Workspace validation passed: {ws.expanduser().resolve()}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
