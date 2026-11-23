#!/usr/bin/env python3
"""Zero-dependency Python 3 reference client for Bilibili OpenAPI operations."""
import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = 'https://member.bilibili.com'


def require_env(name: str) -> str:
    val = os.environ.get(name, '').strip()
    if not val:
        raise RuntimeError(f'Missing required environment variable: {name}')
    return val


def build_bili_v2_headers(client_id: str, client_secret: str, token: str, body_bytes: bytes) -> dict[str, str]:
    content_md5 = hashlib.md5(body_bytes).hexdigest()
    ts = str(int(time.time()))
    nonce = uuid.uuid4().hex
    sign_headers = {
        'x-bili-accesskeyid': client_id,
        'x-bili-content-md5': content_md5,
        'x-bili-signature-method': 'HMAC-SHA256',
        'x-bili-signature-nonce': nonce,
        'x-bili-signature-version': '2.0',
        'x-bili-timestamp': ts,
    }
    sign_payload = '\n'.join(f'{k}:{sign_headers[k]}' for k in sorted(sign_headers))
    sig = hmac.new(client_secret.encode('utf-8'), sign_payload.encode('utf-8'), hashlib.sha256).hexdigest()
    return {
        'X-Bili-Accesskeyid': client_id,
        'X-Bili-Content-Md5': content_md5,
        'X-Bili-Signature-Method': 'HMAC-SHA256',
        'X-Bili-Signature-Nonce': nonce,
        'X-Bili-Signature-Version': '2.0',
        'X-Bili-Timestamp': ts,
        'Authorization': sig,
        'Access-Token': token,
    }


def api_call(
    method: str,
    path: str,
    query: dict,
    body: dict | None = None,
    client_id: str = '',
    client_secret: str = '',
    token: str = '',
    dry_run: bool = False,
) -> dict:
    qs = urllib.parse.urlencode(query)
    url = f'{BASE}{path}?{qs}' if qs else f'{BASE}{path}'
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    headers: dict[str, str] = {}
    if data is not None:
        headers['Content-Type'] = 'application/json'
    if client_secret:
        headers.update(build_bili_v2_headers(client_id, client_secret, token, data or b''))
    if dry_run:
        safe_q = {k: ('<redacted>' if 'token' in k else v) for k, v in query.items()}
        safe_h = {k: ('<redacted>' if k.lower() in ('authorization', 'access-token') else v) for k, v in headers.items()}
        return {'dryRun': True, 'method': method, 'url': f'{BASE}{path}', 'query': safe_q, 'headers': safe_h, 'body': body}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            text = resp.read().decode('utf-8').strip()
            out = json.loads(text) if text else {'ok': True}
    except urllib.error.HTTPError as err:
        raise RuntimeError(f'HTTP {err.code}: {err.read().decode("utf-8", errors="replace")}') from err
    if isinstance(out, dict):
        code = out.get('code')
        if code not in (0, None):
            raise RuntimeError(f'Bilibili API error (code={code}): {json.dumps(out, ensure_ascii=False)}')
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Bilibili OpenAPI reference client.')
    parser.add_argument('--dry-run', action='store_true', help='Preview request without network I/O.')
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('list-categories', help='List valid Bilibili partition IDs (tid).')
    p_view = sub.add_parser('get-work', help='Read back archive status and metadata.')
    p_view.add_argument('--bvid', required=True)
    p_stat = sub.add_parser('work-stats', help='Fetch archive performance metrics.')
    p_stat.add_argument('--bvid', required=True)
    sub.add_parser('account-stats', help='Fetch account-level statistics.')
    p_sub = sub.add_parser('submit-archive', help='Submit an uploaded video by upload_token.')
    p_sub.add_argument('--upload-token', required=True)
    p_sub.add_argument('--title', required=True)
    p_sub.add_argument('--desc', default='')
    p_sub.add_argument('--tag', required=True, help='Comma-separated tags.')
    p_sub.add_argument('--tid', type=int, required=True)
    p_sub.add_argument('--copyright', type=int, choices=[1, 2], default=1)
    p_sub.add_argument('--source', default='')
    p_sub.add_argument('--cover', default='')

    args = parser.parse_args(argv)
    try:
        client_id = 'DRY_RUN_CLIENT' if args.dry_run else require_env('BILIBILI_CLIENT_ID')
        token = 'DRY_RUN_TOKEN' if args.dry_run else require_env('BILIBILI_ACCESS_TOKEN')
        client_secret = 'DRY_RUN_SECRET' if args.dry_run else os.environ.get('BILIBILI_CLIENT_SECRET', '').strip()
        auth_q = {'client_id': client_id, 'access_token': token}
        if args.cmd == 'list-categories':
            res = api_call('GET', '/arcopen/fn/archive/type/list', auth_q, client_id=client_id, client_secret=client_secret, token=token, dry_run=args.dry_run)
        elif args.cmd == 'get-work':
            res = api_call('GET', '/arcopen/fn/archive/view', {**auth_q, 'resource_id': args.bvid}, client_id=client_id, client_secret=client_secret, token=token, dry_run=args.dry_run)
        elif args.cmd == 'work-stats':
            res = api_call('GET', '/arcopen/fn/data/arc/stat', {**auth_q, 'resource_id': args.bvid}, client_id=client_id, client_secret=client_secret, token=token, dry_run=args.dry_run)
        elif args.cmd == 'account-stats':
            res = api_call('GET', '/arcopen/fn/data/user/stat', auth_q, client_id=client_id, client_secret=client_secret, token=token, dry_run=args.dry_run)
        else:
            if args.copyright == 2 and not args.source.strip():
                raise ValueError('--source is required when --copyright=2 (reprint)')
            body = {
                'title': args.title,
                'desc': args.desc,
                'tag': args.tag,
                'tid': args.tid,
                'copyright': args.copyright,
                'source': args.source,
                'cover': args.cover,
            }
            res = api_call(
                'POST',
                '/arcopen/fn/archive/add-by-utoken',
                {**auth_q, 'upload_token': args.upload_token},
                body=body,
                client_id=client_id,
                client_secret=client_secret,
                token=token,
                dry_run=args.dry_run,
            )
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
