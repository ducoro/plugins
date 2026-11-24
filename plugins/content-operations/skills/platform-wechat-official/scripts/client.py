#!/usr/bin/env python3
"""Zero-dependency Python 3 reference client for WeChat Official Account API."""
import argparse
from datetime import datetime, timedelta, timezone
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

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import render_wechat_html as rwh  # noqa: E402

BASE = 'https://api.weixin.qq.com'


def require_env(name: str) -> str:
    val = os.environ.get(name, '').strip()
    if not val:
        raise RuntimeError(f'Missing required environment variable: {name}')
    return val


def check_wechat_error(out: dict) -> None:
    errcode = out.get('errcode')
    if errcode not in (0, None):
        hint = ''
        if errcode == 48001:
            hint = ' [API unauthorized: unverified personal subscription accounts lack draft/datacube API access; fall back to https://mp.weixin.qq.com/ official web studio]'
        elif errcode == 40164:
            hint = ' [IP not allowlisted: add this host public IP in mp.weixin.qq.com -> Basic Settings or fall back to official web studio]'
        raise RuntimeError(f'WeChat API error (errcode={errcode}){hint}: {json.dumps(out, ensure_ascii=False)}')


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
    file_path = file_path.expanduser().resolve()
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


def resolve_local_asset(src: str, base_dir: Path) -> Path:
    cand = Path(src).expanduser()
    if cand.is_absolute() and cand.is_file():
        return cand
    for anchor in (base_dir, base_dir.parent):
        p = (anchor / src).resolve()
        if p.is_file():
            return p
    raise RuntimeError(f'Local inline image not found for src="{src}" (searched under {base_dir} and {base_dir.parent})')


def run_stage_draft(args, token: str) -> dict:
    src_path = Path(args.content_file).expanduser().resolve()
    if not src_path.is_file():
        raise RuntimeError(f'Content file not found: {src_path}')
    raw_text = src_path.read_text(encoding='utf-8')
    title = (args.title or '').strip()
    digest = (args.digest or '').strip()

    if src_path.suffix.lower() in ('.md', '.markdown'):
        themes = rwh.load_themes(Path(args.workspace) if args.workspace else None)
        if args.theme not in themes:
            raise RuntimeError(f'Unknown theme "{args.theme}". Available: {", ".join(sorted(themes))}')
        renderer = rwh.WeChatRenderer(
            themes[args.theme],
            section_numbering=True if args.section_numbering else None,
            aigc_footer=args.aigc_footer,
            cjk_spacing=not args.no_cjk_spacing,
        )
        rendered = renderer.convert(raw_text)
        html = rendered['html']
        title = title or rendered['title']
        digest = digest or rendered['digest']
    else:
        marker = re.search(r'<!--\s*WECHAT_BODY_START\s*-->(.*?)<!--\s*WECHAT_BODY_END\s*-->', raw_text, re.S)
        html = marker.group(1).strip() if marker else raw_text

    if not title:
        raise RuntimeError('Title is required (pass --title or include an H1 heading / JSON header in Markdown)')
    if len(title) > 64:
        raise RuntimeError(f'Title length {len(title)} exceeds WeChat 64-char limit')

    issues = rwh.validate_wechat_html(html)
    errors = [item for item in issues if item['level'] == 'ERROR']
    if errors:
        raise RuntimeError(f'WeChat HTML validation failed with {len(errors)} error(s): {json.dumps(errors, ensure_ascii=False)}')

    # Upload all local inline <img src="..."> and rewrite to WeChat CDN URLs
    uploaded_images = []
    img_rx = re.compile(r'(<img\b[^>]*?\bsrc=["\'])([^"\']+)(["\'])', re.I)
    cache: dict[str, str] = {}

    def replace_img(m: re.Match) -> str:
        prefix, img_src, suffix = m.group(1), m.group(2), m.group(3)
        if re.match(r'^https?://', img_src, re.I) or img_src.startswith('data:'):
            return m.group(0)
        if img_src in cache:
            return f'{prefix}{cache[img_src]}{suffix}'
        local_file = resolve_local_asset(img_src, src_path.parent)
        res = api_upload_multipart('/cgi-bin/media/uploadimg', token, local_file, dry_run=args.dry_run)
        new_url = f'https://mmbiz.qpic.cn/dry-run/{local_file.name}' if args.dry_run else res.get('url', '')
        if not new_url:
            raise RuntimeError(f'WeChat uploadimg returned no url for {local_file}: {res}')
        cache[img_src] = new_url
        uploaded_images.append({'source': img_src, 'file': str(local_file), 'url': new_url})
        return f'{prefix}{new_url}{suffix}'

    final_html = img_rx.sub(replace_img, html)

    cover_path = Path(args.cover).expanduser().resolve()
    thumb_res = api_upload_multipart('/cgi-bin/material/add_material', token, cover_path, {'type': 'image'}, dry_run=args.dry_run)
    thumb_media_id = 'DRY_RUN_THUMB_MEDIA_ID' if args.dry_run else thumb_res.get('media_id', '')
    if not thumb_media_id:
        raise RuntimeError(f'WeChat upload-thumb returned no media_id: {thumb_res}')

    safe_digest = rwh.truncate_utf8_bytes(digest, 120)
    body = {
        'articles': [{
            'title': title,
            'author': args.author,
            'digest': safe_digest,
            'content': final_html,
            'content_source_url': args.source_url,
            'thumb_media_id': thumb_media_id,
            'need_open_comment': args.open_comment,
            'only_fans_can_comment': args.only_fans_comment,
            'show_cover_pic': args.show_cover_pic,
        }]
    }
    draft_res = api_post('/cgi-bin/draft/add', token, body, dry_run=args.dry_run)
    return {
        'dryRun': args.dry_run,
        'title': title,
        'digest': safe_digest,
        'thumbMediaId': thumb_media_id,
        'uploadedInlineImages': uploaded_images,
        'validationWarnings': [item for item in issues if item['level'] == 'WARN'],
        'draft': draft_res,
    }


def run_add_image_post(args, token: str) -> dict:
    title = args.title.strip()
    if not title or len(title) > 32:
        raise RuntimeError(f'WeChat image post (newspic) title must be 1–32 chars, got {len(title)}')
    content = args.content
    if args.content_file:
        content = Path(args.content_file).expanduser().resolve().read_text(encoding='utf-8').strip()
    if len(content) > 1000:
        raise RuntimeError(f'WeChat image post (newspic) content must be <= 1000 chars, got {len(content)}')

    media_ids: list[str] = []
    if args.image_media_ids:
        media_ids.extend([m.strip() for m in args.image_media_ids.split(',') if m.strip()])
    if args.images:
        for idx, raw_path in enumerate([p.strip() for p in args.images.split(',') if p.strip()], start=1):
            res = api_upload_multipart('/cgi-bin/material/add_material', token, Path(raw_path), {'type': 'image'}, dry_run=args.dry_run)
            mid = f'DRY_RUN_IMG_{idx}' if args.dry_run else res.get('media_id', '')
            if not mid:
                raise RuntimeError(f'WeChat upload-thumb returned no media_id for {raw_path}: {res}')
            media_ids.append(mid)

    if not media_ids or len(media_ids) > 20:
        raise RuntimeError(f'WeChat image post (newspic) requires 1–20 images, got {len(media_ids)}')

    body = {
        'articles': [{
            'article_type': 'newspic',
            'title': title,
            'content': content,
            'image_info': {'image_list': [{'image_media_id': mid} for mid in media_ids]},
            'need_open_comment': args.open_comment,
            'only_fans_can_comment': args.only_fans_comment,
        }]
    }
    res = api_post('/cgi-bin/draft/add', token, body, dry_run=args.dry_run)
    return {'dryRun': args.dry_run, 'articleType': 'newspic', 'imageCount': len(media_ids), 'imageMediaIds': media_ids, 'draft': res}


def run_fetch_stats(args, token: str) -> dict:
    """Pull daily summary + cumulative article stats over the last N days and optionally append to workspace snapshots."""
    days = max(1, min(30, int(args.days)))
    end_dt = (
        datetime.strptime(args.end_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        if args.end_date
        else (datetime.now(timezone.utc) - timedelta(days=1))
    )
    dates = [(end_dt - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days - 1, -1, -1)]
    if args.dry_run:
        return {
            'dryRun': True,
            'dates': dates,
            'endpoints': ['/datacube/getarticlesummary', '/datacube/getarticletotal'],
            'workspace': str(Path(args.workspace).expanduser().resolve()) if args.workspace else None,
        }

    by_article: dict[str, dict] = {}
    warnings: list[dict] = []
    for day in dates:
        for endpoint in ('/datacube/getarticlesummary', '/datacube/getarticletotal'):
            try:
                resp = api_post(endpoint, token, {'begin_date': day, 'end_date': day}, dry_run=False)
            except RuntimeError as exc:
                warnings.append({'date': day, 'endpoint': endpoint, 'error': str(exc)})
                continue
            for item in resp.get('list') or []:
                details = item.get('details')
                latest = details[-1] if isinstance(details, list) and details else item
                key = str(item.get('msgid') or item.get('title') or f'{day}-{len(by_article)}')
                cur = by_article.setdefault(key, {
                    'workId': key,
                    'title': item.get('title') or '',
                    'refDate': item.get('ref_date') or day,
                    'views': 0,
                    'likes': 0,
                    'shares': 0,
                    'saves': 0,
                    'oriPageReads': 0,
                    'targetUser': 0,
                })
                cur['title'] = cur['title'] or item.get('title') or ''
                cur['views'] = max(cur['views'], int(latest.get('int_page_read_count', 0) or 0))
                cur['likes'] = max(cur['likes'], int(latest.get('like_count', latest.get('old_like_count', 0)) or 0))
                cur['shares'] = max(cur['shares'], int(latest.get('share_count', 0) or 0))
                cur['saves'] = max(cur['saves'], int(latest.get('add_to_fav_count', 0) or 0))
                cur['oriPageReads'] = max(cur['oriPageReads'], int(latest.get('ori_page_read_count', 0) or 0))
                cur['targetUser'] = max(cur['targetUser'], int(latest.get('target_user', 0) or 0))

    for art in by_article.values():
        art['openRate'] = round((art['views'] / art['targetUser']) * 100, 2) if art['targetUser'] > 0 else None

    articles = sorted(by_article.values(), key=lambda x: (x['views'], x['shares']), reverse=True)
    appended = 0
    snap_file = None
    if args.workspace:
        ws = Path(args.workspace).expanduser().resolve()
        snap_path = ws / 'analytics' / 'snapshots.jsonl'
        snap_path.parent.mkdir(parents=True, exist_ok=True)
        now_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        with snap_path.open('a', encoding='utf-8') as fh:
            for art in articles:
                pmetrics = {
                    'oriPageReads': art['oriPageReads'],
                    'targetUser': art['targetUser'],
                    'refDate': art['refDate'],
                }
                if art['openRate'] is not None:
                    pmetrics['openRate'] = art['openRate']
                row = {
                    'workId': art['workId'],
                    'platform': 'wechat-official',
                    'accountId': args.account_id or 'wechat-official-default',
                    'title': art['title'],
                    'window': args.window,
                    'capturedAt': now_iso,
                    'metrics': {
                        'views': art['views'],
                        'likes': art['likes'],
                        'comments': 0,
                        'shares': art['shares'],
                        'saves': art['saves'],
                    },
                    'platformMetrics': pmetrics,
                }
                fh.write(json.dumps(row, ensure_ascii=False) + '\n')
                appended += 1
        snap_file = str(snap_path)

    return {
        'ok': True,
        'dateRange': {'begin': dates[0], 'end': dates[-1], 'days': len(dates)},
        'articleCount': len(articles),
        'articles': articles,
        'snapshotsAppended': appended,
        'snapshotsFile': snap_file,
        'warnings': warnings,
    }


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

    p_draft = sub.add_parser('add-draft', help='Create an Official Account draft article from raw HTML.')
    p_draft.add_argument('--title', required=True)
    p_draft.add_argument('--content-file', required=True, help='Path to HTML body file.')
    p_draft.add_argument('--thumb-media-id', required=True)
    p_draft.add_argument('--author', default='')
    p_draft.add_argument('--digest', default='')
    p_draft.add_argument('--source-url', default='')
    p_draft.add_argument('--open-comment', type=int, choices=[0, 1], default=1)
    p_draft.add_argument('--only-fans-comment', type=int, choices=[0, 1], default=0)
    p_draft.add_argument('--show-cover-pic', type=int, choices=[0, 1], default=0)

    p_stage = sub.add_parser('stage-draft', help='Render/validate Markdown or HTML, upload local inline images + cover, and create draft.')
    p_stage.add_argument('--content-file', required=True, help='Path to Markdown (.md) or WeChat-compatible HTML file.')
    p_stage.add_argument('--cover', required=True, help='Local cover image path (2.35:1 900x383 recommended).')
    p_stage.add_argument('--title', default='', help='Override title (extracted from H1 / JSON header when omitted).')
    p_stage.add_argument('--theme', default='professional-clean', help='WeChat theme name for Markdown input.')
    p_stage.add_argument('--workspace', default='', help='Optional content-ops workspace to load custom learned themes.')
    p_stage.add_argument('--aigc-footer', action='store_true', help='Append optional AIGC disclosure footer (off by default).')
    p_stage.add_argument('--section-numbering', action='store_true', help='Number H2 headings sequentially.')
    p_stage.add_argument('--no-cjk-spacing', action='store_true', help='Disable automatic CJK-Latin spacing.')
    p_stage.add_argument('--author', default='')
    p_stage.add_argument('--digest', default='')
    p_stage.add_argument('--source-url', default='')
    p_stage.add_argument('--open-comment', type=int, choices=[0, 1], default=1)
    p_stage.add_argument('--only-fans-comment', type=int, choices=[0, 1], default=0)
    p_stage.add_argument('--show-cover-pic', type=int, choices=[0, 1], default=0)

    p_pic = sub.add_parser('add-image-post', help='Create a WeChat image carousel post (newspic / 小绿书) draft.')
    p_pic.add_argument('--title', required=True, help='Post title (1–32 chars).')
    p_pic.add_argument('--images', default='', help='Comma-separated local image paths (uploaded automatically as permanent material).')
    p_pic.add_argument('--image-media-ids', default='', help='Comma-separated existing permanent image media_ids.')
    p_pic.add_argument('--content', default='', help='Plain text body (<= 1000 chars).')
    p_pic.add_argument('--content-file', default='', help='Optional path to plain text body file.')
    p_pic.add_argument('--open-comment', type=int, choices=[0, 1], default=1)
    p_pic.add_argument('--only-fans-comment', type=int, choices=[0, 1], default=0)

    p_get = sub.add_parser('get-draft', help='Read back a draft from WeChat draft box (HTML + plaintext for edit learning).')
    p_get.add_argument('--media-id', required=True)

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

    p_fstats = sub.add_parser('fetch-stats', help='Pull multi-day WeChat article summary/total stats and optionally append to workspace analytics/snapshots.jsonl.')
    p_fstats.add_argument('--days', type=int, default=7, help='Number of trailing days to query (1–30, default 7).')
    p_fstats.add_argument('--end-date', default='', help='Optional end date YYYY-MM-DD (default: yesterday UTC).')
    p_fstats.add_argument('--workspace', default='', help='Optional content-ops workspace to append rows into analytics/snapshots.jsonl.')
    p_fstats.add_argument('--account-id', default='wechat-official-default', help='Account identifier stored in snapshots.jsonl.')
    p_fstats.add_argument('--window', default='7d', choices=['24h', '72h', '7d', '30d'], help='Snapshot window label.')

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
                html = Path(args.content_file).expanduser().resolve().read_text(encoding='utf-8')
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
                        'show_cover_pic': args.show_cover_pic,
                    }]
                }
                res = api_post('/cgi-bin/draft/add', token, body, dry_run=args.dry_run)
            elif args.cmd == 'stage-draft':
                res = run_stage_draft(args, token)
            elif args.cmd == 'add-image-post':
                res = run_add_image_post(args, token)
            elif args.cmd == 'get-draft':
                res = api_post('/cgi-bin/draft/get', token, {'media_id': args.media_id}, dry_run=args.dry_run)
                if not args.dry_run and isinstance(res, dict) and isinstance(res.get('news_item'), list) and res['news_item']:
                    first = res['news_item'][0]
                    res = {
                        'mediaId': args.media_id,
                        'title': first.get('title', ''),
                        'digest': first.get('digest', ''),
                        'html': first.get('content', ''),
                        'plainText': rwh.html_to_plaintext(first.get('content', '')),
                        'raw': res,
                    }
            elif args.cmd == 'submit-publish':
                res = api_post('/cgi-bin/freepublish/submit', token, {'media_id': args.media_id}, dry_run=args.dry_run)
            elif args.cmd == 'poll-publish':
                res = api_post('/cgi-bin/freepublish/get', token, {'publish_id': args.publish_id}, dry_run=args.dry_run)
            elif args.cmd == 'user-read':
                res = api_post('/datacube/getuserread', token, {'begin_date': args.begin_date, 'end_date': args.end_date}, dry_run=args.dry_run)
            elif args.cmd == 'user-cumulate':
                res = api_post('/datacube/getusercumulate', token, {'begin_date': args.begin_date, 'end_date': args.end_date}, dry_run=args.dry_run)
            elif args.cmd == 'fetch-stats':
                res = run_fetch_stats(args, token)
            else:
                res = api_post('/datacube/getarticletotal', token, {'begin_date': args.begin_date, 'end_date': args.end_date}, dry_run=args.dry_run)
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
