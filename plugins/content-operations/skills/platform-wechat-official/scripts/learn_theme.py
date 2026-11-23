#!/usr/bin/env python3
"""Zero-dependency WeChat theme learner: extract a reusable theme JSON from an article URL or saved HTML."""
from __future__ import annotations

import argparse
from collections import Counter
import colorsys
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fetch_wechat_article as fwa  # noqa: E402


def parse_color_to_hex(raw: str) -> str | None:
    s = (raw or '').strip()
    if re.fullmatch(r'#[0-9a-fA-F]{6}', s):
        return s.lower()
    if re.fullmatch(r'#[0-9a-fA-F]{3}', s):
        return '#' + ''.join(ch * 2 for ch in s[1:].lower())
    m = re.match(r'rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})', s, re.I)
    if m:
        r, g, b = (max(0, min(255, int(m.group(i)))) for i in (1, 2, 3))
        return f'#{r:02x}{g:02x}{b:02x}'
    return None


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    s = h.lstrip('#')
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def is_neutral(h: str, threshold: int = 26) -> bool:
    r, g, b = hex_to_rgb(h)
    return max(r, g, b) - min(r, g, b) <= threshold


def lightness(h: str) -> float:
    r, g, b = hex_to_rgb(h)
    return colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)[1]


def adjust_lightness(h: str, target_l: float) -> str:
    r, g, b = hex_to_rgb(h)
    hue, _l, sat = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    nr, ng, nb = colorsys.hls_to_rgb(hue, max(0.0, min(1.0, target_l)), sat)
    return f'#{int(nr * 255):02x}{int(ng * 255):02x}{int(nb * 255):02x}'


def contrast_ratio(h1: str, h2: str) -> float:
    def lum(h: str) -> float:
        vals = []
        for c in hex_to_rgb(h):
            x = c / 255.0
            vals.append(x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4)
        return 0.2126 * vals[0] + 0.7152 * vals[1] + 0.0722 * vals[2]
    l1, l2 = lum(h1), lum(h2)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


class _StyleSampler(HTMLParser):
    def __init__(self):
        super().__init__()
        self.accent_colors: Counter[str] = Counter()
        self.text_colors: Counter[str] = Counter()
        self.bg_colors: Counter[str] = Counter()
        self.quote_bgs: Counter[str] = Counter()
        self.h2_texts: list[str] = []
        self._in_h2 = False

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t == 'h2':
            self._in_h2 = True
        style = dict(attrs).get('style', '')
        if not style:
            return
        props = {}
        for part in style.split(';'):
            if ':' in part:
                k, v = part.split(':', 1)
                props[k.strip().lower()] = v.strip()

        fg = parse_color_to_hex(props.get('color', ''))
        bg = parse_color_to_hex(props.get('background-color', '') or props.get('background', ''))
        border_m = re.search(r'(#[0-9a-fA-F]{3,6}|rgba?\([^)]+\))', props.get('border-left', '') + ' ' + props.get('border-bottom', ''))
        border_c = parse_color_to_hex(border_m.group(1)) if border_m else None

        if border_c and not is_neutral(border_c):
            self.accent_colors[border_c] += 4
        if fg:
            if not is_neutral(fg) and 0.12 <= lightness(fg) <= 0.72:
                weight = 4 if t in ('h1', 'h2', 'h3', 'strong', 'a') else 2
                self.accent_colors[fg] += weight
            elif t in ('p', 'section', 'span') and lightness(fg) < 0.45:
                self.text_colors[fg] += 1
        if bg:
            if t == 'blockquote' or 'border-left' in props:
                self.quote_bgs[bg] += 2
            elif lightness(bg) >= 0.88 or lightness(bg) <= 0.18:
                self.bg_colors[bg] += 1
            elif not is_neutral(bg) and lightness(bg) <= 0.65:
                self.accent_colors[bg] += 2

    def handle_endtag(self, tag):
        if tag.lower() == 'h2':
            self._in_h2 = False

    def handle_data(self, data):
        if self._in_h2 and data.strip():
            self.h2_texts.append(data.strip())


def extract_theme_from_html(page_html: str, theme_name: str, source_label: str = '') -> dict:
    body = fwa.slice_js_content(page_html)
    sampler = _StyleSampler()
    sampler.feed(body)

    primary = sampler.accent_colors.most_common(1)[0][0] if sampler.accent_colors else '#2563eb'
    bg = sampler.bg_colors.most_common(1)[0][0] if sampler.bg_colors else '#ffffff'
    is_dark = lightness(bg) < 0.35

    if is_dark:
        text = '#e2e8f0'
        text_light = '#94a3b8'
        surface = adjust_lightness(bg, min(0.24, lightness(bg) + 0.08))
        border = adjust_lightness(bg, min(0.32, lightness(bg) + 0.14))
        quote_bg = surface
        inline_bg = surface
        inline_text = adjust_lightness(primary, max(0.68, lightness(primary)))
    else:
        raw_text = sampler.text_colors.most_common(1)[0][0] if sampler.text_colors else '#2c2c2c'
        text = raw_text if contrast_ratio(raw_text, bg) >= 4.5 else '#2c2c2c'
        text_light = '#6b7280'
        surface = adjust_lightness(primary, 0.96) if not is_neutral(primary) else '#f8fafc'
        border = adjust_lightness(primary, 0.88) if not is_neutral(primary) else '#e5e7eb'
        cand_qbg = sampler.quote_bgs.most_common(1)[0][0] if sampler.quote_bgs else surface
        quote_bg = cand_qbg if contrast_ratio(text, cand_qbg) >= 4.5 else surface
        inline_bg = surface
        inline_text = primary if contrast_ratio(primary, inline_bg) >= 4.5 else text

    numbered_h2 = sum(1 for h in sampler.h2_texts if re.match(r'^0?\d+[.、·\s]', h))
    section_numbering = numbered_h2 >= 2

    lower_html = body.lower()
    uses_serif = bool(re.search(r'font-family\s*:[^;]*(songti|simsun|noto serif|georgia|stsong)', lower_html))
    h2_blocks = re.findall(r'<h2\b[^>]*style=["\']([^"\']+)["\']', body, re.I)
    h2_joined = ' '.join(h2_blocks).lower()
    if 'background' in h2_joined and ('#fff' in h2_joined or '255, 255, 255' in h2_joined or 'white' in h2_joined):
        h2_style = 'pill-banner'
    elif 'text-align' in h2_joined and 'center' in h2_joined:
        h2_style = 'centered-clean'
    elif 'border-left' in h2_joined:
        h2_style = 'left-bar-rule' if 'border-bottom' in h2_joined else 'left-bar'
    else:
        h2_style = 'thin-bottom'

    dm_primary = adjust_lightness(primary, max(0.62, min(0.82, lightness(primary) + 0.18)))
    desc = f'Custom theme learned from {source_label}' if source_label else 'Custom learned WeChat theme'
    return {
        'name': theme_name,
        'description': desc,
        'sectionNumbering': section_numbering,
        'typography': {
            'fontFamily': 'serif' if uses_serif else 'sans',
            'fontSize': 16,
            'lineHeight': 1.9 if uses_serif else 1.85,
            'letterSpacing': '0.03em' if uses_serif else '0.02em',
            'borderRadius': '6px',
        },
        'layout': {
            'h1Align': 'center' if h2_style == 'centered-clean' else 'left',
            'h2Style': h2_style,
            'quoteStyle': 'left-bar',
        },
        'colors': {
            'primary': primary,
            'secondary': adjust_lightness(primary, max(0.22, lightness(primary) - 0.08)),
            'text': text,
            'textLight': text_light,
            'bg': bg,
            'surface': surface,
            'codeBg': '#1e293b',
            'codeText': '#e2e8f0',
            'inlineCodeBg': inline_bg,
            'inlineCodeText': inline_text,
            'quoteBorder': primary,
            'quoteBg': quote_bg,
            'border': border,
        },
        'darkmode': {
            'bg': '#18181b',
            'text': '#e4e4e7',
            'textLight': '#a1a1aa',
            'primary': dm_primary,
            'codeBg': '#0f172a',
            'quoteBg': '#27272a',
        },
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Learn a reusable WeChat theme JSON from a public article URL or saved HTML file.')
    ap.add_argument('url', nargs='?', help='Public WeChat article URL (plain HTTP only; stops on verification gate).')
    ap.add_argument('--file', help='Path to locally saved WeChat article HTML.')
    ap.add_argument('--name', required=True, help='Lowercase kebab-case theme name (e.g. my-brand-red).')
    ap.add_argument('--workspace', help='Path to content-ops workspace; saves to <workspace>/style/themes/<name>.json.')
    ap.add_argument('-o', '--output', help='Optional explicit output path for the learned theme JSON.')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)

    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', args.name):
        print(f'Error: theme --name must be lowercase kebab-case, got "{args.name}"', file=sys.stderr)
        return 1
    if not args.url and not args.file:
        ap.error('Provide either a URL or --file <saved.html>')

    if args.file:
        fp = Path(args.file).expanduser().resolve()
        if not fp.is_file():
            print(f'Error: file not found: {fp}', file=sys.stderr)
            return 1
        page_html = fp.read_text(encoding='utf-8', errors='replace')
        source_label = fp.name
    else:
        try:
            page_html = fwa.fetch_public_html(args.url)
        except Exception as exc:
            print(f'Error: HTTP fetch failed: {exc}', file=sys.stderr)
            return 1
        if not fwa.has_wechat_content(page_html):
            out = {
                'ok': False,
                'verificationRequired': True,
                'url': args.url,
                'message': 'WeChat returned a verification page; save the article HTML from a real browser and re-run with --file <saved.html>.',
            }
            print(json.dumps(out, indent=2, ensure_ascii=False) if args.json else out['message'], file=sys.stderr if not args.json else sys.stdout)
            return 2
        source_label = fwa.extract_meta(page_html).get('account') or args.url

    theme = extract_theme_from_html(page_html, args.name, source_label=source_label)
    out_path = None
    if args.output:
        out_path = Path(args.output).expanduser().resolve()
    elif args.workspace:
        out_path = Path(args.workspace).expanduser().resolve() / 'style' / 'themes' / f'{args.name}.json'

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(theme, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    payload = {'ok': True, 'theme': theme, 'outputPath': str(out_path) if out_path else None}
    print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else f"Learned theme '{args.name}' (primary={theme['colors']['primary']}, bg={theme['colors']['bg']}) -> {out_path or 'stdout'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
