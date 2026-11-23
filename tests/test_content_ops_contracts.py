"""Schema, platform specs, and board payload contract consistency tests for content-operations."""
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins' / 'content-operations'
SKILLS = PLUGIN / 'skills'

EXPECTED_PLATFORMS = [
    'bilibili',
    'douyin',
    'facebook',
    'instagram',
    'kuaishou',
    'linkedin',
    'pinterest',
    'threads',
    'tiktok',
    'wechat-channels',
    'wechat-official',
    'x-twitter',
    'xiaohongshu',
    'youtube',
]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ContentOpsContractsTest(unittest.TestCase):
    def test_all_14_platforms_have_valid_specs_and_matching_daily_caps(self):
        build_mod = load_module(SKILLS / 'content-ops-loop' / 'scripts' / 'build_boards.py', 'build_boards_mod')
        self.assertEqual(sorted(build_mod.DEFAULT_DAILY_CAPS.keys()), EXPECTED_PLATFORMS)

        for plat in EXPECTED_PLATFORMS:
            spec_path = SKILLS / f'platform-{plat}' / 'references' / 'specs.json'
            self.assertTrue(spec_path.is_file(), f'Missing specs.json for {plat}')
            spec = json.loads(spec_path.read_text(encoding='utf-8'))
            self.assertEqual(spec['platform'], plat)
            self.assertIn('contentLimits', spec)
            self.assertIn('mediaRules', spec)
            self.assertIn('publishPolicy', spec)
            self.assertTrue(spec['contentLimits'].get('modes'), f'{plat} must declare at least one content mode')

    def test_all_5_board_inline_placeholders_match_build_boards_payload_keys(self):
        init_mod = load_module(SKILLS / 'content-ops-loop' / 'scripts' / 'init_workspace.py', 'init_ws_mod')
        build_mod = load_module(SKILLS / 'content-ops-loop' / 'scripts' / 'build_boards.py', 'build_boards_mod2')

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / 'content-ops'
            # Ensure build_boards is importable for init_workspace
            sys.path.insert(0, str(SKILLS / 'content-ops-loop' / 'scripts'))
            try:
                init_mod.init_workspace(ws)
            finally:
                sys.path.pop(0)
            payloads = build_mod.build_payloads(ws)

            seed_re = re.compile(r'<script id="board-initial-data" type="application/json">\s*(.*?)\s*</script>', re.S)
            for board_name, payload in payloads.items():
                src_html = (SKILLS / 'content-ops-loop' / 'assets' / 'boards' / board_name / 'index.html').read_text(encoding='utf-8')
                m = seed_re.search(src_html)
                self.assertIsNotNone(m, f'{board_name}: missing board-initial-data script tag')
                placeholder = json.loads(m.group(1))
                self.assertEqual(
                    set(placeholder.keys()),
                    set(payload.keys()),
                    f'{board_name}: inline placeholder keys drift from build_boards.py output',
                )

    def test_media_production_card_deck_template_declares_export_frames(self):
        template = SKILLS / 'shortform-social' / 'assets' / 'card-deck-template' / 'index.html'
        self.assertTrue(template.is_file(), 'Missing card-deck-template/index.html')
        html = template.read_text(encoding='utf-8')
        frames = re.findall(r'data-ducoro-export-frame="([^"]+)"', html)
        self.assertEqual(frames, ['card-01', 'card-02', 'thumb-16x9', 'wechat-cover', 'wechat-square'])
        self.assertIn('html[data-ducoro-render="shot"]', html)
        self.assertIn('data-mark-ignore', html)
        self.assertTrue((SKILLS / 'shortform-social' / 'assets' / 'card-deck-template' / 'README.md').is_file())


if __name__ == '__main__':
    unittest.main()
