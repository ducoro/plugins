#!/usr/bin/env python3
"""Zero-dependency Python 3 reference client for YouTube Data API v3."""
import argparse
import json
import mimetypes
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://www.googleapis.com/youtube/v3'
UPLOAD_BASE = 'https://www.googleapis.com/upload/youtube/v3'
OAUTH_TOKEN_URL = 'https://oauth2.googleapis.com/token'


def refresh_oauth_token(dry_run: bool = False) -> dict:
    client_id = 'DRY_RUN_CLIENT_ID' if dry_run else require_env('YOUTUBE_CLIENT_ID')
    client_secret = 'DRY_RUN_SECRET' if dry_run else require_env('YOUTUBE_CLIENT_SECRET')
    refresh_token = 'DRY_RUN_REFRESH_TOKEN' if dry_run else require_env('YOUTUBE_REFRESH_TOKEN')
    form = {
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
    }
    if dry_run:
        return {'dryRun': True, 'method': 'POST', 'url': OAUTH_TOKEN_URL, 'form': {**form, 'client_secret': '<redacted>', 'refresh_token': '<redacted>'}}
    req = urllib.request.Request(
        OAUTH_TOKEN_URL,
        data=urllib.parse.urlencode(form).encode('utf-8'),
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            text = resp.read().decode('utf-8').strip()
            return json.loads(text) if text else {'ok': True}
    except urllib.error.HTTPError as err:
        raise RuntimeError(f'HTTP {err.code}: {err.read().decode("utf-8", errors="replace")}') from err


def require_env(name: str) -> str:
    val = os.environ.get(name, '').strip()
    if not val:
        raise RuntimeError(f'Missing required environment variable: {name}')
    return val


def api_call(method: str, base: str, path: str, token: str, query: dict | None = None, body: dict | None = None, extra_headers: dict | None = None, dry_run: bool = False) -> dict:
    qs = urllib.parse.urlencode(query or {})
    url = f'{base}{path}?{qs}' if qs else f'{base}{path}'
    headers = {'Authorization': f'Bearer {token}', **(extra_headers or {})}
    if dry_run:
        redacted = {k: ('Bearer <redacted>' if k == 'Authorization' else v) for k, v in headers.items()}
        return {'dryRun': True, 'method': method, 'url': url, 'headers': redacted, 'body': body}
    data = json.dumps(body).encode('utf-8') if body is not None else None
    if data is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            text = resp.read().decode('utf-8').strip()
            out = json.loads(text) if text else {'ok': True}
            if 'Location' in resp.headers:
                out['uploadLocation'] = resp.headers['Location']
            return out
    except urllib.error.HTTPError as err:
        raise RuntimeError(f'HTTP {err.code}: {err.read().decode("utf-8", errors="replace")}') from err


def upload_binary(method: str, url: str, file_path: Path, token: str | None, content_type: str | None = None, dry_run: bool = False) -> dict:
    if not file_path.is_file():
        raise RuntimeError(f'File not found: {file_path}')
    raw = file_path.read_bytes()
    mime = content_type or mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream'
    headers = {'Content-Type': mime, 'Content-Length': str(len(raw))}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    if dry_run:
        redacted = {k: ('Bearer <redacted>' if k == 'Authorization' else v) for k, v in headers.items()}
        return {'dryRun': True, 'method': method, 'url': url, 'headers': redacted, 'file': file_path.name, 'sizeBytes': len(raw)}
    req = urllib.request.Request(url, data=raw, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            text = resp.read().decode('utf-8').strip()
            return json.loads(text) if text else {'ok': True}
    except urllib.error.HTTPError as err:
        raise RuntimeError(f'HTTP {err.code}: {err.read().decode("utf-8", errors="replace")}') from err


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='YouTube Data API v3 reference client.')
    parser.add_argument('--dry-run', action='store_true', help='Preview request without network I/O.')
    sub = parser.add_subparsers(dest='cmd', required=True)

    sub.add_parser('refresh-token', help='Exchange YOUTUBE_CLIENT_ID/SECRET/REFRESH_TOKEN for a fresh 1h access token.')

    p_cat = sub.add_parser('list-categories', help='List YouTube video category IDs.')
    p_cat.add_argument('--region', default='US')

    p_init = sub.add_parser('init-upload', help='Initialize a resumable video upload session.')
    p_init.add_argument('--title', required=True)
    p_init.add_argument('--description', default='')
    p_init.add_argument('--category-id', default='22')
    p_init.add_argument('--privacy', choices=['public', 'unlisted', 'private'], default='private')
    p_init.add_argument('--publish-at', default=None, help='ISO-8601 datetime (requires --privacy private).')
    p_init.add_argument('--tags', nargs='*', default=[])
    p_init.add_argument('--made-for-kids', action='store_true')
    p_init.add_argument('--content-type', default='video/mp4', help='Declared X-Upload-Content-Type.')
    p_init.add_argument('--content-length', type=int, default=None, help='Optional X-Upload-Content-Length in bytes.')

    p_put = sub.add_parser('upload-video', help='PUT binary video bytes to the uploadLocation returned by init-upload.')
    p_put.add_argument('--upload-url', required=True)
    p_put.add_argument('--file', required=True)
    p_put.add_argument('--content-type', default='video/mp4')

    p_thumb = sub.add_parser('set-thumbnail', help='Upload a custom thumbnail image (<2 MB) for a video.')
    p_thumb.add_argument('--video-id', required=True)
    p_thumb.add_argument('--file', required=True)

    p_stat = sub.add_parser('video-stats', help='Fetch live video snippet, status, and statistics.')
    p_stat.add_argument('--video-id', required=True)

    p_cmts = sub.add_parser('list-comments', help='List top-level comment threads on a video.')
    p_cmts.add_argument('--video-id', required=True)
    p_cmts.add_argument('--max-results', type=int, default=25)

    p_rep = sub.add_parser('reply-comment', help='Reply to a YouTube comment thread.')
    p_rep.add_argument('--parent-id', required=True)
    p_rep.add_argument('--text', required=True)

    args = parser.parse_args(argv)
    try:
        if args.cmd == 'refresh-token':
            res = refresh_oauth_token(dry_run=args.dry_run)
        else:
            token = 'DRY_RUN_TOKEN' if args.dry_run else require_env('YOUTUBE_ACCESS_TOKEN')
            if args.cmd == 'list-categories':
                res = api_call('GET', BASE, '/videoCategories', token, {'part': 'snippet', 'regionCode': args.region}, dry_run=args.dry_run)
            elif args.cmd == 'init-upload':
                if args.publish_at and args.privacy != 'private':
                    raise ValueError('publishAt requires --privacy private')
                status_obj: dict = {'privacyStatus': args.privacy, 'selfDeclaredMadeForKids': args.made_for_kids}
                if args.publish_at:
                    status_obj['publishAt'] = args.publish_at
                body = {
                    'snippet': {'title': args.title, 'description': args.description, 'tags': args.tags, 'categoryId': args.category_id},
                    'status': status_obj,
                }
                extra = {'X-Upload-Content-Type': args.content_type}
                if args.content_length is not None:
                    extra['X-Upload-Content-Length'] = str(args.content_length)
                res = api_call('POST', UPLOAD_BASE, '/videos', token, {'uploadType': 'resumable', 'part': 'snippet,status'}, body=body, extra_headers=extra, dry_run=args.dry_run)
            elif args.cmd == 'upload-video':
                res = upload_binary('PUT', args.upload_url, Path(args.file), token, content_type=args.content_type, dry_run=args.dry_run)
            elif args.cmd == 'set-thumbnail':
                url = f'{UPLOAD_BASE}/thumbnails/set?{urllib.parse.urlencode({"videoId": args.video_id, "uploadType": "media"})}'
                res = upload_binary('POST', url, Path(args.file), token, dry_run=args.dry_run)
            elif args.cmd == 'video-stats':
                res = api_call('GET', BASE, '/videos', token, {'part': 'snippet,statistics,status', 'id': args.video_id}, dry_run=args.dry_run)
            elif args.cmd == 'list-comments':
                res = api_call('GET', BASE, '/commentThreads', token, {'part': 'snippet,replies', 'videoId': args.video_id, 'maxResults': args.max_results}, dry_run=args.dry_run)
            else:
                res = api_call('POST', BASE, '/comments', token, {'part': 'snippet'}, body={'snippet': {'parentId': args.parent_id, 'textOriginal': args.text}}, dry_run=args.dry_run)
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
