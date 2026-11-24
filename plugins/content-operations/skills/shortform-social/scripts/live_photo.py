#!/usr/bin/env python3
"""Zero-dependency Live Photo motion-card CLI (budget diagnosis, contact sheet, compose, native .pvt pack & validate)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple
import uuid

SCRIPT_DIR = Path(__file__).resolve().parent
SWIFT_PACKAGER = SCRIPT_DIR / 'live_photo_packager.swift'

PLATFORM_BUDGETS: Dict[str, Dict[str, Any]] = {
    'xiaohongshu': {
        'label': 'Xiaohongshu Live Photo', 'targetSec': 5.0, 'maxSec': 5.2, 'minSec': 1.5,
        'width': 1080, 'height': 1440, 'fps': 30,
        'publishNote': 'Transfer the .pvt bundle as a single item (e.g. AirDrop) to iPhone and publish via the Xiaohongshu mobile app.',
    },
    'wechat': {
        'label': 'WeChat Official Account Live Photo', 'targetSec': 3.0, 'maxSec': 3.2, 'minSec': 1.0,
        'width': 1080, 'height': 1440, 'fps': 30,
        'publishNote': 'Transfer the .pvt bundle as a single item to iPhone and upload inside the WeChat mobile editor (desktop web cannot ingest .pvt).',
    },
}

LAYOUT_CLIP_COUNTS = {'single': 1, 'grid-2': 2, 'grid-3': 3, 'stack-3': 3, 'triple-row': 3, 'grid-4': 4}


def diagnose_budget(duration_sec: float, target_platform: str, clip_count: int = 1) -> Dict[str, Any]:
    """Deterministically classify video duration against platform Live Photo budgets."""
    if target_platform not in PLATFORM_BUDGETS:
        raise ValueError(f'Unknown platform {target_platform!r}; expected one of: {", ".join(PLATFORM_BUDGETS)}')
    if duration_sec <= 0:
        raise ValueError(f'duration_sec must be > 0, got {duration_sec}')
    if clip_count < 1 or clip_count > 4:
        raise ValueError(f'clip_count must be 1..4, got {clip_count}')

    spec = PLATFORM_BUDGETS[target_platform]
    target = float(spec['targetSec'])
    min_ok = round(target * 0.85, 2)
    long_threshold = round(target * 1.6, 2)

    if duration_sec > long_threshold:
        status = 'long_video_needs_diagnosis'
        action = (
            'Generate a sparse contact sheet first (`contact-sheet`), inspect timestamps, '
            'and confirm with the user whether to trim a window, speed up, or split into a triple collage.'
        )
    elif duration_sec < min_ok:
        status = 'too_short_needs_confirm'
        action = (
            f'Clip ({duration_sec:.2f}s) is shorter than the {target:.0f}s target; '
            'ask whether to supply a longer clip, accept a shorter Live Photo, or explicitly allow slowdown.'
        )
    else:
        status = 'ready'
        action = f'Duration ({duration_sec:.2f}s) fits {target:.0f}s budget cleanly; extract first frame for static card review before rendering.'

    return {
        'platform': target_platform,
        'durationSec': round(duration_sec, 3),
        'clipCount': clip_count,
        'targetSec': target,
        'maxSec': spec['maxSec'],
        'status': status,
        'recommendedAction': action,
        'publishNote': spec['publishNote'],
    }


def build_layout_filter(
    layout: str,
    width: int = 1080,
    height: int = 1440,
    gap: int = 8,
    has_overlay: bool = False,
    crop_x: Optional[List[float]] = None,
    bg_color: str = '0x111214',
) -> Tuple[str, str]:
    """Build deterministic ffmpeg filter_complex graph for single, grid-2, grid-3, stack-3, triple-row, or grid-4."""
    if layout not in LAYOUT_CLIP_COUNTS:
        raise ValueError(f'Unknown layout {layout!r}; expected one of: {", ".join(LAYOUT_CLIP_COUNTS)}')
    if width <= 0 or height <= 0 or width % 2 != 0 or height % 2 != 0:
        raise ValueError('width and height must be positive even integers')

    def _fit(idx: int, cw: int, ch: int, out_lbl: str) -> str:
        cx = 0.5
        if crop_x and idx < len(crop_x):
            cx = max(0.0, min(1.0, float(crop_x[idx])))
        return (
            f'[{idx}:v]scale={cw}:{ch}:force_original_aspect_ratio=increase,'
            f'crop={cw}:{ch}:(iw-ow)*{cx:.3f}:(ih-oh)/2,setsar=1,format=yuv420p[{out_lbl}]'
        )

    parts: List[str] = []
    if layout == 'single':
        parts.append(_fit(0, width, height, 'base'))
    elif layout == 'grid-2':
        ch = (height - gap) // 2
        ch -= ch % 2
        parts.append(f'color=c={bg_color}:s={width}x{height}[bg]')
        parts.append(_fit(0, width, ch, 'v0'))
        parts.append(_fit(1, width, height - ch - gap, 'v1'))
        parts.append('[bg][v0]overlay=0:0:shortest=1[m0]')
        parts.append(f'[m0][v1]overlay=0:{ch + gap}:shortest=1[base]')
    elif layout == 'stack-3':
        ch = (height - gap * 2) // 3
        ch -= ch % 2
        last_h = height - ch * 2 - gap * 2
        parts.append(f'color=c={bg_color}:s={width}x{height}[bg]')
        parts.append(_fit(0, width, ch, 'v0'))
        parts.append(_fit(1, width, ch, 'v1'))
        parts.append(_fit(2, width, last_h, 'v2'))
        parts.append('[bg][v0]overlay=0:0:shortest=1[m0]')
        parts.append(f'[m0][v1]overlay=0:{ch + gap}:shortest=1[m1]')
        parts.append(f'[m1][v2]overlay=0:{(ch + gap) * 2}:shortest=1[base]')
    elif layout == 'grid-3':
        top_h = int(height * 0.52)
        top_h -= top_h % 2
        bot_h = height - top_h - gap
        half_w = (width - gap) // 2
        half_w -= half_w % 2
        parts.append(f'color=c={bg_color}:s={width}x{height}[bg]')
        parts.append(_fit(0, width, top_h, 'v0'))
        parts.append(_fit(1, half_w, bot_h, 'v1'))
        parts.append(_fit(2, width - half_w - gap, bot_h, 'v2'))
        parts.append('[bg][v0]overlay=0:0:shortest=1[m0]')
        parts.append(f'[m0][v1]overlay=0:{top_h + gap}:shortest=1[m1]')
        parts.append(f'[m1][v2]overlay={half_w + gap}:{top_h + gap}:shortest=1[base]')
    elif layout == 'triple-row':
        cw = (width - gap * 2) // 3
        cw -= cw % 2
        last_w = width - cw * 2 - gap * 2
        parts.append(f'color=c={bg_color}:s={width}x{height}[bg]')
        parts.append(_fit(0, cw, height, 'v0'))
        parts.append(_fit(1, cw, height, 'v1'))
        parts.append(_fit(2, last_w, height, 'v2'))
        parts.append('[bg][v0]overlay=0:0:shortest=1[m0]')
        parts.append(f'[m0][v1]overlay={cw + gap}:0:shortest=1[m1]')
        parts.append(f'[m1][v2]overlay={(cw + gap) * 2}:0:shortest=1[base]')
    else:  # grid-4
        hw = (width - gap) // 2
        hw -= hw % 2
        hh = (height - gap) // 2
        hh -= hh % 2
        rw = width - hw - gap
        bh = height - hh - gap
        parts.append(f'color=c={bg_color}:s={width}x{height}[bg]')
        parts.append(_fit(0, hw, hh, 'v0'))
        parts.append(_fit(1, rw, hh, 'v1'))
        parts.append(_fit(2, hw, bh, 'v2'))
        parts.append(_fit(3, rw, bh, 'v3'))
        parts.append('[bg][v0]overlay=0:0:shortest=1[m0]')
        parts.append(f'[m0][v1]overlay={hw + gap}:0:shortest=1[m1]')
        parts.append(f'[m1][v2]overlay=0:{hh + gap}:shortest=1[m2]')
        parts.append(f'[m2][v3]overlay={hw + gap}:{hh + gap}:shortest=1[base]')

    if has_overlay:
        ov_idx = LAYOUT_CLIP_COUNTS[layout]
        parts.append(f'[{ov_idx}:v]scale={width}:{height},format=rgba[ov]')
        parts.append('[base][ov]overlay=0:0:format=auto,format=yuv420p[outv]')
        return (';'.join(parts), '[outv]')
    return (';'.join(parts), '[base]')


def _require_tool(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f'Required system tool `{name}` not found on PATH.')
    return found


def probe_video(video_path: Path, target_platform: str) -> Dict[str, Any]:
    ffprobe = _require_tool('ffprobe')
    vp = video_path.resolve()
    if not vp.is_file():
        raise FileNotFoundError(f'Video not found: {vp}')
    cmd = [ffprobe, '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', str(vp)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    meta = json.loads(proc.stdout)
    streams = meta.get('streams', [])
    v_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
    if not v_stream:
        raise ValueError(f'No video stream found in {vp}')
    a_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    duration = float(meta.get('format', {}).get('duration') or v_stream.get('duration') or 0.0)
    fps_raw = str(v_stream.get('avg_frame_rate') or '30/1')
    num, den = (fps_raw.split('/') + ['1'])[:2]
    fps = round(float(num) / float(den), 2) if float(den) > 0 else 0.0
    diag = diagnose_budget(duration, target_platform)
    return {
        'file': str(vp),
        'width': int(v_stream.get('width', 0)),
        'height': int(v_stream.get('height', 0)),
        'codec': v_stream.get('codec_name', ''),
        'fps': fps,
        'hasAudio': a_stream is not None,
        'durationSec': round(duration, 3),
        'budget': diag,
    }


def make_contact_sheet(video_path: Path, out_png: Path, cols: int = 3, rows: int = 3) -> Dict[str, Any]:
    ffmpeg = _require_tool('ffmpeg')
    info = probe_video(video_path, 'xiaohongshu')
    total = max(1, cols * rows)
    dur = max(0.2, float(info['durationSec']))
    fps_sample = total / dur
    out_png = out_png.resolve()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    vf = f'fps={fps_sample:.6f},scale=360:-2,tile={cols}x{rows}:padding=6:margin=6:color=0x18181B'
    subprocess.run(
        [ffmpeg, '-y', '-i', str(video_path.resolve()), '-frames:v', '1', '-vf', vf, str(out_png)],
        capture_output=True,
        text=True,
        check=True,
    )
    return {'output': str(out_png), 'cols': cols, 'rows': rows, 'durationSec': info['durationSec']}


def extract_frame(video_path: Path, out_jpg: Path, at_sec: float = 0.0) -> Dict[str, Any]:
    ffmpeg = _require_tool('ffmpeg')
    out_jpg = out_jpg.resolve()
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [ffmpeg, '-y', '-ss', f'{max(0.0, at_sec):.3f}', '-i', str(video_path.resolve()), '-frames:v', '1', '-q:v', '2', str(out_jpg)],
        capture_output=True,
        text=True,
        check=True,
    )
    return {'output': str(out_jpg), 'atSec': max(0.0, at_sec)}


def compose_motion_card(
    videos: List[Path],
    out_mov: Path,
    target_platform: str,
    layout: str,
    start_sec: float = 0.0,
    duration_sec: Optional[float] = None,
    overlay_png: Optional[Path] = None,
    key_jpg: Optional[Path] = None,
    fallback_mp4: Optional[Path] = None,
    fallback_gif: Optional[Path] = None,
    crop_x: Optional[List[float]] = None,
    gap: int = 8,
    bg_color: str = '0x111214',
    mute: bool = False,
) -> Dict[str, Any]:
    ffmpeg = _require_tool('ffmpeg')
    if target_platform not in PLATFORM_BUDGETS:
        raise ValueError(f'Unknown platform: {target_platform}')
    need_n = LAYOUT_CLIP_COUNTS.get(layout)
    if need_n is None:
        raise ValueError(f'Unknown layout: {layout}')
    if len(videos) != need_n:
        raise ValueError(f'Layout {layout!r} requires exactly {need_n} video input(s), got {len(videos)}')

    spec = PLATFORM_BUDGETS[target_platform]
    dur = float(duration_sec) if duration_sec is not None else float(spec['targetSec'])
    if dur <= 0 or dur > float(spec['maxSec']):
        raise ValueError(f'Requested duration {dur}s exceeds {target_platform} hard ceiling ({spec["maxSec"]}s)')

    w, h, fps = int(spec['width']), int(spec['height']), int(spec['fps'])
    filter_graph, map_label = build_layout_filter(
        layout, w, h, gap=gap, has_overlay=overlay_png is not None, crop_x=crop_x, bg_color=bg_color,
    )

    out_mov = out_mov.resolve()
    out_mov.parent.mkdir(parents=True, exist_ok=True)

    cmd: List[str] = [ffmpeg, '-y']
    for vp in videos:
        resolved = vp.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f'Input video not found: {resolved}')
        cmd.extend(['-ss', f'{max(0.0, start_sec):.3f}', '-t', f'{dur:.3f}', '-i', str(resolved)])
    if overlay_png is not None:
        ov = overlay_png.resolve()
        if not ov.is_file():
            raise FileNotFoundError(f'Overlay PNG not found: {ov}')
        cmd.extend(['-loop', '1', '-t', f'{dur:.3f}', '-i', str(ov)])

    audio_args = ['-an'] if mute else ['-map', '0:a?', '-c:a', 'aac', '-b:a', '128k']
    cmd.extend([
        '-filter_complex', filter_graph,
        '-map', map_label,
        *audio_args,
        '-t', f'{dur:.3f}',
        '-r', str(fps),
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-profile:v', 'high',
        '-movflags', '+faststart',
        str(out_mov),
    ])
    subprocess.run(cmd, capture_output=True, text=True, check=True)

    artifacts: Dict[str, Any] = {
        'platform': target_platform,
        'layout': layout,
        'mov': str(out_mov),
        'width': w,
        'height': h,
        'durationSec': dur,
        'publishNote': spec['publishNote'],
    }
    if key_jpg is not None:
        extract_frame(out_mov, key_jpg, at_sec=0.0)
        artifacts['keyJpg'] = str(key_jpg.resolve())
    if fallback_mp4 is not None:
        mp4 = fallback_mp4.resolve()
        mp4.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [ffmpeg, '-y', '-i', str(out_mov), '-c:v', 'copy', '-movflags', '+faststart', str(mp4)],
            capture_output=True,
            text=True,
            check=True,
        )
        artifacts['fallbackMp4'] = str(mp4)
    if fallback_gif is not None:
        gif = fallback_gif.resolve()
        gif.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                ffmpeg, '-y', '-i', str(out_mov),
                '-vf', 'fps=12,scale=540:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse',
                str(gif),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        artifacts['fallbackGif'] = str(gif)
    return artifacts


def package_pvt(jpg_path: Path, mov_path: Path, out_pvt: Path, asset_id: Optional[str] = None) -> Dict[str, Any]:
    if platform.system() != 'Darwin':
        raise RuntimeError(
            'Native .pvt packaging requires macOS ImageIO/AVFoundation (swift). '
            'On non-macOS hosts, export --fallback-mp4 or --fallback-gif via `compose`.'
        )
    swift = _require_tool('swift')
    uid = (asset_id or str(uuid.uuid4())).upper()
    proc = subprocess.run(
        [swift, str(SWIFT_PACKAGER), str(jpg_path.resolve()), str(mov_path.resolve()), str(out_pvt.resolve()), uid],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f'Swift Live Photo packager failed: {proc.stderr.strip() or proc.stdout.strip()}')
    return json.loads(proc.stdout.strip())


def validate_motion_artifact(target: Path, target_platform: str) -> Dict[str, Any]:
    """Deterministically verify a .pvt bundle or standalone MOV against platform hard constraints."""
    if target_platform not in PLATFORM_BUDGETS:
        raise ValueError(f'Unknown platform: {target_platform}')
    spec = PLATFORM_BUDGETS[target_platform]
    target = target.resolve()
    errors: List[Dict[str, str]] = []

    def fail_rule(rule: str, msg: str) -> None:
        errors.append({'rule': rule, 'message': msg})

    mov_to_check: Optional[Path] = None
    jpg_to_check: Optional[Path] = None
    asset_id: Optional[str] = None

    if target.is_dir() and target.suffix.lower() == '.pvt':
        jpg_to_check = target / 'IMG.JPG'
        mov_to_check = target / 'IMG.MOV'
        plist_path = target / 'metadata.plist'
        for name, p in (('IMG.JPG', jpg_to_check), ('IMG.MOV', mov_to_check), ('metadata.plist', plist_path)):
            if not p.is_file() or p.stat().st_size == 0:
                fail_rule('pvt_structure', f'Missing or empty {name} inside {target.name}')
        if plist_path.is_file() and plist_path.stat().st_size > 0:
            try:
                plist_data = plistlib.loads(plist_path.read_bytes())
                asset_id = str(plist_data.get('PFVideoComplementMetadataPairingIdentifierKey') or '').strip()
                if not asset_id:
                    fail_rule('pvt_pairing_id', 'metadata.plist is missing PFVideoComplementMetadataPairingIdentifierKey')
            except Exception as err:
                fail_rule('pvt_structure', f'Unreadable metadata.plist: {err}')
    elif target.is_file() and target.suffix.lower() in ('.mov', '.mp4'):
        mov_to_check = target
    else:
        fail_rule('artifact_type', f'Target must be a .pvt bundle directory or .mov/.mp4 file: {target}')

    probed: Dict[str, Any] = {}
    if mov_to_check and mov_to_check.is_file() and mov_to_check.stat().st_size > 0:
        try:
            probed = probe_video(mov_to_check, target_platform)
            if probed['width'] != spec['width'] or probed['height'] != spec['height']:
                fail_rule('dimensions', f'MOV dimensions {probed["width"]}x{probed["height"]} must equal {spec["width"]}x{spec["height"]}')
            if probed['durationSec'] > spec['maxSec']:
                fail_rule('duration_ceiling', f'MOV duration {probed["durationSec"]}s exceeds {target_platform} max {spec["maxSec"]}s')
            if probed['durationSec'] < spec['minSec']:
                fail_rule('duration_floor', f'MOV duration {probed["durationSec"]}s is below minimum {spec["minSec"]}s')
        except Exception as err:
            fail_rule('mov_probe', f'Unable to probe MOV: {err}')

    if jpg_to_check and jpg_to_check.is_file() and jpg_to_check.stat().st_size > 0:
        raw = jpg_to_check.read_bytes()
        if not raw.startswith(b'\xff\xd8'):
            fail_rule('jpg_signature', 'IMG.JPG is not a valid JPEG file')
        if asset_id and asset_id.encode('ascii', errors='ignore') not in raw:
            fail_rule('pvt_pairing_id', f'Pairing UUID {asset_id} not embedded in IMG.JPG MakerNote')

    return {'passed': len(errors) == 0, 'target': str(target), 'platform': target_platform, 'assetId': asset_id, 'probed': probed, 'errorCount': len(errors), 'errors': errors}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description='Live Photo motion-card toolchain (zero third-party Python packages).')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_probe = sub.add_parser('probe', help='Probe video metadata and diagnose platform duration budget.')
    p_probe.add_argument('video', type=Path)
    p_probe.add_argument('--platform', default='xiaohongshu', choices=list(PLATFORM_BUDGETS.keys()))
    p_probe.add_argument('--json', action='store_true', dest='as_json')

    p_cs = sub.add_parser('contact-sheet', help='Render a sparse tiled contact sheet for low-cost long-video review.')
    p_cs.add_argument('video', type=Path)
    p_cs.add_argument('-o', '--output', required=True, type=Path)
    p_cs.add_argument('--cols', type=int, default=3)
    p_cs.add_argument('--rows', type=int, default=3)
    p_cs.add_argument('--json', action='store_true', dest='as_json')

    p_fr = sub.add_parser('extract-frame', help='Extract a single representative JPEG frame for static-card review.')
    p_fr.add_argument('video', type=Path)
    p_fr.add_argument('-o', '--output', required=True, type=Path)
    p_fr.add_argument('--at', type=float, default=0.0)
    p_fr.add_argument('--json', action='store_true', dest='as_json')

    p_comp = sub.add_parser('compose', help='Compose 1080x1440 single or multi-grid Live Photo MOV plus optional fallbacks.')
    p_comp.add_argument('videos', nargs='+', type=Path)
    p_comp.add_argument('-o', '--output', required=True, type=Path)
    p_comp.add_argument('--platform', default='xiaohongshu', choices=list(PLATFORM_BUDGETS.keys()))
    p_comp.add_argument('--layout', default='single', choices=list(LAYOUT_CLIP_COUNTS.keys()))
    p_comp.add_argument('--start', type=float, default=0.0)
    p_comp.add_argument('--duration', type=float, default=None)
    p_comp.add_argument('--overlay', type=Path, default=None)
    p_comp.add_argument('--key-jpg', type=Path, default=None)
    p_comp.add_argument('--fallback-mp4', type=Path, default=None)
    p_comp.add_argument('--fallback-gif', type=Path, default=None)
    p_comp.add_argument('--crop-x', default=None, help='Comma-separated horizontal crop focus 0.0..1.0 per clip')
    p_comp.add_argument('--gap', type=int, default=8)
    p_comp.add_argument('--bg-color', default='0x111214', help='Gutter/background color in ffmpeg 0xRRGGBB format')
    p_comp.add_argument('--mute', action='store_true', help='Strip source audio instead of preserving primary clip audio')
    p_comp.add_argument('--json', action='store_true', dest='as_json')

    p_pvt = sub.add_parser('package-pvt', help='Package JPG + MOV into an Apple .pvt Live Photo bundle (macOS native).')
    p_pvt.add_argument('jpg', type=Path)
    p_pvt.add_argument('mov', type=Path)
    p_pvt.add_argument('-o', '--output', required=True, type=Path)
    p_pvt.add_argument('--asset-id', default=None)
    p_pvt.add_argument('--json', action='store_true', dest='as_json')

    p_val = sub.add_parser('validate', help='Validate a .pvt bundle or MOV against platform duration & dimension ceilings.')
    p_val.add_argument('target', type=Path)
    p_val.add_argument('--platform', default='xiaohongshu', choices=list(PLATFORM_BUDGETS.keys()))
    p_val.add_argument('--json', action='store_true', dest='as_json')

    args = parser.parse_args(argv)
    try:
        dispatch = {
            'probe': lambda: probe_video(args.video, args.platform),
            'contact-sheet': lambda: make_contact_sheet(args.video, args.output, args.cols, args.rows),
            'extract-frame': lambda: extract_frame(args.video, args.output, args.at),
            'compose': lambda: compose_motion_card(
                args.videos, args.output, args.platform, args.layout, args.start, args.duration, args.overlay,
                args.key_jpg, args.fallback_mp4, args.fallback_gif,
                crop_x=[float(x) for x in args.crop_x.split(',')] if args.crop_x else None,
                gap=args.gap, bg_color=args.bg_color, mute=args.mute,
            ),
            'package-pvt': lambda: package_pvt(args.jpg, args.mov, args.output, asset_id=args.asset_id),
            'validate': lambda: validate_motion_artifact(args.target, args.platform),
        }
        res = dispatch[args.cmd]()
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return (0 if res['passed'] else 1) if args.cmd == 'validate' else 0
    except Exception as exc:
        print(json.dumps({'passed': False, 'error': str(exc)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
