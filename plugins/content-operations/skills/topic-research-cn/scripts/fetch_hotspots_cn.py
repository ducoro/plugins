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


def fetch_json(url: str, extra_headers: dict | None = None, timeout: int = 10):
    req = urllib.request.Request(url, headers={**HEADERS, **(extra_headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8', errors='replace'))


def fetch_weibo() -> list[dict]:
    data = fetch_json(ENDPOINTS['weibo'], {'Referer': 'https://weibo.com/'})
    items = []
    for entry in data.get('data', {}).get('realtime', []):
        note = str(entry.get('note') or '').strip()
        if not note:
            continue
        items.append({
            'title': note,
            'source': 'weibo',
            'hot': int(entry.get('num') or 0),
            'url': f'https://s.weibo.com/weibo?q={urllib.parse.quote("#" + note + "#")}',
            'tag': str(entry.get('label_name') or ''),
        })
    return items


def fetch_toutiao() -> list[dict]:
    data = fetch_json(ENDPOINTS['toutiao'])
    items = []
    for entry in data.get('data', []):
        title = str(entry.get('Title') or '').strip()
        if not title:
            continue
        items.append({
            'title': title,
            'source': 'toutiao',
            'hot': int(entry.get('HotValue') or 0),
            'url': str(entry.get('Url') or ''),
            'tag': '',
        })
    return items


def fetch_baidu() -> list[dict]:
    data = fetch_json(ENDPOINTS['baidu'])
    items = []
    for card in data.get('data', {}).get('cards', []):
        content = card.get('content', [])
        if not content:
            continue
        entries = content[0].get('content', []) if isinstance(content[0], dict) else content
        for entry in entries:
            word = str(entry.get('word') or '').strip()
            if not word:
                continue
            items.append({
                'title': word,
                'source': 'baidu',
                'hot': int(entry.get('hotScore') or 0),
                'url': str(entry.get('url') or ''),
                'tag': '',
            })
    return items


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
    ap.add_argument('--limit', type=int, default=20, help='Maximum merged items to return (default 20).')
    ap.add_argument('--dry-run', action='store_true', help='Print source endpoints without sending requests.')
    ap.add_argument('--json', action='store_true', help='Output structured JSON.')
    args = ap.parse_args(argv)

    selected = [('weibo', fetch_weibo), ('toutiao', fetch_toutiao), ('baidu', fetch_baidu)]
    if args.dry_run:
        print(json.dumps({'dryRun': True, 'region': 'cn', 'sources': ENDPOINTS}, indent=2, ensure_ascii=False))
        return 0

    all_items: list[dict] = []
    ok_sources: list[str] = []
    failed_sources: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=len(selected)) as pool:
        futs = {pool.submit(fn): name for name, fn in selected}
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
    tz = timezone(timedelta(hours=8))
    payload = {
        'timestamp': datetime.now(tz).isoformat(),
        'region': 'cn',
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
