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
LP = _load_mod(SCRIPTS / 'live_photo.py', 'live_photo')
EXAMPLES_DIR = SHORTFORM / 'assets' / 'examples'


class VisualCardStudioUnitAndFormalTest(unittest.TestCase):
    """Covers deterministic color math, scaffolding, CLI contracts, exhaustive formal checks, and fault injection."""

    def test_bundled_template_passes_audit_cleanly(self):
        # Bundled starter template contains demo placeholders: strict audit catches them, --allow-placeholders passes
        strict_rep = CD.audit_deck(TEMPLATE_DIR)
        self.assertFalse(strict_rep['passed'])
        self.assertIn('unfinished_placeholders', {e['rule'] for e in strict_rep['errors']})

        report = CD.audit_deck(TEMPLATE_DIR, allow_placeholders=True)
        self.assertTrue(report['passed'], f"Template audit failed: {report['errors']}")
        self.assertEqual(report['errorCount'], 0)
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
        """Class-A formal proof: 5x5x5 sRGB cube (125 colors) x 3 styles = 375 combinations satisfy WCAG 2.1 AA."""
        levels = (0, 64, 128, 192, 255)
        checked = 0
        for r, g, b in itertools.product(levels, repeat=3):
            hex_in = f'#{r:02X}{g:02X}{b:02X}'
            for style in CC.STYLES:
                res = CC.build_brand_theme(hex_in, style, theme_id='brand')
                self.assertTrue(res['contrast']['passed'], f'{hex_in} / {style} failed contrast')
                ratios = res['contrast']['ratios']
                self.assertGreaterEqual(ratios['ink_on_bg'], 4.5)
                self.assertGreaterEqual(ratios['accent_on_bg'], 3.0)
                self.assertGreaterEqual(ratios['accent_on_surface'], 3.0)
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
            # 1. All 3 styles x all 6 presets (including 4:5 Instagram & LinkedIn PDF carousels)
            for style, meta in CC.STYLES.items():
                default_theme = meta['defaultTheme']
                for preset in CD.PRESETS:
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
                    if preset in ('ig-carousel', 'linkedin-pdf'):
                        rendered_html = (out_dir / 'index.html').read_text(encoding='utf-8')
                        self.assertIn('frame-4x5', rendered_html)
                        self.assertIn('@page { size: 1080px 1350px; margin: 0; }', rendered_html)

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
        """Fault injection for all 5 objective hard guards + verification that freeform custom HTML passes."""
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

            # Guard 1: bad frame dimensions (and verify --allow-custom-size permits custom dimensions)
            bad_dim_html = good_html.replace('data-export-width="900"', 'data-export-width="777"')
            check_fault('f1-dim', bad_dim_html, 'frame_dimensions')
            self.assertTrue(CD.audit_deck(Path(tmp) / 'f1-dim', allow_custom_size=True)['passed'])

            # Guard 2: duplicate export frame id
            check_fault(
                'f2-dup',
                good_html.replace('data-export-frame="wechat-square"', 'data-export-frame="wechat-cover"'),
                'unique_identities',
            )

            # Guard 3: broken local image / remote hotlink / file URI
            check_fault(
                'f3a-missing-img',
                good_html.replace('<div class="accent-rule"></div>', '<img src="assets/does-not-exist.png" alt="x" />', 1),
                'asset_paths',
            )
            check_fault(
                'f3b-remote-img',
                good_html.replace('<div class="accent-rule"></div>', '<img src="https://example.com/pic.png" alt="x" />', 1),
                'asset_paths',
            )
            check_fault(
                'f3c-file-uri',
                good_html.replace('<div class="accent-rule"></div>', '<img src="' + 'file:' + '///tmp/a.png" alt="x" />', 1),
                'asset_paths',
            )

            # Guard 4: unfinished placeholder text / placeholder box
            check_fault(
                'f4-placeholder',
                good_html.replace('@AuditTest', 'TODO replace brand', 1),
                'unfinished_placeholders',
            )

            # Guard 5: low-contrast declared theme
            low_contrast_css = (
                'html[data-style="grid-spec"][data-theme="badbrand"] {\n'
                '  --bg: #FFFFFF; --surface: #FFFFFF; --ink: #DDDDDD; --muted: #EEEEEE;\n'
                '  --accent: #F0F0F0; --accent-ink: #FFFFFF; --accent-soft: #F9F9F9; --border: #EEEEEE;\n'
                '}\n</style>'
            )
            check_fault(
                'f5-contrast',
                good_html.replace('data-theme="cobalt-grid"', 'data-theme="badbrand"').replace('</style>', low_contrast_css),
                'contrast_check',
            )

            # Advisories (non-blocking warnings): tiny font & WeChat pair check warn but never block
            warn_dir = Path(tmp) / 'advisory-only'
            warn_dir.mkdir()
            (warn_dir / 'index.html').write_text(
                good_html.replace('class="lead-copy"', 'class="lead-copy" style="font-size: 11px;"', 1),
                encoding='utf-8',
            )
            wrep = CD.audit_deck(warn_dir)
            self.assertTrue(wrep['passed'])
            self.assertIn('min_font_advisory', {w['rule'] for w in wrep['warnings']})

            # Creative freedom: freeform custom HTML using only standard render.md `data-export-frame` + inline CSS pixels passes cleanly!
            free_dir = Path(tmp) / 'freeform-custom'
            free_dir.mkdir()
            (free_dir / 'index.html').write_text(
                '<!doctype html><html><body>'
                '<section data-export-frame="slide-01" '
                'style="width:1080px;height:1350px;background:#FDF4E7;color:#1F1A17;position:relative;">'
                '<h1 style="color:#E63946;font-size:64px;">Custom Editorial Poster</h1>'
                '<footer style="position:absolute;bottom:24px;">@Creator</footer></section>'
                '</body></html>',
                encoding='utf-8',
            )
            frep = CD.audit_deck(free_dir)
            self.assertTrue(frep['passed'], f'Freeform custom HTML was wrongly blocked: {frep["errors"]}')
            self.assertEqual(frep['errorCount'], 0)

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

            # Fresh scaffold contains starter placeholders: strict audit blocks until filled, --allow-placeholders passes
            p_audit_strict = subprocess.run(
                [sys.executable, script, 'audit', str(deck_dir), '--json'],
                capture_output=True, text=True,
            )
            self.assertEqual(p_audit_strict.returncode, 1)
            self.assertIn('unfinished_placeholders', {e['rule'] for e in json.loads(p_audit_strict.stdout)['errors']})

            p_audit = subprocess.run(
                [sys.executable, script, 'audit', str(deck_dir), '--allow-placeholders', '--json'],
                capture_output=True, text=True, check=True,
            )
            audit_data = json.loads(p_audit.stdout)
            self.assertTrue(audit_data['passed'])
            self.assertEqual(audit_data['errorCount'], 0)

    def test_golden_examples_gallery_and_all_three_decks_pass_audit_zero_placeholders(self):
        """All 3 finished golden examples pass card_deck audit with 0 warnings and zero placeholder stubs."""
        gallery = EXAMPLES_DIR / 'index.html'
        self.assertTrue(gallery.is_file(), 'Missing golden examples gallery index.html')
        gallery_html = gallery.read_text(encoding='utf-8')

        expected = {
            'xhs-tool-teardown': 5,
            'xhs-travel-route': 4,
            'wechat-cover-pair': 3,
            'xhs-live-photo': 3,
        }
        for slug, expected_frames in expected.items():
            self.assertIn(f'{slug}/index.html', gallery_html)
            deck_dir = EXAMPLES_DIR / slug
            rep = CD.audit_deck(deck_dir)
            self.assertTrue(rep['passed'], f'Golden example {slug} failed audit: {rep["errors"]}')
            self.assertEqual(rep['errorCount'], 0)
            self.assertEqual(rep['warningCount'], 0)
            self.assertEqual(rep['frameCount'], expected_frames)
            raw = (deck_dir / 'index.html').read_text(encoding='utf-8')
            frames_body = raw.split('<!-- FRAMES_START -->', 1)[1].split('<!-- FRAMES_END -->', 1)[0]
            self.assertNotIn('替换为 <img', frames_body, f'Golden example {slug} leaked placeholder text')
            self.assertNotIn('media-placeholder', frames_body, f'Golden example {slug} leaked placeholder box')

    def test_formal_exhaustive_live_photo_budget_and_layout_filters(self):
        """Class-A formal proof: 160 budget combinations + all 10 ffmpeg filter graphs satisfy invariants."""
        durations = (
            0.4, 1.0, 2.0, 2.5, 2.55, 3.0, 3.2, 4.2, 4.25, 4.8,
            4.81, 5.0, 5.2, 7.9, 8.0, 8.1, 12.0, 30.0, 60.0, 120.0,
        )
        checked = 0
        for plat, spec in LP.PLATFORM_BUDGETS.items():
            target = float(spec['targetSec'])
            min_ok = round(target * 0.85, 2)
            long_th = round(target * 1.6, 2)
            for dur in durations:
                for clips in (1, 2, 3, 4):
                    res = LP.diagnose_budget(dur, plat, clips)
                    if dur > long_th:
                        self.assertEqual(res['status'], 'long_video_needs_diagnosis')
                    elif dur < min_ok:
                        self.assertEqual(res['status'], 'too_short_needs_confirm')
                    else:
                        self.assertEqual(res['status'], 'ready')
                    checked += 1
        self.assertEqual(checked, 160)

        # Exhaustively verify all 5 layouts x overlay flag
        for layout, count in LP.LAYOUT_CLIP_COUNTS.items():
            for has_ov in (False, True):
                graph, out_lbl = LP.build_layout_filter(layout, 1080, 1440, has_overlay=has_ov)
                for idx in range(count):
                    self.assertIn(f'[{idx}:v]', graph)
                if has_ov:
                    self.assertIn(f'[{count}:v]', graph)
                    self.assertEqual(out_lbl, '[outv]')
                else:
                    self.assertEqual(out_lbl, '[base]')

    def test_live_photo_fault_injection_and_optional_native_roundtrip(self):
        """Fault injection for Live Photo validator (plus real ffmpeg/Swift end-to-end when installed)."""
        import platform as py_platform
        import plistlib
        import shutil

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Fault 1: broken .pvt missing files
            bad_pvt = root / 'broken.pvt'
            bad_pvt.mkdir()
            rep = LP.validate_motion_artifact(bad_pvt, 'xiaohongshu')
            self.assertFalse(rep['passed'])
            self.assertIn('pvt_structure', {e['rule'] for e in rep['errors']})

            # Fault 2: .pvt with mismatched pairing UUID and fake JPG header
            mismatch_pvt = root / 'mismatch.pvt'
            mismatch_pvt.mkdir()
            (mismatch_pvt / 'IMG.JPG').write_bytes(b'NOTAJPEG')
            (mismatch_pvt / 'IMG.MOV').write_bytes(b'NOTAMOV')
            (mismatch_pvt / 'metadata.plist').write_bytes(
                plistlib.dumps({
                    'PFVideoComplementMetadataVersionKey': '1',
                    'PFVideoComplementMetadataPairingIdentifierKey': '11111111-2222-3333-4444-555555555555',
                })
            )
            rep2 = LP.validate_motion_artifact(mismatch_pvt, 'wechat')
            self.assertFalse(rep2['passed'])
            rules2 = {e['rule'] for e in rep2['errors']}
            self.assertIn('jpg_signature', rules2)
            self.assertIn('pvt_pairing_id', rules2)

            # Real ffmpeg + optional macOS Swift roundtrip + duration/dimension fault injection
            if shutil.which('ffmpeg') and shutil.which('ffprobe'):
                src = root / 'clip.mp4'
                subprocess.run(
                    ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=640x480:rate=24:duration=4',
                     '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(src)],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                # Wrong dimensions (640x480) & over-duration for WeChat (4s > 3.2s) must fail closed
                bad_clip = LP.validate_motion_artifact(src, 'wechat')
                self.assertFalse(bad_clip['passed'])
                bad_rules = {e['rule'] for e in bad_clip['errors']}
                self.assertIn('dimensions', bad_rules)
                self.assertIn('duration_ceiling', bad_rules)

                # Valid 3s WeChat triple-row compose + contact-sheet
                cs = LP.make_contact_sheet(src, root / 'cs.png', cols=2, rows=2)
                self.assertTrue(Path(cs['output']).is_file())
                mov_out = root / 'triple.mov'
                jpg_out = root / 'triple.jpg'
                LP.compose_motion_card(
                    [src, src, src], mov_out, target_platform='wechat',
                    layout='triple-row', duration_sec=3.0, key_jpg=jpg_out,
                    fallback_mp4=root / 'triple-fallback.mp4',
                )
                ok_mov = LP.validate_motion_artifact(mov_out, 'wechat')
                self.assertTrue(ok_mov['passed'], ok_mov['errors'])

                if py_platform.system() == 'Darwin' and shutil.which('swift'):
                    pvt_out = root / 'triple.pvt'
                    LP.package_pvt(jpg_out, mov_out, pvt_out)
                    ok_pvt = LP.validate_motion_artifact(pvt_out, 'wechat')
                    self.assertTrue(ok_pvt['passed'], ok_pvt['errors'])


if __name__ == '__main__':
    unittest.main()
