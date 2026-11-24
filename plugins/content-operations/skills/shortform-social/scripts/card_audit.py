#!/usr/bin/env python3
"""Objective offline structural & accessibility audit for visual card decks (zero aesthetic lock-in)."""
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
    (1080, 1440): '3:4 vertical card (Xiaohongshu / Instagram / WeChat newspic)',
    (1080, 1350): '4:5 vertical feed card (Instagram)',
    (1080, 1920): '9:16 vertical story / cover',
    (1080, 1080): '1:1 square card / WeChat share cover',
    (900, 383): 'WeChat 2.35:1 primary cover',
    (1280, 720): '16:9 video thumbnail (YouTube / Bilibili)',
    (1200, 675): '16:9 social card (X / LinkedIn)',
    (1000, 1500): '2:3 vertical pin (Pinterest)',
}

FONT_SIZE_PX_RE = re.compile(r'font-size\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*px', re.I)
INLINE_WIDTH_PX_RE = re.compile(r'(?:^|;)\s*width\s*:\s*([0-9]+)\s*px', re.I)
INLINE_HEIGHT_PX_RE = re.compile(r'(?:^|;)\s*height\s*:\s*([0-9]+)\s*px', re.I)
CSS_VAR_RE = re.compile(r'--([a-z-]+)\s*:\s*([^;}\n]+)')
PLACEHOLDER_TEXT_RE = re.compile(r'(?:\bTODO\b|\bTBD\b|\[insert\s+[^\]]+\]|替换为\s*<img)', re.I)
WINDOWS_ABS_RE = re.compile(r'^[A-Za-z]:\\')
FILE_URI_PREFIX = 'file:' + '//'
KNOWN_FRAME_CLASS_DIMS = {
    'frame-3x4': ('1080', '1440'),
    'frame-4x5': ('1080', '1350'),
    'frame-16x9': ('1280', '720'),
    'frame-wechat-wide': ('900', '383'),
    'frame-wechat-sq': ('1080', '1080'),
}


class _DeckParser(HTMLParser):
    """Lightweight HTML structure collector for objective offline auditing."""

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
        self.advisories: List[Dict[str, Any]] = []
        self.placeholder_hits: List[Dict[str, Any]] = []
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

        if 'data-export-frame' in attr_map:
            width_val = attr_map.get('data-export-width', '').strip()
            height_val = attr_map.get('data-export-height', '').strip()
            style_raw = attr_map.get('style', '')
            if not width_val:
                mw = INLINE_WIDTH_PX_RE.search(style_raw)
                if mw:
                    width_val = mw.group(1)
            if not height_val:
                mh = INLINE_HEIGHT_PX_RE.search(style_raw)
                if mh:
                    height_val = mh.group(1)
            if not width_val or not height_val:
                for cls_name in attr_map.get('class', '').split():
                    if cls_name in KNOWN_FRAME_CLASS_DIMS:
                        cw, ch = KNOWN_FRAME_CLASS_DIMS[cls_name]
                        width_val = width_val or cw
                        height_val = height_val or ch
                        break
            frame_info = {
                'id': attr_map.get('data-export-frame', '').strip(),
                'width': width_val,
                'height': height_val,
                'card': attr_map.get('data-card', '').strip(),
                'depth': self._tag_depth,
                'headings': [],
            }
            self.frames.append(frame_info)
            self._frame_stack.append(frame_info)

        current_frame = self._frame_stack[-1] if self._frame_stack else None
        if current_frame is None:
            return

        cls_set = set(attr_map.get('class', '').split())
        if 'media-placeholder' in cls_set:
            self.placeholder_hits.append({
                'frame': current_frame['id'],
                'message': f'Unreplaced .media-placeholder block remains inside {current_frame["id"]}.',
            })

        if tag in ('h1', 'h2') or 'title-square' in cls_set or 'title-wide' in cls_set:
            self._heading_capture = {'frame': current_frame, 'depth': self._tag_depth, 'parts': []}

        if tag == 'img':
            self.imgs.append({'frame': current_frame['id'], 'src': attr_map.get('src', '').strip()})

        style_attr = attr_map.get('style', '').strip()
        if style_attr:
            for m in FONT_SIZE_PX_RE.finditer(style_attr):
                px = float(m.group(1))
                if px < 14.0:
                    self.advisories.append({
                        'rule': 'min_font_advisory',
                        'severity': 'warning',
                        'frame': current_frame['id'],
                        'message': f'Inline font-size {px:g}px in {current_frame["id"]} may be hard to read on mobile feeds.',
                    })

    def handle_data(self, data: str) -> None:
        if self._in_style:
            self._style_buf.append(data)
            return
        if self._heading_capture is not None:
            self._heading_capture['parts'].append(data)
        if self._frame_stack and PLACEHOLDER_TEXT_RE.search(data):
            fid = self._frame_stack[-1]['id']
            self.placeholder_hits.append({
                'frame': fid,
                'message': f'Placeholder marker found in visible copy of {fid}: {data.strip()[:60]!r}',
            })

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


def audit_deck(
    target: Path,
    allow_remote_img: bool = False,
    allow_custom_size: bool = False,
    allow_placeholders: bool = False,
) -> Dict[str, Any]:
    """Run objective structural, asset, placeholder, and WCAG AA contrast checks without aesthetic lock-in."""
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

    # 1. Objective export frame declarations & platform dimensions
    if not parser.frames:
        add_issue('frame_dimensions', 'error', 'No [data-export-frame] elements declared in HTML.')

    seen_frames: set = set()
    wide_frames: List[Dict[str, Any]] = []
    square_frames: List[Dict[str, Any]] = []

    for fr in parser.frames:
        fid = fr['id']
        if not fid:
            add_issue('unique_identities', 'error', 'Encountered empty data-export-frame attribute.')
        elif fid in seen_frames:
            add_issue('unique_identities', 'error', f'Duplicate data-export-frame id: {fid}', fid)
        else:
            seen_frames.add(fid)

        try:
            w, h = int(fr['width']), int(fr['height'])
        except ValueError:
            add_issue('frame_dimensions', 'error', f'Frame {fid or "(unnamed)"} must declare integer export width/height.', fid)
            continue

        if w <= 0 or h <= 0:
            add_issue('frame_dimensions', 'error', f'Frame {fid} must have positive dimensions, got {w}x{h}.', fid)
        elif not allow_custom_size and (w, h) not in ALLOWED_DIMENSIONS:
            allowed_str = ', '.join(f'{aw}x{ah}' for aw, ah in sorted(ALLOWED_DIMENSIONS))
            add_issue(
                'frame_dimensions',
                'error',
                f'Frame {fid} size {w}x{h} is outside standard platform dimensions ({allowed_str}); pass --allow-custom-size if intentional.',
                fid,
            )
        if (w, h) == (900, 383):
            wide_frames.append(fr)
        elif (w, h) == (1080, 1080):
            square_frames.append(fr)

    # 2. Objective Board addressability uniqueness
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

    # 3. Objective local image asset integrity
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
                add_issue('asset_paths', 'error', f'Remote image URL in {fid} ({src}); download locally into assets/ for deterministic rendering.', fid)
            continue
        resolved = (base_dir / src).resolve()
        try:
            resolved.relative_to(base_dir)
        except ValueError:
            add_issue('asset_paths', 'error', f'Image path escapes deck directory in {fid}: {src}', fid)
            continue
        if not resolved.is_file():
            add_issue('asset_paths', 'error', f'Missing local image asset in {fid}: {src}', fid)

    # 4. Objective unfinished placeholder guard (prevents accidentally shipping scaffold stubs)
    if not allow_placeholders:
        for hit in parser.placeholder_hits:
            add_issue('unfinished_placeholders', 'error', hit['message'], hit['frame'])

    # 5. Objective WCAG 2.1 AA contrast check when a named theme is declared (freeform custom HTML is allowed)
    style_name = parser.html_attrs.get('data-style', '').strip()
    theme_name = parser.html_attrs.get('data-theme', '').strip()
    if theme_name:
        if theme_name in cc.THEMES:
            contrast = cc.evaluate_palette_contrast(cc.THEMES[theme_name])
            if not contrast['passed']:
                add_issue('contrast_check', 'error', f'Preset theme {theme_name} failed WCAG AA contrast: {contrast["failures"]}')
        else:
            custom_tokens = _extract_custom_theme_tokens(css_blob, theme_name)
            if custom_tokens:
                try:
                    contrast = cc.evaluate_palette_contrast(custom_tokens)
                except ValueError as err:
                    add_issue('contrast_check', 'error', f'Invalid hex token in custom theme {theme_name!r}: {err}')
                else:
                    if not contrast['passed']:
                        add_issue('contrast_check', 'error', f'Custom theme {theme_name!r} failed WCAG AA contrast: {contrast["failures"]}')

    # 6. Non-blocking helpful advisories (never block valid creative choices)
    for item in parser.advisories:
        add_issue(item['rule'], 'warning', item['message'], item.get('frame', ''))

    if wide_frames:
        if not square_frames:
            add_issue(
                'wechat_pair_advisory',
                'warning',
                'WeChat 2.35:1 cover (900x383) has no companion 1:1 (1080x1080) share cover; WeChat will center-crop when forwarded.',
                wide_frames[0]['id'],
            )
        else:
            wide_clean = _strip_punct(wide_frames[0]['headings'][0] if wide_frames[0]['headings'] else '')
            sq_clean = _strip_punct(square_frames[0]['headings'][0] if square_frames[0]['headings'] else '')
            if len(wide_clean) > 14 and sq_clean and sq_clean == wide_clean:
                add_issue(
                    'wechat_pair_advisory',
                    'warning',
                    f'WeChat 1:1 cover {square_frames[0]["id"]} repeats the long 2.35:1 headline verbatim; consider a shorter title or visual-led 1:1 crop.',
                    square_frames[0]['id'],
                )

    return {
        'passed': len(errors) == 0,
        'file': str(html_path),
        'style': style_name or 'custom',
        'theme': theme_name or 'custom',
        'frameCount': len(parser.frames),
        'frames': [f'{f["id"]} ({f["width"]}x{f["height"]})' for f in parser.frames],
        'errorCount': len(errors),
        'warningCount': len(warnings),
        'errors': errors,
        'warnings': warnings,
    }
