#!/usr/bin/env python3
"""Per-piece verifiable source ledger and claim grounding gate (zero dependencies)."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

VALID_STATUSES = ('verified', 'unverified', 'user_provided')
VALID_CLAIM_TYPES = ('fact', 'inference', 'opinion', 'user_experience')
VALID_SOURCE_TYPES = ('web_url', 'local_file', 'first_hand_test', 'publication_or_interview')


def _is_http_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme in ('http', 'https') and bool(parsed.netloc)


def load_ledger(path: Path) -> dict:
    if path.is_file():
        data = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data, dict) and isinstance(data.get('sources'), list):
            return data
    return {'version': 1, 'sources': []}


def save_ledger(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def add_source(
    ledger_path: Path,
    *,
    title: str,
    claim: str,
    url: str = '',
    source_type: str = 'web_url',
    locator: str = '',
    publisher: str = '',
    published_at: str = '',
    status: str = 'verified',
) -> dict:
    title = title.strip()
    claim = claim.strip()
    url = url.strip()
    locator = locator.strip()
    if not title or not claim:
        raise ValueError('Both --title and --claim must be non-empty.')
    if status not in VALID_STATUSES:
        raise ValueError(f'Invalid status "{status}". Must be one of: {", ".join(VALID_STATUSES)}')
    if source_type not in VALID_SOURCE_TYPES:
        raise ValueError(f'Invalid source_type "{source_type}". Must be one of: {", ".join(VALID_SOURCE_TYPES)}')
    if url and not _is_http_url(url):
        raise ValueError(f'Invalid URL: "{url}" (must start with http:// or https://).')
    if status == 'verified':
        if source_type == 'web_url' and not _is_http_url(url):
            raise ValueError('A "verified" web_url source requires a valid http(s):// URL (or pass --source-type local_file|first_hand_test|publication_or_interview with --locator).')
        if source_type != 'web_url' and not locator:
            raise ValueError(f'A "verified" {source_type} source requires a non-empty --locator (file path, publication citation, or test record).')

    ledger = load_ledger(ledger_path)
    next_id = f'S{len(ledger["sources"]) + 1}'
    entry = {
        'id': next_id,
        'title': title,
        'claim': claim,
        'sourceType': source_type,
        'url': url,
        'locator': locator,
        'publisher': publisher.strip(),
        'publishedAt': published_at.strip(),
        'status': status,
        'recordedAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }
    ledger['sources'].append(entry)
    save_ledger(ledger_path, ledger)
    return entry


def verify_claims(ledger_path: Path, claims_path: Path) -> dict:
    """Ensure every factual claim has a verified source and every user_experience comes from user_provided."""
    ledger = load_ledger(ledger_path)
    sources_by_id = {str(s.get('id')): s for s in ledger.get('sources', [])}
    raw = json.loads(claims_path.read_text(encoding='utf-8'))
    claims = raw.get('claims') if isinstance(raw, dict) else raw
    if not isinstance(claims, list) or not claims:
        raise ValueError('claims file must contain a non-empty "claims" array.')

    issues: list[dict] = []
    for idx, item in enumerate(claims, start=1):
        cid = str(item.get('id') or f'C{idx}')
        ctype = str(item.get('type') or '')
        status = str(item.get('status') or 'supported')
        sids = [str(s) for s in (item.get('sourceIds') or item.get('source_ids') or [])]
        if ctype not in VALID_CLAIM_TYPES:
            issues.append({'claimId': cid, 'level': 'ERROR', 'message': f'Unknown claim type "{ctype}".'})
            continue
        if status == 'unsupported':
            issues.append({'claimId': cid, 'level': 'ERROR', 'message': 'Unsupported claim must be removed or narrowed before drafting.'})
            continue
        missing = [sid for sid in sids if sid not in sources_by_id]
        if missing:
            issues.append({'claimId': cid, 'level': 'ERROR', 'message': f'Unknown source id(s): {", ".join(missing)}.'})
            continue
        linked = [sources_by_id[sid] for sid in sids]
        if ctype == 'fact':
            if not any(src.get('status') == 'verified' for src in linked):
                issues.append({'claimId': cid, 'level': 'ERROR', 'message': 'Factual claim requires at least one verified source (URL or non-web locator).'})
        elif ctype == 'user_experience':
            if not any(src.get('status') == 'user_provided' for src in linked):
                issues.append({'claimId': cid, 'level': 'ERROR', 'message': 'User-experience claim requires a user_provided source from the current brief.'})
        elif ctype == 'inference' and not linked:
            issues.append({'claimId': cid, 'level': 'WARN', 'message': 'Inference has no linked basis source; state uncertainty explicitly.'})

    errors = sum(1 for i in issues if i['level'] == 'ERROR')
    return {
        'ok': errors == 0,
        'claimCount': len(claims),
        'sourceCount': len(sources_by_id),
        'errors': errors,
        'warnings': len(issues) - errors,
        'issues': issues,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Manage per-piece verifiable source ledger and verify claims grounding.')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_add = sub.add_parser('add', help='Append a verified, unverified, or user_provided source entry.')
    p_add.add_argument('--ledger', required=True, help='Path to sources.json.')
    p_add.add_argument('--title', required=True, help='Source title or user note label.')
    p_add.add_argument('--claim', required=True, help='Specific fact or detail supported by this source.')
    p_add.add_argument('--url', default='', help='http(s) URL (required when --status verified and --source-type web_url).')
    p_add.add_argument('--source-type', choices=VALID_SOURCE_TYPES, default='web_url', help='Provenance kind (default web_url; supports local_file, first_hand_test, publication_or_interview).')
    p_add.add_argument('--locator', default='', help='Non-web citation anchor (local file path, book/page, interview date, or test log).')
    p_add.add_argument('--publisher', default='', help='Organization, author, or channel.')
    p_add.add_argument('--published-at', default='', help='Publication date (YYYY-MM-DD).')
    p_add.add_argument('--status', choices=VALID_STATUSES, default='verified')

    p_ls = sub.add_parser('list', help='List recorded sources in a ledger.')
    p_ls.add_argument('--ledger', required=True, help='Path to sources.json.')
    p_ls.add_argument('--json', action='store_true')

    p_ver = sub.add_parser('verify-claims', help='Verify claims.json against sources.json before drafting/publishing.')
    p_ver.add_argument('--ledger', required=True, help='Path to sources.json.')
    p_ver.add_argument('--claims', required=True, help='Path to claims.json.')
    p_ver.add_argument('--json', action='store_true')

    args = ap.parse_args(argv)
    try:
        if args.cmd == 'add':
            entry = add_source(
                Path(args.ledger).expanduser().resolve(),
                title=args.title,
                claim=args.claim,
                url=args.url,
                source_type=args.source_type,
                locator=args.locator,
                publisher=args.publisher,
                published_at=args.published_at,
                status=args.status,
            )
            print(json.dumps(entry, indent=2, ensure_ascii=False))
            return 0
        if args.cmd == 'list':
            data = load_ledger(Path(args.ledger).expanduser().resolve())
            if args.json:
                print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                for item in data['sources']:
                    print(f"[{item['id']}][{item['status']}] {item['title']} — {item['claim']} ({item['url'] or 'no-url'})")
            return 0
        report = verify_claims(Path(args.ledger).expanduser().resolve(), Path(args.claims).expanduser().resolve())
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report['ok'] else 2
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
