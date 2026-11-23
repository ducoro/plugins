#!/usr/bin/env python3
"""Deterministic local image inspection and editing helper for content-operations.

`probe` works with Python 3 standard library only (PNG, JPEG, GIF, WebP).
Pixel transforms (`ratio-crop`, `resize`, `compress`, `rounded`, `overlay`) use Pillow
when installed and report a clear setup hint if Pillow is absent.
"""
import argparse
import json
from pathlib import Path
import struct
import sys


def probe_image_stdlib(path: Path) -> dict:
    raw = path.read_bytes()
    size_bytes = len(raw)
    width = height = None
    fmt = path.suffix.lstrip('.').lower() or 'unknown'

    if raw[:8] == b'\x89PNG\r\n\x1a\n' and len(raw) >= 24:
        fmt = 'png'
        width, height = struct.unpack('>II', raw[16:24])
    elif raw[:6] in (b'GIF87a', b'GIF89a') and len(raw) >= 10:
        fmt = 'gif'
        width, height = struct.unpack('<HH', raw[6:10])
    elif raw[:4] == b'RIFF' and raw[8:12] == b'WEBP' and len(raw) >= 30:
        fmt = 'webp'
        chunk = raw[12:16]
        if chunk == b'VP8X' and len(raw) >= 30:
            width = 1 + int.from_bytes(raw[24:27], 'little')
            height = 1 + int.from_bytes(raw[27:30], 'little')
        elif chunk == b'VP8 ' and len(raw) >= 30:
            width, height = struct.unpack('<HH', raw[26:30])
            width &= 0x3FFF
            height &= 0x3FFF
        elif chunk == b'VP8L' and len(raw) >= 25:
            bits = int.from_bytes(raw[21:25], 'little')
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
    elif raw[:2] == b'\xff\xd8':
        fmt = 'jpeg'
        i = 2
        while i + 2 < len(raw):
            if raw[i] != 0xFF:
                i += 1
                continue
            # Skip repeated 0xFF fill bytes per JPEG spec
            while i < len(raw) and raw[i] == 0xFF:
                i += 1
            if i >= len(raw):
                break
            marker = raw[i]
            i += 1
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                if i + 7 <= len(raw):
                    height, width = struct.unpack('>HH', raw[i + 3:i + 7])
                break
            if marker in (0xD8, 0xD9, 0x01, 0x00) or (0xD0 <= marker <= 0xD7):
                continue
            if i + 2 > len(raw):
                break
            seg_len = struct.unpack('>H', raw[i:i + 2])[0]
            if seg_len < 2:
                break
            i += seg_len

    ratio = round(width / height, 4) if width and height else None
    return {
        'path': str(path),
        'format': fmt,
        'width': width,
        'height': height,
        'aspectRatio': ratio,
        'sizeBytes': size_bytes,
    }


def require_pillow():
    try:
        from PIL import Image, ImageDraw
        return Image, ImageDraw
    except ImportError as exc:
        raise RuntimeError(
            'Pillow is required for pixel transforms. Install with: python3 -m pip install Pillow'
        ) from exc


def parse_ratio(text: str) -> float:
    if ':' in text:
        w, h = text.split(':', 1)
        return float(w) / float(h)
    return float(text)


def save_image(img, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() in ('.jpg', '.jpeg') and img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
    img.save(out)


def cmd_ratio_crop(args) -> dict:
    Image, _ = require_pillow()
    target_ratio = parse_ratio(args.ratio)
    with Image.open(args.input) as img:
        w, h = img.size
        cur_ratio = w / h
        if cur_ratio > target_ratio:
            new_w = int(round(h * target_ratio))
            new_h = h
        else:
            new_w = w
            new_h = int(round(w / target_ratio))
        left = (w - new_w) // 2
        top = (h - new_h) // 2
        if args.gravity == 'top':
            top = 0
        elif args.gravity == 'bottom':
            top = h - new_h
        cropped = img.crop((left, top, left + new_w, top + new_h))
        if args.max_width and cropped.width > args.max_width:
            scale = args.max_width / cropped.width
            cropped = cropped.resize((args.max_width, int(round(cropped.height * scale))), Image.LANCZOS)
        save_image(cropped, Path(args.output))
    return probe_image_stdlib(Path(args.output))


def cmd_resize(args) -> dict:
    Image, _ = require_pillow()
    with Image.open(args.input) as img:
        w, h = img.size
        if args.width and args.height:
            target = (args.width, args.height)
        elif args.width:
            target = (args.width, int(round(h * (args.width / w))))
        elif args.height:
            target = (int(round(w * (args.height / h))), args.height)
        else:
            raise ValueError('Provide --width and/or --height')
        resized = img.resize(target, Image.LANCZOS)
        save_image(resized, Path(args.output))
    return probe_image_stdlib(Path(args.output))


def cmd_compress(args) -> dict:
    Image, _ = require_pillow()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    max_bytes = int(args.max_kb * 1024)
    with Image.open(args.input) as img:
        rgb = img.convert('RGB')
        quality = max(1, min(95, args.quality))
        used_quality = quality
        while True:
            used_quality = quality
            rgb.save(out, format='JPEG', quality=quality, optimize=True)
            if out.stat().st_size <= max_bytes or quality <= 35:
                break
            quality = max(35, quality - 8)
    info = probe_image_stdlib(out)
    info['qualityUsed'] = used_quality
    info['metCeiling'] = info['sizeBytes'] <= max_bytes
    return info


def cmd_overlay(args) -> dict:
    Image, _ = require_pillow()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(args.input).convert('RGBA') as base, Image.open(args.overlay).convert('RGBA') as mark:
        if args.overlay_width:
            scale = args.overlay_width / mark.width
            mark = mark.resize((args.overlay_width, int(round(mark.height * scale))), Image.LANCZOS)
        if args.opacity < 1.0:
            alpha = mark.getchannel('A').point(lambda px: int(px * args.opacity))
            mark.putalpha(alpha)
        pad = args.margin
        positions = {
            'top-left': (pad, pad),
            'top-right': (base.width - mark.width - pad, pad),
            'bottom-left': (pad, base.height - mark.height - pad),
            'bottom-right': (base.width - mark.width - pad, base.height - mark.height - pad),
            'center': ((base.width - mark.width) // 2, (base.height - mark.height) // 2),
        }
        xy = positions[args.position]
        base.alpha_composite(mark, dest=xy)
        if out.suffix.lower() in ('.jpg', '.jpeg'):
            base.convert('RGB').save(out, quality=92)
        else:
            base.save(out)
    return probe_image_stdlib(out)


def cmd_rounded(args) -> dict:
    Image, ImageDraw = require_pillow()
    from PIL import ImageChops
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(args.input).convert('RGBA') as img:
        mask = Image.new('L', img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([(0, 0), (img.width - 1, img.height - 1)], radius=args.radius, fill=255)
        combined_alpha = ImageChops.darker(img.getchannel('A'), mask)
        img.putalpha(combined_alpha)
        img.save(out, format='PNG')
    return probe_image_stdlib(out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Deterministic image probe and pixel operations.')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_probe = sub.add_parser('probe', help='Inspect image dimensions, aspect ratio, format, and byte size.')
    p_probe.add_argument('input', help='Path to image file.')

    p_crop = sub.add_parser('ratio-crop', help='Crop an image to an exact aspect ratio.')
    p_crop.add_argument('input')
    p_crop.add_argument('output')
    p_crop.add_argument('--ratio', required=True, help='Aspect ratio like 3:4, 9:16, 16:9, or 0.8.')
    p_crop.add_argument('--gravity', choices=['center', 'top', 'bottom'], default='center')
    p_crop.add_argument('--max-width', type=int, default=None)

    p_resize = sub.add_parser('resize', help='Resize an image proportionally or to exact dimensions.')
    p_resize.add_argument('input')
    p_resize.add_argument('output')
    p_resize.add_argument('--width', type=int, default=None)
    p_resize.add_argument('--height', type=int, default=None)

    p_comp = sub.add_parser('compress', help='Compress an image as JPEG under a target KB ceiling.')
    p_comp.add_argument('input')
    p_comp.add_argument('output')
    p_comp.add_argument('--max-kb', type=int, required=True)
    p_comp.add_argument('--quality', type=int, default=90)

    p_over = sub.add_parser('overlay', help='Composite a logo, watermark, badge, or QR image onto a base image.')
    p_over.add_argument('input')
    p_over.add_argument('overlay')
    p_over.add_argument('output')
    p_over.add_argument('--position', choices=['top-left', 'top-right', 'bottom-left', 'bottom-right', 'center'], default='bottom-right')
    p_over.add_argument('--margin', type=int, default=24)
    p_over.add_argument('--overlay-width', type=int, default=None)
    p_over.add_argument('--opacity', type=float, default=1.0)

    p_round = sub.add_parser('rounded', help='Apply rounded corners and export as PNG with alpha.')
    p_round.add_argument('input')
    p_round.add_argument('output')
    p_round.add_argument('--radius', type=int, default=32, help='Corner radius in pixels.')

    args = parser.parse_args(argv)
    try:
        if args.cmd == 'probe':
            res = probe_image_stdlib(Path(args.input))
        elif args.cmd == 'ratio-crop':
            res = cmd_ratio_crop(args)
        elif args.cmd == 'resize':
            res = cmd_resize(args)
        elif args.cmd == 'compress':
            res = cmd_compress(args)
        elif args.cmd == 'rounded':
            res = cmd_rounded(args)
        else:
            res = cmd_overlay(args)
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
