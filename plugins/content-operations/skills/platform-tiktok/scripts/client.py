#!/usr/bin/env python3
"""Zero-dependency Python 3 reference client for TikTok Open API v2."""
import argparse
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://open.tiktokapis.com/v2'


def require_env(name: str) -> str:
    val = os.environ.get(name, '').strip()
    if not val:
        raise RuntimeError(f'Missing required environment variable: {name}')
    return val


def check_tiktok_error(out: dict) -> None:
    err_obj = out.get('error')
    if isinstance(err_obj, dict):
        code = err_obj.get('code')
        if code not in ('ok', '', None):
            raise RuntimeError(f'TikTok API error ({code}): {json.dumps(out, ensure_ascii=False)}')


def api_call(method: str, path: str, token: str, query: dict | None = None, body: dict | None = None, dry_run: bool = False) -> dict:
    qs = urllib.parse.urlencode(query or {})
    url = f'{BASE}{path}?{qs}' if qs else f'{BASE}{path}'
    if dry_run:
        return {'dryRun': True, 'method': method, 'url': url, 'headers': {'Authorization': 'Bearer <redacted>'}, 'body': body}
    data = json.dumps(body).encode('utf-8') if body is not None else None
    headers = {'Authorization': f'Bearer {token}'}
    if data is not None:
        headers['Content-Type'] = 'application/json; charset=UTF-8'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            text = resp.read().decode('utf-8').strip()
            out = json.loads(text) if text else {'ok': True}
    except urllib.error.HTTPError as err:
        raise RuntimeError(f'HTTP {err.code}: {err.read().decode("utf-8", errors="replace")}') from err
    if isinstance(out, dict):
        check_tiktok_error(out)
    return out


def refresh_oauth_token(dry_run: bool = False) -> dict:
    client_key = 'DRY_RUN_KEY' if dry_run else require_env('TIKTOK_CLIENT_KEY')
    client_secret = 'DRY_RUN_SECRET' if dry_run else require_env('TIKTOK_CLIENT_SECRET')
    refresh_token = 'DRY_RUN_REFRESH_TOKEN' if dry_run else require_env('TIKTOK_REFRESH_TOKEN')
    form = {
        'client_key': client_key,
        'client_secret': client_secret,
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
    }
    url = f'{BASE}/oauth/token/'
    if dry_run:
        return {'dryRun': True, 'method': 'POST', 'url': url, 'form': {**form, 'client_secret': '<redacted>', 'refresh_token': '<redacted>'}}
    req = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(form).encode('utf-8'),
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            text = resp.read().decode('utf-8').strip()
            out = json.loads(text) if text else {'ok': True}
    except urllib.error.HTTPError as err:
        raise RuntimeError(f'HTTP {err.code}: {err.read().decode("utf-8", errors="replace")}') from err
    if isinstance(out, dict):
        if out.get('error') and not isinstance(out.get('error'), dict):
            raise RuntimeError(f'TikTok OAuth error: {json.dumps(out, ensure_ascii=False)}')
        check_tiktok_error(out)
    return out


def upload_video_file(upload_url: str, file_path: Path, content_type: str = 'video/mp4', dry_run: bool = False) -> dict:
    if not file_path.is_file():
        raise RuntimeError(f'Video file not found: {file_path}')
    raw = file_path.read_bytes()
    total = len(raw)
    if total == 0:
        raise RuntimeError(f'Video file is empty: {file_path}')
    headers = {
        'Content-Type': content_type,
        'Content-Length': str(total),
        'Content-Range': f'bytes 0-{total - 1}/{total}',
    }
    if dry_run:
        return {'dryRun': True, 'method': 'PUT', 'url': upload_url, 'headers': headers, 'file': file_path.name, 'sizeBytes': total}
    req = urllib.request.Request(upload_url, data=raw, headers=headers, method='PUT')
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            text = resp.read().decode('utf-8').strip()
            return json.loads(text) if text else {'ok': True, 'status': resp.status}
    except urllib.error.HTTPError as err:
        raise RuntimeError(f'HTTP {err.code}: {err.read().decode("utf-8", errors="replace")}') from err


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='TikTok API v2 reference client.')
    parser.add_argument('--dry-run', action='store_true', help='Preview HTTP request without sending.')
    sub = parser.add_subparsers(dest='cmd', required=True)

    sub.add_parser('refresh-token', help='Exchange TIKTOK_CLIENT_KEY/SECRET/REFRESH_TOKEN for a fresh 24h access token.')
    sub.add_parser('creator-info', help='Query allowed privacy levels and creator posting limits.')
    sub.add_parser('account-stats', help='Fetch creator profile and follower stats.')

    p_init = sub.add_parser('init-video-url', help='Initialize a PULL_FROM_URL video publish (verified domain required).')
    p_init.add_argument('--title', required=True)
    p_init.add_argument('--video-url', required=True)
    p_init.add_argument('--privacy', default='SELF_ONLY')
    p_init.add_argument('--aigc', action='store_true')

    p_finit = sub.add_parser('init-video-file', help='Initialize a direct local FILE_UPLOAD video publish session.')
    p_finit.add_argument('--title', required=True)
    p_finit.add_argument('--file', required=True, help='Path to local video file.')
    p_finit.add_argument('--privacy', default='SELF_ONLY')
    p_finit.add_argument('--aigc', action='store_true')

    p_fput = sub.add_parser('upload-video-file', help='PUT local video bytes to the upload_url returned by init-video-file.')
    p_fput.add_argument('--upload-url', required=True)
    p_fput.add_argument('--file', required=True)
    p_fput.add_argument('--content-type', default='video/mp4')

    p_status = sub.add_parser('publish-status', help='Poll publish status by publish_id.')
    p_status.add_argument('--publish-id', required=True)

    p_list = sub.add_parser('list-videos', help='List recent published videos with stats.')
    p_list.add_argument('--max-count', type=int, default=20)

    args = parser.parse_args(argv)
    try:
        if args.cmd == 'refresh-token':
            res = refresh_oauth_token(dry_run=args.dry_run)
        elif args.cmd == 'upload-video-file':
            res = upload_video_file(args.upload_url, Path(args.file), content_type=args.content_type, dry_run=args.dry_run)
        else:
            token = 'DRY_RUN_TOKEN' if args.dry_run else require_env('TIKTOK_ACCESS_TOKEN')
            if args.cmd == 'creator-info':
                res = api_call('POST', '/post/publish/creator_info/query/', token, body={}, dry_run=args.dry_run)
            elif args.cmd == 'account-stats':
                res = api_call('GET', '/user/info/', token, {'fields': 'open_id,username,display_name,follower_count,likes_count,video_count'}, dry_run=args.dry_run)
            elif args.cmd == 'init-video-url':
                body = {
                    'post_info': {'title': args.title, 'privacy_level': args.privacy, 'is_aigc': args.aigc},
                    'source_info': {'source': 'PULL_FROM_URL', 'video_url': args.video_url},
                }
                res = api_call('POST', '/post/publish/video/init/', token, body=body, dry_run=args.dry_run)
            elif args.cmd == 'init-video-file':
                fp = Path(args.file)
                if not fp.is_file():
                    raise RuntimeError(f'Video file not found: {fp}')
                size = fp.stat().st_size
                if size == 0:
                    raise RuntimeError(f'Video file is empty: {fp}')
                body = {
                    'post_info': {'title': args.title, 'privacy_level': args.privacy, 'is_aigc': args.aigc},
                    'source_info': {
                        'source': 'FILE_UPLOAD',
                        'video_size': size,
                        'chunk_size': size,
                        'total_chunk_count': 1,
                    },
                }
                res = api_call('POST', '/post/publish/video/init/', token, body=body, dry_run=args.dry_run)
            elif args.cmd == 'publish-status':
                res = api_call('POST', '/post/publish/status/fetch/', token, body={'publish_id': args.publish_id}, dry_run=args.dry_run)
            else:
                res = api_call(
                    'POST',
                    '/video/list/',
                    token,
                    {'fields': 'id,title,create_time,share_url,view_count,like_count,comment_count,share_count'},
                    body={'max_count': args.max_count},
                    dry_run=args.dry_run,
                )
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
