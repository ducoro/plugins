#!/usr/bin/env python3
"""Tamper-proof outbound reply guard: approval hash pinning, leak/promise blocking, and idempotency."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

BLOCKED_CONTENT_RULES: list[tuple[str, re.Pattern[str]]] = [
    ('unresolved_placeholder', re.compile(r'\{\{[^}]+\}\}|\[TODO[^\]]*\]|\[INSERT[^\]]*\]|<CUSTOMER_NAME>', re.I)),
    ('secret_or_token_leak', re.compile(r'\b(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{20,})\b|-----BEGIN [A-Z ]+PRIVATE KEY-----')),
    ('local_path_leak', re.compile(r'(?:/Users/|/home/|C:\\Users\\)[A-Za-z0-9_.-]+')),
    ('unauthorized_commitment', re.compile(r'\b(we\s+guarantee\s+a\s+full\s+refund|refund\s+has\s+been\s+issued|we\s+will\s+ship\s+this\s+by|100%\s+uptime\s+guarantee|we\s+accept\s+legal\s+liability)\b|保证全额退款|承诺.*上线|承担全部法律责任', re.I)),
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def body_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode('utf-8')).hexdigest()[:16]


def scan_reply_body(body: str, *, allow_commitments: bool = False) -> list[str]:
    errors: list[str] = []
    if not body or len(body.strip()) < 5:
        errors.append('empty_reply_body')
        return errors
    for code, pat in BLOCKED_CONTENT_RULES:
        if code == 'unauthorized_commitment' and allow_commitments:
            continue
        if pat.search(body):
            errors.append(code)
    return errors


def _load_queue(workspace: Path) -> tuple[Path, dict]:
    p = workspace / 'outbound-queue.json'
    data = json.loads(p.read_text(encoding='utf-8')) if p.is_file() else {'schemaVersion': 'customer-support-outbound/1', 'drafts': {}}
    data.setdefault('drafts', {})
    return p, data


def _load_tickets(workspace: Path) -> dict:
    p = workspace / 'tickets/tickets.json'
    return json.loads(p.read_text(encoding='utf-8')).get('tickets', {}) if p.is_file() else {}


def _load_reply_log(workspace: Path) -> list[dict]:
    p = workspace / 'reply-log.jsonl'
    if not p.is_file():
        return []
    rows = []
    for line in p.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def stage_draft(workspace: Path, ticket_id: str, body: str, *, draft_id: str | None = None) -> dict:
    workspace = workspace.expanduser().resolve()
    tickets = _load_tickets(workspace)
    if ticket_id not in tickets:
        raise ValueError(f'Unknown ticketId: {ticket_id}')
    ticket = tickets[ticket_id]
    issues = scan_reply_body(body, allow_commitments=False)
    h = body_hash(body)
    did = draft_id or f'draft-{hashlib.sha256(f"{ticket_id}:{h}".encode("utf-8")).hexdigest()[:10]}'
    requires_approval = bool(ticket.get('requiresHumanApproval', True)) or ('unauthorized_commitment' in issues)

    q_path, queue = _load_queue(workspace)
    draft = {
        'draftId': did,
        'ticketId': ticket_id,
        'body': body,
        'draftHash': h,
        'requiresHumanApproval': requires_approval,
        'status': 'blocked' if [i for i in issues if i != 'unauthorized_commitment'] else 'awaiting_approval',
        'scanViolations': issues,
        'approvedBy': None,
        'approvedAt': None,
        'approvedBodyHash': None,
        'sentAt': None,
        'externalReplyId': None,
        'stagedAt': utc_now().isoformat().replace('+00:00', 'Z'),
    }
    queue['drafts'][did] = draft
    queue['updatedAt'] = draft['stagedAt']
    q_path.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return draft


def approve_draft(workspace: Path, draft_id: str, approved_by: str) -> dict:
    workspace = workspace.expanduser().resolve()
    if not approved_by.strip():
        raise ValueError('approved_by must be a non-empty human identifier')
    q_path, queue = _load_queue(workspace)
    if draft_id not in queue['drafts']:
        raise ValueError(f'Unknown draftId: {draft_id}')
    draft = queue['drafts'][draft_id]
    hard_blocks = [v for v in scan_reply_body(draft['body'], allow_commitments=True)]
    if hard_blocks:
        raise ValueError(f'Cannot approve draft with hard safety violations: {hard_blocks}')
    now_iso = utc_now().isoformat().replace('+00:00', 'Z')
    draft['draftHash'] = body_hash(draft['body'])
    draft['approvedBy'] = approved_by.strip()
    draft['approvedAt'] = now_iso
    draft['approvedBodyHash'] = draft['draftHash']
    draft['status'] = 'approved'
    queue['updatedAt'] = now_iso
    q_path.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return draft


def check_send(workspace: Path, draft_id: str, *, now: datetime | None = None) -> dict:
    workspace = workspace.expanduser().resolve()
    now_dt = now or utc_now()
    q_path, queue = _load_queue(workspace)
    if draft_id not in queue['drafts']:
        return {'allowed': False, 'reasons': ['unknown_draft_id']}

    draft = queue['drafts'][draft_id]
    reasons: list[str] = []

    if draft.get('status') == 'sent':
        reasons.append('already_sent')

    # Re-scan body at send time (even after approval, leaks/placeholders are never allowed)
    live_hash = body_hash(draft.get('body', ''))
    hard_blocks = scan_reply_body(draft.get('body', ''), allow_commitments=bool(draft.get('approvedBy')))
    reasons.extend(hard_blocks)

    if draft.get('requiresHumanApproval', True):
        if not draft.get('approvedBy') or not draft.get('approvedBodyHash'):
            reasons.append('missing_human_approval')
        elif live_hash != draft.get('approvedBodyHash'):
            reasons.append('tampered_after_approval')
            draft['status'] = 'awaiting_approval'
            draft['approvedBy'] = None
            draft['approvedBodyHash'] = None
            q_path.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    # Idempotency & cooldown check against reply-log.jsonl
    policy_path = workspace / 'sla-policy.json'
    cooldown_h = float(json.loads(policy_path.read_text(encoding='utf-8')).get('replyCooldownHours', 24)) if policy_path.is_file() else 24.0
    cutoff = now_dt - timedelta(hours=cooldown_h)
    for rec in _load_reply_log(workspace):
        if rec.get('ticketId') == draft.get('ticketId'):
            if rec.get('bodyHash') == live_hash:
                reasons.append('duplicate_reply_hash')
                break
            try:
                sent_dt = datetime.fromisoformat(str(rec.get('sentAt', '')).replace('Z', '+00:00'))
                if sent_dt >= cutoff:
                    reasons.append('ticket_in_reply_cooldown')
                    break
            except ValueError:
                continue

    return {
        'allowed': len(reasons) == 0,
        'draftId': draft_id,
        'ticketId': draft.get('ticketId'),
        'liveHash': live_hash,
        'reasons': sorted(set(reasons)),
    }


def record_sent(workspace: Path, draft_id: str, external_reply_id: str, *, now: datetime | None = None) -> dict:
    workspace = workspace.expanduser().resolve()
    gate = check_send(workspace, draft_id, now=now)
    if not gate['allowed']:
        raise ValueError(f'Send blocked by reply_guard: {gate["reasons"]}')
    if not external_reply_id.strip():
        raise ValueError('external_reply_id is required to prove delivery')

    now_iso = (now or utc_now()).isoformat().replace('+00:00', 'Z')
    q_path, queue = _load_queue(workspace)
    draft = queue['drafts'][draft_id]
    draft['status'] = 'sent'
    draft['sentAt'] = now_iso
    draft['externalReplyId'] = external_reply_id.strip()
    queue['updatedAt'] = now_iso
    q_path.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    log_entry = {
        'draftId': draft_id,
        'ticketId': draft['ticketId'],
        'bodyHash': gate['liveHash'],
        'approvedBy': draft.get('approvedBy'),
        'externalReplyId': external_reply_id.strip(),
        'sentAt': now_iso,
    }
    with (workspace / 'reply-log.jsonl').open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

    # Update ticket status to replied
    t_path = workspace / 'tickets/tickets.json'
    if t_path.is_file():
        store = json.loads(t_path.read_text(encoding='utf-8'))
        if draft['ticketId'] in store.get('tickets', {}):
            store['tickets'][draft['ticketId']]['status'] = 'replied'
            store['updatedAt'] = now_iso
            t_path.write_text(json.dumps(store, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    return log_entry


def main() -> int:
    parser = argparse.ArgumentParser(description='Tamper-proof outbound reply guard for customer-support-ops.')
    parser.add_argument('workspace')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_stage = sub.add_parser('stage')
    p_stage.add_argument('--ticket', required=True)
    p_stage.add_argument('--body-file', required=True)
    p_stage.add_argument('--draft-id', default=None)

    p_app = sub.add_parser('approve')
    p_app.add_argument('--draft-id', required=True)
    p_app.add_argument('--approved-by', required=True)

    p_chk = sub.add_parser('check-send')
    p_chk.add_argument('--draft-id', required=True)

    p_rec = sub.add_parser('record-sent')
    p_rec.add_argument('--draft-id', required=True)
    p_rec.add_argument('--external-reply-id', required=True)

    args = parser.parse_args()
    ws = Path(args.workspace)
    if args.cmd == 'stage':
        body = Path(args.body_file).expanduser().resolve().read_text(encoding='utf-8')
        print(json.dumps(stage_draft(ws, args.ticket, body, draft_id=args.draft_id), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'approve':
        print(json.dumps(approve_draft(ws, args.draft_id, args.approved_by), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'check-send':
        res = check_send(ws, args.draft_id)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0 if res['allowed'] else 2
    if args.cmd == 'record-sent':
        print(json.dumps(record_sent(ws, args.draft_id, args.external_reply_id), indent=2, ensure_ascii=False))
        return 0
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
