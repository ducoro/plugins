#!/usr/bin/env python3
"""Zero-dependency SEO keyword demand probe (Baidu OpenSearch + 360 search suggestions)."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    ),
}
BAIDU_SU = 'https://suggestion.baidu.com/su'
SO360_SU = 'https://sug.so.360.cn/suggest'


def fetch_json(url: str, timeout: int = 8):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8', errors='replace'))


def baidu_suggestions(keyword: str) -> list[str]:
    url = f"{BAIDU_SU}?{urllib.parse.urlencode({'wd': keyword, 'action': 'opensearch', 'ie': 'utf-8'})}"
    try:
        data = fetch_json(url)
        if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
            return [str(x).strip() for x in data[1] if str(x).strip()]
    except Exception:
        pass
    return []


def so360_suggestions(keyword: str) -> list[str]:
    url = f"{SO360_SU}?{urllib.parse.urlencode({'word': keyword, 'encodein': 'utf-8', 'encodeout': 'utf-8', 'format': 'json'})}"
    try:
        data = fetch_json(url)
        return [str(item.get('word') or '').strip() for item in data.get('result', []) if str(item.get('word') or '').strip()]
    except Exception:
        pass
    return []


def analyze_keyword(keyword: str) -> dict:
    b = baidu_suggestions(keyword)
    s = so360_suggestions(keyword)
    b_score = min(len(b), 10)
    s_score = min(len(s), 10)
    related = list(dict.fromkeys(b + s))
    return {
        'keyword': keyword,
        'seoScore': round((b_score + s_score) / 2.0, 1),
        'baiduScore': b_score,
        'so360Score': s_score,
        'baiduSuggestions': b[:8],
        'so360Suggestions': s[:8],
        'relatedKeywords': related[:12],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Probe real search autocomplete suggestions for keyword demand.')
    ap.add_argument('keywords', nargs='+', help='One or more keywords to analyze.')
    ap.add_argument('--dry-run', action='store_true', help='Preview request URLs without network calls.')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)

    if args.dry_run:
        out = {
            'dryRun': True,
            'keywords': args.keywords,
            'endpoints': [BAIDU_SU, SO360_SU],
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    results = [analyze_keyword(kw) for kw in args.keywords]
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for r in results:
            print(f"{r['keyword']}: {r['seoScore']}/10 (Baidu {r['baiduScore']}, 360 {r['so360Score']})")
            if r['relatedKeywords']:
                print(f"  Related: {', '.join(r['relatedKeywords'][:6])}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
