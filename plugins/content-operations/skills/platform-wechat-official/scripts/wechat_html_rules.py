"""WeChat Official Account HTML validation rules and 9 rich container block renderers."""
from __future__ import annotations

import html as html_lib
from html.parser import HTMLParser
import re

WECHAT_STYLE_RULES = [
    ('position_unsupported', re.compile(r'\bposition\s*:\s*(?:fixed|absolute|sticky)\b', re.I), 'ERROR', 'position: fixed/absolute/sticky is unsupported in WeChat'),
    ('keyframes', re.compile(r'@keyframes|\banimation\s*:', re.I), 'ERROR', 'CSS animations are unsupported in WeChat'),
    ('media_query', re.compile(r'@media\b', re.I), 'ERROR', '@media queries are unsupported; use data-darkmode-*'),
    ('import_css', re.compile(r'@import\b', re.I), 'ERROR', '@import is unsupported in WeChat'),
    ('css_var', re.compile(r'\bvar\s*\(\s*--', re.I), 'ERROR', 'CSS variables var(--*) are unsupported; resolve to hex colors'),
    ('external_font', re.compile(r"url\s*\(['\"]?https?://[^)]*\.(?:woff2?|ttf|otf|eot)", re.I), 'ERROR', 'External web fonts do not load in WeChat'),
    ('float_css', re.compile(r'\bfloat\s*:\s*(?:left|right)\b', re.I), 'WARN', 'CSS float is unreliable in WeChat; flex is safer'),
    ('display_grid', re.compile(r'\bdisplay\s*:\s*grid\b', re.I), 'WARN', 'display: grid has partial support in older WeChat clients; flex is safer'),
]

WECHAT_TAG_RULES = {
    'style': ('style_tag', 'ERROR', '<style> tags are stripped by WeChat; inline all styles'),
    'script': ('script_tag', 'ERROR', '<script> tags are forbidden in WeChat articles'),
    'link': ('link_tag', 'ERROR', 'External <link> stylesheets/fonts are stripped by WeChat'),
    'div': ('div_tag', 'WARN', '<div> may be normalized to <section> by WeChat editor'),
    'iframe': ('iframe_tag', 'WARN', '<iframe> only works for allowlisted sources (e.g. Tencent Video)'),
}

WECHAT_ATTR_RULES = {
    'class': ('class_attr', 'WARN', 'class attributes are stripped by WeChat; rely on inline style'),
    'id': ('id_attr', 'WARN', 'id attributes are stripped by WeChat'),
}

WECHAT_HTML_RULES = WECHAT_STYLE_RULES  # Backward-compatible export name


def _has_cjk(text: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def truncate_utf8_bytes(text: str, max_bytes: int = 120) -> str:
    """Truncate text cleanly at UTF-8 byte boundary (WeChat digest ceiling is 120 UTF-8 bytes)."""
    cleaned = re.sub(r'\s+', ' ', text).strip()
    if len(cleaned.encode('utf-8')) <= max_bytes:
        return cleaned
    ellipsis = '…'
    budget = max(0, max_bytes - len(ellipsis.encode('utf-8')))
    out = []
    used = 0
    for ch in cleaned:
        size = len(ch.encode('utf-8'))
        if used + size > budget:
            break
        out.append(ch)
        used += size
    return ''.join(out).rstrip() + ellipsis


def html_to_plaintext(markup: str) -> str:
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', markup, flags=re.S | re.I)
    text = re.sub(r'<(?:br|p|div|section|h[1-6]|tr)[^>]*>', '\n', text, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    text = html_lib.unescape(text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


class _WeChatHTMLAuditor(HTMLParser):
    """Inspect only real HTML tags, attributes, and inline style values (ignoring prose & <code> text)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.counts: dict[str, int] = {}
        self.meta: dict[str, tuple[str, str]] = {}
        self.samples: dict[str, str] = {}
        self.img_count = 0

    def _hit(self, rule: str, level: str, message: str, sample: str) -> None:
        self.counts[rule] = self.counts.get(rule, 0) + 1
        if rule not in self.meta:
            self.meta[rule] = (level, message)
            self.samples[rule] = sample[:80]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t == 'img':
            self.img_count += 1
        if t in WECHAT_TAG_RULES:
            rule, level, msg = WECHAT_TAG_RULES[t]
            self._hit(rule, level, msg, f'<{t}>')
        for k, v in attrs:
            kl = k.lower()
            val = v or ''
            if kl in WECHAT_ATTR_RULES:
                rule, level, msg = WECHAT_ATTR_RULES[kl]
                self._hit(rule, level, msg, f'<{t} {kl}="{val[:40]}">')
            elif kl == 'style' and val:
                for rule, rx, level, msg in WECHAT_STYLE_RULES:
                    matches = rx.findall(val)
                    for _ in matches:
                        self._hit(rule, level, msg, val)
            elif t == 'a' and kl == 'href' and re.match(r'^https?://(?!mp\.weixin\.qq\.com)', val, re.I):
                self._hit(
                    'external_link',
                    'WARN',
                    'External links are blocked for unverified accounts; convert to footnotes',
                    f'<a href="{val[:50]}">',
                )


def validate_wechat_html(markup: str) -> list[dict]:
    """Validate HTML tags, attributes, and inline styles against WeChat compatibility rules."""
    body = markup
    marker = re.search(r'<!--\s*WECHAT_BODY_START\s*-->(.*?)<!--\s*WECHAT_BODY_END\s*-->', markup, re.S)
    if marker:
        body = marker.group(1)
    else:
        body_match = re.search(r'<body[^>]*>(.*)</body>', markup, re.S | re.I)
        if body_match:
            body = body_match.group(1)

    auditor = _WeChatHTMLAuditor()
    auditor.feed(body)
    auditor.close()

    issues = []
    for rule, count in auditor.counts.items():
        level, msg = auditor.meta[rule]
        issues.append({'rule': rule, 'level': level, 'message': msg, 'count': count, 'sample': auditor.samples[rule]})

    if auditor.img_count > 10:
        issues.append({
            'rule': 'too_many_images',
            'level': 'WARN',
            'message': f'Article contains {auditor.img_count} inline images; WeChat recommends <= 10 for stable delivery',
            'count': auditor.img_count,
            'sample': '',
        })
    return issues


def dm_attr(color: str | None = None, bgcolor: str | None = None) -> str:
    parts = []
    if color:
        parts.append(f'data-darkmode-color="{color}"')
    if bgcolor:
        parts.append(f'data-darkmode-bgcolor="{bgcolor}"')
    return (' ' + ' '.join(parts)) if parts else ''


def render_container_block(kind: str, arg: str, body: str, c: dict, dm: dict, render_inline) -> str:
    """Render one of the 9 WeChat-safe :::container blocks using inline-styled <section> tags."""
    p = c['primary']
    lines = [ln.strip() for ln in body.strip().splitlines() if ln.strip()]
    is_cn = _has_cjk(body + ' ' + arg)
    if kind == 'callout':
        bg_hex = c.get('bg', '#ffffff').lstrip('#')
        is_dark_canvas = len(bg_hex) == 6 and (int(bg_hex[0:2], 16) * 0.299 + int(bg_hex[2:4], 16) * 0.587 + int(bg_hex[4:6], 16) * 0.114) < 128
        parts = arg.strip().split(None, 1)
        variant = parts[0].lower() if parts else 'info'
        custom_title = parts[1].strip() if len(parts) > 1 else ''
        if is_dark_canvas:
            palette = {
                'tip': ('#34d399', '#064e3b', '#ecfdf5', '提示' if is_cn else 'TIP'),
                'warning': ('#fbbf24', '#451a03', '#fffbeb', '注意' if is_cn else 'WARNING'),
                'info': ('#60a5fa', '#1e3a8a', '#eff6ff', '说明' if is_cn else 'INFO'),
                'danger': ('#f87171', '#450a0a', '#fef2f2', '警示' if is_cn else 'DANGER'),
            }
        else:
            palette = {
                'tip': ('#059669', '#ecfdf5', '#1f2937', '提示' if is_cn else 'TIP'),
                'warning': ('#d97706', '#fffbeb', '#1f2937', '注意' if is_cn else 'WARNING'),
                'info': ('#2563eb', '#eff6ff', '#1f2937', '说明' if is_cn else 'INFO'),
                'danger': ('#dc2626', '#fef2f2', '#1f2937', '警示' if is_cn else 'DANGER'),
            }
        if variant not in palette and arg.strip():
            custom_title = arg.strip()
        accent, bg, txt, default_title = palette.get(variant, palette['info'])
        title = html_lib.escape(custom_title) if custom_title else default_title
        content = '<br />'.join(render_inline(ln) for ln in lines)
        return (
            f'<section style="background-color: {bg}; border-left: 4px solid {accent}; '
            f'padding: 14px 16px; border-radius: 4px; margin: 18px 0; font-size: 15px; line-height: 1.75; color: {txt};"'
            f'{dm_attr(dm["text"], dm["quoteBg"])}>'
            f'<section style="font-weight: 700; color: {accent}; margin-bottom: 6px; font-size: 13px; letter-spacing: 1px;">{title}</section>'
            f'<section style="color: {txt};">{content}</section></section>'
        )
    if kind == 'steps':
        rows = []
        for idx, ln in enumerate(lines, start=1):
            rows.append(
                f'<section style="display: flex; align-items: flex-start; margin-bottom: 12px; '
                f'background-color: {c["surface"]}; border: 1px solid {c["border"]}; '
                f'border-radius: 8px; padding: 12px 14px;"'
                f'{dm_attr(dm["text"], dm["quoteBg"])}>'
                f'<section style="flex-shrink: 0; width: 24px; height: 24px; line-height: 24px; text-align: center; '
                f'border-radius: 999px; background-color: {p}; color: #ffffff; font-size: 13px; font-weight: 700; margin-right: 12px;">{idx}</section>'
                f'<section style="flex: 1; font-size: 15px; line-height: 1.7; color: {c["text"]};"'
                f'{dm_attr(dm["text"])}>{render_inline(ln)}</section></section>'
            )
        return f'<section style="margin: 18px 0;">{"".join(rows)}</section>'
    if kind == 'timeline':
        rows = []
        for ln in lines:
            rows.append(
                f'<section style="display: flex; margin-bottom: 14px;">'
                f'<section style="flex-shrink: 0; width: 16px; display: flex; flex-direction: column; align-items: center;">'
                f'<section style="width: 10px; height: 10px; border-radius: 50%; background-color: {p}; margin-top: 7px;"><span leaf=""><br /></span></section>'
                f'<section style="width: 2px; flex: 1; background-color: {c["border"]}; margin-top: 4px;"><span leaf=""><br /></span></section></section>'
                f'<section style="flex: 1; padding-left: 10px; font-size: 15px; line-height: 1.75; color: {c["text"]};"'
                f'{dm_attr(dm["text"])}>{render_inline(ln)}</section></section>'
            )
        return f'<section style="margin: 18px 0;">{"".join(rows)}</section>'
    if kind == 'dialogue':
        bubbles = []
        for ln in lines:
            if ln.startswith('>'):
                msg = render_inline(ln.lstrip('>').strip())
                bubbles.append(
                    f'<section style="display: flex; justify-content: flex-end; margin-bottom: 10px;">'
                    f'<section style="background-color: {p}; color: #ffffff; padding: 10px 14px; '
                    f'border-radius: 12px 12px 2px 12px; max-width: 82%; font-size: 15px; line-height: 1.65;">{msg}</section></section>'
                )
            else:
                msg = render_inline(ln)
                bubbles.append(
                    f'<section style="display: flex; justify-content: flex-start; margin-bottom: 10px;">'
                    f'<section style="background-color: {c["surface"]}; color: {c["text"]}; padding: 10px 14px; '
                    f'border-radius: 12px 12px 12px 2px; max-width: 82%; font-size: 15px; line-height: 1.65;"'
                    f'{dm_attr(dm["text"], dm["quoteBg"])}>{msg}</section></section>'
                )
        return f'<section style="margin: 18px 0;">{"".join(bubbles)}</section>'
    if kind == 'pullquote':
        content = '<br />'.join(render_inline(ln) for ln in lines)
        return (
            f'<section style="margin: 30px 0; padding: 0 20px; text-align: center;">'
            f'<section style="font-size: 28px; line-height: 1; color: {p}; font-weight: 700; margin-bottom: 8px;">“</section>'
            f'<section style="font-size: 18px; font-weight: 600; line-height: 1.85; color: {c["text"]};"'
            f'{dm_attr(dm["text"])}>{content}</section>'
            f'<section style="width: 36px; height: 2px; background-color: {p}; margin: 14px auto 0;"><span leaf=""><br /></span></section></section>'
        )
    if kind == 'label':
        text_html = render_inline(' '.join(lines))
        if arg.lower() == 'pill':
            return (
                f'<section style="margin: 26px 0 12px;">'
                f'<span style="display: inline-block; background-color: {p}; color: #ffffff; '
                f'font-size: 13px; font-weight: 700; padding: 4px 14px; border-radius: 999px; letter-spacing: 1px;">{text_html}</span></section>'
            )
        return (
            f'<section style="display: flex; align-items: center; margin: 26px 0 12px;">'
            f'<section style="flex-shrink: 0; width: 4px; height: 16px; background-color: {p}; border-radius: 2px; margin-right: 8px;"><span leaf=""><br /></span></section>'
            f'<section style="font-size: 16px; font-weight: 700; color: {c["text"]};"'
            f'{dm_attr(dm["text"])}>{text_html}</section></section>'
        )
    if kind == 'highlight':
        content = '<br />'.join(render_inline(ln) for ln in lines)
        return (
            f'<section style="margin: 20px 0; padding: 16px 18px; background-color: {c["quoteBg"]}; '
            f'border: 1px solid {c["border"]}; border-radius: 8px; font-size: 15px; line-height: 1.8; color: {c["text"]};"'
            f'{dm_attr(dm["text"], dm["quoteBg"])}>{content}</section>'
        )
    if kind == 'summary':
        heading = html_lib.escape(arg.strip()) if arg.strip() else ('核心要点' if is_cn else 'KEY TAKEAWAYS')
        items = ''.join(
            f'<section style="margin: 6px 0; font-size: 15px; line-height: 1.75; color: {c["text"]};"'
            f'{dm_attr(dm["text"])}>• {render_inline(ln.lstrip("-*• "))}</section>'
            for ln in lines
        )
        return (
            f'<section style="margin: 24px 0; padding: 16px 18px; background-color: {c["surface"]}; '
            f'border-top: 3px solid {p}; border-radius: 6px;"'
            f'{dm_attr(dm["text"], dm["quoteBg"])}>'
            f'<section style="font-size: 14px; font-weight: 700; color: {p}; margin-bottom: 8px; letter-spacing: 1px;">{heading}</section>'
            f'{items}</section>'
        )
    content = '<br />'.join(render_inline(ln) for ln in lines)
    return (
        f'<section style="margin: 22px 0; padding: 16px 20px; border-left: 4px solid {c["quoteBorder"]}; '
        f'background-color: {c["quoteBg"]}; border-radius: 0 6px 6px 0; font-size: 16px; '
        f'line-height: 1.8; font-style: italic; color: {c["text"]};"'
        f'{dm_attr(dm["text"], dm["quoteBg"])}>{content}</section>'
    )


def build_preview_page(result: dict, theme: dict) -> str:
    safe_title = html_lib.escape(result['title'] or 'WeChat Article Preview')
    ts = resolve_theme_style(theme)
    return (
        '<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        f'<title>{safe_title}</title>\n<style>\n'
        'body{margin:0;padding:28px 16px 64px;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;}\n'
        '.bar{max-width:700px;margin:0 auto 16px;display:flex;justify-content:space-between;align-items:center;gap:12px;'
        'background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px 16px;font-size:13px;color:#4b5563;}\n'
        '.bar button{background:#111827;color:#fff;border:0;border-radius:8px;padding:8px 14px;font-size:13px;cursor:pointer;}\n'
        f'.sheet{{max-width:700px;margin:0 auto;background:{theme["colors"]["bg"]};border:1px solid {theme["colors"]["border"]};border-radius:12px;padding:28px 24px;}}\n'
        f'.h1-preview{{margin:0 0 18px;font-size:24px;line-height:1.35;color:{theme["colors"]["text"]};font-family:{ts["headingFont"]};text-align:{ts["h1Align"]};}}\n'
        '</style>\n</head>\n<body>\n'
        f'<div class="bar"><span>Theme: <strong>{html_lib.escape(result["theme"])}</strong> · {result["plainTextLength"]} chars · {len(result["images"])} images</span>'
        '<button type="button" onclick="copyWeChat()">Copy for WeChat Editor</button></div>\n'
        '<main class="sheet">\n'
        f'<h1 class="h1-preview">{safe_title}</h1>\n'
        '<!-- WECHAT_BODY_START -->\n'
        f'{result["html"]}\n'
        '<!-- WECHAT_BODY_END -->\n'
        '</main>\n<script>\n'
        'function copyWeChat(){const s=document.querySelector("main.sheet > section");if(!s)return;'
        'const r=document.createRange();r.selectNodeContents(s);const sel=window.getSelection();'
        'sel.removeAllRanges();sel.addRange(r);document.execCommand("copy");sel.removeAllRanges();'
        'alert("Copied WeChat-compatible HTML. Paste directly into mp.weixin.qq.com.");}\n'
        '</script>\n</body>\n</html>\n'
    )


SANS_STACK = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', "
    "Arial, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"
)
SERIF_STACK = "'Songti SC', 'Noto Serif SC', 'STSong', 'SimSun', Georgia, serif"


def resolve_theme_style(theme: dict) -> dict:
    """Resolve typography and layout defaults for both built-in and custom learned themes."""
    typo = theme.get('typography') or {}
    layout = theme.get('layout') or {}
    ff_kind = str(typo.get('fontFamily') or 'sans')
    if ff_kind == 'serif':
        body_font, heading_font = SERIF_STACK, SERIF_STACK
    elif ff_kind == 'serif-body-sans-heading':
        body_font, heading_font = SERIF_STACK, SANS_STACK
    else:
        body_font, heading_font = SANS_STACK, SANS_STACK
    return {
        'bodyFont': body_font,
        'headingFont': heading_font,
        'fontSize': int(typo.get('fontSize', 16)),
        'lineHeight': str(typo.get('lineHeight', 1.85)),
        'letterSpacing': str(typo.get('letterSpacing', '0.02em')),
        'borderRadius': str(typo.get('borderRadius', '6px')),
        'h1Align': str(layout.get('h1Align', 'left')),
        'h2Style': str(layout.get('h2Style', 'left-bar')),
        'quoteStyle': str(layout.get('quoteStyle', 'left-bar')),
    }


def render_h2_heading(inner_html: str, c: dict, dm: dict, ts: dict) -> str:
    """Render an H2 using the theme's distinct structural style rather than one uniform underline."""
    style_kind = ts['h2Style']
    hf = ts['headingFont']
    rad = ts['borderRadius']
    p, s, txt = c['primary'], c.get('secondary', c['primary']), c['text']
    if style_kind == 'pill-banner':
        return (
            f'<h2 style="font-family: {hf}; font-size: 18px; font-weight: 700; color: #ffffff; '
            f'background-color: {p}; margin: 30px 0 16px; padding: 9px 16px; border-radius: {rad}; '
            f'line-height: 1.45; letter-spacing: 0.03em;"'
            f'{dm_attr("#ffffff", dm["primary"])}>{inner_html}</h2>'
        )
    if style_kind == 'centered-clean':
        return (
            f'<h2 style="font-family: {hf}; font-size: 20px; font-weight: 700; color: {txt}; '
            f'text-align: center; margin: 36px 0 18px; padding-bottom: 10px; '
            f'border-bottom: 1px solid {c["border"]}; line-height: 1.45; letter-spacing: 0.08em;"'
            f'{dm_attr(dm["text"])}>{inner_html}</h2>'
        )
    if style_kind == 'bold-bottom':
        return (
            f'<h2 style="font-family: {hf}; font-size: 20px; font-weight: 800; color: {s}; '
            f'margin: 30px 0 14px; padding-bottom: 8px; border-bottom: 4px solid {txt}; '
            f'line-height: 1.4; letter-spacing: 0.02em;"'
            f'{dm_attr(dm["primary"])}>{inner_html}</h2>'
        )
    if style_kind == 'left-bar-rule':
        return (
            f'<h2 style="font-family: {hf}; font-size: 20px; font-weight: 700; color: {txt}; '
            f'margin: 30px 0 14px; padding: 4px 0 8px 12px; border-left: 4px solid {p}; '
            f'border-bottom: 1px solid {c["border"]}; line-height: 1.4;"'
            f'{dm_attr(dm["text"])}>{inner_html}</h2>'
        )
    if style_kind == 'gradient-underline':
        return (
            f'<h2 style="font-family: {hf}; font-size: 20px; font-weight: 700; color: {txt}; '
            f'margin: 30px 0 14px; padding-bottom: 10px; '
            f'border-bottom: 2px solid {p}; border-left: 4px solid {s}; padding-left: 10px; line-height: 1.4;"'
            f'{dm_attr(dm["text"])}>{inner_html}</h2>'
        )
    if style_kind == 'left-bar':
        return (
            f'<h2 style="font-family: {hf}; font-size: 20px; font-weight: 700; color: {txt}; '
            f'margin: 30px 0 14px; padding: 6px 0 6px 12px; border-left: 4px solid {p}; line-height: 1.4;"'
            f'{dm_attr(dm["text"])}>{inner_html}</h2>'
        )
    return (
        f'<h2 style="font-family: {hf}; font-size: 20px; font-weight: 700; color: {p}; '
        f'margin: 30px 0 14px; padding-bottom: 8px; border-bottom: 2px solid {p}; line-height: 1.4;"'
        f'{dm_attr(dm["primary"])}>{inner_html}</h2>'
    )


def render_blockquote_block(inner_html: str, c: dict, dm: dict, ts: dict) -> str:
    """Render blockquote matching the theme's quoteStyle."""
    qstyle = ts['quoteStyle']
    rad = ts['borderRadius']
    if qstyle == 'card':
        return (
            f'<blockquote style="margin: 20px 0; padding: 14px 18px; border: 1px solid {c["border"]}; '
            f'border-left: 4px solid {c["quoteBorder"]}; background-color: {c["quoteBg"]}; '
            f'border-radius: {rad}; font-size: 15px; line-height: {ts["lineHeight"]}; color: {c["text"]};"'
            f'{dm_attr(dm["text"], dm["quoteBg"])}>{inner_html}</blockquote>'
        )
    if qstyle == 'minimal-rule':
        return (
            f'<blockquote style="margin: 20px 0; padding: 6px 16px; border-left: 2px solid {c["quoteBorder"]}; '
            f'font-size: 15px; line-height: {ts["lineHeight"]}; color: {c["textLight"]}; font-style: italic;"'
            f'{dm_attr(dm["textLight"])}>{inner_html}</blockquote>'
        )
    return (
        f'<blockquote style="margin: 18px 0; padding: 12px 16px; border-left: 4px solid {c["quoteBorder"]}; '
        f'background-color: {c["quoteBg"]}; border-radius: 0 {rad} {rad} 0; '
        f'font-size: 15px; line-height: {ts["lineHeight"]}; color: {c["textLight"]};"'
        f'{dm_attr(dm["textLight"], dm["quoteBg"])}>{inner_html}</blockquote>'
    )


def build_gallery_page(samples: list[dict]) -> str:
    """Build a side-by-side HTML theme gallery so operators can pick a WeChat theme visually."""
    cards = []
    for item in samples:
        theme = item['themeObj']
        colors = theme['colors']
        name = html_lib.escape(theme['name'])
        desc = html_lib.escape(theme.get('description', ''))
        swatches = ''.join(
            f'<span title="{k}: {colors[k]}" style="display:inline-block;width:14px;height:14px;'
            f'border-radius:3px;border:1px solid rgba(0,0,0,0.12);background:{colors[k]};"></span>'
            for k in ('primary', 'secondary', 'bg', 'text')
            if k in colors
        )
        cards.append(
            f'<article class="theme-card" data-theme="{name}">'
            f'<header class="theme-head"><div><strong>{name}</strong>'
            f'<p class="theme-desc">{desc}</p></div><div class="swatches">{swatches}</div></header>'
            f'<div class="theme-frame" style="background:{colors["bg"]};border-color:{colors["border"]};">'
            f'{item["html"]}</div></article>'
        )
    return (
        '<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        '<title>WeChat Theme Gallery</title>\n<style>\n'
        'body{margin:0;padding:24px;background:#f3f4f6;color:#111827;'
        'font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;}\n'
        'h1{margin:0 0 6px;font-size:22px;}\n'
        '.sub{margin:0 0 20px;color:#4b5563;font-size:13px;}\n'
        '.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:18px;}\n'
        '.theme-card{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:14px;'
        'display:flex;flex-direction:column;gap:10px;}\n'
        '.theme-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;}\n'
        '.theme-desc{margin:4px 0 0;font-size:12px;color:#6b7280;line-height:1.45;}\n'
        '.swatches{display:flex;gap:4px;flex-shrink:0;padding-top:2px;}\n'
        '.theme-frame{border:1px solid #e5e7eb;border-radius:8px;padding:16px;overflow:auto;max-height:420px;}\n'
        '</style>\n</head>\n<body>\n'
        f'<h1>WeChat Theme Gallery ({len(samples)} themes)</h1>\n'
        '<p class="sub">Generated with render_wechat_html.py --gallery. Pick a theme name and pass --theme &lt;name&gt;.</p>\n'
        f'<section class="grid">\n{"".join(cards)}\n</section>\n</body>\n</html>\n'
    )
