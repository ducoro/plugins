#!/usr/bin/env python3
"""Zero-dependency real-time CN trend radar (Weibo, Toutiao, Baidu)."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import json
import sys
import urllib.parse
import urllib.request

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/plain, */*',
}

ENDPOINTS = {
    'weibo': 'https://weibo.com/ajax/side/hotSearch',
    'toutiao': 'https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc',
    'baidu': 'https://top.baidu.com/api/board?platform=wise&tab=realtime',
}


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def fetch_json(url: str, extra_headers: dict | None = None, timeout: int = 10):
    req = urllib.request.Request(url, headers={**HEADERS, **(extra_headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8', errors='replace'))


def _matches_query(query: str, title: str) -> bool:
    q = (query or '').strip().lower()
    if not q:
        return True
    t = title.lower()
    return any(tok in t for tok in q.split() if tok)


def fetch_weibo(query: str = '') -> list[dict]:
    data = fetch_json(ENDPOINTS['weibo'], {'Referer': 'https://weibo.com/'})
    now_str = _iso_utc_now()
    items = []
    for entry in data.get('data', {}).get('realtime', []):
        note = str(entry.get('note') or '').strip()
        if not note or not _matches_query(query, note):
            continue
        hot = int(entry.get('num') or 0)
        items.append({
            'title': note,
            'source': 'weibo',
            'hot': hot,
            'url': f'https://s.weibo.com/weibo?q={urllib.parse.quote("#" + note + "#")}',
            'publishedAt': now_str,
            'engagement': {'score': hot},
            'tag': str(entry.get('label_name') or ''),
            'isSeedListing': True,
            'isPrimarySource': False,
        })
    return items


def fetch_toutiao(query: str = '') -> list[dict]:
    data = fetch_json(ENDPOINTS['toutiao'])
    now_str = _iso_utc_now()
    items = []
    for entry in data.get('data', []):
        title = str(entry.get('Title') or '').strip()
        if not title or not _matches_query(query, title):
            continue
        hot = int(entry.get('HotValue') or 0)
        items.append({
            'title': title,
            'source': 'toutiao',
            'hot': hot,
            'url': str(entry.get('Url') or ''),
            'publishedAt': now_str,
            'engagement': {'score': hot},
            'tag': '',
            'isSeedListing': True,
            'isPrimarySource': False,
        })
    return items


def fetch_baidu(query: str = '') -> list[dict]:
    data = fetch_json(ENDPOINTS['baidu'])
    now_str = _iso_utc_now()
    items = []
    for card in data.get('data', {}).get('cards', []):
        content = card.get('content', [])
        if not content:
            continue
        entries = content[0].get('content', []) if isinstance(content[0], dict) else content
        for entry in entries:
            word = str(entry.get('word') or '').strip()
            if not word or not _matches_query(query, word):
                continue
            hot = int(entry.get('hotScore') or 0)
            items.append({
                'title': word,
                'source': 'baidu',
                'hot': hot,
                'url': str(entry.get('url') or ''),
                'publishedAt': now_str,
                'engagement': {'score': hot},
                'tag': '',
                'isSeedListing': True,
                'isPrimarySource': False,
            })
    return items


SOURCE_FETCHERS = {
    'weibo': fetch_weibo,
    'toutiao': fetch_toutiao,
    'baidu': fetch_baidu,
}


def normalize_and_merge(items: list[dict], limit: int) -> list[dict]:
    seen = set()
    deduped = []
    for item in items:
        key = item['title'].strip().lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(dict(item))
    by_source: dict[str, list[dict]] = {}
    for item in deduped:
        by_source.setdefault(item['source'], []).append(item)
    for group in by_source.values():
        group.sort(key=lambda x: int(x.get('hot') or 0), reverse=True)
        n = len(group)
        for rank, entry in enumerate(group):
            entry['hotNormalized'] = round(100.0 * (n - rank) / n, 1) if n else 0.0
    deduped.sort(key=lambda x: (-float(x.get('hotNormalized', 0.0)), x['source'], x['title']))
    return deduped[:limit]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Fetch live CN trending topics (Weibo, Toutiao, Baidu).')
    ap.add_argument('--sources', default='weibo,toutiao,baidu', help='Comma-separated CN sources (default: weibo,toutiao,baidu).')
    ap.add_argument('--query', default='', help='Optional keyword filter for CN hot boards.')
    ap.add_argument('--window-days', type=int, default=7, help='Lookback window metadata in days (default 7).')
    ap.add_argument('--limit', type=int, default=20, help='Maximum merged items to return (default 20).')
    ap.add_argument('--envelope', action='store_true', help='Emit content-ops-signal-envelope/1 JSON for signal_gate.py ingest.')
    ap.add_argument('--dry-run', action='store_true', help='Print source endpoints without sending requests.')
    ap.add_argument('--json', action='store_true', help='Output structured JSON.')
    args = ap.parse_args(argv)

    requested = [s.strip().lower() for s in args.sources.split(',') if s.strip()]
    unknown = [s for s in requested if s not in SOURCE_FETCHERS]
    if unknown:
        print(f'Unknown CN sources: {", ".join(unknown)}. Valid: {", ".join(SOURCE_FETCHERS)}', file=sys.stderr)
        return 2
    selected = [(name, SOURCE_FETCHERS[name]) for name in requested]

    if args.dry_run:
        print(json.dumps({
            'dryRun': True,
            'region': 'cn',
            'query': args.query,
            'sources': {name: ENDPOINTS[name] for name, _ in selected},
        }, indent=2, ensure_ascii=False))
        return 0

    all_items: list[dict] = []
    ok_sources: list[str] = []
    failed_sources: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=len(selected)) as pool:
        futs = {pool.submit(fn, args.query): name for name, fn in selected}
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                rows = fut.result()
                if rows:
                    ok_sources.append(name)
                    all_items.extend(rows)
                else:
                    failed_sources[name] = 'empty response'
            except Exception as exc:
                failed_sources[name] = str(exc)

    merged = normalize_and_merge(all_items, max(1, args.limit))
    if args.envelope:
        envelope = {
            'schema': 'content-ops-signal-envelope/1',
            'generatedAt': _iso_utc_now(),
            'region': 'cn',
            'query': args.query,
            'windowDays': args.window_days,
            'provenance': 'public_api',
            'source': ','.join(sorted(ok_sources)) or 'cn_public',
            'status': 'ok' if ok_sources and not failed_sources else ('partial' if ok_sources else 'error'),
            'sourcesOk': sorted(ok_sources),
            'sourcesFailed': failed_sources,
            'items': merged,
        }
        print(json.dumps(envelope, indent=2, ensure_ascii=False))
        return 0 if merged else 1

    tz = timezone(timedelta(hours=8))
    payload = {
        'timestamp': datetime.now(tz).isoformat(),
        'region': 'cn',
        'query': args.query,
        'sourcesOk': sorted(ok_sources),
        'sourcesFailed': failed_sources,
        'count': len(merged),
        'items': merged,
    }
    if not merged:
        payload['fallbackHint'] = 'All CN live boards failed; fall back to built-in web_search.'
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"CN Hotspots: {len(merged)} items from {', '.join(sorted(ok_sources)) or 'none'}")
        for idx, item in enumerate(merged, start=1):
            print(f"  {idx:2d}. [{item['source']}] ({item['hotNormalized']}) {item['title']}")
    return 0 if merged else 1


if __name__ == '__main__':
    sys.exit(main())
