#!/usr/bin/env python3
"""Zero-dependency real-time Global trend & keyword radar (HN/Algolia, Lobsters, GitHub, Polymarket, DEV.to, arXiv, Google News)."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HEADERS = {
    'User-Agent': 'ducoro-content-ops/1.3 (+https://github.com/ducoro/plugins)',
    'Accept': 'application/json, application/atom+xml, application/rss+xml, text/plain, */*',
}

ENDPOINTS = {
    'hackernews': 'https://hacker-news.firebaseio.com/v0/topstories.json',
    'hackernews_search': 'https://hn.algolia.com/api/v1/search_by_date',
    'lobsters': 'https://lobste.rs/hottest.json',
    'github': 'https://api.github.com/search/repositories',
    'polymarket': 'https://gamma-api.polymarket.com/markets',
    'devto': 'https://dev.to/api/articles',
    'arxiv': 'https://export.arxiv.org/api/query',
    'gnews': 'https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en',
    'gnews_search': 'https://news.google.com/rss/search',
}
HN_ITEM_TMPL = 'https://hacker-news.firebaseio.com/v0/item/{id}.json'
ATOM_NS = {'atom': 'http://www.w3.org/2005/Atom'}


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _epoch_to_iso(ts: int | float | None) -> str:
    if not ts:
        return _iso_now()
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _rfc2822_to_iso(value: str | None) -> str:
    if not value:
        return _iso_now()
    try:
        dt = parsedate_to_datetime(value.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except (TypeError, ValueError):
        return _iso_now()


def fetch_text(url: str, extra_headers: dict | None = None, timeout: int = 12) -> str:
    req = urllib.request.Request(url, headers={**HEADERS, **(extra_headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode('utf-8', errors='replace')


def fetch_json(url: str, extra_headers: dict | None = None, timeout: int = 12):
    return json.loads(fetch_text(url, extra_headers=extra_headers, timeout=timeout))


def _matches_query(query: str, *fields: str) -> bool:
    q = (query or '').strip().lower()
    if not q:
        return True
    haystack = ' '.join(f or '' for f in fields).lower()
    if q in haystack:
        return True
    tokens = [tok for tok in q.split() if len(tok) >= 2]
    return bool(tokens) and all(tok in haystack for tok in tokens)


def fetch_hackernews(limit: int = 15, query: str = '', window_days: int = 30) -> list[dict]:
    if query.strip():
        cutoff_ts = int((datetime.now(timezone.utc) - timedelta(days=max(1, window_days))).timestamp())
        params = urllib.parse.urlencode({
            'query': query.strip(),
            'tags': 'story',
            'numericFilters': f'created_at_i>{cutoff_ts}',
            'hitsPerPage': min(max(limit, 5), 30),
        })
        data = fetch_json(f"{ENDPOINTS['hackernews_search']}?{params}")
        hits = data.get('hits', []) if isinstance(data, dict) else []
        items: list[dict] = []
        for h in hits[:limit]:
            if not isinstance(h, dict):
                continue
            title = str(h.get('title') or '').strip()
            oid = str(h.get('objectID') or '').strip()
            if not title or not oid:
                continue
            score = int(h.get('points') or 0)
            comments = int(h.get('num_comments') or 0)
            items.append({
                'title': title,
                'source': 'hackernews',
                'hot': score,
                'url': str(h.get('url') or f'https://news.ycombinator.com/item?id={oid}'),
                'author': str(h.get('author') or ''),
                'snippet': str(h.get('story_text') or '')[:400],
                'publishedAt': str(h.get('created_at') or _epoch_to_iso(h.get('created_at_i'))),
                'engagement': {'score': score, 'comments': comments},
                'tag': '',
                'isSeedListing': True,
                'isPrimarySource': False,
            })
        return items

    ids = fetch_json(ENDPOINTS['hackernews'])
    if not isinstance(ids, list):
        return []
    items = []
    for sid in ids[:limit]:
        try:
            entry = fetch_json(HN_ITEM_TMPL.format(id=sid), timeout=6)
        except Exception:
            continue
        if not isinstance(entry, dict):
            continue
        title = str(entry.get('title') or '').strip()
        if not title:
            continue
        score = int(entry.get('score') or 0)
        comments = int(entry.get('descendants') or 0)
        items.append({
            'title': title,
            'source': 'hackernews',
            'hot': score,
            'url': str(entry.get('url') or f'https://news.ycombinator.com/item?id={sid}'),
            'author': str(entry.get('by') or ''),
            'snippet': '',
            'publishedAt': _epoch_to_iso(entry.get('time')),
            'engagement': {'score': score, 'comments': comments},
            'tag': '',
            'isSeedListing': True,
            'isPrimarySource': False,
        })
    return items


def fetch_lobsters(limit: int = 15, query: str = '', window_days: int = 30) -> list[dict]:
    data = fetch_json(ENDPOINTS['lobsters'])
    if not isinstance(data, list):
        return []
    items: list[dict] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get('title') or '').strip()
        tags = entry.get('tags') or []
        tag_str = ','.join(str(t) for t in tags[:4])
        if not title or not _matches_query(query, title, tag_str):
            continue
        score = int(entry.get('score') or 0)
        comments = int(entry.get('comment_count') or 0)
        submitter = entry.get('submitter_user')
        author = submitter.get('username', '') if isinstance(submitter, dict) else str(submitter or '')
        items.append({
            'title': title,
            'source': 'lobsters',
            'hot': score,
            'url': str(entry.get('url') or entry.get('short_id_url') or ''),
            'author': author,
            'snippet': str(entry.get('description_plain') or '')[:400],
            'publishedAt': str(entry.get('created_at') or _iso_now()),
            'engagement': {'score': score, 'comments': comments},
            'tag': tag_str,
            'isSeedListing': True,
            'isPrimarySource': False,
        })
        if len(items) >= limit:
            break
    return items


def fetch_github(limit: int = 12, query: str = '', window_days: int = 30) -> list[dict]:
    since_days = min(max(window_days, 1), 30) if query else 7
    since_date = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime('%Y-%m-%d')
    q_expr = f'{query.strip()} pushed:>={since_date}' if query.strip() else f'created:>={since_date} stars:>25'
    url = f"{ENDPOINTS['github']}?{urllib.parse.urlencode({'q': q_expr, 'sort': 'stars', 'order': 'desc', 'per_page': min(limit, 25)})}"
    data = fetch_json(url, extra_headers={'Accept': 'application/vnd.github+json'})
    rows = data.get('items', []) if isinstance(data, dict) else []
    items: list[dict] = []
    for repo in rows[:limit]:
        if not isinstance(repo, dict):
            continue
        full_name = str(repo.get('full_name') or '').strip()
        desc = str(repo.get('description') or '').strip()
        html_url = str(repo.get('html_url') or '').strip()
        if not full_name or not html_url:
            continue
        stars = int(repo.get('stargazers_count') or 0)
        forks = int(repo.get('forks_count') or 0)
        owner = repo.get('owner') if isinstance(repo.get('owner'), dict) else {}
        items.append({
            'title': f'{full_name}: {desc[:110]}' if desc else full_name,
            'source': 'github',
            'hot': stars,
            'url': html_url,
            'author': str(owner.get('login') or ''),
            'snippet': desc[:400],
            'publishedAt': str(repo.get('pushed_at') or repo.get('updated_at') or repo.get('created_at') or _iso_now()),
            'engagement': {'likes': stars, 'shares': forks, 'score': stars},
            'tag': str(repo.get('language') or ''),
            'isSeedListing': True,
            'isPrimarySource': True,
        })
    return items


def fetch_polymarket(limit: int = 12, query: str = '', window_days: int = 30) -> list[dict]:
    params = urllib.parse.urlencode({
        'active': 'true', 'closed': 'false', 'order': 'volume24hr', 'ascending': 'false',
        'limit': max(limit * 2, 20) if query else limit,
    })
    data = fetch_json(f"{ENDPOINTS['polymarket']}?{params}")
    if not isinstance(data, list):
        return []
    items: list[dict] = []
    for market in data:
        if not isinstance(market, dict):
            continue
        question = str(market.get('question') or '').strip()
        desc = str(market.get('description') or '').strip()
        if not question or not _matches_query(query, question, desc):
            continue
        events = market.get('events') if isinstance(market.get('events'), list) else []
        slug = (events[0].get('slug') if events and isinstance(events[0], dict) else None) or market.get('slug') or ''
        url = f'https://polymarket.com/event/{slug}' if slug else 'https://polymarket.com/'
        vol24 = float(market.get('volume24hr') or 0.0)
        items.append({
            'title': question,
            'source': 'polymarket',
            'hot': int(round(vol24)),
            'url': url,
            'author': 'polymarket',
            'snippet': desc[:400],
            'publishedAt': str(market.get('updatedAt') or market.get('createdAt') or _iso_now()),
            'engagement': {'volume24hr': round(vol24, 2), 'score': int(round(vol24))},
            'tag': 'prediction-market',
            'isSeedListing': True,
            'isPrimarySource': False,
        })
        if len(items) >= limit:
            break
    return items


def fetch_devto(limit: int = 12, query: str = '', window_days: int = 30) -> list[dict]:
    params = urllib.parse.urlencode({'top': min(max(window_days, 1), 30), 'per_page': 30 if query else min(limit, 25)})
    data = fetch_json(f"{ENDPOINTS['devto']}?{params}")
    if not isinstance(data, list):
        return []
    items: list[dict] = []
    for art in data:
        if not isinstance(art, dict):
            continue
        title = str(art.get('title') or '').strip()
        tags = art.get('tag_list') or []
        tag_str = ','.join(tags) if isinstance(tags, list) else str(tags)
        desc = str(art.get('description') or '').strip()
        url = str(art.get('url') or '').strip()
        if not title or not url or not _matches_query(query, title, desc, tag_str):
            continue
        likes = int(art.get('public_reactions_count') or 0)
        comments = int(art.get('comments_count') or 0)
        user = art.get('user') if isinstance(art.get('user'), dict) else {}
        items.append({
            'title': title,
            'source': 'devto',
            'hot': likes,
            'url': url,
            'author': str(user.get('username') or ''),
            'snippet': desc[:400],
            'publishedAt': str(art.get('published_at') or _iso_now()),
            'engagement': {'likes': likes, 'comments': comments, 'score': likes},
            'tag': tag_str,
            'isSeedListing': True,
            'isPrimarySource': False,
        })
        if len(items) >= limit:
            break
    return items


def fetch_arxiv(limit: int = 10, query: str = '', window_days: int = 30) -> list[dict]:
    q = query.strip()
    if q:
        search_q = f'all:"{q}"' if (' ' in q and '"' not in q) else f'all:{q}'
    else:
        search_q = 'cat:cs.AI'
    params = urllib.parse.urlencode({
        'search_query': search_q,
        'sortBy': 'submittedDate',
        'sortOrder': 'descending',
        'max_results': min(limit, 20),
    })
    xml_text = fetch_text(f"{ENDPOINTS['arxiv']}?{params}")
    root = ET.fromstring(xml_text)
    items: list[dict] = []
    for entry in root.findall('atom:entry', ATOM_NS)[:limit]:
        title = ' '.join((entry.findtext('atom:title', '', ATOM_NS) or '').split())
        raw_id = (entry.findtext('atom:id', '', ATOM_NS) or '').strip()
        url = raw_id.replace('http://', 'https://', 1) if raw_id.startswith('http://') else raw_id
        published = (entry.findtext('atom:published', '', ATOM_NS) or entry.findtext('atom:updated', '', ATOM_NS) or _iso_now()).strip()
        summary = ' '.join((entry.findtext('atom:summary', '', ATOM_NS) or '').split())[:400]
        first_author = entry.findtext('atom:author/atom:name', '', ATOM_NS) or ''
        if not title or not url:
            continue
        items.append({
            'title': title,
            'source': 'arxiv',
            'hot': 0,
            'url': url,
            'author': first_author.strip(),
            'snippet': summary,
            'publishedAt': published,
            'engagement': {'score': 0},
            'tag': 'paper',
            'isSeedListing': True,
            'isPrimarySource': True,
        })
    return items


def fetch_gnews(limit: int = 12, query: str = '', window_days: int = 30) -> list[dict]:
    q = query.strip()
    if q:
        q_term = f'"{q}"' if (' ' in q and '"' not in q) else q
        params = urllib.parse.urlencode({
            'q': f'{q_term} when:{max(1, min(window_days, 90))}d',
            'hl': 'en-US',
            'gl': 'US',
            'ceid': 'US:en',
        })
        url = f"{ENDPOINTS['gnews_search']}?{params}"
    else:
        url = ENDPOINTS['gnews']
    xml_text = fetch_text(url)
    root = ET.fromstring(xml_text)
    items: list[dict] = []
    for rank, entry in enumerate(root.findall('.//item')[:limit]):
        title = ' '.join((entry.findtext('title') or '').split())
        link = (entry.findtext('link') or '').strip()
        pub_date = _rfc2822_to_iso(entry.findtext('pubDate'))
        publisher = (entry.findtext('source') or 'google-news').strip()
        if not title or not link:
            continue
        items.append({
            'title': title,
            'source': 'gnews',
            'hot': max(1, limit - rank),
            'url': link,
            'author': publisher,
            'snippet': '',
            'publishedAt': pub_date,
            'engagement': {'score': max(1, limit - rank)},
            'tag': 'news',
            'isSeedListing': True,
            'isPrimarySource': False,
        })
    return items


SOURCE_FETCHERS = {
    'hackernews': fetch_hackernews,
    'lobsters': fetch_lobsters,
    'github': fetch_github,
    'polymarket': fetch_polymarket,
    'devto': fetch_devto,
    'arxiv': fetch_arxiv,
    'gnews': fetch_gnews,
}


def normalize_and_merge(items: list[dict], limit: int) -> list[dict]:
    seen: set[str] = set()
    deduped: list[dict] = []
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
    ap = argparse.ArgumentParser(
        description='Fetch live Global trend & keyword signals (HN/Algolia, Lobsters, GitHub, Polymarket, DEV.to, arXiv, Google News).'
    )
    ap.add_argument(
        '--sources',
        default='hackernews,lobsters,github,polymarket,devto,arxiv,gnews',
        help='Comma-separated sources to query (default: all 7 verified keyless sources).',
    )
    ap.add_argument('--query', default='', help='Optional topic/entity keyword query.')
    ap.add_argument('--window-days', type=int, default=30, help='Lookback window in days (default 30).')
    ap.add_argument('--limit', type=int, default=20, help='Maximum merged items to return (default 20).')
    ap.add_argument('--envelope', action='store_true', help='Emit content-ops-signal-envelope/1 JSON for signal_gate.py ingest.')
    ap.add_argument('--dry-run', action='store_true', help='Print selected source endpoints without sending requests.')
    ap.add_argument('--json', action='store_true', help='Output structured JSON.')
    args = ap.parse_args(argv)

    requested = [s.strip().lower() for s in args.sources.split(',') if s.strip()]
    unknown = [s for s in requested if s not in SOURCE_FETCHERS]
    if unknown:
        print(f'Unknown global sources: {", ".join(unknown)}. Valid: {", ".join(SOURCE_FETCHERS)}', file=sys.stderr)
        return 2
    selected = [(name, SOURCE_FETCHERS[name]) for name in requested]

    if args.dry_run:
        print(json.dumps({
            'dryRun': True, 'region': 'global', 'query': args.query, 'windowDays': args.window_days,
            'sources': {name: ENDPOINTS[name] for name, _ in selected},
        }, indent=2, ensure_ascii=False))
        return 0

    per_source_limit = max(6, min(20, args.limit))
    all_items: list[dict] = []
    ok_sources: list[str] = []
    failed_sources: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=len(selected)) as pool:
        futs = {pool.submit(fn, per_source_limit, args.query, args.window_days): name for name, fn in selected}
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
    now_str = _iso_now()

    if args.envelope:
        print(json.dumps({
            'schema': 'content-ops-signal-envelope/1',
            'generatedAt': now_str,
            'region': 'global',
            'query': args.query,
            'windowDays': args.window_days,
            'provenance': 'public_api',
            'source': ','.join(sorted(ok_sources)) or 'global_public',
            'status': 'ok' if ok_sources and not failed_sources else ('partial' if ok_sources else 'error'),
            'sourcesOk': sorted(ok_sources),
            'sourcesFailed': failed_sources,
            'items': merged,
        }, indent=2, ensure_ascii=False))
        return 0 if merged else 1

    payload = {
        'timestamp': now_str, 'region': 'global', 'query': args.query,
        'sourcesOk': sorted(ok_sources), 'sourcesFailed': failed_sources,
        'count': len(merged), 'items': merged,
    }
    if not merged:
        payload['fallbackHint'] = 'All global feeds failed; use Ducoro Connectors (ducoro-cli mcp catalog) or built-in web_search.'
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"Global Hotspots: {len(merged)} items from {', '.join(sorted(ok_sources)) or 'none'}")
        for idx, item in enumerate(merged, start=1):
            print(f"  {idx:2d}. [{item['source']}] ({item['hotNormalized']}) {item['title']}")
    return 0 if merged else 1


if __name__ == '__main__':
    sys.exit(main())
