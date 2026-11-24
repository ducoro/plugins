#!/usr/bin/env python3
"""CLI & scaffolding entry point for Social Visual Card Studio (zero external dependencies)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR.parent / 'assets' / 'card-deck-template'

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import card_audit as ca  # noqa: E402
import card_blueprints as bp  # noqa: E402
import card_colors as cc  # noqa: E402

audit_deck = ca.audit_deck


def scaffold_deck(
    target_dir: Path,
    preset: str,
    style: str,
    theme: Optional[str],
    title: str,
    brand: str,
    pages: int,
    layouts: Optional[List[str]],
    brand_hex: Optional[str],
    overwrite: bool,
) -> Dict[str, Any]:
    """Generate a self-contained Ducoro Board card deck folder from the bundled studio shell."""
    if style not in cc.STYLES:
        raise ValueError(f'Unknown style {style!r}; expected one of: {", ".join(cc.STYLES)}')

    brand_css = ''
    chosen_theme = theme or str(cc.STYLES[style]['defaultTheme'])
    if brand_hex:
        brand_result = cc.build_brand_theme(brand_hex, style, theme_id='brand')
        chosen_theme = 'brand'
        brand_css = str(brand_result['css'])
    elif chosen_theme not in cc.THEMES:
        raise ValueError(f'Unknown theme {chosen_theme!r}; run `themes` to list presets or pass --brand-hex')

    shell_html = (TEMPLATE_DIR / 'index.html').read_text(encoding='utf-8')
    readme_src = (TEMPLATE_DIR / 'README.md').read_text(encoding='utf-8')

    frames_blocks: List[str] = []
    if preset == 'xhs-carousel':
        seq = bp.pick_carousel_layouts(pages, layouts)
        total = len(seq)
        for idx, layout in enumerate(seq, start=1):
            frames_blocks.append(bp.render_3x4_frame(f'card-{idx:02d}', layout, idx, total, brand=brand, deck_title=title))
    elif preset == 'wechat-cover-pair':
        frames_blocks.append(bp.render_wechat_pair(wide_title=title, brand=brand))
    elif preset == 'video-thumb':
        frames_blocks.append(bp.render_video_thumb(title=title, brand=brand))
    elif preset == 'full-showcase':
        total = len(bp.LAYOUT_NAMES)
        for idx, layout in enumerate(bp.LAYOUT_NAMES, start=1):
            frames_blocks.append(bp.render_3x4_frame(f'card-{idx:02d}', layout, idx, total, brand=brand, deck_title=title))
        frames_blocks.append(bp.render_wechat_pair(wide_title=title, brand=brand))
        frames_blocks.append(bp.render_video_thumb(title=title, brand=brand))
    else:
        raise ValueError(f'Unknown preset {preset!r}; expected xhs-carousel | wechat-cover-pair | video-thumb | full-showcase')

    html_out = re.sub(r'data-style="[^"]+"', f'data-style="{style}"', shell_html, count=1)
    html_out = re.sub(r'data-theme="[^"]+"', f'data-theme="{chosen_theme}"', html_out, count=1)
    html_out = re.sub(r'<title>.*?</title>', f'<title>{title}</title>', html_out, count=1, flags=re.S)
    if brand_css:
        html_out = html_out.replace('/* <!-- BRAND_THEME_HERE --> */', brand_css)

    start_marker, end_marker = '<!-- FRAMES_START -->', '<!-- FRAMES_END -->'
    if start_marker not in html_out or end_marker not in html_out:
        raise RuntimeError('Template shell is missing FRAMES_START/FRAMES_END markers')
    before, rest = html_out.split(start_marker, 1)
    _, after = rest.split(end_marker, 1)
    html_out = f'{before}{start_marker}\n\n' + '\n\n'.join(frames_blocks) + f'\n\n    {end_marker}{after}'

    target_dir = target_dir.resolve()
    index_path = target_dir / 'index.html'
    readme_path = target_dir / 'README.md'
    if index_path.exists() and not overwrite:
        raise FileExistsError(f'{index_path} already exists (pass --overwrite to replace)')

    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / 'assets').mkdir(exist_ok=True)
    index_path.write_text(html_out, encoding='utf-8')
    if overwrite or not readme_path.exists():
        readme_path.write_text(readme_src, encoding='utf-8')

    audit = ca.audit_deck(target_dir, allow_placeholders=True)
    return {
        'dir': str(target_dir),
        'index': str(index_path),
        'readme': str(readme_path),
        'preset': preset,
        'style': style,
        'theme': chosen_theme,
        'frameCount': audit['frameCount'],
        'auditPassed': audit['passed'],
        'errors': audit['errors'],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description='Social Visual Card Studio CLI (themes, brand-theme, scaffold, audit).')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_themes = sub.add_parser('themes', help='List all built-in styles, preset palettes, and WCAG 2.1 contrast ratios.')
    p_themes.add_argument('--json', action='store_true', dest='as_json')

    p_brand = sub.add_parser('brand-theme', help='Derive a WCAG-safe [data-theme] CSS block from a brand hex color.')
    p_brand.add_argument('hex_color', help='Brand hex color, e.g. #2D6CDF')
    p_brand.add_argument('--style', required=True, choices=list(cc.STYLES.keys()))
    p_brand.add_argument('--id', default='brand', dest='theme_id')
    p_brand.add_argument('--json', action='store_true', dest='as_json')

    p_scaf = sub.add_parser('scaffold', help='Create a self-contained Ducoro Board card deck directory.')
    p_scaf.add_argument('target_dir', type=Path)
    p_scaf.add_argument('--preset', default='xhs-carousel', choices=['xhs-carousel', 'wechat-cover-pair', 'video-thumb', 'full-showcase'])
    p_scaf.add_argument('--style', default='paper-studio', choices=list(cc.STYLES.keys()))
    p_scaf.add_argument('--theme', default=None)
    p_scaf.add_argument('--brand-hex', default=None)
    p_scaf.add_argument('--title', default='核心观点卡片组')
    p_scaf.add_argument('--brand', default='@BrandName')
    p_scaf.add_argument('--pages', type=int, default=5)
    p_scaf.add_argument('--layouts', default=None, help='Comma-separated layout names for xhs-carousel')
    p_scaf.add_argument('--overwrite', action='store_true')
    p_scaf.add_argument('--json', action='store_true', dest='as_json')

    p_audit = sub.add_parser('audit', help='Run deterministic offline structural and contrast checks on a card deck.')
    p_audit.add_argument('target', type=Path)
    p_audit.add_argument('--allow-remote-img', action='store_true')
    p_audit.add_argument('--allow-custom-size', action='store_true')
    p_audit.add_argument('--allow-placeholders', action='store_true')
    p_audit.add_argument('--json', action='store_true', dest='as_json')

    args = parser.parse_args(argv)

    try:
        if args.cmd == 'themes':
            report = cc.list_themes_report()
            if args.as_json:
                print(json.dumps({'styles': cc.STYLES, 'themes': report}, ensure_ascii=False, indent=2))
            else:
                for t in report:
                    r = t['contrast']['ratios']
                    print(f"{t['id']:16s} [{t['style']:14s}] ink/bg={r['ink_on_bg']} accent/bg={r['accent_on_bg']} PASS={t['contrast']['passed']}")
            return 0

        if args.cmd == 'brand-theme':
            res = cc.build_brand_theme(args.hex_color, args.style, theme_id=args.theme_id)
            print(json.dumps(res, ensure_ascii=False, indent=2) if args.as_json else res['css'])
            return 0

        if args.cmd == 'scaffold':
            custom_layouts = [x.strip() for x in args.layouts.split(',') if x.strip()] if args.layouts else None
            res = scaffold_deck(
                target_dir=args.target_dir,
                preset=args.preset,
                style=args.style,
                theme=args.theme,
                title=args.title,
                brand=args.brand,
                pages=args.pages,
                layouts=custom_layouts,
                brand_hex=args.brand_hex,
                overwrite=args.overwrite,
            )
            if args.as_json:
                print(json.dumps(res, ensure_ascii=False, indent=2))
            else:
                print(f"Scaffolded {res['frameCount']} frame(s) into {res['dir']} ({res['style']} / {res['theme']})")
            return 0 if res['auditPassed'] else 1

        if args.cmd == 'audit':
            res = ca.audit_deck(
                args.target,
                allow_remote_img=args.allow_remote_img,
                allow_custom_size=args.allow_custom_size,
                allow_placeholders=args.allow_placeholders,
            )
            if args.as_json:
                print(json.dumps(res, ensure_ascii=False, indent=2))
            else:
                status = 'PASS' if res['passed'] else 'FAIL'
                print(f"[{status}] {res['file']} — {res['frameCount']} frames, {res['errorCount']} errors, {res['warningCount']} warnings")
                for e in res['errors']:
                    print(f"  ERROR [{e['rule']}]: {e['message']}")
                for w in res['warnings']:
                    print(f"  WARN  [{w['rule']}]: {w['message']}")
            return 0 if res['passed'] else 1
    except Exception as exc:
        if getattr(args, 'as_json', False):
            print(json.dumps({'passed': False, 'error': str(exc)}, ensure_ascii=False))
        else:
            print(f'ERROR: {exc}', file=sys.stderr)
        return 2

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
