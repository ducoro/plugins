#!/usr/bin/env python3
"""Zero-dependency Python 3 reference client for Meta Threads API."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://graph.threads.net/v1.0'
FRONT_JSON_RE = re.compile(r'^\s*```json\s*\n(.*?)\n```\s*\n?(.*)$', re.S)


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


def parse_threads_variant(variant_path: Path) -> tuple[list[str], str | None, str | None, str | None]:
    """Parse a threads variant markdown/json file into ordered post parts, optional firstReply, topic_tag, and reply_control."""
    if not variant_path.is_file():
        raise RuntimeError(f'Variant file not found: {variant_path}')
    raw = variant_path.read_text(encoding='utf-8')
    if variant_path.suffix.lower() == '.json':
        meta = json.loads(raw)
        body = str(meta.get('body', '') or '')
    else:
        m = FRONT_JSON_RE.match(raw)
        if not m:
            raise RuntimeError(f'Variant {variant_path} must start with a ```json metadata fence')
        meta = json.loads(m.group(1))
        body = m.group(2).strip()
    norm_body = body.replace('\r\n', '\n').replace('\r', '\n')
    if isinstance(meta.get('threads'), list) and meta['threads']:
        parts = [str(p).strip() for p in meta['threads'] if str(p).strip()]
    elif re.search(r'\n---\s*\n', norm_body):
        parts = [p.strip() for p in re.split(r'\n---\s*\n', norm_body) if p.strip()]
    else:
        parts = [norm_body.strip()] if norm_body.strip() else []
    options = meta.get('options') or {}
    topics = meta.get('topics') or []
    topic_tag = str(options.get('topic_tag') or (topics[0] if topics else '') or '').strip() or None
    reply_control = str(options.get('reply_control') or '').strip() or None
    first_reply = str(options.get('firstReply') or '').strip() or None
    if not parts:
        raise RuntimeError(f'Variant {variant_path} contains no post text')
    return parts, first_reply, topic_tag, reply_control


def post_thread_chain(
    parts: list[str],
    uid: str,
    token: str,
    *,
    first_reply: str | None = None,
    topic_tag: str | None = None,
    reply_control: str | None = None,
    resume_reply_to: str | None = None,
    dry_run: bool = False,
) -> tuple[dict, bool]:
    """Publish a multi-post Threads chain (create-container -> publish per item) with partial-failure recovery."""
    chain: list[tuple[str, str]] = [('post', p.strip()) for p in parts if p.strip()]
    if first_reply and first_reply.strip():
        chain.append(('firstReply', first_reply.strip()))
    if not chain:
        raise RuntimeError('post-thread requires at least one non-empty post')

    if dry_run:
        steps = []
        prev_id = resume_reply_to
        for idx, (kind, text) in enumerate(chain):
            params: dict = {'media_type': 'TEXT', 'text': text}
            if idx == 0 and not resume_reply_to and topic_tag:
                params['topic_tag'] = topic_tag
            if reply_control:
                params['reply_control'] = reply_control
            if prev_id:
                params['reply_to_id'] = prev_id
            steps.append({
                'index': idx,
                'kind': kind,
                'create': api_call('POST', f'/{uid}/threads', token, params, dry_run=True),
                'publish': api_call('POST', f'/{uid}/threads_publish', token, {'creation_id': f'<container_id_{idx}>'}, dry_run=True),
            })
            prev_id = f'<post_id_{idx}>'
        return {'dryRun': True, 'totalSteps': len(steps), 'steps': steps}, True

    published: list[dict] = []
    prev_id = resume_reply_to
    for idx, (kind, text) in enumerate(chain):
        params = {'media_type': 'TEXT', 'text': text}
        if idx == 0 and not resume_reply_to and topic_tag:
            params['topic_tag'] = topic_tag
        if reply_control:
            params['reply_control'] = reply_control
        if prev_id:
            params['reply_to_id'] = prev_id
        try:
            c_res = api_call('POST', f'/{uid}/threads', token, params, dry_run=False)
            cid = str(c_res.get('id') or '')
            if not cid:
                raise RuntimeError(f'Threads create-container missing id: {json.dumps(c_res)}')
            p_res = api_call('POST', f'/{uid}/threads_publish', token, {'creation_id': cid}, dry_run=False)
            pid = str(p_res.get('id') or '')
            if not pid:
                raise RuntimeError(f'Threads publish missing id: {json.dumps(p_res)}')
        except Exception as exc:
            return {
                'ok': False,
                'partial': len(published) > 0,
                'failedAtIndex': idx,
                'failedKind': kind,
                'error': str(exc),
                'resumeReplyTo': prev_id,
                'publishedPosts': published,
            }, False
        published.append({'index': idx, 'kind': kind, 'containerId': cid, 'postId': pid})
        prev_id = pid

    return {
        'ok': True,
        'rootPostId': published[0]['postId'],
        'publishedPosts': published,
    }, True


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

    p_th = sub.add_parser('post-thread', help='Publish a multi-post Threads chain and optional firstReply sequentially.')
    p_th.add_argument('--variant', default=None, help='Path to variants/threads.md (or .json) to parse thread parts and options.')
    p_th.add_argument('--parts', nargs='+', default=None, help='Ordered post texts (alternative to --variant).')
    p_th.add_argument('--first-reply', default=None, help='Optional follow-up reply (overrides variant options.firstReply).')
    p_th.add_argument('--topic-tag', default=None, help='Optional native topic_tag on the root post.')
    p_th.add_argument('--reply-control', choices=['everyone', 'accounts_you_follow', 'mentioned_only'], default=None)
    p_th.add_argument('--resume-reply-to', default=None, help='Resume chaining from an already-published Threads post ID.')

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
    exit_code = 0
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
        elif args.cmd == 'post-thread':
            if args.variant:
                parts, var_fr, var_tag, var_rc = parse_threads_variant(Path(args.variant))
                first_reply = args.first_reply if args.first_reply is not None else var_fr
                topic_tag = args.topic_tag if args.topic_tag is not None else var_tag
                reply_control = args.reply_control if args.reply_control is not None else var_rc
            elif args.parts:
                parts = list(args.parts)
                first_reply = args.first_reply
                topic_tag = args.topic_tag
                reply_control = args.reply_control
            else:
                raise RuntimeError('post-thread requires --variant or --parts')
            res, ok = post_thread_chain(
                parts,
                uid,
                token,
                first_reply=first_reply,
                topic_tag=topic_tag,
                reply_control=reply_control,
                resume_reply_to=args.resume_reply_to,
                dry_run=args.dry_run,
            )
            if not ok:
                exit_code = 1
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
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
