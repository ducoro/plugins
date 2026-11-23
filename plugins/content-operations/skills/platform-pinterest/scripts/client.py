#!/usr/bin/env python3
"""Zero-dependency Python 3 reference client for Pinterest API v5."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://api.pinterest.com/v5'


def require_env(name: str) -> str:
    val = os.environ.get(name, '').strip()
    if not val:
        raise RuntimeError(f'Missing required environment variable: {name}')
    return val


def api_call(method: str, path: str, token: str, query: dict | None = None, body: dict | None = None, dry_run: bool = False) -> dict:
    qs = urllib.parse.urlencode(query or {})
    url = f'{BASE}{path}?{qs}' if qs else f'{BASE}{path}'
    if dry_run:
        return {'dryRun': True, 'method': method, 'url': url, 'headers': {'Authorization': 'Bearer <redacted>'}, 'body': body}
    data = json.dumps(body).encode('utf-8') if body is not None else None
    headers = {'Authorization': f'Bearer {token}'}
    if data is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            text = resp.read().decode('utf-8').strip()
            return json.loads(text) if text else {'ok': True}
    except urllib.error.HTTPError as err:
        raise RuntimeError(f'HTTP {err.code}: {err.read().decode("utf-8", errors="replace")}') from err


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Pinterest API v5 reference client.')
    parser.add_argument('--dry-run', action='store_true', help='Preview HTTP call without sending.')
    sub = parser.add_subparsers(dest='cmd', required=True)

    sub.add_parser('list-boards', help='List boards to retrieve valid board_id values.')

    p_pin = sub.add_parser('create-pin', help='Create an image Pin by HTTPS image URL.')
    p_pin.add_argument('--board-id', required=True)
    p_pin.add_argument('--title', required=True)
    p_pin.add_argument('--description', default='')
    p_pin.add_argument('--image-url', required=True)
    p_pin.add_argument('--link', default=None)
    p_pin.add_argument('--alt-text', default=None)

    p_get = sub.add_parser('get-pin', help='Read back a Pin by ID to verify live metadata.')
    p_get.add_argument('--pin-id', required=True)

    p_upd = sub.add_parser('update-pin', help='Update an existing Pin title, description, link, or alt text.')
    p_upd.add_argument('--pin-id', required=True)
    p_upd.add_argument('--title', default=None)
    p_upd.add_argument('--description', default=None)
    p_upd.add_argument('--link', default=None)
    p_upd.add_argument('--alt-text', default=None)

    p_ana = sub.add_parser('pin-analytics', help='Fetch Pin analytics for a date range.')
    p_ana.add_argument('--pin-id', required=True)
    p_ana.add_argument('--start-date', required=True, help='YYYY-MM-DD')
    p_ana.add_argument('--end-date', required=True, help='YYYY-MM-DD')

    args = parser.parse_args(argv)
    try:
        token = 'DRY_RUN_TOKEN' if args.dry_run else require_env('PINTEREST_ACCESS_TOKEN')
        if args.cmd == 'list-boards':
            res = api_call('GET', '/boards', token, dry_run=args.dry_run)
        elif args.cmd == 'create-pin':
            body: dict = {
                'board_id': args.board_id,
                'title': args.title,
                'description': args.description,
                'media_source': {'source_type': 'image_url', 'url': args.image_url},
            }
            if args.link:
                body['link'] = args.link
            if args.alt_text:
                body['alt_text'] = args.alt_text
            res = api_call('POST', '/pins', token, body=body, dry_run=args.dry_run)
        elif args.cmd == 'get-pin':
            res = api_call('GET', f'/pins/{args.pin_id}', token, dry_run=args.dry_run)
        elif args.cmd == 'update-pin':
            body = {}
            if args.title is not None:
                body['title'] = args.title
            if args.description is not None:
                body['description'] = args.description
            if args.link is not None:
                body['link'] = args.link
            if args.alt_text is not None:
                body['alt_text'] = args.alt_text
            if not body:
                raise RuntimeError('update-pin requires at least one of --title, --description, --link, or --alt-text')
            res = api_call('PATCH', f'/pins/{args.pin_id}', token, body=body, dry_run=args.dry_run)
        else:
            res = api_call(
                'GET',
                f'/pins/{args.pin_id}/analytics',
                token,
                {
                    'start_date': args.start_date,
                    'end_date': args.end_date,
                    'metric_types': 'IMPRESSION,SAVE,PIN_CLICK,OUTBOUND_CLICK',
                },
                dry_run=args.dry_run,
            )
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
