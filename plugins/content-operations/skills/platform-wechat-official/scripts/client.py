#!/usr/bin/env python3
"""Zero-dependency Python 3 reference client for WeChat Official Account API."""
import argparse
import json
import mimetypes
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = 'https://api.weixin.qq.com'


def require_env(name: str) -> str:
    val = os.environ.get(name, '').strip()
    if not val:
        raise RuntimeError(f'Missing required environment variable: {name}')
    return val


def check_wechat_error(out: dict) -> None:
    errcode = out.get('errcode')
    if errcode not in (0, None):
        raise RuntimeError(f'WeChat API error (errcode={errcode}): {json.dumps(out, ensure_ascii=False)}')


def api_post(path: str, token: str | None, body: dict, dry_run: bool = False) -> dict:
    if dry_run:
        suffix = '?access_token=<redacted>' if token is not None else ''
        safe_body = {k: ('<redacted>' if 'secret' in k.lower() else v) for k, v in body.items()}
        return {'dryRun': True, 'method': 'POST', 'url': f'{BASE}{path}{suffix}', 'body': safe_body}
    url = f'{BASE}{path}?{urllib.parse.urlencode({"access_token": token})}' if token is not None else f'{BASE}{path}'
    req = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json; charset=utf-8'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            text = resp.read().decode('utf-8').strip()
            out = json.loads(text) if text else {'ok': True}
    except urllib.error.HTTPError as err:
        raise RuntimeError(f'HTTP {err.code}: {err.read().decode("utf-8", errors="replace")}') from err
    if isinstance(out, dict):
        check_wechat_error(out)
    return out


def api_upload_multipart(path: str, token: str, file_path: Path, query: dict | None = None, dry_run: bool = False) -> dict:
    if not file_path.is_file():
        raise RuntimeError(f'Image file not found: {file_path}')
    q = {**(query or {}), 'access_token': token}
    if dry_run:
        safe_q = {k: ('<redacted>' if k == 'access_token' else v) for k, v in q.items()}
        return {'dryRun': True, 'method': 'POST', 'url': f'{BASE}{path}', 'query': safe_q, 'file': file_path.name, 'sizeBytes': file_path.stat().st_size}
    raw = file_path.read_bytes()
    mime = mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream'
    boundary = f'----ducoroWx{uuid.uuid4().hex}'
    payload = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="media"; filename="{file_path.name}"\r\n'
        f'Content-Type: {mime}\r\n\r\n'.encode('utf-8')
        + raw
        + f'\r\n--{boundary}--\r\n'.encode('utf-8')
    )
    url = f'{BASE}{path}?{urllib.parse.urlencode(q)}'
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            text = resp.read().decode('utf-8').strip()
            out = json.loads(text) if text else {'ok': True}
    except urllib.error.HTTPError as err:
        raise RuntimeError(f'HTTP {err.code}: {err.read().decode("utf-8", errors="replace")}') from err
    if isinstance(out, dict):
        check_wechat_error(out)
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='WeChat Official Account API reference client.')
    parser.add_argument('--dry-run', action='store_true', help='Preview HTTP call without sending.')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_tok = sub.add_parser('get-token', help='Fetch a fresh 2h stable_token using WECHAT_OFFICIAL_APP_ID & APP_SECRET.')
    p_tok.add_argument('--force-refresh', action='store_true', help='Force rotation of the current token.')

    p_img = sub.add_parser('upload-image', help='Upload an inline article image (returns WeChat CDN url).')
    p_img.add_argument('--file', required=True)

    p_thumb = sub.add_parser('upload-thumb', help='Upload a permanent cover image material (returns thumb_media_id).')
    p_thumb.add_argument('--file', required=True)

    p_draft = sub.add_parser('add-draft', help='Create an Official Account draft article.')
    p_draft.add_argument('--title', required=True)
    p_draft.add_argument('--content-file', required=True, help='Path to HTML body file.')
    p_draft.add_argument('--thumb-media-id', required=True)
    p_draft.add_argument('--author', default='')
    p_draft.add_argument('--digest', default='')
    p_draft.add_argument('--source-url', default='')
    p_draft.add_argument('--open-comment', type=int, choices=[0, 1], default=1)
    p_draft.add_argument('--only-fans-comment', type=int, choices=[0, 1], default=0)

    p_pub = sub.add_parser('submit-publish', help='Submit a draft media_id via freepublish.')
    p_pub.add_argument('--media-id', required=True)

    p_stat = sub.add_parser('poll-publish', help='Poll freepublish status by publish_id.')
    p_stat.add_argument('--publish-id', required=True)

    p_read = sub.add_parser('user-read', help='Fetch aggregate read stats (YYYY-MM-DD, <=3 day range).')
    p_read.add_argument('--begin-date', required=True)
    p_read.add_argument('--end-date', required=True)

    p_cum = sub.add_parser('user-cumulate', help='Fetch follower cumulate stats (YYYY-MM-DD, <=7 day range).')
    p_cum.add_argument('--begin-date', required=True)
    p_cum.add_argument('--end-date', required=True)

    p_art = sub.add_parser('article-total', help='Fetch per-article cumulative stats (YYYY-MM-DD, 1-day range).')
    p_art.add_argument('--begin-date', required=True)
    p_art.add_argument('--end-date', required=True)

    args = parser.parse_args(argv)
    try:
        if args.cmd == 'get-token':
            app_id = 'DRY_RUN_APP_ID' if args.dry_run else require_env('WECHAT_OFFICIAL_APP_ID')
            app_secret = 'DRY_RUN_SECRET' if args.dry_run else require_env('WECHAT_OFFICIAL_APP_SECRET')
            res = api_post(
                '/cgi-bin/stable_token',
                None,
                {'grant_type': 'client_credential', 'appid': app_id, 'secret': app_secret, 'force_refresh': args.force_refresh},
                dry_run=args.dry_run,
            )
        else:
            token = 'DRY_RUN_TOKEN' if args.dry_run else require_env('WECHAT_OFFICIAL_ACCESS_TOKEN')
            if args.cmd == 'upload-image':
                res = api_upload_multipart('/cgi-bin/media/uploadimg', token, Path(args.file), dry_run=args.dry_run)
            elif args.cmd == 'upload-thumb':
                res = api_upload_multipart('/cgi-bin/material/add_material', token, Path(args.file), {'type': 'image'}, dry_run=args.dry_run)
            elif args.cmd == 'add-draft':
                with open(args.content_file, encoding='utf-8') as fh:
                    html = fh.read()
                body = {
                    'articles': [{
                        'title': args.title,
                        'author': args.author,
                        'digest': args.digest,
                        'content': html,
                        'content_source_url': args.source_url,
                        'thumb_media_id': args.thumb_media_id,
                        'need_open_comment': args.open_comment,
                        'only_fans_can_comment': args.only_fans_comment,
                    }]
                }
                res = api_post('/cgi-bin/draft/add', token, body, dry_run=args.dry_run)
            elif args.cmd == 'submit-publish':
                res = api_post('/cgi-bin/freepublish/submit', token, {'media_id': args.media_id}, dry_run=args.dry_run)
            elif args.cmd == 'poll-publish':
                res = api_post('/cgi-bin/freepublish/get', token, {'publish_id': args.publish_id}, dry_run=args.dry_run)
            elif args.cmd == 'user-read':
                res = api_post('/datacube/getuserread', token, {'begin_date': args.begin_date, 'end_date': args.end_date}, dry_run=args.dry_run)
            elif args.cmd == 'user-cumulate':
                res = api_post('/datacube/getusercumulate', token, {'begin_date': args.begin_date, 'end_date': args.end_date}, dry_run=args.dry_run)
            else:
                res = api_post('/datacube/getarticletotal', token, {'begin_date': args.begin_date, 'end_date': args.end_date}, dry_run=args.dry_run)
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
