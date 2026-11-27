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
import re
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


def _parse_optional_bool(raw: object) -> bool | None:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        val = raw.strip().lower()
        if val in {'true', '1', 'yes', 'y'}:
            return True
        if val in {'false', '0', 'no', 'n'}:
            return False
    return None


def _parse_optional_rating(raw: object) -> int | None:
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if 1 <= raw <= 5 else None
    s = str(raw).strip()
    if not s:
        return None
    try:
        val = int(s)
    except ValueError:
        return None
    return val if 1 <= val <= 5 else None


def http_get_json(url: str, *, headers: dict[str, str] | None = None, timeout: int = 15) -> object:
    req_headers = {'User-Agent': DEFAULT_UA, 'Accept': 'application/json'}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read(2_000_000).decode('utf-8', errors='replace'))


def fetch_github_issues(
    repo: str,
    *,
    state: str = 'open',
    limit: int = 30,
    api_url: str | None = None,
    meta: dict | None = None,
) -> list[dict]:
    if state not in {'open', 'closed', 'all'}:
        raise ValueError(f'Invalid GitHub issue state: {state}')
    clamped_limit = max(1, min(100, int(limit)))
    url = api_url or f'https://api.github.com/repos/{repo}/issues?state={state}&per_page={clamped_limit}'
    headers = {}
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    raw_items = http_get_json(url, headers=headers)
    if not isinstance(raw_items, list):
        raise ValueError('Unexpected GitHub API response: expected a JSON array of issues')
    if meta is not None:
        meta['rawCount'] = len(raw_items)
        meta['limit'] = clamped_limit
        meta['truncated'] = len(raw_items) >= clamped_limit
    tickets = []
    for item in raw_items:
        if not isinstance(item, dict) or 'pull_request' in item:
            continue
        ext_id = f'{repo}#{item.get("number")}'
        created_iso = normalize_iso(item.get('created_at'))
        updated_raw = item.get('updated_at')
        ticket = {
            'ticketId': f'github_issues:{ext_id}',
            'channel': 'github_issues',
            'externalId': ext_id,
            'customer': (item.get('user') or {}).get('login', 'unknown'),
            'subject': (item.get('title') or '').strip(),
            'body': (item.get('body') or '').strip(),
            'url': item.get('html_url', ''),
            'labels': [lb.get('name', '') for lb in item.get('labels', []) if isinstance(lb, dict) and lb.get('name')],
            'createdAt': created_iso,
            'status': 'resolved' if item.get('state') == 'closed' else 'open',
        }
        if updated_raw:
            ticket['lastInboundAt'] = normalize_iso(updated_raw)
        tickets.append(ticket)
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
            ticket: dict = {
                'ticketId': f'{channel}:{ext_id}',
                'channel': channel,
                'externalId': ext_id,
                'customer': customer,
                'subject': subject,
                'body': body,
                'url': lower.get('url') or '',
                'createdAt': normalize_iso(created),
                'status': 'resolved' if status.lower() in {'closed', 'solved', 'resolved'} else 'open',
            }
            rating = _parse_optional_rating(lower.get('rating') or lower.get('stars') or lower.get('score'))
            if rating is not None:
                ticket['rating'] = rating
            root_cause = (
                lower.get('root_cause_id')
                or lower.get('rootcauseid')
                or lower.get('root_cause')
                or lower.get('root cause')
                or ''
            )
            if root_cause:
                ticket['rootCauseId'] = root_cause
            vip = _parse_optional_bool(lower.get('vip'))
            if vip is not None:
                ticket['vip'] = vip
            raw_labels = lower.get('labels') or lower.get('tags') or ''
            if raw_labels:
                labels = [part.strip() for part in re.split(r'[;,]', raw_labels) if part.strip()]
                if labels:
                    ticket['labels'] = labels
            last_inbound = lower.get('last_inbound_at') or lower.get('lastinboundat') or ''
            if last_inbound:
                ticket['lastInboundAt'] = normalize_iso(last_inbound)
            tickets.append(ticket)
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
        ticket: dict = {
            'ticketId': obj.get('ticketId') or f'{channel}:{ext_id}',
            'channel': channel,
            'externalId': ext_id,
            'customer': str(obj.get('customer') or 'unknown'),
            'subject': str(obj.get('subject') or '(no subject)'),
            'body': str(obj.get('body') or ''),
            'url': str(obj.get('url') or ''),
            'labels': [str(lb) for lb in (obj.get('labels') or []) if str(lb).strip()],
            'createdAt': normalize_iso(obj.get('createdAt')),
            'status': str(obj.get('status') or 'open'),
        }
        rating = _parse_optional_rating(obj.get('rating'))
        if rating is not None:
            ticket['rating'] = rating
        if obj.get('rootCauseId'):
            ticket['rootCauseId'] = str(obj['rootCauseId']).strip()
        vip = _parse_optional_bool(obj.get('vip'))
        if vip is not None:
            ticket['vip'] = vip
        if isinstance(obj.get('riskFlags'), list):
            ticket['riskFlags'] = [str(f).strip() for f in obj['riskFlags'] if str(f).strip()]
        if obj.get('priority') in {'P0', 'P1', 'P2', 'P3'}:
            ticket['priority'] = obj['priority']
        if isinstance(obj.get('requiresHumanApproval'), bool):
            ticket['requiresHumanApproval'] = obj['requiresHumanApproval']
        if isinstance(obj.get('escalationReasons'), list):
            ticket['escalationReasons'] = [str(r).strip() for r in obj['escalationReasons'] if str(r).strip()]
        if obj.get('lastInboundAt'):
            ticket['lastInboundAt'] = normalize_iso(obj.get('lastInboundAt'))
        tickets.append(ticket)
    return tickets


def merge_tickets(data_dir: Path, incoming: list[dict]) -> dict:
    data_dir = data_dir.expanduser().resolve()
    store_path = data_dir / 'tickets/tickets.json'
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
            merged = dict(item)
            # Preserve existing triage & classification metadata when re-ingesting
            for field in ('rootCauseId', 'priority', 'requiresHumanApproval', 'escalationReasons', 'riskFlags', 'vip', 'lastInboundAt'):
                if field in existing and (field not in merged or merged[field] is None):
                    merged[field] = existing[field]
            # Merge list fields monotonically rather than dropping prior reasons/flags
            for list_field in ('escalationReasons', 'riskFlags'):
                if isinstance(existing.get(list_field), list) and isinstance(merged.get(list_field), list):
                    merged[list_field] = sorted(set(existing[list_field]) | set(merged[list_field]))
            if existing.get('requiresHumanApproval') is True:
                merged['requiresHumanApproval'] = True
            if existing.get('status') == 'replied' and merged.get('status') == 'open':
                merged['status'] = 'replied'
            tickets_map[tid] = merged
            updated += 1
    store['updatedAt'] = utc_now()
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(json.dumps(store, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return {'added': added, 'updated': updated, 'total': len(tickets_map)}


def main() -> int:
    parser = argparse.ArgumentParser(description='Ingest real customer feedback into customer-support-ops.')
    parser.add_argument('data_dir', help='Path to customer-support-ops data directory')
    parser.add_argument('--github-repo', default=None)
    parser.add_argument('--state', choices=('open', 'closed', 'all'), default='open', help='GitHub issues state filter')
    parser.add_argument('--limit', type=int, default=30, help='Maximum GitHub issues to fetch per call (1-100)')
    parser.add_argument('--eml', default=None)
    parser.add_argument('--mbox', default=None)
    parser.add_argument('--csv', default=None)
    parser.add_argument('--jsonl', default=None)
    args = parser.parse_args()

    collected: list[dict] = []
    warnings: list[str] = []
    if args.github_repo:
        gh_meta: dict = {}
        collected.extend(fetch_github_issues(args.github_repo, state=args.state, limit=args.limit, meta=gh_meta))
        if gh_meta.get('truncated'):
            warnings.append(
                f"github_issues_possibly_truncated: fetched {gh_meta['rawCount']} items hitting limit={gh_meta['limit']}; increase --limit or use Connector pagination"
            )
    if args.eml:
        collected.extend(parse_eml_path(Path(args.eml)))
    if args.mbox:
        collected.extend(parse_mbox_file(Path(args.mbox)))
    if args.csv:
        collected.extend(parse_csv_file(Path(args.csv)))
    if args.jsonl:
        collected.extend(parse_jsonl_file(Path(args.jsonl)))

    result = merge_tickets(Path(args.data_dir), collected)
    if warnings:
        result['warnings'] = warnings
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
