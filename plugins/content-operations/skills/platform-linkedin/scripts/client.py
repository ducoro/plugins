#!/usr/bin/env python3
"""Zero-dependency Python 3 reference client for LinkedIn REST API."""
import argparse
import json
import mimetypes
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

REST_BASE = 'https://api.linkedin.com/rest'
V2_BASE = 'https://api.linkedin.com/v2'
API_VERSION = os.environ.get('LINKEDIN_API_VERSION', '202601').strip() or '202601'
FRONT_JSON_RE = re.compile(r'^\s*```json\s*\n(.*?)\n```\s*\n?(.*)$', re.S)


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


def parse_linkedin_variant(variant_path: Path) -> tuple[str, str | None]:
    """Parse a linkedin variant markdown/json file into main commentary and optional firstReply."""
    if not variant_path.is_file():
        raise RuntimeError(f'Variant file not found: {variant_path}')
    raw = variant_path.read_text(encoding='utf-8')
    if variant_path.suffix.lower() == '.json':
        meta = json.loads(raw)
        body = str(meta.get('body', '') or '').strip()
    else:
        m = FRONT_JSON_RE.match(raw)
        if not m:
            raise RuntimeError(f'Variant {variant_path} must start with a ```json metadata fence')
        meta = json.loads(m.group(1))
        body = m.group(2).strip()
    options = meta.get('options') or {}
    first_reply = str(options.get('firstReply') or '').strip() or None
    if not body:
        raise RuntimeError(f'Variant {variant_path} contains no post commentary')
    return body, first_reply


def post_with_first_reply(
    text: str,
    author_urn: str,
    token: str,
    *,
    first_reply: str | None = None,
    visibility: str = 'PUBLIC',
    image_urn: str | None = None,
    alt_text: str = '',
    resume_post_urn: str | None = None,
    dry_run: bool = False,
) -> tuple[dict, bool]:
    """Publish a LinkedIn post and optionally attach options.firstReply as the first comment, preserving postUrn on partial failure."""
    post_body: dict = {
        'author': author_urn,
        'commentary': text,
        'visibility': visibility,
        'distribution': {'feedDistribution': 'MAIN_FEED'},
        'lifecycleState': 'PUBLISHED',
        'isReshareDisabledByAuthor': False,
    }
    if image_urn:
        media_obj: dict = {'id': image_urn}
        if alt_text:
            media_obj['altText'] = alt_text
        post_body['content'] = {'media': media_obj}

    fr_clean = (first_reply or '').strip() or None
    if dry_run:
        steps = []
        target_urn = resume_post_urn or '<returned_post_urn>'
        if not resume_post_urn:
            steps.append({'kind': 'post', 'request': api_call('POST', f'{REST_BASE}/posts', token, body=post_body, dry_run=True)})
        if fr_clean:
            enc = urllib.parse.quote(target_urn, safe='')
            steps.append({
                'kind': 'firstReply',
                'request': api_call(
                    'POST',
                    f'{REST_BASE}/socialActions/{enc}/comments',
                    token,
                    body={'actor': author_urn, 'object': target_urn, 'message': {'text': fr_clean}},
                    dry_run=True,
                ),
            })
        return {'dryRun': True, 'totalSteps': len(steps), 'steps': steps}, True

    post_urn = resume_post_urn
    post_res = None
    if not post_urn:
        post_res = api_call('POST', f'{REST_BASE}/posts', token, body=post_body, dry_run=False)
        post_urn = str(post_res.get('postUrn') or post_res.get('id') or '')
        if not post_urn:
            raise RuntimeError(f'LinkedIn post response missing postUrn: {json.dumps(post_res)}')

    public_url = f'https://www.linkedin.com/feed/update/{post_urn}'
    if not fr_clean:
        return {'ok': True, 'postUrn': post_urn, 'publicUrl': public_url, 'post': post_res, 'firstReply': None}, True

    enc = urllib.parse.quote(post_urn, safe='')
    try:
        cmt_res = api_call(
            'POST',
            f'{REST_BASE}/socialActions/{enc}/comments',
            token,
            body={'actor': author_urn, 'object': post_urn, 'message': {'text': fr_clean}},
            dry_run=False,
        )
    except Exception as exc:
        return {
            'ok': False,
            'partial': True,
            'failedKind': 'firstReply',
            'error': str(exc),
            'postUrn': post_urn,
            'publicUrl': public_url,
            'resumePostUrn': post_urn,
        }, False

    return {'ok': True, 'postUrn': post_urn, 'publicUrl': public_url, 'post': post_res, 'firstReply': cmt_res}, True


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

    p_pfr = sub.add_parser('post-with-first-reply', help='Publish a post (or --variant) and attach options.firstReply as the first comment.')
    p_pfr.add_argument('--variant', default=None, help='Path to variants/linkedin.md (or .json) to parse body and options.firstReply.')
    p_pfr.add_argument('--text', default=None, help='Post commentary (alternative to --variant).')
    p_pfr.add_argument('--first-reply', default=None, help='Optional first comment text (overrides variant options.firstReply).')
    p_pfr.add_argument('--visibility', choices=['PUBLIC', 'CONNECTIONS'], default='PUBLIC')
    p_pfr.add_argument('--image-urn', default=None)
    p_pfr.add_argument('--alt-text', default='')
    p_pfr.add_argument('--resume-post-urn', default=None, help='Resume attaching firstReply to an already-published post URN.')

    p_cmts = sub.add_parser('list-comments', help='List comments on a post URN.')
    p_cmts.add_argument('--post-urn', required=True)

    p_rep = sub.add_parser('comment', help='Post a comment on a post URN.')
    p_rep.add_argument('--post-urn', required=True)
    p_rep.add_argument('--text', required=True)

    args = parser.parse_args(argv)
    exit_code = 0
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
        elif args.cmd == 'post-with-first-reply':
            author = 'urn:li:person:DRY_RUN' if args.dry_run else require_env('LINKEDIN_AUTHOR_URN')
            if args.variant:
                body_text, var_fr = parse_linkedin_variant(Path(args.variant))
                first_reply = args.first_reply if args.first_reply is not None else var_fr
            elif args.text or args.resume_post_urn:
                body_text = args.text or ''
                first_reply = args.first_reply
            else:
                raise RuntimeError('post-with-first-reply requires --variant, --text, or --resume-post-urn')
            res, ok = post_with_first_reply(
                body_text,
                author,
                token,
                first_reply=first_reply,
                visibility=args.visibility,
                image_urn=args.image_urn,
                alt_text=args.alt_text,
                resume_post_urn=args.resume_post_urn,
                dry_run=args.dry_run,
            )
            if not ok:
                exit_code = 1
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
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
