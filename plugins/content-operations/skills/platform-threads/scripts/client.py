#!/usr/bin/env python3
"""Zero-dependency Python 3 reference client for Meta Threads API."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://graph.threads.net/v1.0'


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
    if method == 'GET':
        url = f'{BASE}{path}?{urllib.parse.urlencode(q)}'
        req = urllib.request.Request(url, method='GET')
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
    parser = argparse.ArgumentParser(description='Threads API reference client.')
    parser.add_argument('--dry-run', action='store_true', help='Preview HTTP call without sending.')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_c = sub.add_parser('create-container', help='Create a Threads post, media, carousel child, or reply container.')
    p_c.add_argument('--media-type', choices=['TEXT', 'IMAGE', 'VIDEO'], default='TEXT')
    p_c.add_argument('--text', default='')
    p_c.add_argument('--media-url', default=None)
    p_c.add_argument('--topic-tag', default=None)
    p_c.add_argument('--reply-to', default=None)
    p_c.add_argument('--reply-control', choices=['everyone', 'accounts_you_follow', 'mentioned_only'], default=None)
    p_c.add_argument('--is-carousel-item', action='store_true', help='Mark container as a carousel child item.')

    p_car = sub.add_parser('create-carousel', help='Create a parent CAROUSEL container from child container IDs.')
    p_car.add_argument('--children-ids', required=True, help='Comma-separated child container IDs (2-10).')
    p_car.add_argument('--text', default='')
    p_car.add_argument('--topic-tag', default=None)
    p_car.add_argument('--reply-control', choices=['everyone', 'accounts_you_follow', 'mentioned_only'], default=None)

    p_st = sub.add_parser('container-status', help='Poll Threads container processing status.')
    p_st.add_argument('--container-id', required=True)

    p_pub = sub.add_parser('publish', help='Publish a created Threads container.')
    p_pub.add_argument('--container-id', required=True)

    p_gp = sub.add_parser('get-post', help='Read back live Threads post permalink and metadata.')
    p_gp.add_argument('--post-id', required=True)

    p_ins = sub.add_parser('insights', help='Fetch post insights.')
    p_ins.add_argument('--post-id', required=True)

    p_rep = sub.add_parser('list-replies', help='List replies on a Threads post.')
    p_rep.add_argument('--post-id', required=True)

    p_mr = sub.add_parser('manage-reply', help='Hide or unhide a reply on your post.')
    p_mr.add_argument('--reply-id', required=True)
    p_mr.add_argument('--hide', choices=['true', 'false'], required=True)

    args = parser.parse_args(argv)
    try:
        token = 'DRY_RUN_TOKEN' if args.dry_run else require_env('THREADS_ACCESS_TOKEN')
        uid = 'DRY_RUN_UID' if args.dry_run else require_env('THREADS_USER_ID')
        if args.cmd == 'create-container':
            if args.media_type == 'TEXT' and not args.text:
                raise RuntimeError('create-container with --media-type TEXT requires --text')
            if args.media_type in ('IMAGE', 'VIDEO') and not args.media_url:
                raise RuntimeError(f'create-container with --media-type {args.media_type} requires --media-url')
            p: dict = {'media_type': args.media_type}
            if args.text and not args.is_carousel_item:
                p['text'] = args.text
            if args.is_carousel_item:
                p['is_carousel_item'] = 'true'
            if args.media_url and args.media_type == 'IMAGE':
                p['image_url'] = args.media_url
            elif args.media_url and args.media_type == 'VIDEO':
                p['video_url'] = args.media_url
            if args.topic_tag:
                p['topic_tag'] = args.topic_tag
            if args.reply_to:
                p['reply_to_id'] = args.reply_to
            if args.reply_control:
                p['reply_control'] = args.reply_control
            res = api_call('POST', f'/{uid}/threads', token, p, dry_run=args.dry_run)
        elif args.cmd == 'create-carousel':
            p = {'media_type': 'CAROUSEL', 'children': args.children_ids}
            if args.text:
                p['text'] = args.text
            if args.topic_tag:
                p['topic_tag'] = args.topic_tag
            if args.reply_control:
                p['reply_control'] = args.reply_control
            res = api_call('POST', f'/{uid}/threads', token, p, dry_run=args.dry_run)
        elif args.cmd == 'container-status':
            res = api_call('GET', f'/{args.container_id}', token, {'fields': 'status,error_message'}, dry_run=args.dry_run)
        elif args.cmd == 'publish':
            res = api_call('POST', f'/{uid}/threads_publish', token, {'creation_id': args.container_id}, dry_run=args.dry_run)
        elif args.cmd == 'get-post':
            res = api_call('GET', f'/{args.post_id}', token, {'fields': 'id,text,permalink,timestamp,media_type'}, dry_run=args.dry_run)
        elif args.cmd == 'insights':
            res = api_call('GET', f'/{args.post_id}/insights', token, {'metric': 'views,likes,replies,reposts,quotes'}, dry_run=args.dry_run)
        elif args.cmd == 'list-replies':
            res = api_call('GET', f'/{args.post_id}/replies', token, {'fields': 'id,text,username,timestamp,hide_status'}, dry_run=args.dry_run)
        else:
            res = api_call('POST', f'/{args.reply_id}/manage_reply', token, {'hide': args.hide}, dry_run=args.dry_run)
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
