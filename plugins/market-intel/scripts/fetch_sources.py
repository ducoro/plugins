#!/usr/bin/env python3
"""Fetch live public intelligence from verified public sources into market-intel-signal/1."""
from __future__ import annotations

import argparse
import base64
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

DEFAULT_UA = 'DucoroMarketIntel/1.1 (+https://ducoro.ai)'
SEC_UA = 'DucoroMarketIntel contact@ducoro.ai'
SUPPORTED_KINDS = {
    'webpage', 'rss', 'github_releases', 'github_repo_activity', 'github_file',
    'github_trending', 'producthunt', 'appstore_ios', 'npm', 'pypi',
    'greenhouse_jobs', 'ashby_jobs', 'lever_jobs', 'sec_edgar', 'hn_algolia',
}

_PRODUCTHUNT_GRAPHQL_QUERY = """
query($first: Int!) {
  posts(first: $first, order: RANKING) {
    edges {
      node {
        id
        name
        tagline
        url
        votesCount
        commentsCount
        reviewsCount
        reviewsRating
        createdAt
      }
    }
  }
}
""".strip()


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


class _GitHubTrendingParser(HTMLParser):
    """Parse GitHub Trending <article class="Box-row"> rows with completeness tracking."""

    def __init__(self) -> None:
        super().__init__()
        self.expected_count = 0
        self.entries: list[dict] = []
        self._in_row = False
        self._row_depth = 0
        self._in_h2 = False
        self._in_p = False
        self._in_lang = False
        self._in_stars = False
        self._in_span = False
        self._cur: dict | None = None
        self._buf: list[str] = []

    def _flush_text(self) -> str:
        text = re.sub(r'\s+', ' ', ''.join(self._buf)).strip()
        self._buf.clear()
        return text

    def handle_starttag(self, tag: str, attrs) -> None:
        t = tag.lower()
        attr_map = dict(attrs)
        cls = attr_map.get('class', '')
        if t == 'article' and 'Box-row' in cls.split():
            self.expected_count += 1
            self._in_row = True
            self._row_depth = 1
            self._cur = {
                'repo': '', 'url': '', 'description': '', 'language': '',
                'stars': None, 'periodStars': None, 'periodLabel': '',
            }
            return
        if not self._in_row or self._cur is None:
            return
        self._row_depth += 1
        if t == 'h2':
            self._in_h2 = True
        elif t == 'a':
            href = (attr_map.get('href') or '').strip()
            if self._in_h2 and href.startswith('/') and not self._cur['repo']:
                parts = [p for p in href.strip('/').split('/') if p]
                if len(parts) == 2:
                    repo = f'{parts[0]}/{parts[1]}'
                    self._cur['repo'] = repo
                    self._cur['url'] = f'https://github.com/{repo}'
            elif href.endswith('/stargazers') and self._cur['stars'] is None:
                self._in_stars = True
                self._buf.clear()
        elif t == 'p' and not self._cur['description']:
            self._in_p = True
            self._buf.clear()
        elif t == 'span':
            if attr_map.get('itemprop') == 'programmingLanguage':
                self._in_lang = True
                self._buf.clear()
            else:
                self._in_span = True
                self._buf.clear()

    def handle_endtag(self, tag: str) -> None:
        if not self._in_row or self._cur is None:
            return
        t = tag.lower()
        if t == 'h2':
            self._in_h2 = False
        elif t == 'p' and self._in_p:
            self._cur['description'] = self._flush_text()
            self._in_p = False
        elif t == 'a' and self._in_stars:
            num = re.sub(r'[^0-9]', '', self._flush_text())
            self._cur['stars'] = int(num) if num else None
            self._in_stars = False
        elif t == 'span':
            if self._in_lang:
                self._cur['language'] = self._flush_text()
                self._in_lang = False
            elif self._in_span:
                text = self._flush_text()
                if 'star' in text.lower() and self._cur['periodStars'] is None:
                    m = re.search(r'([0-9][0-9,]*)\s+stars?', text, re.I)
                    if m:
                        self._cur['periodStars'] = int(m.group(1).replace(',', ''))
                        self._cur['periodLabel'] = text
                self._in_span = False
        self._row_depth -= 1
        if self._row_depth <= 0:
            if self._cur['repo']:
                self._cur['rank'] = len(self.entries) + 1
                self.entries.append(self._cur)
            self._in_row = False
            self._cur = None

    def handle_data(self, data: str) -> None:
        if self._in_p or self._in_lang or self._in_stars or self._in_span:
            self._buf.append(data)


def classify_error(exc: Exception) -> tuple[str, int | None]:
    """Classify fetch errors into actionable operational categories without over-claiming account bans."""
    msg = str(exc).lower()
    if isinstance(exc, urllib.error.HTTPError):
        code = int(exc.code)
        reason = str(getattr(exc, 'reason', '') or '').lower()
        combined = f'{reason} {msg}'
        if code == 429:
            return 'rate_limited', code
        if code == 401:
            return 'auth_required', code
        if code == 403:
            if any(tok in combined for tok in ('rate limit', 'too many requests', 'quota', 'secondary rate')):
                return 'rate_limited', code
            if any(tok in combined for tok in ('captcha', 'cloudflare', 'challenge', 'verify')):
                return 'challenge', code
            return 'access_denied', code
        if any(tok in combined for tok in ('captcha', 'cloudflare', 'challenge', 'verify')):
            return 'challenge', code
        return 'http_error', code
    if any(tok in msg for tok in ('captcha', 'cloudflare', 'risk_control', 'challenge', 'verification required')):
        return 'challenge', None
    if isinstance(exc, (TimeoutError, ssl.SSLError, urllib.error.URLError, OSError)):
        return 'network_timeout', None
    if isinstance(exc, (ET.ParseError, json.JSONDecodeError, ValueError, KeyError)):
        return 'parse_error', None
    return 'unknown', None


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


def http_post_json(url: str, payload: dict, *, extra_headers: dict[str, str] | None = None, timeout: int = 15) -> tuple[int, str]:
    headers = {'User-Agent': DEFAULT_UA, 'Accept': 'application/json', 'Content-Type': 'application/json'}
    if extra_headers:
        headers.update(extra_headers)
    body_bytes = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=body_bytes, headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(2_000_000)
        charset = resp.headers.get_content_charset() or 'utf-8'
        return resp.status, raw.decode(charset, errors='replace')


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


def _github_headers() -> dict[str, str] | None:
    token = os.environ.get('GITHUB_TOKEN', '').strip()
    return {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json'} if token else None


def fetch_single_source(entity_slug: str, source: dict, timeout: int = 15) -> dict:
    kind = source.get('kind', '')
    source_id = source.get('id') or kind
    observed_at = utc_now()
    if kind not in SUPPORTED_KINDS:
        return {
            'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind,
            'ok': False, 'errorKind': 'unsupported_kind',
            'error': f'Unsupported source kind: {kind}', 'observedAt': observed_at,
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
            gh_headers = _github_headers()
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

        if kind == 'github_repo_activity':
            repo = source['repo']
            limit = int(source.get('limit', 10))
            gh_headers = _github_headers()
            commits_url = source.get('commitsApiUrl') or f'https://api.github.com/repos/{repo}/commits?per_page={limit}'
            issues_url = source.get('issuesApiUrl') or f'https://api.github.com/repos/{repo}/issues?state=all&sort=updated&per_page={min(limit * 2, 100)}'

            _, commits_body = http_get(commits_url, extra_headers=gh_headers, timeout=timeout)
            raw_commits = json.loads(commits_body)
            commits = [
                {
                    'sha': str(c.get('sha', ''))[:12],
                    'message': ((c.get('commit') or {}).get('message') or '').splitlines()[0].strip()[:200],
                    'author': ((c.get('commit') or {}).get('author') or {}).get('name', ''),
                    'date': ((c.get('commit') or {}).get('author') or {}).get('date', ''),
                    'url': c.get('html_url', ''),
                }
                for c in raw_commits[:limit]
                if isinstance(c, dict)
            ]

            _, issues_body = http_get(issues_url, extra_headers=gh_headers, timeout=timeout)
            raw_issues = json.loads(issues_body)
            issues: list[dict] = []
            prs: list[dict] = []
            for item in raw_issues:
                if not isinstance(item, dict):
                    continue
                entry = {
                    'number': int(item.get('number', 0)),
                    'title': str(item.get('title', '')).strip()[:200],
                    'state': str(item.get('state', '')).lower(),
                    'author': ((item.get('user') or {}).get('login') or ''),
                    'authorAssociation': str(item.get('author_association', 'NONE')),
                    'comments': int(item.get('comments', 0) or 0),
                    'updatedAt': str(item.get('updated_at', '')),
                    'url': str(item.get('html_url', '')),
                    'labels': sorted(
                        str(lb.get('name', '')).strip()
                        for lb in (item.get('labels') or [])
                        if isinstance(lb, dict) and lb.get('name')
                    ),
                }
                if 'pull_request' in item:
                    if len(prs) < limit:
                        prs.append(entry)
                else:
                    if len(issues) < limit:
                        issues.append(entry)

            return {
                'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind, 'ok': True,
                'url': f'https://github.com/{repo}', 'observedAt': observed_at,
                'structured': {'repo': repo, 'commits': commits, 'issues': issues, 'prs': prs},
            }

        if kind == 'github_file':
            repo = source['repo']
            path = (source.get('path') or '').strip()
            ref = (source.get('ref') or '').strip()
            gh_headers = _github_headers()
            if source.get('apiUrl'):
                url = source['apiUrl']
            else:
                ep = (
                    f'https://api.github.com/repos/{repo}/contents/{urllib.parse.quote(path, safe="/")}'
                    if path else f'https://api.github.com/repos/{repo}/readme'
                )
                url = f'{ep}?ref={urllib.parse.quote(ref)}' if ref else ep
            _, body = http_get(url, extra_headers=gh_headers, timeout=timeout)
            data = json.loads(body)
            if not isinstance(data, dict) or not data.get('sha'):
                raise ValueError('Invalid GitHub file response: missing blob sha')
            resolved_path = str(data.get('path') or path or 'README.md')
            lines: list[str] = []
            if data.get('encoding') == 'base64' and data.get('content'):
                decoded = base64.b64decode(''.join(str(data['content']).split())).decode('utf-8', errors='replace')
                lines = [ln.strip() for ln in decoded.splitlines() if ln.strip()][:200]
            return {
                'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind, 'ok': True,
                'url': data.get('html_url') or f'https://github.com/{repo}/blob/{ref or "HEAD"}/{resolved_path}',
                'observedAt': observed_at,
                'structured': {
                    'repo': repo,
                    'path': resolved_path,
                    'ref': ref or 'default',
                    'blobSha': str(data['sha']),
                    'size': int(data.get('size', 0) or 0),
                    'lines': lines,
                },
            }

        if kind == 'github_trending':
            since = str(source.get('since', 'daily')).lower()
            if since not in {'daily', 'weekly', 'monthly'}:
                raise ValueError(f'Unsupported GitHub Trending since value: {since}')
            language = (source.get('language') or '').strip()
            spoken = (source.get('spokenLanguage') or '').strip()
            if source.get('apiUrl'):
                url = source['apiUrl']
            else:
                lang_seg = f'/{urllib.parse.quote(language)}' if language else ''
                qs = {'since': since}
                if spoken:
                    qs['spoken_language_code'] = spoken
                url = f'https://github.com/trending{lang_seg}?{urllib.parse.urlencode(qs)}'
            _, html = http_get(url, timeout=timeout)
            parser = _GitHubTrendingParser()
            parser.feed(html)
            if parser.expected_count == 0 or len(parser.entries) != parser.expected_count:
                raise ValueError(
                    f'Incomplete GitHub Trending parse: expected {parser.expected_count} rows, parsed {len(parser.entries)}'
                )
            return {
                'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind, 'ok': True,
                'url': url, 'observedAt': observed_at,
                'structured': {
                    'since': since,
                    'language': language,
                    'expectedCount': parser.expected_count,
                    'parsedCount': len(parser.entries),
                    'complete': True,
                    'entries': parser.entries,
                },
            }

        if kind == 'producthunt':
            limit = int(source.get('limit', 10))
            token = os.environ.get('PRODUCTHUNT_TOKEN', '').strip()
            if token and (source.get('graphqlUrl') or not source.get('apiUrl')):
                gql_url = source.get('graphqlUrl') or 'https://api.producthunt.com/v2/api/graphql'
                _, body = http_post_json(
                    gql_url,
                    {'query': _PRODUCTHUNT_GRAPHQL_QUERY, 'variables': {'first': limit}},
                    extra_headers={'Authorization': f'Bearer {token}'},
                    timeout=timeout,
                )
                payload = json.loads(body)
                if payload.get('errors'):
                    raise ValueError(f'Product Hunt GraphQL error: {payload["errors"]}')
                edges = (((payload.get('data') or {}).get('posts') or {}).get('edges') or [])
                posts = []
                for edge in edges[:limit]:
                    node = (edge or {}).get('node') or {}
                    posts.append({
                        'id': str(node.get('id', '')),
                        'name': str(node.get('name', '')).strip(),
                        'tagline': str(node.get('tagline', '')).strip(),
                        'url': str(node.get('url', '')).strip(),
                        'votesCount': int(node.get('votesCount', 0) or 0),
                        'commentsCount': int(node.get('commentsCount', 0) or 0),
                        'reviewsCount': int(node.get('reviewsCount', 0) or 0),
                        'reviewsRating': node.get('reviewsRating'),
                        'createdAt': str(node.get('createdAt', '')),
                    })
                return {
                    'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind, 'ok': True,
                    'url': 'https://www.producthunt.com/', 'observedAt': observed_at,
                    'structured': {'mode': 'graphql', 'posts': posts},
                }

            feed_url = source.get('apiUrl') or 'https://www.producthunt.com/feed'
            _, xml_body = http_get(feed_url, timeout=timeout)
            entries = parse_rss_or_atom(xml_body, limit=limit)
            posts = [
                {
                    'name': e['title'],
                    'tagline': e['summary'],
                    'url': e['url'],
                    'publishedAt': e['publishedAt'],
                }
                for e in entries
            ]
            return {
                'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind, 'ok': True,
                'url': feed_url, 'observedAt': observed_at,
                'structured': {'mode': 'rss', 'posts': posts},
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
        error_kind, http_status = classify_error(exc)
        err_rec = {
            'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind,
            'ok': False, 'errorKind': error_kind, 'error': str(exc), 'observedAt': observed_at,
        }
        if http_status is not None:
            err_rec['httpStatus'] = http_status
        return err_rec

    return {
        'entitySlug': entity_slug, 'sourceId': source_id, 'kind': kind,
        'ok': False, 'errorKind': 'unknown', 'error': 'Unhandled kind', 'observedAt': observed_at,
    }


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
