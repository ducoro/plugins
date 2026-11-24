#!/usr/bin/env python3
"""Zero-dependency Python 3 reference client for YouTube Data API v3 and Analytics API v2."""
import argparse
from datetime import datetime, timedelta, timezone
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
ANALYTICS_BASE = 'https://youtubeanalytics.googleapis.com/v2'
OAUTH_TOKEN_URL = 'https://oauth2.googleapis.com/token'

DEFAULT_CHANNEL_METRICS = (
    'views,estimatedMinutesWatched,averageViewDuration,'
    'averageViewPercentage,subscribersGained,subscribersLost,likes'
)
DEFAULT_VIDEO_METRICS = (
    'views,estimatedMinutesWatched,averageViewDuration,'
    'averageViewPercentage,likes,comments,shares,subscribersGained'
)
AVERAGE_METRICS = {'averageViewDuration', 'averageViewPercentage'}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def resolve_date_range(days: int, start_date: str | None, end_date: str | None) -> tuple[str, str]:
    if days <= 0:
        raise ValueError('--days must be positive')
    now = utc_now()
    end_str = (end_date or now.strftime('%Y-%m-%d')).strip()
    start_str = (start_date or (now - timedelta(days=days)).strftime('%Y-%m-%d')).strip()
    datetime.strptime(start_str, '%Y-%m-%d')
    datetime.strptime(end_str, '%Y-%m-%d')
    if start_str > end_str:
        raise ValueError(f'start-date ({start_str}) cannot be after end-date ({end_str})')
    return start_str, end_str


def parse_analytics_report(raw: dict) -> dict:
    """Normalize YouTube Analytics API columnHeaders + rows into daily entries and summary totals."""
    headers = [str(col.get('name') or f'col_{i}') for i, col in enumerate(raw.get('columnHeaders') or [])]
    rows = raw.get('rows') or []
    daily: list[dict] = []
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}

    for row in rows:
        entry: dict = {}
        for idx, col_name in enumerate(headers):
            val = row[idx] if idx < len(row) else None
            entry[col_name] = val
            if col_name == 'day':
                continue
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                sums[col_name] = sums.get(col_name, 0.0) + float(val)
                counts[col_name] = counts.get(col_name, 0) + 1
        daily.append(entry)

    totals: dict = {}
    for metric, total_val in sums.items():
        if metric in AVERAGE_METRICS:
            totals[metric] = round(total_val / max(counts.get(metric, 1), 1), 2)
        else:
            totals[metric] = int(round(total_val)) if abs(total_val - round(total_val)) < 1e-6 else round(total_val, 2)

    platform_metrics: dict = {}
    if 'averageViewDuration' in totals:
        platform_metrics['avgViewDurationSec'] = totals['averageViewDuration']
    if 'averageViewPercentage' in totals:
        platform_metrics['avgViewPct'] = totals['averageViewPercentage']
    if 'estimatedMinutesWatched' in totals:
        platform_metrics['estimatedMinutesWatched'] = totals['estimatedMinutesWatched']
    if 'subscribersGained' in totals:
        platform_metrics['subscribersGained'] = totals['subscribersGained']
    if 'subscribersLost' in totals:
        platform_metrics['subscribersLost'] = totals['subscribersLost']

    return {
        'rowCount': len(daily),
        'daily': daily,
        'totals': totals,
        'platformMetrics': platform_metrics,
    }


def append_snapshot(workspace: Path, row: dict) -> str:
    snap_path = workspace.expanduser().resolve() / 'analytics' / 'snapshots.jsonl'
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    with snap_path.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + '\n')
    return str(snap_path)


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
    parser = argparse.ArgumentParser(description='YouTube Data API v3 and Analytics API v2 reference client.')
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

    p_ca = sub.add_parser('channel-analytics', help='Fetch daily channel analytics (AVD, avgViewPct, watch minutes, subs) via YouTube Analytics API v2.')
    p_ca.add_argument('--days', type=int, default=14, help='Lookback window in days when --start-date is omitted (default 14).')
    p_ca.add_argument('--start-date', default=None, help='Start date YYYY-MM-DD (inclusive).')
    p_ca.add_argument('--end-date', default=None, help='End date YYYY-MM-DD (inclusive).')
    p_ca.add_argument('--metrics', default=DEFAULT_CHANNEL_METRICS, help='Comma-separated YouTube Analytics metrics.')
    p_ca.add_argument('--ids', default='channel==MINE', help='YouTube Analytics ids parameter (default channel==MINE).')
    p_ca.add_argument('--workspace', default='', help='Optional content-ops workspace to append an account snapshot into analytics/snapshots.jsonl.')
    p_ca.add_argument('--account-id', default='youtube-main', help='Account ID used when writing to snapshots.jsonl.')

    p_va = sub.add_parser('video-analytics', help='Fetch single-video analytics (AVD, avgViewPct, watch minutes, shares, subs) and optionally append to snapshots.jsonl.')
    p_va.add_argument('--video-id', required=True)
    p_va.add_argument('--days', type=int, default=30, help='Lookback window in days when --start-date is omitted (default 30).')
    p_va.add_argument('--start-date', default=None, help='Start date YYYY-MM-DD (inclusive).')
    p_va.add_argument('--end-date', default=None, help='End date YYYY-MM-DD (inclusive).')
    p_va.add_argument('--metrics', default=DEFAULT_VIDEO_METRICS, help='Comma-separated YouTube Analytics metrics.')
    p_va.add_argument('--with-stats', action='store_true', help='Also query Data API /videos to enrich title and lifetime counts.')
    p_va.add_argument('--workspace', default='', help='Optional content-ops workspace to append a work snapshot into analytics/snapshots.jsonl.')
    p_va.add_argument('--window', choices=['24h', '72h', '7d', '30d'], default='7d', help='Snapshot window label (default 7d).')
    p_va.add_argument('--account-id', default='youtube-main', help='Account ID used when writing to snapshots.jsonl.')
    p_va.add_argument('--topic-id', default='', help='Optional topicId metadata for cross-platform grouping.')
    p_va.add_argument('--title', default='', help='Optional work title override for snapshots.jsonl.')

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
            elif args.cmd == 'channel-analytics':
                start_str, end_str = resolve_date_range(args.days, args.start_date, args.end_date)
                query = {
                    'ids': args.ids,
                    'startDate': start_str,
                    'endDate': end_str,
                    'metrics': args.metrics,
                    'dimensions': 'day',
                    'sort': 'day',
                }
                raw = api_call('GET', ANALYTICS_BASE, '/reports', token, query, dry_run=args.dry_run)
                if args.dry_run:
                    res = raw
                else:
                    parsed = parse_analytics_report(raw)
                    res = {'startDate': start_str, 'endDate': end_str, **parsed}
                    if args.workspace:
                        totals = parsed['totals']
                        snap = {
                            'capturedAt': utc_now().strftime('%Y-%m-%dT%H:%M:%SZ'),
                            'platform': 'youtube',
                            'accountId': args.account_id,
                            'window': 'account',
                            'source': 'api',
                            'metrics': {
                                'views': int(totals.get('views', 0) or 0),
                                'likes': int(totals.get('likes', 0) or 0),
                            },
                            'platformMetrics': parsed['platformMetrics'],
                        }
                        res['snapshotAppended'] = append_snapshot(Path(args.workspace), snap)
            elif args.cmd == 'video-analytics':
                start_str, end_str = resolve_date_range(args.days, args.start_date, args.end_date)
                query = {
                    'ids': 'channel==MINE',
                    'startDate': start_str,
                    'endDate': end_str,
                    'metrics': args.metrics,
                    'filters': f'video=={args.video_id}',
                    'dimensions': 'day',
                    'sort': 'day',
                }
                raw = api_call('GET', ANALYTICS_BASE, '/reports', token, query, dry_run=args.dry_run)
                if args.dry_run:
                    res = {'dryRun': True, 'analyticsRequest': raw}
                    if args.with_stats:
                        res['statsRequest'] = api_call('GET', BASE, '/videos', token, {'part': 'snippet,statistics,status', 'id': args.video_id}, dry_run=True)
                else:
                    parsed = parse_analytics_report(raw)
                    title = args.title
                    lifetime = {}
                    if args.with_stats:
                        vdata = api_call('GET', BASE, '/videos', token, {'part': 'snippet,statistics,status', 'id': args.video_id}, dry_run=False)
                        item = (vdata.get('items') or [{}])[0]
                        title = title or str((item.get('snippet') or {}).get('title') or '')
                        stats = item.get('statistics') or {}
                        lifetime = {
                            'views': int(stats.get('viewCount', 0) or 0),
                            'likes': int(stats.get('likeCount', 0) or 0),
                            'comments': int(stats.get('commentCount', 0) or 0),
                        }
                    res = {
                        'videoId': args.video_id,
                        'startDate': start_str,
                        'endDate': end_str,
                        'title': title,
                        **parsed,
                    }
                    if lifetime:
                        res['lifetimeStats'] = lifetime
                    if args.workspace:
                        totals = parsed['totals']
                        snap = {
                            'capturedAt': utc_now().strftime('%Y-%m-%dT%H:%M:%SZ'),
                            'platform': 'youtube',
                            'accountId': args.account_id,
                            'workId': args.video_id,
                            'window': args.window,
                            'source': 'api',
                            'metrics': {
                                'views': int(lifetime.get('views', totals.get('views', 0)) or 0),
                                'likes': int(lifetime.get('likes', totals.get('likes', 0)) or 0),
                                'comments': int(lifetime.get('comments', totals.get('comments', 0)) or 0),
                                'shares': int(totals.get('shares', 0) or 0),
                                'saves': 0,
                            },
                            'platformMetrics': parsed['platformMetrics'],
                        }
                        if args.topic_id:
                            snap['topicId'] = args.topic_id
                        if title:
                            snap['title'] = title
                        res['snapshotAppended'] = append_snapshot(Path(args.workspace), snap)
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
