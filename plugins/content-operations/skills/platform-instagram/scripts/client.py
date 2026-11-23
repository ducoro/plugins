#!/usr/bin/env python3
"""Zero-dependency Python 3 reference client for Instagram Graph API."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://graph.instagram.com/v21.0'


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
    if method == 'GET' or method == 'DELETE':
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
    parser = argparse.ArgumentParser(description='Instagram Graph API reference client.')
    parser.add_argument('--dry-run', action='store_true', help='Preview request without network I/O.')
    sub = parser.add_subparsers(dest='cmd', required=True)

    sub.add_parser('quota', help='Check 24h content publishing limit.')

    p_c = sub.add_parser('create-container', help='Create an image, video carousel child, Reels, or Story container.')
    p_c.add_argument('--media-type', choices=['IMAGE', 'VIDEO', 'REELS', 'STORIES'], default='IMAGE')
    p_c.add_argument('--media-kind', choices=['image', 'video'], default=None, help='For STORIES: choose image or video (auto-inferred from URL extension if omitted).')
    p_c.add_argument('--media-url', required=True, help='Public HTTPS URL to JPEG or MP4.')
    p_c.add_argument('--caption', default='')
    p_c.add_argument('--is-carousel-item', action='store_true', help='Mark container as a carousel child item.')

    p_car = sub.add_parser('create-carousel', help='Create a parent CAROUSEL container from child container IDs.')
    p_car.add_argument('--children-ids', required=True, help='Comma-separated child container IDs (2-10).')
    p_car.add_argument('--caption', default='')

    p_st = sub.add_parser('container-status', help='Poll container processing status.')
    p_st.add_argument('--container-id', required=True)

    p_pub = sub.add_parser('publish', help='Publish a FINISHED container.')
    p_pub.add_argument('--container-id', required=True)

    p_gm = sub.add_parser('get-media', help='Read back live media permalink and metadata.')
    p_gm.add_argument('--media-id', required=True)

    p_ins = sub.add_parser('media-insights', help='Fetch live media insights.')
    p_ins.add_argument('--media-id', required=True)

    p_ains = sub.add_parser('account-insights', help='Fetch daily account-level reach/total_value insights.')
    p_ains.add_argument('--metrics', default='reach', help='Comma-separated Meta v21+ account insight metrics.')
    p_ains.add_argument('--metric-type', choices=['total_value', 'time_series'], default='total_value')

    p_cmts = sub.add_parser('list-comments', help='List comments on a media object.')
    p_cmts.add_argument('--media-id', required=True)

    p_rep = sub.add_parser('reply-comment', help='Reply to a comment.')
    p_rep.add_argument('--comment-id', required=True)
    p_rep.add_argument('--message', required=True)

    p_del = sub.add_parser('delete-comment', help='Delete a comment by ID.')
    p_del.add_argument('--comment-id', required=True)

    args = parser.parse_args(argv)
    try:
        token = 'DRY_RUN_TOKEN' if args.dry_run else require_env('INSTAGRAM_ACCESS_TOKEN')
        uid = 'DRY_RUN_IG_ID' if args.dry_run else require_env('INSTAGRAM_USER_ID')
        if args.cmd == 'quota':
            res = api_call('GET', f'/{uid}/content_publishing_limit', token, {'fields': 'config,quota_usage'}, dry_run=args.dry_run)
        elif args.cmd == 'create-container':
            p: dict = {}
            if args.caption and not args.is_carousel_item:
                p['caption'] = args.caption
            if args.is_carousel_item:
                p['is_carousel_item'] = 'true'
            if args.media_type == 'IMAGE':
                p['image_url'] = args.media_url
            elif args.media_type == 'VIDEO':
                p['media_type'] = 'VIDEO'
                p['video_url'] = args.media_url
            elif args.media_type == 'REELS':
                p['media_type'] = 'REELS'
                p['video_url'] = args.media_url
            else:
                p['media_type'] = 'STORIES'
                inferred = args.media_kind
                if not inferred:
                    path_lower = urllib.parse.urlparse(args.media_url).path.lower()
                    inferred = 'image' if path_lower.endswith(('.jpg', '.jpeg', '.png')) else 'video'
                p['image_url' if inferred == 'image' else 'video_url'] = args.media_url
            res = api_call('POST', f'/{uid}/media', token, p, dry_run=args.dry_run)
        elif args.cmd == 'create-carousel':
            p = {'media_type': 'CAROUSEL', 'children': args.children_ids}
            if args.caption:
                p['caption'] = args.caption
            res = api_call('POST', f'/{uid}/media', token, p, dry_run=args.dry_run)
        elif args.cmd == 'container-status':
            res = api_call('GET', f'/{args.container_id}', token, {'fields': 'status_code,status'}, dry_run=args.dry_run)
        elif args.cmd == 'publish':
            res = api_call('POST', f'/{uid}/media_publish', token, {'creation_id': args.container_id}, dry_run=args.dry_run)
        elif args.cmd == 'get-media':
            res = api_call('GET', f'/{args.media_id}', token, {'fields': 'id,permalink,timestamp,media_type'}, dry_run=args.dry_run)
        elif args.cmd == 'media-insights':
            res = api_call('GET', f'/{args.media_id}/insights', token, {'metric': 'views,reach,saved,shares,likes,comments'}, dry_run=args.dry_run)
        elif args.cmd == 'account-insights':
            res = api_call('GET', f'/{uid}/insights', token, {'metric': args.metrics, 'period': 'day', 'metric_type': args.metric_type}, dry_run=args.dry_run)
        elif args.cmd == 'list-comments':
            res = api_call('GET', f'/{args.media_id}/comments', token, {'fields': 'id,text,username,timestamp'}, dry_run=args.dry_run)
        elif args.cmd == 'reply-comment':
            res = api_call('POST', f'/{args.comment_id}/replies', token, {'message': args.message}, dry_run=args.dry_run)
        else:
            res = api_call('DELETE', f'/{args.comment_id}', token, dry_run=args.dry_run)
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
