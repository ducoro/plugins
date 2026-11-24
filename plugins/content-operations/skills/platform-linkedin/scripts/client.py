#!/usr/bin/env python3
"""Zero-dependency Python 3 reference client for LinkedIn REST API."""
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

REST_BASE = 'https://api.linkedin.com/rest'
V2_BASE = 'https://api.linkedin.com/v2'
API_VERSION = os.environ.get('LINKEDIN_API_VERSION', '202601').strip() or '202601'
FRONT_JSON_RE = re.compile(r'^\s*```json\s*\n(.*?)\n```\s*\n?(.*)$', re.S)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def require_env(name: str) -> str:
    val = os.environ.get(name, '').strip()
    if not val:
        raise RuntimeError(f'Missing required environment variable: {name}')
    return val


def resolve_org_urn(explicit: str | None, dry_run: bool = False) -> str:
    if explicit and explicit.strip():
        urn = explicit.strip()
    elif dry_run:
        return 'urn:li:organization:DRY_RUN'
    else:
        urn = os.environ.get('LINKEDIN_ORG_URN', '').strip()
        if not urn:
            author = os.environ.get('LINKEDIN_AUTHOR_URN', '').strip()
            if author.startswith('urn:li:organization:'):
                urn = author
    if not urn.startswith('urn:li:organization:'):
        raise RuntimeError('Organization analytics requires --org-urn urn:li:organization:<id> (or LINKEDIN_ORG_URN)')
    return urn


def resolve_time_range_ms(days: int, start_ms: int | None, end_ms: int | None) -> tuple[int, int]:
    if days <= 0:
        raise ValueError('--days must be positive')
    now_ms = int(utc_now().timestamp() * 1000)
    end_val = end_ms if end_ms is not None else now_ms
    start_val = start_ms if start_ms is not None else int((utc_now() - timedelta(days=days)).timestamp() * 1000)
    if start_val > end_val:
        raise ValueError(f'start-ms ({start_val}) cannot be after end-ms ({end_val})')
    return start_val, end_val


def parse_org_share_statistics(raw: dict) -> dict:
    """Normalize LinkedIn organizationalEntityShareStatistics elements into daily rows and totals."""
    elements = raw.get('elements') or []
    daily: list[dict] = []
    totals = {
        'impressionCount': 0,
        'uniqueImpressionsCount': 0,
        'clickCount': 0,
        'likeCount': 0,
        'commentCount': 0,
        'shareCount': 0,
    }
    engagement_vals: list[float] = []

    for el in elements:
        stats = el.get('totalShareStatistics') or {}
        tr = el.get('timeRange') or {}
        start_ts = tr.get('start')
        day_str = (
            datetime.fromtimestamp(start_ts / 1000.0, tz=timezone.utc).strftime('%Y-%m-%d')
            if isinstance(start_ts, (int, float))
            else None
        )
        row = {
            'date': day_str,
            'impressionCount': int(stats.get('impressionCount', 0) or 0),
            'uniqueImpressionsCount': int(stats.get('uniqueImpressionsCount', 0) or 0),
            'clickCount': int(stats.get('clickCount', 0) or 0),
            'likeCount': int(stats.get('likeCount', 0) or 0),
            'commentCount': int(stats.get('commentCount', 0) or 0),
            'shareCount': int(stats.get('shareCount', 0) or 0),
            'engagement': round(float(stats.get('engagement', 0.0) or 0.0), 4),
        }
        daily.append(row)
        for key in totals:
            totals[key] += row[key]
        if isinstance(stats.get('engagement'), (int, float)):
            engagement_vals.append(float(stats['engagement']))

    impressions = totals['impressionCount']
    if impressions > 0:
        agg_engagement = round(
            (totals['clickCount'] + totals['likeCount'] + totals['commentCount'] + totals['shareCount']) / impressions,
            4,
        )
    elif engagement_vals:
        agg_engagement = round(sum(engagement_vals) / len(engagement_vals), 4)
    else:
        agg_engagement = 0.0

    totals['engagement'] = agg_engagement
    return {
        'rowCount': len(daily),
        'daily': daily,
        'totals': totals,
        'platformMetrics': {
            'uniqueImpressionsCount': totals['uniqueImpressionsCount'],
            'clickCount': totals['clickCount'],
            'engagementRatio': agg_engagement,
        },
    }


def append_snapshot(workspace: Path, row: dict) -> str:
    snap_path = workspace.expanduser().resolve() / 'analytics' / 'snapshots.jsonl'
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    with snap_path.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + '\n')
    return str(snap_path)


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

    p_oa = sub.add_parser('org-analytics', help='Fetch Organization Page daily share/impression statistics (requires r_organization_social).')
    p_oa.add_argument('--org-urn', default=None, help='urn:li:organization:<id> (defaults to LINKEDIN_ORG_URN or org LINKEDIN_AUTHOR_URN).')
    p_oa.add_argument('--days', type=int, default=30, help='Lookback window in days when --start-ms is omitted (default 30).')
    p_oa.add_argument('--start-ms', type=int, default=None, help='Optional UTC start epoch in milliseconds.')
    p_oa.add_argument('--end-ms', type=int, default=None, help='Optional UTC end epoch in milliseconds.')
    p_oa.add_argument('--with-followers', action='store_true', help='Also query organizationalEntityFollowerStatistics.')
    p_oa.add_argument('--workspace', default='', help='Optional content-ops workspace to append an account snapshot into analytics/snapshots.jsonl.')
    p_oa.add_argument('--account-id', default='linkedin-org', help='Account ID used when writing to snapshots.jsonl.')

    p_pa = sub.add_parser('post-analytics', help='Fetch post-level analytics (Org share statistics with --org-urn, or socialActions summary for member posts).')
    p_pa.add_argument('--post-urn', required=True, help='urn:li:share:<id> or urn:li:ugcPost:<id>.')
    p_pa.add_argument('--org-urn', default=None, help='Optional urn:li:organization:<id> to pull impressions/clicks via organizationalEntityShareStatistics.')
    p_pa.add_argument('--workspace', default='', help='Optional content-ops workspace to append a work snapshot into analytics/snapshots.jsonl.')
    p_pa.add_argument('--window', choices=['24h', '72h', '7d', '30d'], default='7d', help='Snapshot window label (default 7d).')
    p_pa.add_argument('--account-id', default='linkedin-main', help='Account ID used when writing to snapshots.jsonl.')
    p_pa.add_argument('--topic-id', default='', help='Optional topicId metadata for cross-platform grouping.')
    p_pa.add_argument('--title', default='', help='Optional work title for snapshots.jsonl.')

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
        elif args.cmd == 'org-analytics':
            org_urn = resolve_org_urn(args.org_urn, dry_run=args.dry_run)
            start_ms, end_ms = resolve_time_range_ms(args.days, args.start_ms, args.end_ms)
            enc_org = urllib.parse.quote(org_urn, safe='')
            time_interval = f'(timeRange:(start:{start_ms},end:{end_ms}),timeGranularityType:DAY)'
            share_url = (
                f'{REST_BASE}/organizationalEntityShareStatistics'
                f'?q=organizationalEntity&organizationalEntity={enc_org}&timeIntervals={time_interval}'
            )
            share_raw = api_call('GET', share_url, token, dry_run=args.dry_run)
            follower_url = (
                f'{REST_BASE}/organizationalEntityFollowerStatistics'
                f'?q=organizationalEntity&organizationalEntity={enc_org}&timeIntervals={time_interval}'
            )
            if args.dry_run:
                res = {'dryRun': True, 'shareStatsRequest': share_raw}
                if args.with_followers:
                    res['followerStatsRequest'] = api_call('GET', follower_url, token, dry_run=True)
            else:
                parsed = parse_org_share_statistics(share_raw)
                res = {'orgUrn': org_urn, 'startMs': start_ms, 'endMs': end_ms, **parsed}
                if args.with_followers:
                    f_raw = api_call('GET', follower_url, token, dry_run=False)
                    organic = paid = 0
                    for el in (f_raw.get('elements') or []):
                        gains = el.get('followerGains') or {}
                        organic += int(gains.get('organicFollowerGain', 0) or 0)
                        paid += int(gains.get('paidFollowerGain', 0) or 0)
                    res['followerGains'] = {'organic': organic, 'paid': paid, 'total': organic + paid}
                    res['platformMetrics']['organicFollowerGain'] = organic
                    res['platformMetrics']['paidFollowerGain'] = paid
                if args.workspace:
                    t = parsed['totals']
                    snap = {
                        'capturedAt': utc_now().strftime('%Y-%m-%dT%H:%M:%SZ'),
                        'platform': 'linkedin',
                        'accountId': args.account_id,
                        'window': 'account',
                        'source': 'api',
                        'metrics': {
                            'views': t['impressionCount'],
                            'likes': t['likeCount'],
                            'comments': t['commentCount'],
                            'shares': t['shareCount'],
                            'saves': 0,
                        },
                        'platformMetrics': res['platformMetrics'],
                    }
                    res['snapshotAppended'] = append_snapshot(Path(args.workspace), snap)
        elif args.cmd == 'post-analytics':
            enc_post = urllib.parse.quote(args.post_urn, safe='')
            if args.org_urn:
                org_urn = resolve_org_urn(args.org_urn, dry_run=args.dry_run)
                enc_org = urllib.parse.quote(org_urn, safe='')
                filter_key = 'ugcPosts' if ':ugcPost:' in args.post_urn else 'shares'
                url = (
                    f'{REST_BASE}/organizationalEntityShareStatistics'
                    f'?q=organizationalEntity&organizationalEntity={enc_org}&{filter_key}=List({enc_post})'
                )
                raw = api_call('GET', url, token, dry_run=args.dry_run)
                if args.dry_run:
                    res = raw
                else:
                    parsed = parse_org_share_statistics(raw)
                    res = {'scope': 'organization_share_statistics', 'orgUrn': org_urn, 'postUrn': args.post_urn, **parsed}
                    if args.workspace:
                        t = parsed['totals']
                        snap = {
                            'capturedAt': utc_now().strftime('%Y-%m-%dT%H:%M:%SZ'),
                            'platform': 'linkedin',
                            'accountId': args.account_id,
                            'workId': args.post_urn,
                            'window': args.window,
                            'source': 'api',
                            'metrics': {
                                'views': t['impressionCount'],
                                'likes': t['likeCount'],
                                'comments': t['commentCount'],
                                'shares': t['shareCount'],
                                'saves': 0,
                            },
                            'platformMetrics': parsed['platformMetrics'],
                        }
                        if args.topic_id:
                            snap['topicId'] = args.topic_id
                        if args.title:
                            snap['title'] = args.title
                        res['snapshotAppended'] = append_snapshot(Path(args.workspace), snap)
            else:
                url = f'{REST_BASE}/socialActions/{enc_post}'
                raw = api_call('GET', url, token, dry_run=args.dry_run)
                if args.dry_run:
                    res = raw
                else:
                    likes_count = int(((raw.get('likesSummary') or {}).get('totalLikes')) or 0)
                    comments_count = int(((raw.get('commentsSummary') or {}).get('totalFirstLevelComments')) or 0)
                    res = {
                        'scope': 'member_public_actions',
                        'postUrn': args.post_urn,
                        'note': 'Personal member API returns likes and comments only; impressions require Organization Page scope or manual export.',
                        'totals': {'likeCount': likes_count, 'commentCount': comments_count},
                    }
                    if args.workspace:
                        snap = {
                            'capturedAt': utc_now().strftime('%Y-%m-%dT%H:%M:%SZ'),
                            'platform': 'linkedin',
                            'accountId': args.account_id,
                            'workId': args.post_urn,
                            'window': args.window,
                            'source': 'api',
                            'metrics': {
                                'views': 0,
                                'likes': likes_count,
                                'comments': comments_count,
                                'shares': 0,
                                'saves': 0,
                            },
                            'platformMetrics': {'impressionsUnavailableOnMemberApi': True},
                        }
                        if args.topic_id:
                            snap['topicId'] = args.topic_id
                        if args.title:
                            snap['title'] = args.title
                        res['snapshotAppended'] = append_snapshot(Path(args.workspace), snap)
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
