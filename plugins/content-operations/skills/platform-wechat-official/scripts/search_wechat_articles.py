#!/usr/bin/env python3
"""Zero-dependency Sogou WeChat article search (for topic demand density; stops cleanly on CAPTCHA)."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import html as html_lib
import http.cookiejar
import json
import re
import sys
import urllib.parse
import urllib.request

CST = timezone(timedelta(hours=8))
BOOTSTRAP_URL = 'https://v.sogou.com/v?ie=utf8&query=&p=40030600'
SEARCH_URL = 'https://weixin.sogou.com/weixin'
UA = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)


def detect_captcha(page_html: str) -> bool:
    low = page_html.lower()
    return ('antispider' in low) or ('seccode' in low) or ('验证码' in page_html and 'news-list' not in low)


def strip_tags(fragment: str) -> str:
    return re.sub(r'\s+', ' ', html_lib.unescape(re.sub(r'<[^>]+>', '', fragment))).strip()


def parse_sogou_results(page_html: str) -> list[dict]:
    items = []
    list_m = re.search(r'<ul[^>]*class="[^"]*news-list[^"]*"[^>]*>(.*?)</ul>', page_html, re.S | re.I)
    if not list_m:
        return items
    for li in re.findall(r'<li\b[^>]*>(.*?)</li>', list_m.group(1), re.S | re.I):
        t_m = re.search(r'<h3[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', li, re.S | re.I)
        if not t_m:
            continue
        href = html_lib.unescape(t_m.group(1).strip())
        if href.startswith('/'):
            href = f'https://weixin.sogou.com{href}'
        title = strip_tags(t_m.group(2))
        sum_m = re.search(r'<p[^>]*class="[^"]*txt-info[^"]*"[^>]*>(.*?)</p>', li, re.S | re.I)
        summary = strip_tags(sum_m.group(1)) if sum_m else ''
        acc_m = re.search(r'class="[^"]*(?:all-time-y2|account)[^"]*"[^>]*>(.*?)</', li, re.S | re.I)
        source = strip_tags(acc_m.group(1)) if acc_m else ''
        ts_m = re.search(r'timeConvert\([\'"]?(\d{10})[\'"]?\)', li) or re.search(r'(\d{10})', li)
        ts = int(ts_m.group(1)) if ts_m else 0
        published_at = datetime.fromtimestamp(ts, tz=CST).strftime('%Y-%m-%d %H:%M:%S') if ts else ''
        items.append({
            'title': title,
            'url': href,
            'summary': summary,
            'account': source,
            'timestamp': ts,
            'publishedAt': published_at,
        })
    return items


def fetch_pages(query: str, max_pages: int = 2) -> tuple[list[dict], bool]:
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [
        ('User-Agent', UA),
        ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'),
        ('Accept-Language', 'zh-CN,zh;q=0.9,en;q=0.8'),
        ('Referer', 'https://weixin.sogou.com/'),
    ]
    try:
        opener.open(BOOTSTRAP_URL, timeout=8).read()
    except Exception:
        pass

    collected: list[dict] = []
    for page in range(1, max_pages + 1):
        url = f"{SEARCH_URL}?{urllib.parse.urlencode({'type': '2', 'query': query, 'ie': 'utf8', 'page': str(page)})}"
        html = opener.open(url, timeout=12).read().decode('utf-8', errors='replace')
        if detect_captcha(html):
            return collected, True
        page_items = parse_sogou_results(html)
        if not page_items:
            break
        collected.extend(page_items)
    return collected, False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Search public WeChat articles via Sogou to inspect recent topic density.')
    ap.add_argument('query', help='Keyword to search.')
    ap.add_argument('--limit', type=int, default=10, help='Max results to return (default 10).')
    ap.add_argument('--days', type=int, default=0, help='Optional client-side recency filter in days (e.g. 7).')
    ap.add_argument('--pages', type=int, default=2, help='Max pages to scan (default 2, max 3).')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)

    if args.dry_run:
        print(json.dumps({'dryRun': True, 'query': args.query, 'endpoint': SEARCH_URL, 'days': args.days}, indent=2, ensure_ascii=False))
        return 0

    try:
        items, captcha = fetch_pages(args.query, max_pages=min(max(1, args.pages), 3))
    except Exception as exc:
        print(f'Error: Sogou WeChat search failed ({exc}); fall back to built-in web_search.', file=sys.stderr)
        return 1

    if args.days > 0:
        cutoff = int((datetime.now(CST) - timedelta(days=args.days)).timestamp())
        items = [it for it in items if it.get('timestamp', 0) >= cutoff]

    items = items[:max(1, args.limit)]
    out = {
        'query': args.query,
        'daysFilter': args.days,
        'captchaDetected': captcha,
        'count': len(items),
        'items': items,
    }
    if captcha:
        out['notice'] = 'Sogou triggered a CAPTCHA gate; stopped immediately without bypassing. Fall back to built-in web_search.'

    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(f"WeChat articles for '{args.query}': {len(items)} item(s) (captcha={captcha})")
        for idx, it in enumerate(items, start=1):
            print(f"  {idx:2d}. [{it['publishedAt'] or 'n/a'}] {it['title']} — {it['account']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
