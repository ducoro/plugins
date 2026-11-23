#!/usr/bin/env python3
"""Offline 10-rule structural and WCAG contrast audit gate for Social Visual Card Studio."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import card_colors as cc  # noqa: E402

ALLOWED_DIMENSIONS = {
    (1080, 1440): '3:4 vertical card',
    (900, 383): 'WeChat 2.35:1 primary cover',
    (1080, 1080): 'WeChat 1:1 square cover',
    (1280, 720): '16:9 video thumbnail',
}

RAW_COLOR_RE = re.compile(r'(?:#[0-9a-fA-F]{3,8}\b|\brgba?\s*\()', re.I)
FONT_SIZE_PX_RE = re.compile(r'font-size\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*px', re.I)
ABS_FOOTER_CSS_RE = re.compile(r'(?:\.card-foot|\.footer)[^{]*\{[^}]*position\s*:\s*absolute', re.I | re.S)
FIGURE_RESET_RE = re.compile(r'\bfigure\b[^{]*\{[^}]*margin\s*:\s*0(?:\s|;|px|\})', re.I | re.S)
FULL_BLACK_SCRIM_RE = re.compile(
    r'inset\s*:\s*0[^}]*rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*(0?\.[4-9]\d*|1(?:\.0+)?)\s*\)',
    re.I | re.S,
)
INLINE_BLACK_SCRIM_RE = re.compile(
    r'rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*(0?\.[4-9]\d*|1(?:\.0+)?)\s*\)',
    re.I,
)
CSS_VAR_RE = re.compile(r'--([a-z-]+)\s*:\s*([^;}\n]+)')
WINDOWS_ABS_RE = re.compile(r'^[A-Za-z]:\\')
FILE_URI_PREFIX = 'file:' + '//'


class _DeckParser(HTMLParser):
    """Lightweight HTML structure collector for offline card-deck auditing."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_attrs: Dict[str, str] = {}
        self.styles: List[str] = []
        self._in_style = False
        self._style_buf: List[str] = []
        self.frames: List[Dict[str, Any]] = []
        self.all_cards: List[str] = []
        self.all_mark_items: List[str] = []
        self.imgs: List[Dict[str, Any]] = []
        self.inline_issues: List[Dict[str, Any]] = []
        self._frame_stack: List[Dict[str, Any]] = []
        self._heading_capture: Optional[Dict[str, Any]] = None
        self._tag_depth = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self._tag_depth += 1
        attr_map = {k.lower(): (v if v is not None else '') for k, v in attrs}

        if tag == 'html':
            self.html_attrs = attr_map
        elif tag == 'style':
            self._in_style = True
            self._style_buf = []

        if 'data-card' in attr_map:
            self.all_cards.append(attr_map['data-card'])
        if 'data-mark-item' in attr_map:
            self.all_mark_items.append(attr_map['data-mark-item'])

        if 'data-ducoro-export-frame' in attr_map:
            frame_info = {
                'id': attr_map.get('data-ducoro-export-frame', '').strip(),
                'width': attr_map.get('data-ducoro-export-width', '').strip(),
                'height': attr_map.get('data-ducoro-export-height', '').strip(),
                'card': attr_map.get('data-card', '').strip(),
                'classes': set(attr_map.get('class', '').split()),
                'depth': self._tag_depth,
                'headings': [],
            }
            self.frames.append(frame_info)
            self._frame_stack.append(frame_info)

        current_frame = self._frame_stack[-1] if self._frame_stack else None
        if current_frame is None:
            return

        cls_set = set(attr_map.get('class', '').split())
        if tag in ('h1', 'h2') or 'title-square' in cls_set or 'title-wide' in cls_set:
            self._heading_capture = {'frame': current_frame, 'depth': self._tag_depth, 'parts': []}
        if tag == 'img':
            self.imgs.append({
                'frame': current_frame['id'],
                'src': attr_map.get('src', '').strip(),
                'style': attr_map.get('style', ''),
            })
        style_attr = attr_map.get('style', '').strip()
        if style_attr:
            self._inspect_inline_style(current_frame, tag, cls_set, attr_map, style_attr)

    def _inspect_inline_style(
        self,
        frame: Dict[str, Any],
        tag: str,
        cls_set: set,
        attr_map: Dict[str, str],
        style_attr: str,
    ) -> None:
        fid = frame['id'] or '(unnamed)'
        if ('card-foot' in cls_set or 'footer' in cls_set or tag == 'footer') and re.search(
            r'position\s*:\s*absolute', style_attr, re.I
        ):
            self.inline_issues.append({
                'rule': 'no_abs_footer',
                'severity': 'error',
                'frame': fid,
                'message': f'Footer in {fid} uses position:absolute; keep footer pinned via flex margin-top:auto.',
            })

        is_wide = frame['width'] == '900' and frame['height'] == '383'
        min_err = 14.0 if is_wide else 16.0
        min_warn = 16.0 if is_wide else 20.0
        for m in FONT_SIZE_PX_RE.finditer(style_attr):
            px = float(m.group(1))
            if px < min_err:
                self.inline_issues.append({
                    'rule': 'min_font_floor',
                    'severity': 'error',
                    'frame': fid,
                    'message': f'Inline font-size {px:g}px in {fid} is below mobile readability floor ({min_err:g}px).',
                })
            elif px < min_warn:
                self.inline_issues.append({
                    'rule': 'min_font_floor',
                    'severity': 'warning',
                    'frame': fid,
                    'message': f'Inline font-size {px:g}px in {fid} is tight for mobile feed legibility (< {min_warn:g}px).',
                })

        if RAW_COLOR_RE.search(style_attr) and not attr_map.get('data-allow-color', '').strip():
            self.inline_issues.append({
                'rule': 'no_raw_inline_hex',
                'severity': 'error',
                'frame': fid,
                'message': (
                    f'Raw inline color in {fid} (<{tag}>) bypasses theme tokens; '
                    'use CSS variables or brand-theme instead (or set data-allow-color="<reason>").'
                ),
            })

        compact = style_attr.replace(' ', '').lower()
        if ('inset:0' in compact or 'height:100%' in compact) and INLINE_BLACK_SCRIM_RE.search(style_attr):
            self.inline_issues.append({
                'rule': 'no_full_black_scrim',
                'severity': 'error',
                'frame': fid,
                'message': f'Full-canvas dark black scrim detected in {fid}; use quiet-zone placement or localized image-toned gradient.',
            })

    def handle_data(self, data: str) -> None:
        if self._in_style:
            self._style_buf.append(data)
        if self._heading_capture is not None:
            self._heading_capture['parts'].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == 'style' and self._in_style:
            self.styles.append(''.join(self._style_buf))
            self._in_style = False
            self._style_buf = []
        if self._heading_capture is not None and self._tag_depth == self._heading_capture['depth']:
            text = re.sub(r'\s+', '', ''.join(self._heading_capture['parts']))
            if text:
                self._heading_capture['frame']['headings'].append(text)
            self._heading_capture = None
        if self._frame_stack and self._tag_depth == self._frame_stack[-1]['depth']:
            self._frame_stack.pop()
        self._tag_depth = max(0, self._tag_depth - 1)


def _strip_punct(text: str) -> str:
    return re.sub(r'[\s，。！？、：；,.!?:;—\-·《》“”"\'()（）【】]+', '', text)


def _extract_custom_theme_tokens(css_text: str, theme_id: str) -> Optional[Dict[str, str]]:
    pattern = re.compile(
        r'data-theme\s*=\s*["\']' + re.escape(theme_id) + r'["\'][^{]*\{([^}]*)\}',
        re.I | re.S,
    )
    matches = pattern.findall(css_text)
    if not matches:
        return None
    raw_vars: Dict[str, str] = {}
    for block in matches:
        for k, v in CSS_VAR_RE.findall(block):
            raw_vars[k.strip()] = v.strip()
    key_map = {'bg': 'bg', 'surface': 'surface', 'ink': 'ink', 'muted': 'muted', 'accent': 'accent', 'accent-ink': 'accentInk'}
    if not all(k in raw_vars for k in key_map):
        return None
    return {dest: raw_vars[src] for src, dest in key_map.items()}


def audit_deck(target: Path, allow_remote_img: bool = False) -> Dict[str, Any]:
    """Run all 10 deterministic offline structural checks on a card deck HTML or directory."""
    target = target.resolve()
    html_path = target / 'index.html' if target.is_dir() else target
    if not html_path.is_file():
        raise FileNotFoundError(f'Deck HTML not found: {html_path}')

    html_text = html_path.read_text(encoding='utf-8')
    base_dir = html_path.parent
    parser = _DeckParser()
    parser.feed(html_text)
    css_blob = '\n'.join(parser.styles)

    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    def add_issue(rule: str, severity: str, message: str, frame: str = '') -> None:
        item = {'rule': rule, 'severity': severity, 'message': message}
        if frame:
            item['frame'] = frame
        (errors if severity == 'error' else warnings).append(item)

    if not parser.frames:
        add_issue('frame_dimensions', 'error', 'No [data-ducoro-export-frame] elements declared in HTML.')

    seen_frames: set = set()
    wide_frames: List[Dict[str, Any]] = []
    square_frames: List[Dict[str, Any]] = []

    for fr in parser.frames:
        fid = fr['id']
        if not fid:
            add_issue('unique_identities', 'error', 'Encountered empty data-ducoro-export-frame attribute.')
        elif fid in seen_frames:
            add_issue('unique_identities', 'error', f'Duplicate data-ducoro-export-frame id: {fid}', fid)
        else:
            seen_frames.add(fid)

        if not fr['card']:
            add_issue('unique_identities', 'error', f'Export frame {fid or "(unnamed)"} is missing data-card identity.', fid)

        try:
            w, h = int(fr['width']), int(fr['height'])
        except ValueError:
            add_issue('frame_dimensions', 'error', f'Frame {fid or "(unnamed)"} must declare integer export width/height.', fid)
            continue

        if (w, h) not in ALLOWED_DIMENSIONS:
            allowed_str = ', '.join(f'{aw}x{ah}' for aw, ah in sorted(ALLOWED_DIMENSIONS))
            add_issue('frame_dimensions', 'error', f'Frame {fid} size {w}x{h} is outside allowed platform ratios ({allowed_str}).', fid)
        elif (w, h) == (900, 383):
            wide_frames.append(fr)
        elif (w, h) == (1080, 1080):
            square_frames.append(fr)

    for label, values in (('data-card', parser.all_cards), ('data-mark-item', parser.all_mark_items)):
        seen: set = set()
        for val in values:
            cleaned = val.strip()
            if not cleaned:
                add_issue('unique_identities', 'error', f'Empty {label} attribute found.')
            elif cleaned in seen:
                add_issue('unique_identities', 'error', f'Duplicate {label} identity: {cleaned}')
            else:
                seen.add(cleaned)

    if not FIGURE_RESET_RE.search(css_blob):
        add_issue('no_figure_drift', 'error', 'Missing CSS reset for figure margin (add `figure { margin: 0; }`).')
    if ABS_FOOTER_CSS_RE.search(css_blob):
        add_issue('no_abs_footer', 'error', 'CSS pins .card-foot/.footer with position:absolute; use flex margin-top:auto.')

    for item in parser.inline_issues:
        add_issue(item['rule'], item['severity'], item['message'], item.get('frame', ''))

    for img in parser.imgs:
        src, fid = img['src'], img['frame']
        if not src:
            add_issue('asset_paths', 'error', f'Empty <img src> in {fid}.', fid)
            continue
        if src.startswith('data:'):
            continue
        lower = src.lower()
        if lower.startswith(FILE_URI_PREFIX) or src.startswith('/') or WINDOWS_ABS_RE.match(src):
            add_issue('asset_paths', 'error', f'Image in {fid} uses absolute or local URI ({src}); use relative assets/ path.', fid)
            continue
        if lower.startswith('http://') or lower.startswith('https://'):
            if not allow_remote_img:
                add_issue('asset_paths', 'error', f'Remote image URL in {fid} ({src}); download locally into assets/ and log SOURCES.md.', fid)
            continue
        resolved = (base_dir / src).resolve()
        try:
            resolved.relative_to(base_dir)
        except ValueError:
            add_issue('asset_paths', 'error', f'Image path escapes deck directory in {fid}: {src}', fid)
            continue
        if not resolved.is_file():
            add_issue('asset_paths', 'error', f'Missing local image asset in {fid}: {src}', fid)

    if wide_frames:
        if not square_frames:
            add_issue(
                'wechat_pair_integrity',
                'error',
                'WeChat 2.35:1 primary cover (900x383) must be paired with a dedicated 1:1 (1080x1080) share cover.',
                wide_frames[0]['id'],
            )
        else:
            wide_clean = _strip_punct(wide_frames[0]['headings'][0] if wide_frames[0]['headings'] else '')
            sq_clean = _strip_punct(square_frames[0]['headings'][0] if square_frames[0]['headings'] else '')
            sq_id = square_frames[0]['id']
            if not sq_clean:
                add_issue('wechat_pair_integrity', 'error', f'WeChat 1:1 cover {sq_id} has no visible heading.', sq_id)
            else:
                if len(sq_clean) > 16:
                    add_issue('wechat_pair_integrity', 'error', f'WeChat 1:1 headline in {sq_id} is too long ({len(sq_clean)} chars > 16).', sq_id)
                elif len(sq_clean) > 12:
                    add_issue('wechat_pair_integrity', 'warning', f'WeChat 1:1 headline in {sq_id} is {len(sq_clean)} chars; 4-10 chars reads sharper.', sq_id)
                if len(wide_clean) > 12 and sq_clean == wide_clean:
                    add_issue('wechat_pair_integrity', 'error', f'WeChat 1:1 cover {sq_id} copies the long 2.35:1 title verbatim; write a short headline.', sq_id)

    if FULL_BLACK_SCRIM_RE.search(css_blob):
        add_issue('no_full_black_scrim', 'error', 'Full-canvas high-opacity black scrim detected in CSS; use quiet-zone or localized gradient.')

    style_name = parser.html_attrs.get('data-style', '').strip()
    theme_name = parser.html_attrs.get('data-theme', '').strip()
    if style_name not in cc.STYLES:
        add_issue('contrast_check', 'error', f'Invalid or missing <html data-style="{style_name}">; expected one of {", ".join(cc.STYLES)}.')
    if not theme_name:
        add_issue('contrast_check', 'error', 'Missing <html data-theme="..."> attribute.')
    elif theme_name in cc.THEMES:
        palette = cc.THEMES[theme_name]
        if style_name in cc.STYLES and palette['style'] != style_name:
            add_issue('contrast_check', 'warning', f'Theme {theme_name!r} belongs to style {palette["style"]!r}, but html declares {style_name!r}.')
        contrast = cc.evaluate_palette_contrast(palette)
        if not contrast['passed']:
            add_issue('contrast_check', 'error', f'Preset theme {theme_name} failed contrast: {contrast["failures"]}')
    else:
        custom_tokens = _extract_custom_theme_tokens(css_blob, theme_name)
        if not custom_tokens:
            add_issue('contrast_check', 'error', f'Unknown theme {theme_name!r}: no complete [data-theme="{theme_name}"] block in <style>.')
        else:
            try:
                contrast = cc.evaluate_palette_contrast(custom_tokens)
            except ValueError as err:
                add_issue('contrast_check', 'error', f'Invalid hex token in custom theme {theme_name!r}: {err}')
            else:
                if not contrast['passed']:
                    add_issue('contrast_check', 'error', f'Custom theme {theme_name!r} failed WCAG 2.1 contrast floor: {contrast["failures"]}')

    return {
        'passed': len(errors) == 0,
        'file': str(html_path),
        'style': style_name,
        'theme': theme_name,
        'frameCount': len(parser.frames),
        'frames': [f'{f["id"]} ({f["width"]}x{f["height"]})' for f in parser.frames],
        'errorCount': len(errors),
        'warningCount': len(warnings),
        'errors': errors,
        'warnings': warnings,
    }
