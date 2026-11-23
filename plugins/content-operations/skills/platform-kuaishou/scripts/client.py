#!/usr/bin/env python3
"""Zero-dependency Python 3 reference client for Kuaishou OpenAPI."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://open.kuaishou.com'


def require_env(name: str) -> str:
    val = os.environ.get(name, '').strip()
    if not val:
        raise RuntimeError(f'Missing required environment variable: {name}')
    return val


def api_call(method: str, path: str, query: dict, dry_run: bool = False) -> dict:
    if dry_run:
        safe = {k: ('<redacted>' if 'token' in k else v) for k, v in query.items()}
        return {'dryRun': True, 'method': method, 'url': f'{BASE}{path}', 'query': safe}
    url = f'{BASE}{path}?{urllib.parse.urlencode(query)}'
    data = b'' if method == 'POST' else None
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            text = resp.read().decode('utf-8').strip()
            out = json.loads(text) if text else {'ok': True}
    except urllib.error.HTTPError as err:
        raise RuntimeError(f'HTTP {err.code}: {err.read().decode("utf-8", errors="replace")}') from err
    if isinstance(out, dict):
        result = out.get('result')
        if result not in (1, None):
            raise RuntimeError(f'Kuaishou API error (result={result}): {json.dumps(out, ensure_ascii=False)}')
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Kuaishou OpenAPI reference client.')
    parser.add_argument('--dry-run', action='store_true', help='Preview HTTP request without sending.')
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('user-info', help='Fetch Kuaishou account info.')
    sub.add_parser('start-upload', help='Initialize a video upload token and endpoint.')
    p_info = sub.add_parser('photo-info', help='Query a published video by photo_id.')
    p_info.add_argument('--photo-id', required=True)
    p_list = sub.add_parser('photo-list', help='List recent published videos.')
    p_list.add_argument('--count', type=int, default=20)

    args = parser.parse_args(argv)
    try:
        app_id = 'DRY_RUN_APP' if args.dry_run else require_env('KUAISHOU_APP_ID')
        token = 'DRY_RUN_TOKEN' if args.dry_run else require_env('KUAISHOU_ACCESS_TOKEN')
        auth = {'app_id': app_id, 'access_token': token}
        if args.cmd == 'user-info':
            res = api_call('GET', '/openapi/user_info', auth, dry_run=args.dry_run)
        elif args.cmd == 'start-upload':
            res = api_call('POST', '/openapi/photo/start_upload', auth, dry_run=args.dry_run)
        elif args.cmd == 'photo-info':
            res = api_call('GET', '/openapi/photo/info', {**auth, 'photo_id': args.photo_id}, dry_run=args.dry_run)
        else:
            res = api_call('GET', '/openapi/photo/list', {**auth, 'count': args.count}, dry_run=args.dry_run)
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
