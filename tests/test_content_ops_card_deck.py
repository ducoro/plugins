"""Unit tests & Class-A formal verification (exhaustive combinations + fault injection) for Visual Card Studio."""
from __future__ import annotations

import importlib.util
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SHORTFORM = ROOT / 'plugins' / 'content-operations' / 'skills' / 'shortform-social'
SCRIPTS = SHORTFORM / 'scripts'
TEMPLATE_DIR = SHORTFORM / 'assets' / 'card-deck-template'


def _load_mod(path: Path, name: str):
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


CC = _load_mod(SCRIPTS / 'card_colors.py', 'card_colors')
BP = _load_mod(SCRIPTS / 'card_blueprints.py', 'card_blueprints')
CD = _load_mod(SCRIPTS / 'card_deck.py', 'card_deck')


class VisualCardStudioUnitAndFormalTest(unittest.TestCase):
    """Covers deterministic color math, scaffolding, CLI contracts, exhaustive formal checks, and fault injection."""

    def test_bundled_template_passes_audit_cleanly(self):
        report = CD.audit_deck(TEMPLATE_DIR)
        self.assertTrue(report['passed'], f"Template audit failed: {report['errors']}")
        self.assertEqual(report['errorCount'], 0)
        self.assertEqual(report['warningCount'], 0)
        self.assertEqual(report['frameCount'], 5)

    def test_formal_exhaustive_all_preset_themes_meet_wcag_invariants(self):
        """Class-A formal proof: every style x preset palette satisfies all 7 WCAG 2.1 contrast thresholds."""
        themes_report = CC.list_themes_report()
        self.assertEqual(len(themes_report), 11)
        styles_seen = set()
        for entry in themes_report:
            styles_seen.add(entry['style'])
            self.assertIn(entry['style'], CC.STYLES)
            contrast = entry['contrast']
            self.assertTrue(
                contrast['passed'],
                f"Preset {entry['id']} violated WCAG invariant: {contrast['failures']}",
            )
            ratios = contrast['ratios']
            self.assertGreaterEqual(ratios['ink_on_bg'], 7.0)
            self.assertGreaterEqual(ratios['ink_on_surface'], 7.0)
            self.assertGreaterEqual(ratios['muted_on_bg'], 4.5)
            self.assertGreaterEqual(ratios['muted_on_surface'], 4.5)
            self.assertGreaterEqual(ratios['accent_on_bg'], 4.5)
            self.assertGreaterEqual(ratios['accent_on_surface'], 4.5)
            self.assertGreaterEqual(ratios['accentInk_on_accent'], 4.5)
        self.assertEqual(styles_seen, set(CC.STYLES.keys()))

    def test_formal_exhaustive_brand_color_cube_across_all_styles(self):
        """Class-A formal proof: 5x5x5 sRGB cube (125 colors) x 3 styles = 375 combinations all satisfy WCAG."""
        levels = (0, 64, 128, 192, 255)
        checked = 0
        for r, g, b in itertools.product(levels, repeat=3):
            hex_in = f'#{r:02X}{g:02X}{b:02X}'
            for style in CC.STYLES:
                res = CC.build_brand_theme(hex_in, style, theme_id='brand')
                self.assertTrue(res['contrast']['passed'], f'{hex_in} / {style} failed contrast')
                ratios = res['contrast']['ratios']
                self.assertGreaterEqual(ratios['accent_on_bg'], 4.5)
                self.assertGreaterEqual(ratios['accent_on_surface'], 4.5)
                self.assertGreaterEqual(ratios['accentInk_on_accent'], 4.5)
                self.assertIn(f'html[data-style="{style}"][data-theme="brand"]', res['css'])
                checked += 1
        self.assertEqual(checked, 375)

    def test_brand_theme_rejects_invalid_inputs(self):
        for bad_hex in ('', 'red', '#12', '#ZZZZZZ', '1234567'):
            with self.assertRaises(ValueError):
                CC.build_brand_theme(bad_hex, 'grid-spec')
        with self.assertRaises(ValueError):
            CC.build_brand_theme('#2D6CDF', 'nonexistent-style')
        with self.assertRaises(ValueError):
            CC.build_brand_theme('#2D6CDF', 'grid-spec', theme_id='Bad_ID')

    def test_formal_exhaustive_scaffold_all_presets_styles_and_layouts(self):
        """Class-A formal proof: every style x every preset + all 10 layouts scaffold & pass audit with 0 errors."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # 1. All 3 styles x 4 presets
            for style, meta in CC.STYLES.items():
                default_theme = meta['defaultTheme']
                for preset in ('xhs-carousel', 'wechat-cover-pair', 'video-thumb', 'full-showcase'):
                    out_dir = root / f'{style}-{preset}'
                    res = CD.scaffold_deck(
                        target_dir=out_dir,
                        preset=preset,
                        style=style,
                        theme=default_theme,
                        title='测试标题用于验证完整导出结构',
                        brand='@TestBrand',
                        pages=5,
                        layouts=None,
                        brand_hex=None,
                        overwrite=True,
                    )
                    self.assertTrue(res['auditPassed'], f'{style}/{preset} failed audit: {res["errors"]}')
                    self.assertTrue((out_dir / 'index.html').is_file())
                    self.assertTrue((out_dir / 'README.md').is_file())

            # 2. Brand-hex scaffold for every style passes custom contrast audit
            for style in CC.STYLES:
                out_dir = root / f'brand-{style}'
                res = CD.scaffold_deck(
                    target_dir=out_dir,
                    preset='wechat-cover-pair',
                    style=style,
                    theme=None,
                    title='品牌色自动化生成与对比度核验指南',
                    brand='@BrandLab',
                    pages=3,
                    layouts=None,
                    brand_hex='#FF2442',
                    overwrite=True,
                )
                self.assertTrue(res['auditPassed'], f'brand/{style} failed audit: {res["errors"]}')
                self.assertEqual(res['theme'], 'brand')

            # 3. Every single layout in BP.LAYOUT_NAMES individually passes audit
            for layout in BP.LAYOUT_NAMES:
                out_dir = root / f'layout-{layout}'
                res = CD.scaffold_deck(
                    target_dir=out_dir,
                    preset='xhs-carousel',
                    style='paper-studio',
                    theme='warm-linen',
                    title='单页版式验真',
                    brand='@Studio',
                    pages=1,
                    layouts=[layout],
                    brand_hex=None,
                    overwrite=True,
                )
                self.assertTrue(res['auditPassed'], f'layout {layout} failed audit: {res["errors"]}')
                self.assertEqual(res['frameCount'], 1)

    def test_fault_injection_every_single_audit_guard_catches_violation(self):
        """Fault injection: intentionally break each of the 10 hard guards and confirm red detection."""
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp) / 'good'
            CD.scaffold_deck(
                target_dir=base_dir,
                preset='wechat-cover-pair',
                style='grid-spec',
                theme='cobalt-grid',
                title='一篇超过十二个字的公众号长标题用于测试短标题分离',
                brand='@AuditTest',
                pages=2,
                layouts=None,
                brand_hex=None,
                overwrite=True,
            )
            good_html = (base_dir / 'index.html').read_text(encoding='utf-8')
            self.assertTrue(CD.audit_deck(base_dir)['passed'])

            def check_fault(name: str, mutated_html: str, expected_rule: str):
                fdir = Path(tmp) / name
                fdir.mkdir(exist_ok=True)
                (fdir / 'index.html').write_text(mutated_html, encoding='utf-8')
                rep = CD.audit_deck(fdir)
                self.assertFalse(rep['passed'], f'Fault {name} unexpectedly passed!')
                rules = {e['rule'] for e in rep['errors']}
                self.assertIn(expected_rule, rules, f'Fault {name} missed {expected_rule}; got {rules}')

            # Fault 1: bad frame dimensions
            check_fault(
                'f1-dim',
                good_html.replace('data-ducoro-export-width="900"', 'data-ducoro-export-width="777"'),
                'frame_dimensions',
            )
            # Fault 2: duplicate export frame id & data-card id
            check_fault(
                'f2-dup',
                good_html.replace('data-ducoro-export-frame="wechat-square"', 'data-ducoro-export-frame="wechat-cover"'),
                'unique_identities',
            )
            # Fault 3: missing figure margin reset
            check_fault(
                'f3-figure',
                good_html.replace('figure, h1, h2, h3, h4, p, ul, ol, blockquote { margin: 0; }', 'h1, h2, p { margin: 0; }'),
                'no_figure_drift',
            )
            # Fault 4: absolute positioned footer
            check_fault(
                'f4-absfoot',
                good_html.replace('<footer class="card-foot">', '<footer class="card-foot" style="position: absolute; bottom: 0;">', 1),
                'no_abs_footer',
            )
            # Fault 5: unreadable tiny font below floor
            check_fault(
                'f5-tinyfont',
                good_html.replace('class="lead-copy"', 'class="lead-copy" style="font-size: 11px;"', 1),
                'min_font_floor',
            )
            # Fault 6: raw inline hex color without exemption
            check_fault(
                'f6-rawhex',
                good_html.replace('class="lead-copy"', 'class="lead-copy" style="color: #FF00AA;"', 1),
                'no_raw_inline_hex',
            )
            # Fault 7a: missing local image asset
            check_fault(
                'f7a-missing-img',
                good_html.replace('<div class="accent-rule"></div>', '<img src="assets/does-not-exist.png" alt="x" />', 1),
                'asset_paths',
            )
            # Fault 7b: remote hotlinked image blocked by default
            check_fault(
                'f7b-remote-img',
                good_html.replace('<div class="accent-rule"></div>', '<img src="https://example.com/pic.png" alt="x" />', 1),
                'asset_paths',
            )
            # Fault 7c: local file URI blocked
            check_fault(
                'f7c-file-uri',
                good_html.replace('<div class="accent-rule"></div>', '<img src="' + 'file:' + '///tmp/a.png" alt="x" />', 1),
                'asset_paths',
            )
            # Fault 8a: WeChat 900x383 without 1:1 companion
            without_sq = good_html.split('<section id="wechat-square"')[0] + '</div></main></body></html>'
            check_fault('f8a-no-square', without_sq, 'wechat_pair_integrity')
            # Fault 8b: WeChat 1:1 copies long 2.35:1 title verbatim
            copied_long = good_html.replace(
                '高转发封面<br />独立短标',
                '一篇超过十二个字的公众号长标题用于测试短标题分离',
            )
            check_fault('f8b-verbatim-long', copied_long, 'wechat_pair_integrity')
            # Fault 9: full-canvas pure black scrim in CSS
            check_fault(
                'f9-black-scrim',
                good_html.replace('</style>', '.bad-overlay { position: absolute; inset: 0; background: rgba(0, 0, 0, 0.7); }\n</style>'),
                'no_full_black_scrim',
            )
            # Fault 10: low-contrast custom brand theme
            low_contrast_css = (
                'html[data-style="grid-spec"][data-theme="badbrand"] {\n'
                '  --bg: #FFFFFF; --surface: #FFFFFF; --ink: #DDDDDD; --muted: #EEEEEE;\n'
                '  --accent: #F0F0F0; --accent-ink: #FFFFFF; --accent-soft: #F9F9F9; --border: #EEEEEE;\n'
                '}\n</style>'
            )
            check_fault(
                'f10-contrast',
                good_html.replace('data-theme="cobalt-grid"', 'data-theme="badbrand"').replace('</style>', low_contrast_css),
                'contrast_check',
            )

    def test_cli_subprocess_exit_codes_and_json_contract(self):
        """Verify CLI entry points (`themes`, `brand-theme`, `scaffold`, `audit`) emit valid JSON & exact exit codes."""
        script = str(SCRIPTS / 'card_deck.py')
        p_themes = subprocess.run([sys.executable, script, 'themes', '--json'], capture_output=True, text=True, check=True)
        themes_data = json.loads(p_themes.stdout)
        self.assertEqual(len(themes_data['themes']), 11)

        p_brand = subprocess.run(
            [sys.executable, script, 'brand-theme', '#1E88E5', '--style', 'paper-studio', '--json'],
            capture_output=True,
            text=True,
            check=True,
        )
        brand_data = json.loads(p_brand.stdout)
        self.assertTrue(brand_data['contrast']['passed'])

        p_bad = subprocess.run(
            [sys.executable, script, 'brand-theme', 'not-a-color', '--style', 'paper-studio', '--json'],
            capture_output=True,
            text=True,
        )
        self.assertEqual(p_bad.returncode, 2)
        self.assertFalse(json.loads(p_bad.stdout)['passed'])

        with tempfile.TemporaryDirectory() as tmp:
            deck_dir = Path(tmp) / 'cli-deck'
            p_scaf = subprocess.run(
                [
                    sys.executable, script, 'scaffold', str(deck_dir),
                    '--preset', 'xhs-carousel', '--style', 'darkroom-frame', '--theme', 'obsidian-gold',
                    '--pages', '4', '--title', '暗房卡片实测', '--overwrite', '--json',
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            scaf_data = json.loads(p_scaf.stdout)
            self.assertTrue(scaf_data['auditPassed'])
            self.assertEqual(scaf_data['frameCount'], 4)

            p_audit = subprocess.run(
                [sys.executable, script, 'audit', str(deck_dir), '--json'],
                capture_output=True,
                text=True,
                check=True,
            )
            audit_data = json.loads(p_audit.stdout)
            self.assertTrue(audit_data['passed'])
            self.assertEqual(audit_data['errorCount'], 0)


if __name__ == '__main__':
    unittest.main()
