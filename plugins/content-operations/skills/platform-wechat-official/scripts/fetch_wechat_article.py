#!/usr/bin/env python3
"""Zero-dependency WeChat article HTML -> clean Markdown extractor (plain HTTP or local --file; never bypasses CAPTCHA)."""
from __future__ import annotations

import argparse
import html as html_lib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import urllib.request

UA = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)


def has_wechat_content(page_html: str) -> bool:
    return bool(re.search(r'id=["\']js_content["\']', page_html, re.I))


def fetch_public_html(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode('utf-8', errors='replace')


def extract_meta(page_html: str) -> dict:
    title = ''
    for pat in (
        r'var\s+msg_title\s*=\s*[\'"]([^\'"]+)[\'"]',
        r'<h1[^>]*id=["\']activity-name["\'][^>]*>(.*?)</h1>',
        r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']',
        r'<title[^>]*>(.*?)</title>',
    ):
        m = re.search(pat, page_html, re.S | re.I)
        if m:
            title = re.sub(r'\s+', ' ', html_lib.unescape(re.sub(r'<[^>]+>', '', m.group(1)))).strip()
            if title:
                break

    account = ''
    for pat in (
        r'var\s+nickname\s*=\s*htmlDecode\(["\']([^"\']+)["\']\)',
        r'<a[^>]*id=["\']js_name["\'][^>]*>(.*?)</a>',
        r'<meta[^>]*name=["\']author["\'][^>]*content=["\']([^"\']+)["\']',
    ):
        m = re.search(pat, page_html, re.S | re.I)
        if m:
            account = re.sub(r'\s+', ' ', html_lib.unescape(re.sub(r'<[^>]+>', '', m.group(1)))).strip()
            if account:
                break
    return {'title': title, 'account': account}


def slice_js_content(page_html: str) -> str:
    """Return inner HTML of #js_content if present, else <body>, else full input."""
    m = re.search(r'<div[^>]*id=["\']js_content["\'][^>]*>', page_html, re.I)
    if m:
        start = m.end()
        depth = 1
        for tok in re.finditer(r'<(/?)div\b[^>]*>', page_html[start:], re.I):
            depth += -1 if tok.group(1) == '/' else 1
            if depth == 0:
                return page_html[start:start + tok.start()]
        return page_html[start:]
    bm = re.search(r'<body[^>]*>(.*)</body>', page_html, re.S | re.I)
    return bm.group(1) if bm else page_html


class _WeChatToMarkdown(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []
        self.skip_depth = 0
        self.in_pre = False
        self.in_blockquote = False
        self.images: list[str] = []

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        amap = dict(attrs)
        if t in ('script', 'style', 'noscript', 'svg'):
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if t in ('h1', 'h2', 'h3', 'h4'):
            self.chunks.append('\n\n' + '#' * int(t[1]) + ' ')
        elif t in ('p', 'section', 'div'):
            self.chunks.append('\n\n')
        elif t == 'br':
            self.chunks.append('\n')
        elif t == 'blockquote':
            self.in_blockquote = True
            self.chunks.append('\n\n> ')
        elif t == 'li':
            self.chunks.append('\n- ')
        elif t == 'pre':
            self.in_pre = True
            self.chunks.append('\n\n```\n')
        elif t == 'code' and not self.in_pre:
            self.chunks.append('`')
        elif t in ('strong', 'b'):
            self.chunks.append('**')
        elif t in ('em', 'i'):
            self.chunks.append('*')
        elif t == 'img':
            src = (amap.get('data-src') or amap.get('src') or '').strip()
            alt = (amap.get('alt') or '').strip()
            if src:
                self.images.append(src)
                self.chunks.append(f'\n\n![{alt}]({src})\n\n')

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in ('script', 'style', 'noscript', 'svg'):
            if self.skip_depth:
                self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if t in ('h1', 'h2', 'h3', 'h4', 'p', 'section', 'div'):
            self.chunks.append('\n')
        elif t == 'blockquote':
            self.in_blockquote = False
            self.chunks.append('\n\n')
        elif t == 'pre':
            self.in_pre = False
            self.chunks.append('\n```\n\n')
        elif t == 'code' and not self.in_pre:
            self.chunks.append('`')
        elif t in ('strong', 'b'):
            self.chunks.append('**')
        elif t in ('em', 'i'):
            self.chunks.append('*')

    def handle_data(self, data):
        if self.skip_depth:
            return
        if self.in_pre:
            self.chunks.append(data)
            return
        cleaned = re.sub(r'[ \t\r\n]+', ' ', data)
        if cleaned.strip():
            self.chunks.append(cleaned)


def html_to_markdown(page_html: str) -> dict:
    meta = extract_meta(page_html)
    body_html = slice_js_content(page_html)
    parser = _WeChatToMarkdown()
    parser.feed(body_html)
    raw_md = ''.join(parser.chunks)
    # Collapse empty bold/italic artifacts and extra blank lines
    raw_md = re.sub(r'\*\*\s*\*\*', '', raw_md)
    raw_md = re.sub(r'\n[ \t]+', '\n', raw_md)
    raw_md = re.sub(r'\n{3,}', '\n\n', raw_md).strip()
    if meta['title'] and not raw_md.startswith('# '):
        raw_md = f"# {meta['title']}\n\n{raw_md}"
    return {
        'title': meta['title'],
        'account': meta['account'],
        'imageCount': len(parser.images),
        'images': parser.images,
        'markdown': raw_md,
        'charCount': len(re.sub(r'\s+', '', raw_md)),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Extract a public WeChat article (URL or saved HTML file) into clean Markdown.')
    ap.add_argument('url', nargs='?', help='Public mp.weixin.qq.com article URL (plain HTTP only; stops on verification gate).')
    ap.add_argument('--file', help='Path to locally saved article HTML file (100% reliable when URL triggers verification).')
    ap.add_argument('-o', '--output', help='Optional path to write Markdown output.')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)

    if not args.url and not args.file:
        ap.error('Provide either a URL or --file <saved.html>')

    if args.file:
        fp = Path(args.file).expanduser().resolve()
        if not fp.is_file():
            print(f'Error: file not found: {fp}', file=sys.stderr)
            return 1
        page_html = fp.read_text(encoding='utf-8', errors='replace')
    else:
        try:
            page_html = fetch_public_html(args.url)
        except Exception as exc:
            print(f'Error: HTTP fetch failed: {exc}', file=sys.stderr)
            return 1
        if not has_wechat_content(page_html):
            out = {
                'ok': False,
                'verificationRequired': True,
                'url': args.url,
                'message': (
                    'WeChat returned a verification page instead of #js_content. '
                    'Do not bypass anti-bot gates: open the URL in a real browser, save the page as HTML, '
                    'and re-run with --file <saved.html>.'
                ),
            }
            print(json.dumps(out, indent=2, ensure_ascii=False) if args.json else out['message'], file=sys.stderr if not args.json else sys.stdout)
            return 2

    res = html_to_markdown(page_html)
    out_path = None
    if args.output:
        out_path = Path(args.output).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(res['markdown'] + '\n', encoding='utf-8')

    if args.json:
        print(json.dumps({**res, 'ok': True, 'outputPath': str(out_path) if out_path else None}, indent=2, ensure_ascii=False))
    elif out_path:
        print(f"Extracted '{res['title'] or 'article'}' ({res['charCount']} chars) -> {out_path}")
    else:
        print(res['markdown'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
