#!/usr/bin/env python3
"""Zero-dependency video inspection, SRT subtitle validation, and script duration estimator."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

SRT_TIME_RE = re.compile(r'^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})$')
CJK_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')
LATIN_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)?")


def _to_ms(h: str, m: str, s: str, ms: str) -> int:
    return ((int(h) * 3600) + (int(m) * 60) + int(s)) * 1000 + int(ms)


def _parse_fps(rate_str: str | None) -> float | None:
    if not rate_str or rate_str == '0/0':
        return None
    if '/' in rate_str:
        num, den = rate_str.split('/', 1)
        try:
            d = float(den)
            return round(float(num) / d, 3) if d else None
        except ValueError:
            return None
    try:
        return round(float(rate_str), 3)
    except ValueError:
        return None


def probe_video(path: Path, measure_loudness: bool = False) -> dict:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f'Video file not found: {path}')
    if not shutil.which('ffprobe'):
        raise RuntimeError('ffprobe is not installed on PATH')
    proc = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', str(path)],
        capture_output=True, text=True, check=False, timeout=20,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(f'ffprobe failed for {path.name}: {proc.stderr.strip()}')
    data = json.loads(proc.stdout)
    fmt = data.get('format') or {}
    streams = data.get('streams') or []
    vstream = next((s for s in streams if s.get('codec_type') == 'video'), None)
    astream = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    if not vstream:
        raise RuntimeError(f'No video stream detected in {path.name}')

    w = int(vstream.get('width') or 0)
    h = int(vstream.get('height') or 0)
    dur_raw = fmt.get('duration') or vstream.get('duration')
    dur = round(float(dur_raw), 2) if dur_raw is not None else None
    out: dict = {
        'ok': True,
        'file': str(path),
        'sizeBytes': path.stat().st_size,
        'durationSec': dur,
        'width': w,
        'height': h,
        'aspectRatio': round(w / h, 4) if (w and h) else None,
        'fps': _parse_fps(vstream.get('avg_frame_rate') or vstream.get('r_frame_rate')),
        'videoCodec': vstream.get('codec_name'),
        'pixFmt': vstream.get('pix_fmt'),
        'colorSpace': vstream.get('color_space'),
        'hasAudio': astream is not None,
        'audioCodec': astream.get('codec_name') if astream else None,
        'audioSampleRate': int(astream['sample_rate']) if (astream and astream.get('sample_rate')) else None,
    }
    if measure_loudness and astream and shutil.which('ffmpeg'):
        lproc = subprocess.run(
            ['ffmpeg', '-hide_banner', '-nostats', '-i', str(path), '-filter_complex', 'ebur128=peak=true', '-f', 'null', '-'],
            capture_output=True, text=True, check=False, timeout=60,
        )
        m_i = re.search(r'Integrated loudness:.*?I:\s*(-?\d+(?:\.\d+)?)\s*LUFS', lproc.stderr, re.S)
        m_tp = re.search(r'True peak:.*?Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS', lproc.stderr, re.S)
        out['loudness'] = {
            'integratedLufs': float(m_i.group(1)) if m_i else None,
            'truePeakDbfs': float(m_tp.group(1)) if m_tp else None,
            'referenceTargetLufs': -14.0,
        }
    return out


def validate_srt(path: Path, max_cjk_chars: int = 18, max_en_chars: int = 42) -> dict:
    """Validate SRT cue syntax, monotonic non-overlapping timestamps, and optional line length advisory."""
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f'SRT file not found: {path}')
    raw = path.read_text(encoding='utf-8-sig').replace('\r\n', '\n').replace('\r', '\n').strip()
    if not raw:
        return {'ok': False, 'cueCount': 0, 'errors': [{'cue': 0, 'message': 'Empty SRT file'}], 'warnings': []}

    blocks = re.split(r'\n{2,}', raw)
    errors: list[dict] = []
    warnings: list[dict] = []
    prev_end_ms = -1
    total_dur_ms = 0

    for idx, blk in enumerate(blocks, start=1):
        lines = [ln.rstrip() for ln in blk.split('\n')]
        if len(lines) < 3:
            errors.append({'cue': idx, 'message': 'Malformed SRT block (expected index, timecode, and >=1 text line)'})
            continue
        if not lines[0].strip().isdigit():
            errors.append({'cue': idx, 'message': f'Non-numeric cue index "{lines[0].strip()}"'})
        elif int(lines[0].strip()) != idx:
            warnings.append({'cue': idx, 'message': f'Cue index {lines[0].strip()} is out of sequence (expected {idx})'})
        m = SRT_TIME_RE.match(lines[1].strip())
        if not m:
            errors.append({'cue': idx, 'message': f'Invalid SRT timestamp line: "{lines[1].strip()}"'})
            continue
        start_ms = _to_ms(*m.groups()[:4])
        end_ms = _to_ms(*m.groups()[4:])
        if end_ms <= start_ms:
            errors.append({'cue': idx, 'message': f'End timestamp <= start timestamp ({lines[1].strip()})'})
        if prev_end_ms >= 0 and start_ms < prev_end_ms:
            errors.append({'cue': idx, 'message': f'Cue overlaps previous cue (starts at {start_ms}ms < prev end {prev_end_ms}ms)'})
        prev_end_ms = max(prev_end_ms, end_ms)
        total_dur_ms = max(total_dur_ms, end_ms)

        text_lines = [ln.strip() for ln in lines[2:] if ln.strip()]
        if not text_lines:
            errors.append({'cue': idx, 'message': 'Cue has no caption text'})
        if len(text_lines) > 2:
            warnings.append({'cue': idx, 'message': f'Cue has {len(text_lines)} lines (<= 2 lines recommended for mobile readability)'})
        for tline in text_lines:
            is_cjk = bool(CJK_RE.search(tline))
            limit = max_cjk_chars if is_cjk else max_en_chars
            if len(tline) > limit:
                warnings.append({'cue': idx, 'message': f'Line length {len(tline)} exceeds recommended {limit} chars: "{tline[:24]}..."'})

    return {
        'ok': not errors,
        'file': str(path),
        'cueCount': len(blocks),
        'totalDurationSec': round(total_dur_ms / 1000.0, 2),
        'errors': errors,
        'warnings': warnings,
    }


def estimate_duration(text: str, cn_cpm: float = 260.0, en_wpm: float = 150.0) -> dict:
    """Estimate spoken script duration from CJK character count and Latin word count."""
    cleaned = re.sub(r'```.*?```', '', text, flags=re.S)
    cleaned = re.sub(r'^#{1,6}\s+.*$', '', cleaned, flags=re.M)
    cleaned = re.sub(r'\[[^\]]*\]\([^)]+\)', '', cleaned)
    cjk_chars = len(CJK_RE.findall(cleaned))
    en_words = len(LATIN_WORD_RE.findall(CJK_RE.sub(' ', cleaned)))
    est_sec = round((cjk_chars / max(cn_cpm, 1.0) + en_words / max(en_wpm, 1.0)) * 60.0, 1)
    return {
        'ok': True,
        'cjkChars': cjk_chars,
        'latinWords': en_words,
        'cnCharsPerMin': cn_cpm,
        'enWordsPerMin': en_wpm,
        'estimatedDurationSec': est_sec,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Video probe, SRT subtitle validation, and spoken script duration estimator.')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_probe = sub.add_parser('probe', help='Inspect video dimensions, codec, fps, duration, and optional EBU R128 loudness.')
    p_probe.add_argument('video', help='Path to local video file.')
    p_probe.add_argument('--loudness', action='store_true', help='Measure integrated LUFS and true peak via ffmpeg ebur128.')

    p_srt = sub.add_parser('validate-srt', help='Validate SRT subtitle syntax, non-overlapping timestamps, and mobile line lengths.')
    p_srt.add_argument('srt', help='Path to .srt file.')
    p_srt.add_argument('--max-cjk-chars', type=int, default=18)
    p_srt.add_argument('--max-en-chars', type=int, default=42)

    p_est = sub.add_parser('estimate-duration', help='Estimate spoken script duration in seconds.')
    p_est.add_argument('script', help='Path to spoken script Markdown/text file.')
    p_est.add_argument('--cn-cpm', type=float, default=260.0, help='Chinese speaking rate in chars/min (default 260).')
    p_est.add_argument('--en-wpm', type=float, default=150.0, help='English speaking rate in words/min (default 150).')

    args = ap.parse_args(argv)
    try:
        if args.cmd == 'probe':
            res = probe_video(Path(args.video), measure_loudness=args.loudness)
        elif args.cmd == 'validate-srt':
            res = validate_srt(Path(args.srt), max_cjk_chars=args.max_cjk_chars, max_en_chars=args.max_en_chars)
        else:
            p = Path(args.script).expanduser().resolve()
            if not p.is_file():
                raise FileNotFoundError(f'Script file not found: {p}')
            res = estimate_duration(p.read_text(encoding='utf-8'), cn_cpm=args.cn_cpm, en_wpm=args.en_wpm)
    except (OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, indent=2, ensure_ascii=False))
        return 2

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
