#!/usr/bin/env python3
"""Zero-dependency Python 3 reference client for Facebook Pages Graph API."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://graph.facebook.com/v21.0'


def require_env(name: str) -> str:
    val = os.environ.get(name, '').strip()
    if not val:
        raise RuntimeError(f'Missing required environment variable: {name}')
    return val


def api_call(method: str, path: str, token: str, params: dict | None = None, dry_run: bool = False) -> dict:
    q = {**(params or {}), 'access_token': token}
    if dry_run:
        safe = {k: ('<redacted>' if k == 'access_token' else v) for k, v in q.items()}
        return {'dryRun': True, 'method': method, 'url': f'{BASE}{path}', 'params': safe}
    if method in ('GET', 'DELETE'):
        url = f'{BASE}{path}?{urllib.parse.urlencode(q)}'
        req = urllib.request.Request(url, method=method)
    else:
        url = f'{BASE}{path}'
        data = urllib.parse.urlencode(q).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            text = resp.read().decode('utf-8').strip()
            return json.loads(text) if text else {'ok': True}
    except urllib.error.HTTPError as err:
        raise RuntimeError(f'HTTP {err.code}: {err.read().decode("utf-8", errors="replace")}') from err


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Facebook Pages Graph API reference client.')
    parser.add_argument('--dry-run', action='store_true', help='Preview HTTP call without sending.')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_feed = sub.add_parser('post-feed', help='Publish a text or link post to the Page feed.')
    p_feed.add_argument('--message', required=True)
    p_feed.add_argument('--link', default=None)

    p_photo = sub.add_parser('post-photo', help='Publish a single photo by HTTPS URL.')
    p_photo.add_argument('--url', required=True)
    p_photo.add_argument('--caption', default='')

    sub.add_parser('list-posts', help='List recent published Page posts.')

    p_cmts = sub.add_parser('list-comments', help='List comments on a post.')
    p_cmts.add_argument('--post-id', required=True)

    p_rep = sub.add_parser('reply-comment', help='Reply to a post or comment.')
    p_rep.add_argument('--object-id', required=True)
    p_rep.add_argument('--message', required=True)

    p_pi = sub.add_parser('post-insights', help='Fetch post-level views and reactions.')
    p_pi.add_argument('--post-id', required=True)
    p_pi.add_argument('--metrics', default='post_media_view,post_reactions_by_type_total', help='Comma-separated Meta v21+ post insight metrics.')

    p_pgi = sub.add_parser('page-insights', help='Fetch daily Page-level views, engagements, and follows.')
    p_pgi.add_argument('--metrics', default='page_media_view,page_post_engagements,page_follows', help='Comma-separated Meta v21+ page insight metrics.')

    args = parser.parse_args(argv)
    try:
        token = 'DRY_RUN_TOKEN' if args.dry_run else require_env('FACEBOOK_PAGE_ACCESS_TOKEN')
        page_id = 'DRY_RUN_PAGE_ID' if args.dry_run else require_env('FACEBOOK_PAGE_ID')
        if args.cmd == 'post-feed':
            p = {'message': args.message}
            if args.link:
                p['link'] = args.link
            res = api_call('POST', f'/{page_id}/feed', token, p, dry_run=args.dry_run)
        elif args.cmd == 'post-photo':
            res = api_call('POST', f'/{page_id}/photos', token, {'url': args.url, 'caption': args.caption}, dry_run=args.dry_run)
        elif args.cmd == 'list-posts':
            res = api_call('GET', f'/{page_id}/published_posts', token, {'fields': 'id,message,permalink_url,created_time', 'limit': 20}, dry_run=args.dry_run)
        elif args.cmd == 'list-comments':
            res = api_call('GET', f'/{args.post_id}/comments', token, {'fields': 'id,from,message,created_time'}, dry_run=args.dry_run)
        elif args.cmd == 'reply-comment':
            res = api_call('POST', f'/{args.object_id}/comments', token, {'message': args.message}, dry_run=args.dry_run)
        elif args.cmd == 'post-insights':
            res = api_call('GET', f'/{args.post_id}/insights', token, {'metric': args.metrics}, dry_run=args.dry_run)
        else:
            res = api_call('GET', f'/{page_id}/insights', token, {'metric': args.metrics, 'period': 'day'}, dry_run=args.dry_run)
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
