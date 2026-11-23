#!/usr/bin/env python3
"""Zero-dependency real-time Global trend radar (Hacker News and Lobsters)."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import sys
import urllib.request

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/plain, */*',
}

ENDPOINTS = {
    'hackernews': 'https://hacker-news.firebaseio.com/v0/topstories.json',
    'lobsters': 'https://lobste.rs/hottest.json',
}
HN_ITEM_TMPL = 'https://hacker-news.firebaseio.com/v0/item/{id}.json'


def fetch_json(url: str, timeout: int = 10):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8', errors='replace'))


def fetch_hackernews(limit: int = 15) -> list[dict]:
    ids = fetch_json(ENDPOINTS['hackernews'])
    if not isinstance(ids, list):
        return []
    items = []
    for sid in ids[:limit]:
        try:
            entry = fetch_json(HN_ITEM_TMPL.format(id=sid), timeout=6)
        except Exception:
            continue
        title = str(entry.get('title') or '').strip()
        if not title:
            continue
        items.append({
            'title': title,
            'source': 'hackernews',
            'hot': int(entry.get('score') or 0),
            'url': str(entry.get('url') or f'https://news.ycombinator.com/item?id={sid}'),
            'tag': '',
        })
    return items


def fetch_lobsters(limit: int = 15) -> list[dict]:
    data = fetch_json(ENDPOINTS['lobsters'])
    if not isinstance(data, list):
        return []
    items = []
    for entry in data[:limit]:
        title = str(entry.get('title') or '').strip()
        if not title:
            continue
        tags = entry.get('tags') or []
        items.append({
            'title': title,
            'source': 'lobsters',
            'hot': int(entry.get('score') or 0),
            'url': str(entry.get('url') or entry.get('short_id_url') or ''),
            'tag': ','.join(str(t) for t in tags[:3]),
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
    ap = argparse.ArgumentParser(description='Fetch live Global tech & builder trending topics (Hacker News, Lobsters).')
    ap.add_argument('--limit', type=int, default=20, help='Maximum merged items to return (default 20).')
    ap.add_argument('--dry-run', action='store_true', help='Print source endpoints without sending requests.')
    ap.add_argument('--json', action='store_true', help='Output structured JSON.')
    args = ap.parse_args(argv)

    selected = [('hackernews', fetch_hackernews), ('lobsters', fetch_lobsters)]
    if args.dry_run:
        print(json.dumps({'dryRun': True, 'region': 'global', 'sources': ENDPOINTS}, indent=2, ensure_ascii=False))
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
    payload = {
        'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'region': 'global',
        'sourcesOk': sorted(ok_sources),
        'sourcesFailed': failed_sources,
        'count': len(merged),
        'items': merged,
    }
    if not merged:
        payload['fallbackHint'] = 'All global feeds failed; fall back to built-in web_search.'
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"Global Hotspots: {len(merged)} items from {', '.join(sorted(ok_sources)) or 'none'}")
        for idx, item in enumerate(merged, start=1):
            print(f"  {idx:2d}. [{item['source']}] ({item['hotNormalized']}) {item['title']}")
    return 0 if merged else 1


if __name__ == '__main__':
    sys.exit(main())
