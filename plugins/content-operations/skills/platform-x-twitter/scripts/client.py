#!/usr/bin/env python3
"""Zero-dependency Python 3 reference client for X (Twitter) API v2."""
import argparse
import base64
import json
import mimetypes
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = 'https://api.x.com'
FRONT_JSON_RE = re.compile(r'^\s*```json\s*\n(.*?)\n```\s*\n?(.*)$', re.S)


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
        with urllib.request.urlopen(req, timeout=20) as resp:
            text = resp.read().decode('utf-8').strip()
            return json.loads(text) if text else {'ok': True}
    except urllib.error.HTTPError as err:
        raise RuntimeError(f'HTTP {err.code}: {err.read().decode("utf-8", errors="replace")}') from err


def encode_multipart(fields: dict[str, str], file_field: str, filename: str, content_type: str, file_bytes: bytes) -> tuple[bytes, str]:
    boundary = f'----ducoroX{uuid.uuid4().hex}'
    parts: list[bytes] = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode('utf-8'))
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
        f'Content-Type: {content_type}\r\n\r\n'.encode('utf-8') + file_bytes + b'\r\n'
    )
    parts.append(f'--{boundary}--\r\n'.encode('utf-8'))
    return b''.join(parts), f'multipart/form-data; boundary={boundary}'


def upload_media_v2(file_path: Path, media_category: str, token: str, dry_run: bool = False) -> dict:
    if not file_path.is_file():
        raise RuntimeError(f'Media file not found: {file_path}')
    raw = file_path.read_bytes()
    mime = mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream'
    init_body = {'total_bytes': len(raw), 'media_type': mime, 'media_category': media_category}
    if dry_run:
        return {
            'dryRun': True,
            'steps': [
                {'method': 'POST', 'url': f'{BASE}/2/media/upload/initialize', 'body': init_body},
                {'method': 'POST', 'url': f'{BASE}/2/media/upload/<media_id>/append', 'fields': {'segment_index': '0'}, 'file': file_path.name, 'sizeBytes': len(raw)},
                {'method': 'POST', 'url': f'{BASE}/2/media/upload/<media_id>/finalize'},
            ],
        }
    init_res = api_call('POST', '/2/media/upload/initialize', token, body=init_body)
    media_id = (init_res.get('data') or {}).get('id') or init_res.get('id')
    if not media_id:
        raise RuntimeError(f'X media initialize did not return media id: {json.dumps(init_res)}')

    chunk_size = 4 * 1024 * 1024
    for seg_idx, offset in enumerate(range(0, len(raw), chunk_size)):
        chunk = raw[offset:offset + chunk_size]
        payload, ctype = encode_multipart({'segment_index': str(seg_idx)}, 'media', file_path.name, mime, chunk)
        req = urllib.request.Request(
            f'{BASE}/2/media/upload/{media_id}/append',
            data=payload,
            headers={'Authorization': f'Bearer {token}', 'Content-Type': ctype},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp.read()
        except urllib.error.HTTPError as err:
            raise RuntimeError(f'HTTP {err.code} on append: {err.read().decode("utf-8", errors="replace")}') from err

    fin_res = api_call('POST', f'/2/media/upload/{media_id}/finalize', token, body={})
    return {'media_id': str(media_id), 'finalize': fin_res}


def refresh_oauth_token(dry_run: bool = False) -> dict:
    client_id = 'DRY_RUN_CLIENT_ID' if dry_run else require_env('X_CLIENT_ID')
    refresh_token = 'DRY_RUN_REFRESH_TOKEN' if dry_run else require_env('X_REFRESH_TOKEN')
    client_secret = os.environ.get('X_CLIENT_SECRET', '').strip()
    form = {'grant_type': 'refresh_token', 'refresh_token': refresh_token, 'client_id': client_id}
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    if client_secret:
        basic = base64.b64encode(f'{client_id}:{client_secret}'.encode('utf-8')).decode('ascii')
        headers['Authorization'] = f'Basic {basic}'
    url = f'{BASE}/2/oauth2/token'
    if dry_run:
        safe_h = {k: ('Basic <redacted>' if k == 'Authorization' else v) for k, v in headers.items()}
        safe_f = {**form, 'refresh_token': '<redacted>'}
        return {'dryRun': True, 'method': 'POST', 'url': url, 'headers': safe_h, 'form': safe_f}
    req = urllib.request.Request(url, data=urllib.parse.urlencode(form).encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            text = resp.read().decode('utf-8').strip()
            return json.loads(text) if text else {'ok': True}
    except urllib.error.HTTPError as err:
        raise RuntimeError(f'HTTP {err.code}: {err.read().decode("utf-8", errors="replace")}') from err


def parse_x_variant(variant_path: Path) -> tuple[list[str], str | None]:
    """Parse an x-twitter variant markdown/json file into ordered tweet parts and optional firstReply."""
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
    first_reply = str(options.get('firstReply') or '').strip() or None
    if not parts:
        raise RuntimeError(f'Variant {variant_path} contains no post text')
    return parts, first_reply


def post_thread_chain(
    parts: list[str],
    token: str,
    *,
    first_reply: str | None = None,
    media_ids: list[str] | None = None,
    resume_reply_to: str | None = None,
    dry_run: bool = False,
) -> tuple[dict, bool]:
    """Publish a root post + thread items + optional firstReply sequentially, preserving partial state on failure."""
    chain: list[tuple[str, str]] = [('post', p.strip()) for p in parts if p.strip()]
    if first_reply and first_reply.strip():
        chain.append(('firstReply', first_reply.strip()))
    if not chain:
        raise RuntimeError('post-thread requires at least one non-empty post')

    if dry_run:
        steps = []
        prev_placeholder = resume_reply_to
        for idx, (kind, text) in enumerate(chain):
            body: dict = {'text': text}
            if prev_placeholder:
                body['reply'] = {'in_reply_to_tweet_id': prev_placeholder}
            if idx == 0 and media_ids:
                body['media'] = {'media_ids': media_ids}
            steps.append({
                'index': idx,
                'kind': kind,
                'request': api_call('POST', '/2/tweets', token, body=body, dry_run=True),
            })
            prev_placeholder = f'<tweet_id_{idx}>'
        return {'dryRun': True, 'totalSteps': len(steps), 'steps': steps}, True

    published: list[dict] = []
    prev_id = resume_reply_to
    for idx, (kind, text) in enumerate(chain):
        body = {'text': text}
        if prev_id:
            body['reply'] = {'in_reply_to_tweet_id': prev_id}
        if idx == 0 and media_ids:
            body['media'] = {'media_ids': media_ids}
        try:
            res = api_call('POST', '/2/tweets', token, body=body, dry_run=False)
        except Exception as exc:
            return {
                'ok': False,
                'partial': len(published) > 0,
                'failedAtIndex': idx,
                'failedKind': kind,
                'error': str(exc),
                'resumeReplyTo': prev_id,
                'publishedTweets': published,
            }, False
        tid = str((res.get('data') or {}).get('id') or res.get('id') or '')
        if not tid:
            return {
                'ok': False,
                'partial': len(published) > 0,
                'failedAtIndex': idx,
                'failedKind': kind,
                'error': f'X API did not return tweet id: {json.dumps(res)}',
                'resumeReplyTo': prev_id,
                'publishedTweets': published,
            }, False
        published.append({
            'index': idx,
            'kind': kind,
            'tweetId': tid,
            'publicUrl': f'https://x.com/i/status/{tid}',
        })
        prev_id = tid

    return {
        'ok': True,
        'rootTweetId': published[0]['tweetId'],
        'rootPublicUrl': published[0]['publicUrl'],
        'publishedTweets': published,
    }, True


def fetch_user_tweets(
    token: str,
    *,
    user_id: str | None = None,
    username: str | None = None,
    since_id: str | None = None,
    max_results: int = 10,
    exclude_replies: bool = False,
    exclude_retweets: bool = True,
    dry_run: bool = False,
) -> dict:
    """Fetch recent tweets for a user-approved benchmark account via official X API v2."""
    if not user_id and not username:
        raise RuntimeError('user-tweets requires --user-id or --username')
    clean_handle = (username or '').strip().lstrip('@')
    excludes = []
    if exclude_replies:
        excludes.append('replies')
    if exclude_retweets:
        excludes.append('retweets')
    q: dict = {
        'max_results': max(5, min(100, max_results)),
        'tweet.fields': 'created_at,public_metrics,conversation_id,lang',
    }
    if since_id:
        q['since_id'] = since_id
    if excludes:
        q['exclude'] = ','.join(excludes)

    if dry_run:
        steps = []
        uid = user_id or '<resolved_user_id>'
        if not user_id and clean_handle:
            steps.append(api_call('GET', f'/2/users/by/username/{clean_handle}', token, {'user.fields': 'public_metrics,description'}, dry_run=True))
        steps.append(api_call('GET', f'/2/users/{uid}/tweets', token, q, dry_run=True))
        return {'dryRun': True, 'steps': steps}

    resolved_user = None
    uid = user_id
    if not uid:
        u_res = api_call('GET', f'/2/users/by/username/{clean_handle}', token, {'user.fields': 'public_metrics,description'}, dry_run=False)
        resolved_user = u_res.get('data') or {}
        uid = str(resolved_user.get('id') or '')
        if not uid:
            raise RuntimeError(f'Could not resolve X user id for @{clean_handle}: {json.dumps(u_res)}')

    tweets_res = api_call('GET', f'/2/users/{uid}/tweets', token, q, dry_run=False)
    out = {'userId': uid, 'tweets': tweets_res.get('data') or [], 'meta': tweets_res.get('meta') or {}}
    if resolved_user:
        out['user'] = resolved_user
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='X API v2 reference client.')
    parser.add_argument('--dry-run', action='store_true', help='Preview HTTP call without sending.')
    sub = parser.add_subparsers(dest='cmd', required=True)

    sub.add_parser('me', help='Fetch authenticated user profile and public metrics.')
    sub.add_parser('refresh-token', help='Exchange X_REFRESH_TOKEN + X_CLIENT_ID (optional X_CLIENT_SECRET) for a fresh 2h access token.')

    p_up = sub.add_parser('upload-media', help='Upload a local image/GIF/video via X v2 chunked media upload.')
    p_up.add_argument('--file', required=True, help='Path to local media file.')
    p_up.add_argument('--media-category', choices=['tweet_image', 'tweet_gif', 'tweet_video'], default='tweet_image')

    p_post = sub.add_parser('post', help='Publish a tweet, reply, or quote tweet.')
    p_post.add_argument('--text', required=True)
    p_post.add_argument('--reply-to', default=None)
    p_post.add_argument('--quote-id', default=None)
    p_post.add_argument('--media-ids', nargs='*', default=None)

    p_thread = sub.add_parser('post-thread', help='Publish a multi-tweet thread and optional firstReply sequentially.')
    p_thread.add_argument('--variant', default=None, help='Path to variants/x-twitter.md (or .json) to parse thread parts and options.firstReply.')
    p_thread.add_argument('--parts', nargs='+', default=None, help='Ordered tweet texts (alternative to --variant).')
    p_thread.add_argument('--first-reply', default=None, help='Optional first reply text (e.g., outbound link or CTA); overrides variant options.firstReply.')
    p_thread.add_argument('--media-ids', nargs='*', default=None, help='Optional media IDs attached to the root post.')
    p_thread.add_argument('--resume-reply-to', default=None, help='Optional tweet ID to resume chaining from after a partial failure.')

    p_get = sub.add_parser('get-tweet', help='Read back a tweet and its public_metrics.')
    p_get.add_argument('--tweet-id', required=True)

    p_ut = sub.add_parser('user-tweets', help='Fetch recent tweets for an approved benchmark account (by --user-id or --username).')
    p_ut.add_argument('--user-id', default=None)
    p_ut.add_argument('--username', default=None)
    p_ut.add_argument('--since-id', default=None, help='Incremental cursor: only return tweets newer than this ID.')
    p_ut.add_argument('--max-results', type=int, default=10)
    p_ut.add_argument('--exclude-replies', action='store_true')
    p_ut.add_argument('--include-retweets', action='store_true')

    p_replies = sub.add_parser('list-replies', help='Search recent replies in a conversation_id.')
    p_replies.add_argument('--conversation-id', required=True)
    p_replies.add_argument('--max-results', type=int, default=20)

    p_act = sub.add_parser('engage', help='Like, repost, or bookmark a tweet.')
    p_act.add_argument('--action', choices=['like', 'repost', 'bookmark'], required=True)
    p_act.add_argument('--tweet-id', required=True)

    args = parser.parse_args(argv)
    exit_code = 0
    try:
        if args.cmd == 'refresh-token':
            res = refresh_oauth_token(dry_run=args.dry_run)
        else:
            token = 'DRY_RUN_TOKEN' if args.dry_run else require_env('X_ACCESS_TOKEN')
            if args.cmd == 'me':
                res = api_call('GET', '/2/users/me', token, {'user.fields': 'public_metrics,username'}, dry_run=args.dry_run)
            elif args.cmd == 'upload-media':
                res = upload_media_v2(Path(args.file), args.media_category, token, dry_run=args.dry_run)
            elif args.cmd == 'post':
                body: dict = {'text': args.text}
                if args.reply_to:
                    body['reply'] = {'in_reply_to_tweet_id': args.reply_to}
                if args.quote_id:
                    body['quote_tweet_id'] = args.quote_id
                if args.media_ids:
                    body['media'] = {'media_ids': args.media_ids}
                res = api_call('POST', '/2/tweets', token, body=body, dry_run=args.dry_run)
            elif args.cmd == 'post-thread':
                if args.variant:
                    parts, var_first_reply = parse_x_variant(Path(args.variant))
                    first_reply = args.first_reply if args.first_reply is not None else var_first_reply
                elif args.parts:
                    parts = list(args.parts)
                    first_reply = args.first_reply
                else:
                    raise RuntimeError('post-thread requires --variant or --parts')
                res, ok = post_thread_chain(
                    parts,
                    token,
                    first_reply=first_reply,
                    media_ids=args.media_ids,
                    resume_reply_to=args.resume_reply_to,
                    dry_run=args.dry_run,
                )
                if not ok:
                    exit_code = 1
            elif args.cmd == 'get-tweet':
                res = api_call('GET', f'/2/tweets/{args.tweet_id}', token, {'tweet.fields': 'public_metrics,created_at,conversation_id'}, dry_run=args.dry_run)
            elif args.cmd == 'user-tweets':
                res = fetch_user_tweets(
                    token,
                    user_id=args.user_id,
                    username=args.username,
                    since_id=args.since_id,
                    max_results=args.max_results,
                    exclude_replies=args.exclude_replies,
                    exclude_retweets=not args.include_retweets,
                    dry_run=args.dry_run,
                )
            elif args.cmd == 'list-replies':
                res = api_call(
                    'GET',
                    '/2/tweets/search/recent',
                    token,
                    {
                        'query': f'conversation_id:{args.conversation_id}',
                        'max_results': max(10, min(100, args.max_results)),
                        'tweet.fields': 'author_id,created_at,public_metrics',
                    },
                    dry_run=args.dry_run,
                )
            else:
                uid = 'DRY_RUN_UID' if args.dry_run else require_env('X_USER_ID')
                endpoint = {'like': 'likes', 'repost': 'retweets', 'bookmark': 'bookmarks'}[args.action]
                res = api_call('POST', f'/2/users/{uid}/{endpoint}', token, body={'tweet_id': args.tweet_id}, dry_run=args.dry_run)
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
