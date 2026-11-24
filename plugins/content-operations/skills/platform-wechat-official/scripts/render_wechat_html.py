#!/usr/bin/env python3
"""Zero-dependency Markdown -> WeChat Official Account inline-style HTML renderer & validator."""
from __future__ import annotations

import argparse
import html as html_lib
import json
from pathlib import Path
import re
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from wechat_html_rules import (  # noqa: E402
    WECHAT_HTML_RULES,
    build_gallery_page,
    build_preview_page,
    dm_attr,
    html_to_plaintext,
    render_blockquote_block,
    render_container_block,
    render_h2_heading,
    resolve_theme_style,
    truncate_utf8_bytes,
    validate_wechat_html,
)

SKILL_DIR = SCRIPT_DIR.parent
THEMES_DIR = SKILL_DIR / 'assets' / 'themes'
MONO_STACK = "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace"
CJK_PUNCT = '，。！？：；、）》」』】〉》'
CJK_LATIN_A = re.compile(r'([\u4e00-\u9fff\u3400-\u4dbf])([A-Za-z0-9])')
CJK_LATIN_B = re.compile(r'([A-Za-z0-9])([\u4e00-\u9fff\u3400-\u4dbf])')
PROTECTED_COMPOUNDS = re.compile(
    r'(`[^`\n]+`|https?://[^\s)\]]+|\[[^\]]+\]\([^)]+\)'
    r'|\b(?:[ABCGHJKQUXabchqux][站股端盘恤版歌光]|[3456]G[\u4e00-\u9fff]{1,2}|第\d+[章节期步条个次天年]|[0-9]{2}后))'
)


def _load_theme_dir(directory: Path, target: dict) -> None:
    if not directory.is_dir():
        return
    for fp in sorted(directory.glob('*.json')):
        try:
            data = json.loads(fp.read_text(encoding='utf-8'))
            if isinstance(data, dict) and data.get('name') and isinstance(data.get('colors'), dict):
                target[data['name']] = data
        except Exception:
            continue


def load_themes(workspace: Path | None = None) -> dict:
    themes: dict = {}
    _load_theme_dir(THEMES_DIR, themes)
    if workspace:
        _load_theme_dir(workspace.expanduser().resolve() / 'style' / 'themes', themes)
    return themes


def strip_variant_header(text: str) -> tuple[dict, str]:
    """Strip an optional leading ```json ... ``` metadata block used by content-ops variants."""
    m = re.match(r'^\s*```json\s*\n(.*?)\n```\s*\n?', text, re.S)
    if not m:
        return {}, text
    try:
        meta = json.loads(m.group(1))
        if isinstance(meta, dict):
            return meta, text[m.end():]
    except json.JSONDecodeError:
        pass
    return {}, text


def fix_cjk_spacing(text: str) -> str:
    """Insert a space between CJK and Latin/digit boundaries outside code, URLs, and fixed compounds."""
    tokens = PROTECTED_COMPOUNDS.split(text)
    out = []
    for idx, tok in enumerate(tokens):
        if idx % 2 == 1:
            out.append(tok)
        else:
            out.append(CJK_LATIN_B.sub(r'\1 \2', CJK_LATIN_A.sub(r'\1 \2', tok)))
    return ''.join(out)


class WeChatRenderer:
    def __init__(self, theme: dict, section_numbering: bool | None = None, aigc_footer: bool = False, cjk_spacing: bool = True):
        self.theme, self.c, self.dm = theme, theme['colors'], theme['darkmode']
        self.ts = resolve_theme_style(theme)
        self.section_numbering = theme.get('sectionNumbering', False) if section_numbering is None else section_numbering
        self.aigc_footer, self.cjk_spacing = aigc_footer, cjk_spacing
        self.footnotes, self.images, self.h2_index, self.table_warnings = [], [], 0, []

    def render_inline(self, raw: str) -> str:
        text = fix_cjk_spacing(raw) if self.cjk_spacing else raw
        placeholders: list[str] = []

        def stash(fragment: str) -> str:
            idx = len(placeholders)
            placeholders.append(fragment)
            return f'\x00PH{idx}\x00'

        def repl_code(m: re.Match) -> str:
            code = html_lib.escape(m.group(1))
            style = (
                f"font-family: {MONO_STACK}; font-size: 14px; padding: 2px 6px; "
                f"border-radius: 4px; background-color: {self.c['inlineCodeBg']}; color: {self.c['inlineCodeText']};"
            )
            return stash(f'<code style="{style}"{dm_attr(self.dm["primary"], self.dm["codeBg"])}>{code}</code>')

        text = re.sub(r'`([^`\n]+)`', repl_code, text)
        text = re.sub(
            r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)',
            lambda m: stash(self._render_image(m.group(2).strip(), m.group(1).strip())),
            text,
        )

        def repl_link(m: re.Match) -> str:
            label, url = html_lib.escape(m.group(1).strip()), m.group(2).strip()
            if re.match(r'^https?://mp\.weixin\.qq\.com', url, re.I):
                safe_url = html_lib.escape(url, quote=True)
                return stash(
                    f'<a href="{safe_url}" style="color: {self.c["primary"]}; text-decoration: underline;"'
                    f'{dm_attr(self.dm["primary"])}>{label}</a>'
                )
            if re.match(r'^https?://', url, re.I):
                self.footnotes.append((m.group(1).strip(), url))
                num = len(self.footnotes)
                return stash(
                    f'<span style="color: {self.c["primary"]}; border-bottom: 1px dashed {self.c["primary"]};"'
                    f'{dm_attr(self.dm["primary"])}>{label}</span>'
                    f'<sup style="color: {self.c["primary"]}; font-size: 11px; margin-left: 2px;"'
                    f'{dm_attr(self.dm["primary"])}>[{num}]</sup>'
                )
            return stash(label)

        text = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', repl_link, text)
        text = html_lib.escape(text)

        def repl_bold(m: re.Match) -> str:
            inner, trail = m.group(1), ''
            while inner and inner[-1] in CJK_PUNCT:
                trail = inner[-1] + trail
                inner = inner[:-1]
            if not inner:
                return trail
            return (
                f'<strong style="font-weight: 700; color: {self.c["text"]};"'
                f'{dm_attr(self.dm["text"])}>{inner}</strong>{trail}'
            )

        text = re.sub(r'\*\*([^*\n]+?)\*\*', repl_bold, text)
        text = re.sub(r'~~([^~\n]+?)~~', r'<del style="opacity: 0.7;">\1</del>', text)
        text = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'<em style="font-style: italic;">\1</em>', text)

        for idx, frag in enumerate(placeholders):
            text = text.replace(f'\x00PH{idx}\x00', frag)
        return text

    def _render_image(self, src: str, alt: str) -> str:
        self.images.append(src)
        safe_src, safe_alt = html_lib.escape(src, quote=True), html_lib.escape(alt, quote=True)
        is_gif = src.lower().split('?')[0].endswith('.gif')
        parts = ['<section style="margin: 22px 0; text-align: center;">']
        if is_gif:
            parts.append(
                '<section style="display: flex; justify-content: flex-end; margin: 0 0 4px 0;">'
                '<span style="background-color: #1f2937; color: #ffffff; font-size: 11px; '
                'padding: 2px 8px; border-radius: 4px; letter-spacing: 1px;">GIF</span></section>'
            )
        parts.append(
            f'<img src="{safe_src}" alt="{safe_alt}" '
            f'style="max-width: 100%; height: auto; display: block; margin: 0 auto; border-radius: 6px;" />'
        )
        if alt:
            parts.append(
                f'<section style="margin-top: 8px; font-size: 13px; color: {self.c["textLight"]}; line-height: 1.5;"'
                f'{dm_attr(self.dm["textLight"])}>{html_lib.escape(alt)}</section>'
            )
        parts.append('</section>')
        return ''.join(parts)

    def _render_table(self, table_lines: list[str]) -> str:
        split_row = lambda line: [cell.strip() for cell in line.strip().strip('|').split('|')]
        headers = split_row(table_lines[0])
        if len(headers) > 4:
            self.table_warnings.append(f'Table has {len(headers)} columns (WeChat mobile recommends <= 4 columns)')
        th_cells = ''.join(
            f'<th style="padding: 8px 10px; border: 1px solid {self.c["border"]}; background-color: {self.c["surface"]}; '
            f'text-align: left; font-weight: 700; font-size: 14px; color: {self.c["text"]};"'
            f'{dm_attr(self.dm["text"], self.dm["quoteBg"])}>{self.render_inline(h)}</th>'
            for h in headers
        )
        body_rows = []
        for row in [split_row(ln) for ln in table_lines[2:]]:
            tds = ''.join(
                f'<td style="padding: 8px 10px; border: 1px solid {self.c["border"]}; font-size: 14px; '
                f'line-height: 1.6; color: {self.c["text"]};"{dm_attr(self.dm["text"])}>'
                f'{self.render_inline(row[i] if i < len(row) else "")}</td>'
                for i in range(len(headers))
            )
            body_rows.append(f'<tr>{tds}</tr>')
        return (
            f'<section style="margin: 18px 0; overflow-x: auto;">'
            f'<table style="width: 100%; border-collapse: collapse; border: 1px solid {self.c["border"]};">'
            f'<thead><tr>{th_cells}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></section>'
        )

    def convert(self, markdown_text: str) -> dict:
        meta, md = strip_variant_header(markdown_text)
        lines = md.replace('\r\n', '\n').split('\n')
        title = str(meta.get('title') or '').strip()
        blocks: list[str] = []
        i, n = 0, len(lines)

        while i < n:
            stripped = lines[i].strip()
            if not stripped:
                i += 1
                continue

            fence = re.match(r'^```([A-Za-z0-9_+-]*)\s*$', stripped)
            if fence:
                lang = fence.group(1).strip() or 'text'
                i += 1
                code_lines = []
                while i < n and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                if i < n:
                    i += 1
                code_text = html_lib.escape('\n'.join(code_lines))
                blocks.append(
                    f'<section style="margin: 18px 0; background-color: {self.c["codeBg"]}; border-radius: 8px; overflow: hidden;"'
                    f'{dm_attr(None, self.dm["codeBg"])}>'
                    f'<section style="display: flex; justify-content: flex-end; padding: 6px 12px 0; '
                    f'font-family: {MONO_STACK}; font-size: 11px; color: #94a3b8; letter-spacing: 0.5px;">{html_lib.escape(lang)}</section>'
                    f'<pre data-lang="{html_lib.escape(lang, quote=True)}" style="margin: 0; padding: 10px 14px 14px; overflow-x: auto; '
                    f'white-space: pre-wrap; word-wrap: break-word; font-family: {MONO_STACK}; font-size: 13px; '
                    f'line-height: 1.6; color: {self.c["codeText"]};"><code>{code_text}</code></pre></section>'
                )
                continue

            cm = re.match(r'^:::(callout|steps|timeline|pullquote|label|quote|dialogue|highlight|summary)(?:[ \t]+(.+?))?\s*$', stripped)
            if cm:
                kind, arg = cm.group(1), cm.group(2) or ''
                i += 1
                buf = []
                while i < n and lines[i].strip() != ':::':
                    buf.append(lines[i])
                    i += 1
                if i < n:
                    i += 1
                blocks.append(render_container_block(kind, arg, '\n'.join(buf), self.c, self.dm, self.render_inline))
                continue

            hm = re.match(r'^(#{1,4})\s+(.*)$', stripped)
            if hm:
                level, heading_text = len(hm.group(1)), hm.group(2).strip()
                i += 1
                if level == 1:
                    if not title:
                        title = heading_text
                    continue
                if level == 2:
                    self.h2_index += 1
                    prefix = f'{self.h2_index:02d} · ' if self.section_numbering else ''
                    blocks.append(render_h2_heading(f'{prefix}{self.render_inline(heading_text)}', self.c, self.dm, self.ts))
                elif level == 3:
                    blocks.append(
                        f'<h3 style="font-family: {self.ts["headingFont"]}; font-size: 17px; font-weight: 700; color: {self.c["text"]}; '
                        f'margin: 24px 0 10px; padding-left: 10px; border-left: 3px solid {self.c["primary"]}; line-height: 1.4;"'
                        f'{dm_attr(self.dm["text"])}>{self.render_inline(heading_text)}</h3>'
                    )
                else:
                    blocks.append(
                        f'<h4 style="font-size: 16px; font-weight: 700; color: {self.c["text"]}; margin: 18px 0 8px; line-height: 1.4;"'
                        f'{dm_attr(self.dm["text"])}>{self.render_inline(heading_text)}</h4>'
                    )
                continue

            if re.match(r'^(?:-{3,}|\*{3,}|_{3,})$', stripped):
                i += 1
                blocks.append(
                    f'<section style="margin: 24px 0; height: 1px; background-color: {self.c["border"]};"><span leaf=""><br /></span></section>'
                )
                continue

            if stripped.startswith('>'):
                q_lines = []
                while i < n and lines[i].strip().startswith('>'):
                    q_lines.append(lines[i].strip()[1:].strip())
                    i += 1
                content = '<br />'.join(self.render_inline(ln) for ln in q_lines if ln)
                blocks.append(render_blockquote_block(content, self.c, self.dm, self.ts))
                continue

            if '|' in stripped and i + 1 < n and re.match(r'^\|?[\s:-]+\|[\s|:-]*$', lines[i + 1].strip()):
                t_lines = [lines[i], lines[i + 1]]
                i += 2
                while i < n and '|' in lines[i].strip() and lines[i].strip():
                    t_lines.append(lines[i])
                    i += 1
                blocks.append(self._render_table(t_lines))
                continue

            if re.match(r'^(?:[-*+]\s+|\d+\.\s+)', stripped):
                ordered = bool(re.match(r'^\d+\.\s+', stripped))
                items, idx_num = [], 1
                while i < n:
                    s = lines[i].strip()
                    m_li = re.match(r'^(\d+)\.\s+(.*)$', s) if ordered else re.match(r'^[-*+]\s+(.*)$', s)
                    if not m_li:
                        break
                    marker = f'{idx_num}.' if ordered else '•'
                    body_txt = m_li.group(2) if ordered else m_li.group(1)
                    items.append(
                        f'<section style="display: flex; align-items: flex-start; margin: 8px 0; font-size: {self.ts["fontSize"]}px; line-height: {self.ts["lineHeight"]}; color: {self.c["text"]};"'
                        f'{dm_attr(self.dm["text"])}>'
                        f'<span style="flex-shrink: 0; width: 22px; color: {self.c["primary"]}; font-weight: 700;"'
                        f'{dm_attr(self.dm["primary"])}>{marker}</span>'
                        f'<section style="flex: 1;">{self.render_inline(body_txt)}</section></section>'
                    )
                    idx_num += 1
                    i += 1
                blocks.append(f'<section style="margin: 14px 0;">{"".join(items)}</section>')
                continue

            img_m = re.match(r'^!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)$', stripped)
            if img_m:
                i += 1
                blocks.append(self._render_image(img_m.group(2).strip(), img_m.group(1).strip()))
                continue

            p_lines = [stripped]
            i += 1
            while i < n:
                nxt = lines[i].strip()
                if not nxt or re.match(r'^(?:#{1,4}\s+|```|:::|>|[-*+]\s+|\d+\.\s+|(?:-{3,}|\*{3,}|_{3,})$|!\[)', nxt):
                    break
                p_lines.append(nxt)
                i += 1
            content = '<br />'.join(self.render_inline(ln) for ln in p_lines)
            blocks.append(
                f'<p style="margin: 14px 0; font-size: {self.ts["fontSize"]}px; line-height: {self.ts["lineHeight"]}; '
                f'color: {self.c["text"]}; letter-spacing: {self.ts["letterSpacing"]};"'
                f'{dm_attr(self.dm["text"])}>{content}</p>'
            )

        if self.footnotes:
            fn_rows = ''.join(
                f'<section style="margin: 4px 0; font-size: 13px; line-height: 1.6; color: {self.c["textLight"]}; word-break: break-all;"'
                f'{dm_attr(self.dm["textLight"])}>[{idx}] {html_lib.escape(lbl)}: {html_lib.escape(url)}</section>'
                for idx, (lbl, url) in enumerate(self.footnotes, start=1)
            )
            blocks.append(
                f'<section style="margin-top: 32px; padding-top: 16px; border-top: 1px solid {self.c["border"]};">'
                f'<section style="font-size: 14px; font-weight: 700; color: {self.c["text"]}; margin-bottom: 8px;"'
                f'{dm_attr(self.dm["text"])}>参考链接</section>{fn_rows}</section>'
            )

        if self.aigc_footer:
            blocks.append(
                f'<section style="margin-top: 24px; padding-top: 12px; border-top: 1px dashed {self.c["border"]}; '
                f'font-size: 12px; color: {self.c["textLight"]}; text-align: center;"'
                f'{dm_attr(self.dm["textLight"])}>本文部分内容由人工智能辅助创作与排版，经作者审核确认。</section>'
            )

        body_html = (
            f'<section style="font-family: {self.ts["bodyFont"]}; font-size: {self.ts["fontSize"]}px; '
            f'line-height: {self.ts["lineHeight"]}; letter-spacing: {self.ts["letterSpacing"]}; '
            f'color: {self.c["text"]}; background-color: {self.c["bg"]}; padding: 8px 4px; word-wrap: break-word;"'
            f'{dm_attr(self.dm["text"], self.dm["bg"])}>\n'
            + '\n'.join(blocks)
            + '\n</section>'
        )
        plain = html_to_plaintext(body_html)
        raw_digest = str(meta.get('digest') or '').strip() or plain
        digest = truncate_utf8_bytes(raw_digest, 120)
        return {
            'title': title,
            'digest': digest,
            'theme': self.theme['name'],
            'html': body_html,
            'images': self.images,
            'footnoteCount': len(self.footnotes),
            'tableWarnings': self.table_warnings,
            'plainTextLength': len(plain),
        }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Render Markdown to WeChat-compatible inline HTML and run 16-rule validation.')
    ap.add_argument('input', nargs='?', help='Input Markdown (or HTML with --validate-only).')
    ap.add_argument('--theme', default='professional-clean', help='Theme name (built-in or learned under <workspace>/style/themes/).')
    ap.add_argument('--workspace', help='Optional content-ops workspace path to load custom learned themes from style/themes/.')
    ap.add_argument('--mode', choices=['api', 'preview'], default='api', help='Output pure WeChat body HTML or standalone browser preview.')
    ap.add_argument('--aigc-footer', action='store_true', help='Append optional AIGC disclosure footer (off by default).')
    ap.add_argument('--section-numbering', action='store_true', help='Force numbered H2 headings regardless of theme default.')
    ap.add_argument('--no-cjk-spacing', action='store_true', help='Disable automatic CJK-Latin spacing.')
    ap.add_argument('--validate-only', action='store_true', help='Validate an existing HTML file against WeChat rules.')
    ap.add_argument('--list-themes', action='store_true', help='List all built-in WeChat themes.')
    ap.add_argument('--gallery', help='Render a side-by-side HTML gallery of all available themes to this output path.')
    ap.add_argument('-o', '--output', help='Write rendered HTML to this path.')
    ap.add_argument('--json', action='store_true', help='Print structured JSON report to stdout.')
    args = ap.parse_args(argv)

    themes = load_themes(Path(args.workspace) if args.workspace else None)
    if args.list_themes:
        summary = [{'name': k, 'description': v['description'], 'sectionNumbering': v.get('sectionNumbering', False)} for k, v in themes.items()]
        print(json.dumps(summary, indent=2, ensure_ascii=False) if args.json else '\n'.join(f"- {t['name']}: {t['description']}" for t in summary))
        return 0
    if args.gallery:
        sample_md = (
            Path(args.input).expanduser().resolve().read_text(encoding='utf-8')
            if args.input and Path(args.input).expanduser().is_file()
            else '# Theme Preview\n\n## Core Section\n\nBody copy with **emphasis**, `inline code`, and [link](https://example.com).\n\n> Quoted takeaway.\n\n:::callout\nKey operational highlight.\n:::\n'
        )
        samples = [{'themeObj': t, 'html': WeChatRenderer(t).convert(sample_md)['html']} for t in themes.values()]
        gal_path = Path(args.gallery).expanduser().resolve()
        gal_path.parent.mkdir(parents=True, exist_ok=True)
        gal_path.write_text(build_gallery_page(samples), encoding='utf-8')
        info = {'ok': True, 'galleryPath': str(gal_path), 'themeCount': len(samples), 'themes': sorted(themes)}
        print(json.dumps(info, indent=2, ensure_ascii=False) if args.json else f'Generated gallery ({len(samples)} themes) -> {gal_path}')
        return 0

    if not args.input:
        ap.error('input file path is required unless --list-themes or --gallery is used')
    in_path = Path(args.input).expanduser().resolve()
    if not in_path.is_file():
        print(f'Error: file not found: {in_path}', file=sys.stderr)
        return 1

    if args.validate_only:
        issues = validate_wechat_html(in_path.read_text(encoding='utf-8'))
        errors = sum(1 for item in issues if item['level'] == 'ERROR')
        warnings = len(issues) - errors
        out = {'file': str(in_path), 'ok': errors == 0, 'errors': errors, 'warnings': warnings, 'issues': issues}
        if args.json:
            print(json.dumps(out, indent=2, ensure_ascii=False))
        else:
            print(f'WeChat HTML validation: {errors} errors, {warnings} warnings')
            for item in issues:
                print(f"  [{item['level']}] {item['rule']} x{item['count']}: {item['message']}")
        return 1 if errors > 0 else 0

    if args.theme not in themes:
        print(f'Error: unknown theme "{args.theme}". Available: {", ".join(sorted(themes))}', file=sys.stderr)
        return 1

    theme = themes[args.theme]
    renderer = WeChatRenderer(theme, True if args.section_numbering else None, args.aigc_footer, not args.no_cjk_spacing)
    result = renderer.convert(in_path.read_text(encoding='utf-8'))
    issues = validate_wechat_html(result['html'])
    errors = sum(1 for item in issues if item['level'] == 'ERROR')
    warnings = len(issues) - errors + len(result['tableWarnings'])
    final_html = build_preview_page(result, theme) if args.mode == 'preview' else result['html']

    out_path = None
    if args.output:
        out_path = Path(args.output).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(final_html, encoding='utf-8')

    report = {
        'ok': errors == 0,
        'mode': args.mode,
        'theme': result['theme'],
        'title': result['title'],
        'digest': result['digest'],
        'images': result['images'],
        'footnoteCount': result['footnoteCount'],
        'plainTextLength': result['plainTextLength'],
        'outputPath': str(out_path) if out_path else None,
        'errors': errors,
        'warnings': warnings,
        'issues': issues,
        'tableWarnings': result['tableWarnings'],
    }
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif not out_path:
        print(final_html)
    else:
        print(f'Rendered {args.mode} HTML ({result["theme"]}) -> {out_path} ({errors} errors, {warnings} warnings)')
    return 1 if errors > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
