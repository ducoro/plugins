#!/usr/bin/env python3
"""Ingest real customer feedback from GitHub Issues, .eml/.mbox mail, CSV exports, or Connector JSONL."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
import hashlib
import json
import mailbox
import os
from pathlib import Path
import urllib.request

DEFAULT_UA = 'DucoroSupportOps/1.0 (+https://ducoro.ai)'


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def normalize_iso(raw: str | None) -> str:
    if not raw:
        return utc_now()
    s = str(raw).strip()
    try:
        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    except (ValueError, TypeError):
        return utc_now()


def http_get_json(url: str, *, headers: dict[str, str] | None = None, timeout: int = 15) -> object:
    req_headers = {'User-Agent': DEFAULT_UA, 'Accept': 'application/json'}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read(2_000_000).decode('utf-8', errors='replace'))


def fetch_github_issues(repo: str, *, state: str = 'open', limit: int = 30, api_url: str | None = None) -> list[dict]:
    url = api_url or f'https://api.github.com/repos/{repo}/issues?state={state}&per_page={limit}'
    headers = {}
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    raw_items = http_get_json(url, headers=headers)
    tickets = []
    for item in raw_items:
        if 'pull_request' in item:
            continue
        ext_id = f'{repo}#{item.get("number")}'
        tickets.append({
            'ticketId': f'github_issues:{ext_id}',
            'channel': 'github_issues',
            'externalId': ext_id,
            'customer': (item.get('user') or {}).get('login', 'unknown'),
            'subject': (item.get('title') or '').strip(),
            'body': (item.get('body') or '').strip(),
            'url': item.get('html_url', ''),
            'labels': [lb.get('name', '') for lb in item.get('labels', []) if isinstance(lb, dict)],
            'createdAt': normalize_iso(item.get('created_at')),
            'status': 'resolved' if item.get('state') == 'closed' else 'open',
        })
    return tickets


def _extract_email_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain' and 'attachment' not in str(part.get('Content-Disposition') or ''):
                try:
                    return part.get_content().strip()
                except Exception:
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode('utf-8', errors='replace').strip()
    try:
        return msg.get_content().strip()
    except Exception:
        payload = msg.get_payload(decode=True)
        return payload.decode('utf-8', errors='replace').strip() if payload else str(msg.get_payload() or '').strip()


def _message_to_ticket(msg, source_name: str) -> dict:
    msg_id = (msg.get('Message-ID') or '').strip('<> ').strip()
    sender = str(msg.get('From') or 'unknown').strip()
    subject = str(msg.get('Subject') or '(no subject)').strip()
    body = _extract_email_body(msg)
    if not msg_id:
        msg_id = hashlib.sha256(f'{sender}|{subject}|{body[:120]}'.encode('utf-8')).hexdigest()[:16]
    return {
        'ticketId': f'email:{msg_id}',
        'channel': 'email',
        'externalId': msg_id,
        'customer': sender,
        'subject': subject,
        'body': body,
        'url': '',
        'sourceFile': source_name,
        'createdAt': normalize_iso(msg.get('Date')),
        'status': 'open',
    }


def parse_eml_path(path: Path) -> list[dict]:
    path = path.expanduser().resolve()
    files = sorted(path.glob('*.eml')) if path.is_dir() else [path]
    tickets = []
    for f in files:
        msg = BytesParser(policy=policy.default).parsebytes(f.read_bytes())
        tickets.append(_message_to_ticket(msg, f.name))
    return tickets


def parse_mbox_file(path: Path) -> list[dict]:
    path = path.expanduser().resolve()
    mbox = mailbox.mbox(str(path))
    tickets = []
    try:
        for msg in mbox:
            parsed = BytesParser(policy=policy.default).parsebytes(msg.as_bytes())
            tickets.append(_message_to_ticket(parsed, path.name))
    finally:
        mbox.close()
    return tickets


def parse_csv_file(path: Path) -> list[dict]:
    path = path.expanduser().resolve()
    tickets = []
    with path.open('r', encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh)
        for idx, row in enumerate(reader, start=1):
            lower = {(k or '').strip().lower(): (v or '').strip() for k, v in row.items()}
            ext_id = lower.get('id') or lower.get('ticket_id') or lower.get('ticket id') or f'row-{idx}'
            subject = lower.get('subject') or lower.get('title') or lower.get('summary') or '(no subject)'
            body = lower.get('body') or lower.get('description') or lower.get('message') or lower.get('content') or ''
            customer = lower.get('customer') or lower.get('requester') or lower.get('email') or lower.get('author') or 'unknown'
            created = lower.get('created_at') or lower.get('created') or lower.get('date') or ''
            channel = lower.get('channel') or 'csv'
            status = lower.get('status') or 'open'
            tickets.append({
                'ticketId': f'{channel}:{ext_id}',
                'channel': channel,
                'externalId': ext_id,
                'customer': customer,
                'subject': subject,
                'body': body,
                'url': lower.get('url') or '',
                'createdAt': normalize_iso(created),
                'status': 'resolved' if status.lower() in {'closed', 'solved', 'resolved'} else 'open',
            })
    return tickets


def parse_jsonl_file(path: Path) -> list[dict]:
    path = path.expanduser().resolve()
    tickets = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        channel = str(obj.get('channel') or 'connector').strip()
        ext_id = str(obj.get('externalId') or obj.get('id') or '').strip()
        if not ext_id:
            continue
        tickets.append({
            'ticketId': obj.get('ticketId') or f'{channel}:{ext_id}',
            'channel': channel,
            'externalId': ext_id,
            'customer': str(obj.get('customer') or 'unknown'),
            'subject': str(obj.get('subject') or '(no subject)'),
            'body': str(obj.get('body') or ''),
            'url': str(obj.get('url') or ''),
            'rating': obj.get('rating'),
            'labels': obj.get('labels') or [],
            'createdAt': normalize_iso(obj.get('createdAt')),
            'status': str(obj.get('status') or 'open'),
            'rootCauseId': obj.get('rootCauseId'),
        })
    return tickets


def merge_tickets(workspace: Path, incoming: list[dict]) -> dict:
    workspace = workspace.expanduser().resolve()
    store_path = workspace / 'tickets/tickets.json'
    store = (
        json.loads(store_path.read_text(encoding='utf-8'))
        if store_path.is_file()
        else {'schemaVersion': 'customer-support-tickets/1', 'updatedAt': utc_now(), 'tickets': {}}
    )
    tickets_map = store.setdefault('tickets', {})
    added = 0
    updated = 0
    for item in incoming:
        tid = item['ticketId']
        if tid not in tickets_map:
            tickets_map[tid] = item
            added += 1
        else:
            existing = tickets_map[tid]
            # Preserve existing rootCauseId & escalation metadata when re-ingesting
            for field in ('rootCauseId', 'priority', 'requiresHumanApproval', 'escalationReasons'):
                if field in existing and field not in item:
                    item[field] = existing[field]
            if existing.get('status') == 'replied' and item.get('status') == 'open':
                item['status'] = 'replied'
            tickets_map[tid] = item
            updated += 1
    store['updatedAt'] = utc_now()
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(json.dumps(store, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return {'added': added, 'updated': updated, 'total': len(tickets_map)}


def main() -> int:
    parser = argparse.ArgumentParser(description='Ingest real customer feedback into customer-support-ops.')
    parser.add_argument('workspace', help='Path to customer-support-ops workspace')
    parser.add_argument('--github-repo', default=None)
    parser.add_argument('--eml', default=None)
    parser.add_argument('--mbox', default=None)
    parser.add_argument('--csv', default=None)
    parser.add_argument('--jsonl', default=None)
    args = parser.parse_args()

    collected: list[dict] = []
    if args.github_repo:
        collected.extend(fetch_github_issues(args.github_repo))
    if args.eml:
        collected.extend(parse_eml_path(Path(args.eml)))
    if args.mbox:
        collected.extend(parse_mbox_file(Path(args.mbox)))
    if args.csv:
        collected.extend(parse_csv_file(Path(args.csv)))
    if args.jsonl:
        collected.extend(parse_jsonl_file(Path(args.jsonl)))

    result = merge_tickets(Path(args.workspace), collected)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
