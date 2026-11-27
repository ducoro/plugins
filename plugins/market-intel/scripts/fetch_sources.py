#!/usr/bin/env python3
"""Fetch live public intelligence from verified keyless sources into market-intel-signal/1."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

DEFAULT_UA = 'DucoroMarketIntel/1.0 (+https://ducoro.ai)'
SEC_UA = 'DucoroMarketIntel contact@ducoro.ai'
SUPPORTED_KINDS = {
    'webpage', 'rss', 'github_releases', 'appstore_ios', 'npm', 'pypi',
    'greenhouse_jobs', 'ashby_jobs', 'lever_jobs', 'sec_edgar', 'hn_algolia',
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


class _TextExtractor(HTMLParser):
    SKIP_TAGS = {'script', 'style', 'noscript', 'svg', 'template'}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.title = ''
        self._in_title = False
        self.lines: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        t = tag.lower()
        if t in self.SKIP_TAGS:
            self._skip_depth += 1
        elif t == 'title':
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        elif t == 'title':
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        cleaned = re.sub(r'\s+', ' ', data).strip()
        if not cleaned:
            return
        if self._in_title and not self.title:
            self.title = cleaned
        self.lines.append(cleaned)


def http_get(url: str, *, sec: bool = False, extra_headers: dict[str, str] | None = None, timeout: int = 15) -> tuple[int, str]:
    headers = {'User-Agent': SEC_UA if sec else DEFAULT_UA, 'Accept': '*/*'}
    if extra_headers:
        headers.update(extra_headers)
    last_exc: Exception | None = None
    for attempt in range(2):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read(2_000_000)
                charset = resp.headers.get_content_charset() or 'utf-8'
                return resp.status, raw.decode(charset, errors='replace')
        except (urllib.error.URLError, ssl.SSLError, TimeoutError, OSError) as exc:
            last_exc = exc
            if isinstance(exc, urllib.error.HTTPError) and 400 <= exc.code < 500:
                raise
            if attempt == 0:
                time.sleep(0.5)
    assert last_exc is not None
    raise last_exc


def _strip_ns(tag: str) -> str:
    return tag.split('}', 1)[-1] if '}' in tag else tag


def parse_rss_or_atom(xml_text: str, limit: int = 10) -> list[dict]:
    root = ET.fromstring(xml_text)
    items: list[dict] = []
    for elem in root.iter():
        t = _strip_ns(elem.tag)
        if t in {'item', 'entry'}:
            title = ''
            link = ''
            published = ''
            summary = ''
            for child in elem:
                ct = _strip_ns(child.tag)
                text = (child.text or '').strip()
                if ct == 'title' and not title:
                    title = text
                elif ct == 'link' and not link:
                    link = child.attrib.get('href', '').strip() or text
                elif ct in {'pubDate', 'published', 'updated'} and not published:
                    published = text
                elif ct in {'description', 'summary', 'content'} and not summary:
                    summary = re.sub(r'<[^>]+>', ' ', text)
                    summary = re.sub(r'\s+', ' ', summary).strip()[:280]
            if title or link:
                items.append({'title': title, 'url': link, 'publishedAt': published, 'summary': summary})
            if len(items) >= limit:
                break
    return items


def fetch_single_source(entity_slug: str, source: dict, timeout: int = 15) -> dict:
    kind = source.get('kind', '')
    source_id = source.get('id') or kind
    observed_at = utc_now()
    if kind not in SUPPORTED_KINDS:
        return {
            'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind,
            'ok': False, 'error': f'Unsupported source kind: {kind}', 'observedAt': observed_at,
        }

    try:
        if kind == 'webpage':
            url = source['url']
            _, html = http_get(url, timeout=timeout)
            parser = _TextExtractor()
            parser.feed(html)
            lines = [ln for ln in parser.lines if len(ln) >= 2][:400]
            return {
                'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind, 'ok': True,
                'url': url, 'observedAt': observed_at,
                'structured': {'title': parser.title, 'lines': lines},
            }

        if kind == 'rss':
            url = source['url']
            _, body = http_get(url, timeout=timeout)
            entries = parse_rss_or_atom(body, limit=int(source.get('limit', 10)))
            return {
                'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind, 'ok': True,
                'url': url, 'observedAt': observed_at,
                'structured': {'entries': entries},
            }

        if kind == 'github_releases':
            repo = source['repo']
            limit = int(source.get('limit', 5))
            url = source.get('apiUrl') or f'https://api.github.com/repos/{repo}/releases?per_page={limit}'
            gh_headers = {'Authorization': f'Bearer {os.environ["GITHUB_TOKEN"]}'} if os.environ.get('GITHUB_TOKEN') else None
            try:
                _, body = http_get(url, extra_headers=gh_headers, timeout=timeout)
                releases = [
                    {
                        'tag': r.get('tag_name', ''),
                        'name': r.get('name') or r.get('tag_name', ''),
                        'publishedAt': r.get('published_at', ''),
                        'url': r.get('html_url', ''),
                        'notes': (r.get('body') or '').strip()[:400],
                    }
                    for r in json.loads(body)[:limit]
                ]
            except urllib.error.HTTPError as exc:
                if exc.code != 403 or source.get('apiUrl'):
                    raise
                # Official keyless GitHub Releases Atom feed fallback when anonymous REST quota is exhausted
                _, atom_xml = http_get(f'https://github.com/{repo}/releases.atom', timeout=timeout)
                releases = [
                    {
                        'tag': e['url'].rsplit('/', 1)[-1] if e['url'] else e['title'],
                        'name': e['title'],
                        'publishedAt': e['publishedAt'],
                        'url': e['url'],
                        'notes': e['summary'],
                    }
                    for e in parse_rss_or_atom(atom_xml, limit=limit)
                ]
            return {
                'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind, 'ok': True,
                'url': releases[0]['url'] if releases and releases[0]['url'] else f'https://github.com/{repo}/releases',
                'observedAt': observed_at,
                'structured': {'repo': repo, 'releases': releases},
            }

        if kind == 'appstore_ios':
            country = source.get('country', 'us')
            if source.get('apiUrl'):
                url = source['apiUrl']
            elif source.get('appId'):
                url = f'https://itunes.apple.com/lookup?id={urllib.parse.quote(str(source["appId"]))}&country={country}'
            else:
                url = f'https://itunes.apple.com/lookup?bundleId={urllib.parse.quote(str(source["bundleId"]))}&country={country}'
            _, body = http_get(url, timeout=timeout)
            results = json.loads(body).get('results', [])
            if not results:
                raise ValueError('No App Store result returned')
            app = results[0]
            return {
                'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind, 'ok': True,
                'url': app.get('trackViewUrl') or url, 'observedAt': observed_at,
                'structured': {
                    'trackName': app.get('trackName', ''),
                    'version': app.get('version', ''),
                    'currentVersionReleaseDate': app.get('currentVersionReleaseDate', ''),
                    'averageUserRating': app.get('averageUserRating'),
                    'userRatingCount': app.get('userRatingCount'),
                    'releaseNotes': (app.get('releaseNotes') or '')[:400],
                },
            }

        if kind == 'npm':
            pkg = source['package']
            url = source.get('apiUrl') or f'https://registry.npmjs.org/{urllib.parse.quote(pkg, safe="@/")}/latest'
            _, body = http_get(url, timeout=timeout)
            data = json.loads(body)
            return {
                'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind, 'ok': True,
                'url': f'https://www.npmjs.com/package/{pkg}', 'observedAt': observed_at,
                'structured': {
                    'package': pkg,
                    'version': data.get('version', ''),
                    'description': data.get('description', ''),
                    'homepage': data.get('homepage', ''),
                },
            }

        if kind == 'pypi':
            pkg = source['package']
            url = source.get('apiUrl') or f'https://pypi.org/pypi/{urllib.parse.quote(pkg)}/json'
            _, body = http_get(url, timeout=timeout)
            info = json.loads(body).get('info', {})
            return {
                'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind, 'ok': True,
                'url': info.get('package_url') or f'https://pypi.org/project/{pkg}/', 'observedAt': observed_at,
                'structured': {
                    'package': pkg,
                    'version': info.get('version', ''),
                    'summary': info.get('summary', ''),
                    'requiresPython': info.get('requires_python', ''),
                },
            }

        if kind == 'greenhouse_jobs':
            token = source['boardToken']
            url = source.get('apiUrl') or f'https://boards-api.greenhouse.io/v1/boards/{urllib.parse.quote(token)}/jobs'
            _, body = http_get(url, timeout=timeout)
            jobs = json.loads(body).get('jobs', [])
            roles = sorted({(j.get('title') or '').strip() for j in jobs if j.get('title')})
            return {
                'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind, 'ok': True,
                'url': f'https://boards.greenhouse.io/{token}', 'observedAt': observed_at,
                'structured': {'openCount': len(jobs), 'sampleTitles': roles[:50]},
            }

        if kind == 'ashby_jobs':
            slug = source['boardSlug']
            url = source.get('apiUrl') or f'https://api.ashbyhq.com/posting-api/job-board/{urllib.parse.quote(slug)}'
            _, body = http_get(url, timeout=timeout)
            jobs = json.loads(body).get('jobs', [])
            roles = sorted({(j.get('title') or '').strip() for j in jobs if j.get('title')})
            depts = sorted({(j.get('department') or '').strip() for j in jobs if j.get('department')})
            return {
                'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind, 'ok': True,
                'url': f'https://jobs.ashbyhq.com/{slug}', 'observedAt': observed_at,
                'structured': {'openCount': len(jobs), 'departments': depts[:30], 'sampleTitles': roles[:50]},
            }

        if kind == 'lever_jobs':
            slug = source['siteSlug']
            url = source.get('apiUrl') or f'https://api.lever.co/v0/postings/{urllib.parse.quote(slug)}?mode=json'
            _, body = http_get(url, timeout=timeout)
            jobs = json.loads(body)
            roles = sorted({(j.get('text') or '').strip() for j in jobs if j.get('text')})
            return {
                'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind, 'ok': True,
                'url': f'https://jobs.lever.co/{slug}', 'observedAt': observed_at,
                'structured': {'openCount': len(jobs), 'sampleTitles': roles[:50]},
            }

        if kind == 'sec_edgar':
            cik = str(source['cik']).zfill(10)
            url = source.get('apiUrl') or f'https://data.sec.gov/submissions/CIK{cik}.json'
            _, body = http_get(url, sec=True, timeout=timeout)
            data = json.loads(body)
            recent = data.get('filings', {}).get('recent', {})
            forms = recent.get('form', [])
            dates = recent.get('filingDate', [])
            accessions = recent.get('accessionNumber', [])
            docs = recent.get('primaryDocument', [])
            allowed = set(source.get('forms', ['10-K', '10-Q', '8-K', 'S-1']))
            filings = []
            for form, fdate, acc, doc in zip(forms, dates, accessions, docs):
                if allowed and form not in allowed:
                    continue
                acc_nodash = acc.replace('-', '')
                filings.append({
                    'form': form,
                    'filingDate': fdate,
                    'accessionNumber': acc,
                    'url': f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_nodash}/{doc}',
                })
                if len(filings) >= int(source.get('limit', 10)):
                    break
            return {
                'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind, 'ok': True,
                'url': f'https://www.sec.gov/edgar/browse/?CIK={cik}', 'observedAt': observed_at,
                'structured': {'companyName': data.get('name', ''), 'cik': cik, 'filings': filings},
            }

        if kind == 'hn_algolia':
            query = source['query']
            limit = int(source.get('limit', 10))
            url = source.get('apiUrl') or (
                f'https://hn.algolia.com/api/v1/search_by_date?query={urllib.parse.quote(query)}&tags=story&hitsPerPage={limit}'
            )
            _, body = http_get(url, timeout=timeout)
            hits = [
                {
                    'title': h.get('title', ''),
                    'url': h.get('url') or f'https://news.ycombinator.com/item?id={h.get("objectID", "")}',
                    'hnUrl': f'https://news.ycombinator.com/item?id={h.get("objectID", "")}',
                    'points': h.get('points', 0),
                    'comments': h.get('num_comments', 0),
                    'createdAt': h.get('created_at', ''),
                }
                for h in json.loads(body).get('hits', [])
            ]
            return {
                'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind, 'ok': True,
                'url': f'https://hn.algolia.com/?q={urllib.parse.quote(query)}', 'observedAt': observed_at,
                'structured': {'query': query, 'hits': hits},
            }
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        ssl.SSLError,
        OSError,
        ValueError,
        KeyError,
        ET.ParseError,
        json.JSONDecodeError,
    ) as exc:
        return {
            'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind,
            'ok': False, 'error': str(exc), 'observedAt': observed_at,
        }

    return {'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind, 'ok': False, 'error': 'Unhandled kind', 'observedAt': observed_at}


def fetch_watchlist(workspace: Path, *, entity_filter: str | None = None, timeout: int = 15) -> dict:
    workspace = workspace.expanduser().resolve()
    watchlist_path = workspace / 'watchlist.json'
    watchlist = json.loads(watchlist_path.read_text(encoding='utf-8'))
    records = []
    for entity in watchlist.get('entities', []):
        slug = entity['slug']
        if entity_filter and slug != entity_filter:
            continue
        for source in entity.get('sources', []):
            records.append(fetch_single_source(slug, source, timeout=timeout))

    return {
        'schemaVersion': 'market-intel-signal/1',
        'generatedAt': utc_now(),
        'dataDir': str(workspace),
        'totalSources': len(records),
        'okCount': sum(1 for r in records if r.get('ok')),
        'failedCount': sum(1 for r in records if not r.get('ok')),
        'records': records,
    }


def merge_captures(workspace: Path, capture_paths: list[Path]) -> dict:
    workspace = workspace.expanduser().resolve()
    records: list[dict] = []
    for raw_path in capture_paths:
        path = Path(raw_path).expanduser().resolve()
        doc = json.loads(path.read_text(encoding='utf-8'))
        if doc.get('schemaVersion') != 'market-intel-signal/1':
            raise ValueError(f'{path}: invalid schemaVersion; expected market-intel-signal/1')
        for rec in doc.get('records', []):
            if isinstance(rec, dict):
                records.append(rec)
    return {
        'schemaVersion': 'market-intel-signal/1',
        'generatedAt': utc_now(),
        'dataDir': str(workspace),
        'totalSources': len(records),
        'okCount': sum(1 for r in records if r.get('ok')),
        'failedCount': sum(1 for r in records if not r.get('ok')),
        'records': records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Fetch live public data for market-intel watchlist.')
    parser.add_argument('data_dir', metavar='<data-dir>', help='Path to market-intel <data-dir>')
    parser.add_argument('--entity', default=None, help='Optional single entity slug filter')
    parser.add_argument('--timeout', type=int, default=15, help='Per-request timeout in seconds')
    parser.add_argument('--merge', nargs='+', default=None, help='Merge multiple per-entity/external capture JSON files into one envelope')
    parser.add_argument('--out', default=None, help='Optional output JSON path')
    args = parser.parse_args()

    if args.merge:
        envelope = merge_captures(Path(args.data_dir), [Path(p) for p in args.merge])
    else:
        envelope = fetch_watchlist(Path(args.data_dir), entity_filter=args.entity, timeout=args.timeout)

    text = json.dumps(envelope, indent=2, ensure_ascii=False) + '\n'
    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding='utf-8')
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
