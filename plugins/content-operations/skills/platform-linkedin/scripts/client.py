#!/usr/bin/env python3
"""Zero-dependency Python 3 reference client for LinkedIn REST API."""
import argparse
import json
import mimetypes
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

REST_BASE = 'https://api.linkedin.com/rest'
V2_BASE = 'https://api.linkedin.com/v2'
API_VERSION = os.environ.get('LINKEDIN_API_VERSION', '202601').strip() or '202601'


def require_env(name: str) -> str:
    val = os.environ.get(name, '').strip()
    if not val:
        raise RuntimeError(f'Missing required environment variable: {name}')
    return val


def api_call(method: str, url: str, token: str, body: dict | None = None, dry_run: bool = False) -> dict:
    headers = {
        'Authorization': f'Bearer {token}',
        'LinkedIn-Version': API_VERSION,
        'X-Restli-Protocol-Version': '2.0.0',
    }
    if dry_run:
        return {'dryRun': True, 'method': method, 'url': url, 'headers': {**headers, 'Authorization': 'Bearer <redacted>'}, 'body': body}
    data = json.dumps(body).encode('utf-8') if body is not None else None
    if data is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            text = resp.read().decode('utf-8').strip()
            out = json.loads(text) if text else {'ok': True}
            if 'x-restli-id' in resp.headers:
                out['postUrn'] = resp.headers['x-restli-id']
            return out
    except urllib.error.HTTPError as err:
        raise RuntimeError(f'HTTP {err.code}: {err.read().decode("utf-8", errors="replace")}') from err


def upload_image(file_path: Path, author_urn: str, token: str, dry_run: bool = False) -> dict:
    if not file_path.is_file():
        raise RuntimeError(f'Image file not found: {file_path}')
    raw = file_path.read_bytes()
    mime = mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream'
    init_body = {'initializeUploadRequest': {'owner': author_urn}}
    if dry_run:
        return {
            'dryRun': True,
            'steps': [
                {'method': 'POST', 'url': f'{REST_BASE}/images?action=initializeUpload', 'body': init_body},
                {'method': 'PUT', 'url': '<returned uploadUrl>', 'contentType': mime, 'file': file_path.name, 'sizeBytes': len(raw)},
            ],
        }
    init_res = api_call('POST', f'{REST_BASE}/images?action=initializeUpload', token, body=init_body)
    val = init_res.get('value') or {}
    upload_url = val.get('uploadUrl')
    image_urn = val.get('image')
    if not upload_url or not image_urn:
        raise RuntimeError(f'LinkedIn initializeUpload missing uploadUrl/image: {json.dumps(init_res)}')
    req = urllib.request.Request(
        upload_url,
        data=raw,
        headers={'Authorization': f'Bearer {token}', 'Content-Type': mime},
        method='PUT',
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp.read()
    except urllib.error.HTTPError as err:
        raise RuntimeError(f'HTTP {err.code} uploading LinkedIn image: {err.read().decode("utf-8", errors="replace")}') from err
    return {'imageUrn': image_urn}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='LinkedIn REST API reference client.')
    parser.add_argument('--dry-run', action='store_true', help='Preview HTTP call without sending.')
    sub = parser.add_subparsers(dest='cmd', required=True)

    sub.add_parser('userinfo', help='Fetch OpenID profile info.')

    p_img = sub.add_parser('upload-image', help='Upload a local image via initializeUpload + PUT and return imageUrn.')
    p_img.add_argument('--file', required=True)

    p_post = sub.add_parser('post', help='Publish a text or single-image post to LinkedIn.')
    p_post.add_argument('--text', required=True)
    p_post.add_argument('--visibility', choices=['PUBLIC', 'CONNECTIONS'], default='PUBLIC')
    p_post.add_argument('--image-urn', default=None, help='Optional image URN returned by upload-image.')
    p_post.add_argument('--alt-text', default='', help='Optional alt text for --image-urn.')

    p_cmts = sub.add_parser('list-comments', help='List comments on a post URN.')
    p_cmts.add_argument('--post-urn', required=True)

    p_rep = sub.add_parser('comment', help='Post a comment on a post URN.')
    p_rep.add_argument('--post-urn', required=True)
    p_rep.add_argument('--text', required=True)

    args = parser.parse_args(argv)
    try:
        token = 'DRY_RUN_TOKEN' if args.dry_run else require_env('LINKEDIN_ACCESS_TOKEN')
        if args.cmd == 'userinfo':
            res = api_call('GET', f'{V2_BASE}/userinfo', token, dry_run=args.dry_run)
        elif args.cmd == 'upload-image':
            author = 'urn:li:person:DRY_RUN' if args.dry_run else require_env('LINKEDIN_AUTHOR_URN')
            res = upload_image(Path(args.file), author, token, dry_run=args.dry_run)
        elif args.cmd == 'post':
            author = 'urn:li:person:DRY_RUN' if args.dry_run else require_env('LINKEDIN_AUTHOR_URN')
            body: dict = {
                'author': author,
                'commentary': args.text,
                'visibility': args.visibility,
                'distribution': {'feedDistribution': 'MAIN_FEED'},
                'lifecycleState': 'PUBLISHED',
                'isReshareDisabledByAuthor': False,
            }
            if args.image_urn:
                media_obj: dict = {'id': args.image_urn}
                if args.alt_text:
                    media_obj['altText'] = args.alt_text
                body['content'] = {'media': media_obj}
            res = api_call('POST', f'{REST_BASE}/posts', token, body=body, dry_run=args.dry_run)
        elif args.cmd == 'list-comments':
            enc = urllib.parse.quote(args.post_urn, safe='')
            res = api_call('GET', f'{REST_BASE}/socialActions/{enc}/comments', token, dry_run=args.dry_run)
        else:
            author = 'urn:li:person:DRY_RUN' if args.dry_run else require_env('LINKEDIN_AUTHOR_URN')
            enc = urllib.parse.quote(args.post_urn, safe='')
            res = api_call(
                'POST',
                f'{REST_BASE}/socialActions/{enc}/comments',
                token,
                body={'actor': author, 'object': args.post_urn, 'message': {'text': args.text}},
                dry_run=args.dry_run,
            )
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
