"""Regression tests for content-operations image_ops.py and check_media_specs.py."""
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / 'plugins' / 'content-operations' / 'skills'
IMG_PY = SKILLS / 'content-ops-loop' / 'scripts' / 'image_ops.py'
SPEC_PY = SKILLS / 'content-ops-loop' / 'scripts' / 'check_media_specs.py'
HAS_PILLOW = importlib.util.find_spec('PIL') is not None


def run_script(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, '-B', str(script), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def make_png(path: Path, width: int, height: int) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)  # RGBA
    raw = b''.join(b'\x00' + b'\x40\x80\xc0\x00' * width for _ in range(height))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def make_jpeg_with_fill_bytes(path: Path, width: int, height: int) -> None:
    # Include EXIF APP1 preceded by repeated 0xFF fill bytes before SOF0
    app1_body = b'Exif\x00\x00' + b'\x00' * 10
    app1 = b'\xff\xff\xff\xe1' + struct.pack('>H', len(app1_body) + 2) + app1_body
    sof0_body = struct.pack('>BHHB', 8, height, width, 3) + b'\x01\x11\x00\x02\x11\x01\x03\x11\x01'
    sof0 = b'\xff\xff\xc0' + struct.pack('>H', len(sof0_body) + 2) + sof0_body
    path.write_bytes(b'\xff\xd8' + app1 + sof0 + b'\xff\xd9')


def make_gif(path: Path, width: int, height: int) -> None:
    path.write_bytes(b'GIF89a' + struct.pack('<HH', width, height) + b'\x00\x00\x00\x3b')


def make_webp_vp8x(path: Path, width: int, height: int) -> None:
    w_bytes = (width - 1).to_bytes(3, 'little')
    h_bytes = (height - 1).to_bytes(3, 'little')
    body = b'WEBP' + b'VP8X' + struct.pack('<I', 10) + b'\x00\x00\x00\x00' + w_bytes + h_bytes
    path.write_bytes(b'RIFF' + struct.pack('<I', len(body)) + body)


class ContentOpsMediaScriptsTest(unittest.TestCase):
    def test_probe_handles_png_jpeg_fill_bytes_gif_and_webp(self):
        with tempfile.TemporaryDirectory() as tmp:
            p_png = Path(tmp) / 'a.png'
            p_jpg = Path(tmp) / 'b.jpg'
            p_gif = Path(tmp) / 'c.gif'
            p_webp = Path(tmp) / 'd.webp'
            make_png(p_png, 320, 240)
            make_jpeg_with_fill_bytes(p_jpg, 1080, 1350)
            make_gif(p_gif, 400, 300)
            make_webp_vp8x(p_webp, 800, 600)

            for path, fmt, w, h in [
                (p_png, 'png', 320, 240),
                (p_jpg, 'jpeg', 1080, 1350),
                (p_gif, 'gif', 400, 300),
                (p_webp, 'webp', 800, 600),
            ]:
                res = run_script(IMG_PY, 'probe', str(path))
                self.assertEqual(res.returncode, 0, res.stderr)
                info = json.loads(res.stdout)
                self.assertEqual((info['format'], info['width'], info['height']), (fmt, w, h))

    @unittest.skipUnless(HAS_PILLOW, 'Pillow not installed')
    def test_pillow_transforms_rgba_to_jpeg_compress_low_quality_and_rounded_alpha(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'rgba.png'
            make_png(src, 200, 200)  # all pixels transparent alpha=0

            out_crop = Path(tmp) / 'crop.jpg'
            self.assertEqual(run_script(IMG_PY, 'ratio-crop', str(src), str(out_crop), '--ratio', '4:5').returncode, 0)
            self.assertTrue(out_crop.is_file())

            out_resize = Path(tmp) / 'resize.jpg'
            self.assertEqual(run_script(IMG_PY, 'resize', str(src), str(out_resize), '--width', '100').returncode, 0)
            self.assertTrue(out_resize.is_file())

            out_comp = Path(tmp) / 'comp.jpg'
            res_comp = run_script(IMG_PY, 'compress', str(src), str(out_comp), '--max-kb', '50', '--quality', '25')
            self.assertEqual(res_comp.returncode, 0, res_comp.stderr)
            comp_info = json.loads(res_comp.stdout)
            self.assertTrue(out_comp.is_file())
            self.assertTrue(comp_info['metCeiling'])

            out_round = Path(tmp) / 'round.png'
            self.assertEqual(run_script(IMG_PY, 'rounded', str(src), str(out_round), '--radius', '20').returncode, 0)
            with Image.open(out_round) as im:
                # Center pixel originally had alpha=0; rounded must preserve transparency!
                self.assertEqual(im.getpixel((100, 100))[3], 0)

    def test_check_media_specs_catches_cjk_weight_fake_jpg_missing_video_path_and_crlf_threads(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / 'd-spec'
            (draft / 'assets').mkdir(parents=True)
            (draft / 'variants').mkdir(parents=True)

            # Fake JPEG: actual PNG renamed .jpg -> passes default browser channel (PNG allowed), REJECTED on --channel api (JPEG only)
            fake_jpg = draft / 'assets' / 'fake.jpg'
            make_png(fake_jpg, 1080, 1350)
            (draft / 'variants' / 'instagram.md').write_text(
                '```json\n' + json.dumps({'platform': 'instagram', 'mode': 'image_text', 'media': [{'type': 'image', 'path': 'assets/fake.jpg'}]}) + '\n```\n\nCaption',
                encoding='utf-8',
            )

            # X post with 150 CJK chars (weight 300 > 280) -> MUST FAIL
            (draft / 'variants' / 'x-twitter.md').write_text(
                '```json\n' + json.dumps({'platform': 'x-twitter', 'mode': 'text', 'media': []}) + '\n```\n\n' + ('测' * 150),
                encoding='utf-8',
            )

            # YouTube video missing path -> MUST FAIL
            (draft / 'variants' / 'youtube.md').write_text(
                '```json\n' + json.dumps({'platform': 'youtube', 'mode': 'video', 'title': 'Demo', 'media': [{'type': 'video'}]}) + '\n```\n\nDesc',
                encoding='utf-8',
            )

            # Bilibili copyright=2 without source -> MUST FAIL
            fake_mp4 = draft / 'assets' / 'v.mp4'
            fake_mp4.write_bytes(b'\x00' * 64)
            (draft / 'variants' / 'bilibili.md').write_text(
                '```json\n' + json.dumps({'platform': 'bilibili', 'mode': 'video', 'title': 'Reprint', 'media': [{'type': 'video', 'path': 'assets/v.mp4'}], 'options': {'tid': 188, 'copyright': 2}}) + '\n```\n\nDesc',
                encoding='utf-8',
            )

            res = run_script(SPEC_PY, str(draft))
            self.assertNotEqual(res.returncode, 0)
            by_plat = {r['platform']: r for r in json.loads(res.stdout)['results']}
            self.assertEqual(by_plat['instagram']['specStatus'], 'pass')
            self.assertEqual(by_plat['x-twitter']['specStatus'], 'fail')
            self.assertEqual(by_plat['youtube']['specStatus'], 'fail')
            self.assertEqual(by_plat['bilibili']['specStatus'], 'fail')
            self.assertTrue(any('source' in i['message'] for i in by_plat['bilibili']['issues']))

            # Under --channel api, Instagram Graph API enforces JPEG-only and rejects PNG disguised as .jpg
            res_api = run_script(SPEC_PY, str(draft), '--channel', 'api')
            self.assertNotEqual(res_api.returncode, 0)
            by_api = {r['platform']: r for r in json.loads(res_api.stdout)['results']}
            self.assertEqual(by_api['instagram']['specStatus'], 'fail')
            self.assertTrue(any(i['code'] == 'unsupported_format' for i in by_api['instagram']['issues']))

            # Verify mode-specific hard limits (WeChat newspic, YouTube shorts 180s, LinkedIn PDF document, XHS 18 imgs, placeholders)
            draft_modes = Path(tmp) / 'd-modes'
            (draft_modes / 'assets').mkdir(parents=True)
            (draft_modes / 'variants').mkdir(parents=True)
            make_png(draft_modes / 'assets' / 'p1.png', 1080, 1440)
            (draft_modes / 'assets' / 'deck.pdf').write_bytes(b'%PDF-1.4\n%%EOF\n')
            (draft_modes / 'assets' / 'short.mp4').write_bytes(b'\x00' * 64)
            # WeChat newspic: title > 32 chars and 0 images -> MUST FAIL
            (draft_modes / 'variants' / 'wechat-official.md').write_text(
                '```json\n' + json.dumps({'platform': 'wechat-official', 'mode': 'newspic', 'title': '超长小绿书标题' * 6, 'media': []}) + '\n```\n\nBody',
                encoding='utf-8',
            )
            # YouTube shorts > 180s -> MUST FAIL
            (draft_modes / 'variants' / 'youtube.md').write_text(
                '```json\n' + json.dumps({'platform': 'youtube', 'mode': 'shorts', 'title': 'Short', 'media': [{'type': 'video', 'path': 'assets/short.mp4', 'durationSec': 190}]}) + '\n```\n\nDesc',
                encoding='utf-8',
            )
            # LinkedIn PDF document carousel -> MUST PASS
            (draft_modes / 'variants' / 'linkedin.md').write_text(
                '```json\n' + json.dumps({'platform': 'linkedin', 'mode': 'document', 'title': 'Framework', 'topics': ['design', 'ops'], 'media': [{'type': 'document', 'path': 'assets/deck.pdf'}]}) + '\n```\n\nSummary.',
                encoding='utf-8',
            )
            # Xiaohongshu 12 images (<= 18) + 6 topics -> PASS with topic recommendation warning
            (draft_modes / 'variants' / 'xiaohongshu.md').write_text(
                '```json\n' + json.dumps({'platform': 'xiaohongshu', 'mode': 'image_text', 'title': '杭州漫步攻略', 'topics': ['a', 'b', 'c', 'd', 'e', 'f'], 'media': [{'type': 'image', 'path': 'assets/p1.png'}] * 12}) + '\n```\n\n真实分享。',
                encoding='utf-8',
            )
            # X Premium long post with TODO placeholder -> fails on unfinished_placeholder, passes once cleaned
            (draft_modes / 'variants' / 'x-twitter.md').write_text(
                '```json\n' + json.dumps({'platform': 'x-twitter', 'mode': 'text', 'options': {'long_post': True}, 'media': []}) + '\n```\n\n' + ('Long post content. ' * 25) + ' TODO add link',
                encoding='utf-8',
            )
            res_m = run_script(SPEC_PY, str(draft_modes))
            self.assertNotEqual(res_m.returncode, 0)
            bm = {r['platform']: r for r in json.loads(res_m.stdout)['results']}
            self.assertEqual(bm['wechat-official']['specStatus'], 'fail')
            self.assertEqual(bm['youtube']['specStatus'], 'fail')
            self.assertEqual(bm['linkedin']['specStatus'], 'pass')
            self.assertEqual(bm['xiaohongshu']['specStatus'], 'pass')
            self.assertTrue(any(w['code'] == 'topic_count_advisory' for w in bm['xiaohongshu']['warnings']))
            self.assertEqual(bm['x-twitter']['specStatus'], 'fail')
            self.assertTrue(any(i['code'] == 'unfinished_placeholder' for i in bm['x-twitter']['issues']))

            # CRLF multi-tweet thread on X must split cleanly and PASS
            draft_ok = Path(tmp) / 'd-crlf'
            (draft_ok / 'variants').mkdir(parents=True)
            (draft_ok / 'variants' / 'x-twitter.md').write_bytes(
                ('```json\n{"platform": "x-twitter", "mode": "text", "media": []}\n```\r\n\r\n'
                 + 'A' * 200 + '\r\n---\r\n' + 'B' * 200).encode('utf-8')
            )
            res_ok = run_script(SPEC_PY, str(draft_ok))
            self.assertEqual(res_ok.returncode, 0, res_ok.stdout)


if __name__ == '__main__':
    unittest.main()
