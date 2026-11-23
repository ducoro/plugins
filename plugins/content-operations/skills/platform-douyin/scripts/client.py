#!/usr/bin/env python3
"""Zero-dependency Python 3 reference client for Douyin OpenAPI reads & token checks."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = 'https://open.douyin.com'


def require_env(name: str) -> str:
    val = os.environ.get(name, '').strip()
    if not val:
        raise RuntimeError(f'Missing required environment variable: {name}')
    return val


def check_business_error(data: dict) -> None:
    err_no = data.get('err_no')
    if err_no not in (0, None):
        raise RuntimeError(f'Douyin API error (err_no={err_no}): {json.dumps(data, ensure_ascii=False)}')
    nested = data.get('data')
    if isinstance(nested, dict):
        code = nested.get('error_code')
        if code not in (0, None):
            raise RuntimeError(f'Douyin API error (error_code={code}): {json.dumps(data, ensure_ascii=False)}')
    extra = data.get('extra')
    if isinstance(extra, dict):
        code = extra.get('error_code')
        if code not in (0, None):
            raise RuntimeError(f'Douyin API error (extra.error_code={code}): {json.dumps(data, ensure_ascii=False)}')


def api_call(
    method: str,
    path: str,
    headers: dict,
    query: dict | None = None,
    payload: dict | None = None,
    dry_run: bool = False,
) -> dict:
    qs = urllib.parse.urlencode(query or {})
    url = f'{BASE_URL}{path}?{qs}' if qs else f'{BASE_URL}{path}'
    if dry_run:
        redacted = {k: ('<redacted>' if 'token' in k.lower() or 'auth' in k.lower() else v) for k, v in headers.items()}
        return {'dryRun': True, 'method': method, 'url': url, 'headers': redacted, 'body': payload}
    req_headers = dict(headers)
    data = None
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        req_headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            text = resp.read().decode('utf-8').strip()
            out = json.loads(text) if text else {'ok': True}
    except urllib.error.HTTPError as err:
        detail = err.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'HTTP {err.code}: {detail}') from err
    if isinstance(out, dict):
        check_business_error(out)
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Douyin OpenAPI reference client.')
    parser.add_argument('--dry-run', action='store_true', help='Print request payload without calling the network.')
    parser.add_argument('--app-type', choices=['web', 'miniapp'], default='web', help='Select Web OpenAPI (/api/douyin/v1/*) or Mini-App (/api/apps/v1/*).')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_query = sub.add_parser('query-videos', help='Query live video metadata by item_ids.')
    p_query.add_argument('--item-ids', nargs='+', required=True, help='One or more Douyin item_ids.')

    p_fans = sub.add_parser('get-fans', help='Query account fan statistics.')
    p_fans.add_argument('--date-type', type=int, default=7, help='Lookback window in days (e.g. 7, 15, 30).')

    args = parser.parse_args(argv)
    try:
        token = 'DRY_RUN_TOKEN' if args.dry_run else require_env('DOUYIN_ACCESS_TOKEN')
        open_id = 'DRY_RUN_OPEN_ID' if args.dry_run else require_env('DOUYIN_OPEN_ID')
        headers = {'access-token': token}
        if args.cmd == 'query-videos':
            path = '/api/douyin/v1/video/video_data/' if args.app_type == 'web' else '/api/apps/v1/video/query/'
            res = api_call('POST', path, headers, query={'open_id': open_id}, payload={'item_ids': args.item_ids}, dry_run=args.dry_run)
        else:
            if args.app_type == 'web':
                path = '/api/douyin/v1/user/fans_data/'
                query = {'open_id': open_id, 'date_type': args.date_type}
            else:
                path = '/api/apps/v1/user/get_fans/'
                query = {'open_id': open_id, 'date_type': args.date_type}
            res = api_call('GET', path, headers, query=query, dry_run=args.dry_run)
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
