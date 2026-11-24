#!/usr/bin/env python3
"""Zero-dependency video inspection, SRT/VTT validation, duration estimator, and line-indexed clip slicer."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

SRT_TIME_RE = re.compile(r'^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})$')
VTT_TIME_RE = re.compile(
    r'^(?:(\d{2}):)?(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(?:(\d{2}):)?(\d{2}):(\d{2})\.(\d{3})(?:\s+.*)?$'
)
CJK_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')
LATIN_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)?")


def _to_ms(h: str | None, m: str, s: str, ms: str) -> int:
    return ((int(h or 0) * 3600) + (int(m) * 60) + int(s)) * 1000 + int(ms)


def _format_srt_ms(ms: int) -> str:
    ms = max(int(ms), 0)
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}'


def _slugify(text: str, fallback: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9]+', '-', text.strip().lower()).strip('-')
    return (cleaned[:40].rstrip('-') or fallback)


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


def parse_subtitle_cues(path: Path) -> tuple[str, list[dict]]:
    """Parse an SRT or WebVTT file into 0-indexed cues with exact millisecond boundaries."""
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f'Subtitle file not found: {path}')
    raw = path.read_text(encoding='utf-8-sig').replace('\r\n', '\n').replace('\r', '\n').strip()
    if not raw:
        raise ValueError(f'Subtitle file is empty: {path.name}')

    is_vtt = raw.startswith('WEBVTT') or path.suffix.lower() == '.vtt'
    blocks = re.split(r'\n{2,}', raw)
    cues: list[dict] = []
    prev_end_ms = -1

    for blk_idx, blk in enumerate(blocks, start=1):
        lines = [ln.rstrip() for ln in blk.split('\n') if ln.strip() != '']
        if not lines:
            continue
        if is_vtt and (lines[0].startswith('WEBVTT') or lines[0].startswith('NOTE') or lines[0].startswith('STYLE') or lines[0].startswith('REGION')):
            continue

        time_line_idx = None
        match = None
        for i, ln in enumerate(lines[:2]):
            m = VTT_TIME_RE.match(ln.strip()) if is_vtt else SRT_TIME_RE.match(ln.strip())
            if m:
                time_line_idx = i
                match = m
                break
        if match is None or time_line_idx is None:
            raise ValueError(f'Invalid subtitle block #{blk_idx} in {path.name}: missing valid timecode')

        start_ms = _to_ms(*match.groups()[:4])
        end_ms = _to_ms(*match.groups()[4:])
        if end_ms <= start_ms:
            raise ValueError(f'Subtitle block #{blk_idx} has end_ms ({end_ms}) <= start_ms ({start_ms})')
        if prev_end_ms >= 0 and start_ms < prev_end_ms:
            raise ValueError(f'Subtitle block #{blk_idx} overlaps previous cue ({start_ms}ms < {prev_end_ms}ms)')
        prev_end_ms = end_ms

        text_lines = [re.sub(r'<[^>]+>', '', ln).strip() for ln in lines[time_line_idx + 1:] if ln.strip()]
        if not text_lines:
            raise ValueError(f'Subtitle block #{blk_idx} has no caption text')

        cues.append({
            'index': len(cues),
            'startMs': start_ms,
            'endMs': end_ms,
            'startSec': round(start_ms / 1000.0, 2),
            'endSec': round(end_ms / 1000.0, 2),
            'lines': text_lines,
            'text': ' '.join(text_lines),
        })

    if not cues:
        raise ValueError(f'No valid subtitle cues found in {path.name}')
    return ('vtt' if is_vtt else 'srt'), cues


def index_transcript(subtitle_path: Path) -> dict:
    """Return 0-indexed transcript lines so a model selects exact [from, to] cue indices instead of guessing timestamps."""
    fmt, cues = parse_subtitle_cues(subtitle_path)
    total_sec = round(max(c['endMs'] for c in cues) / 1000.0, 2)
    formatted = [
        f'{c["index"]} [{c["startSec"]:.1f} - {c["endSec"]:.1f}] {c["text"]}'
        for c in cues
    ]
    return {
        'ok': True,
        'file': str(subtitle_path.expanduser().resolve()),
        'format': fmt,
        'cueCount': len(cues),
        'totalDurationSec': total_sec,
        'cues': cues,
        'formattedLines': formatted,
    }


def plan_clips(
    subtitle_path: Path,
    raw_clips: list[dict],
    *,
    min_sec: float = 20.0,
    max_sec: float = 90.0,
    max_clips: int = 8,
) -> dict:
    """Deterministically validate line-indexed clip ranges: exact cue bounds, duration bounds, and zero overlaps."""
    if min_sec <= 0 or max_sec <= 0 or min_sec > max_sec:
        raise ValueError(f'Invalid duration bounds: min_sec={min_sec}, max_sec={max_sec}')
    if max_clips <= 0:
        raise ValueError(f'max_clips must be positive (got {max_clips})')

    fmt, cues = parse_subtitle_cues(subtitle_path)
    errors: list[dict] = []
    if not isinstance(raw_clips, list) or not raw_clips:
        return {
            'ok': False,
            'format': fmt,
            'cueCount': len(cues),
            'validClips': [],
            'errors': [{'clipIndex': -1, 'message': 'Clip plan must contain a non-empty list of clips'}],
        }
    if len(raw_clips) > max_clips:
        errors.append({'clipIndex': -1, 'message': f'Requested {len(raw_clips)} clips exceeds max_clips ({max_clips})'})

    parsed: list[dict] = []
    for idx, item in enumerate(raw_clips):
        if not isinstance(item, dict):
            errors.append({'clipIndex': idx, 'message': 'Clip entry must be an object'})
            continue
        from_val = item.get('from')
        to_val = item.get('to')
        if isinstance(from_val, bool) or not isinstance(from_val, int):
            errors.append({'clipIndex': idx, 'message': f'Clip "from" must be an integer cue index (got {from_val!r})'})
            continue
        if isinstance(to_val, bool) or not isinstance(to_val, int):
            errors.append({'clipIndex': idx, 'message': f'Clip "to" must be an integer cue index (got {to_val!r})'})
            continue
        if from_val < 0 or to_val < 0 or from_val >= len(cues) or to_val >= len(cues):
            errors.append({'clipIndex': idx, 'message': f'Cue range [{from_val}, {to_val}] out of bounds (valid 0..{len(cues) - 1})'})
            continue
        if from_val > to_val:
            errors.append({'clipIndex': idx, 'message': f'Clip "from" ({from_val}) must be <= "to" ({to_val})'})
            continue

        start_ms = cues[from_val]['startMs']
        end_ms = cues[to_val]['endMs']
        dur_sec = round((end_ms - start_ms) / 1000.0, 2)
        if dur_sec < min_sec or dur_sec > max_sec:
            errors.append({
                'clipIndex': idx,
                'message': f'Clip duration {dur_sec}s outside allowed [{min_sec}s, {max_sec}s] for cues [{from_val}..{to_val}]',
            })
            continue

        title = str(item.get('title') or '').strip()
        if not title:
            errors.append({'clipIndex': idx, 'message': 'Clip requires a non-empty "title"'})
            continue

        parsed.append({
            'originalIndex': idx,
            'from': from_val,
            'to': to_val,
            'startMs': start_ms,
            'endMs': end_ms,
            'startSec': round(start_ms / 1000.0, 3),
            'endSec': round(end_ms / 1000.0, 3),
            'durationSec': dur_sec,
            'title': title,
            'caption': str(item.get('caption') or item.get('content') or '').strip(),
            'cueCount': (to_val - from_val) + 1,
        })

    # Overlap check across all parsed clips sorted chronologically
    ordered = sorted(parsed, key=lambda c: (c['from'], c['to'], c['startMs']))
    for i in range(1, len(ordered)):
        prev = ordered[i - 1]
        cur = ordered[i]
        if cur['from'] <= prev['to'] or cur['startMs'] < prev['endMs']:
            errors.append({
                'clipIndex': cur['originalIndex'],
                'message': (
                    f'Clip [{cur["from"]}..{cur["to"]}] ({cur["startSec"]}s-{cur["endSec"]}s) overlaps '
                    f'clip [{prev["from"]}..{prev["to"]}] ({prev["startSec"]}s-{prev["endSec"]}s)'
                ),
            })

    valid_clips: list[dict] = []
    if not errors:
        for seq, c in enumerate(parsed, start=1):
            slug = _slugify(c['title'], f'clip-{seq:02d}')
            valid_clips.append({
                'clipId': f'clip-{seq:02d}-{slug}',
                'sequence': seq,
                'from': c['from'],
                'to': c['to'],
                'startMs': c['startMs'],
                'endMs': c['endMs'],
                'startSec': c['startSec'],
                'endSec': c['endSec'],
                'durationSec': c['durationSec'],
                'title': c['title'],
                'caption': c['caption'],
                'cueCount': c['cueCount'],
            })

    return {
        'ok': not errors,
        'format': fmt,
        'cueCount': len(cues),
        'minSec': min_sec,
        'maxSec': max_sec,
        'validClips': valid_clips,
        'errors': errors,
    }


def render_rebased_srt(cues: list[dict], from_idx: int, to_idx: int) -> str:
    """Slice cues[from_idx..to_idx] and rebase all timestamps to start at 00:00:00,000."""
    origin_ms = cues[from_idx]['startMs']
    blocks: list[str] = []
    for seq, cue in enumerate(cues[from_idx: to_idx + 1], start=1):
        rel_start = max(cue['startMs'] - origin_ms, 0)
        rel_end = max(cue['endMs'] - origin_ms, rel_start + 1)
        body = '\n'.join(cue['lines'])
        blocks.append(f'{seq}\n{_format_srt_ms(rel_start)} --> {_format_srt_ms(rel_end)}\n{body}')
    return '\n\n'.join(blocks) + '\n'


def build_slice_ffmpeg_cmd(
    video_path: Path,
    out_video: Path,
    start_sec: float,
    duration_sec: float,
    *,
    aspect: str = '9:16',
    burn_srt: Path | None = None,
) -> list[str]:
    vf_filters: list[str] = []
    if aspect == '9:16':
        vf_filters.append("scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920")
    if burn_srt is not None:
        esc = (
            str(burn_srt)
            .replace('\\', '\\\\')
            .replace(':', '\\:')
            .replace("'", "\\'")
            .replace(',', '\\,')
            .replace('[', '\\[')
            .replace(']', '\\]')
        )
        vf_filters.append(f"subtitles=filename={esc}:force_style='Alignment=2,MarginV=120,FontSize=18'")

    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-ss', f'{start_sec:.3f}',
        '-i', str(video_path),
        '-t', f'{duration_sec:.3f}',
    ]
    if vf_filters:
        cmd.extend(['-vf', ','.join(vf_filters)])
    cmd.extend([
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
        '-c:a', 'aac', '-ar', '48000', '-b:a', '160k',
        '-movflags', '+faststart',
        str(out_video),
    ])
    return cmd


def ffmpeg_has_filter(filter_name: str) -> bool:
    """Return True if local ffmpeg binary supports the named libavfilter (e.g. 'subtitles')."""
    if not shutil.which('ffmpeg'):
        return False
    proc = subprocess.run(
        ['ffmpeg', '-hide_banner', '-filters'],
        capture_output=True, text=True, check=False, timeout=15,
    )
    if proc.returncode != 0:
        return False
    return bool(re.search(rf'\b{re.escape(filter_name)}\b', proc.stdout))


def slice_clips(
    video_path: Path,
    subtitle_path: Path,
    raw_clips: list[dict],
    out_dir: Path,
    *,
    min_sec: float = 20.0,
    max_sec: float = 90.0,
    max_clips: int = 8,
    aspect: str = '9:16',
    burn_subtitles: bool = False,
    dry_run: bool = False,
) -> dict:
    """Validate line-indexed clips, emit rebased SRT files, and slice MP4 outputs via local ffmpeg."""
    video_resolved = video_path.expanduser().resolve()
    if not dry_run and not video_resolved.is_file():
        raise FileNotFoundError(f'Video file not found: {video_resolved}')

    plan_res = plan_clips(
        subtitle_path,
        raw_clips,
        min_sec=min_sec,
        max_sec=max_sec,
        max_clips=max_clips,
    )
    if not plan_res['ok']:
        return {**plan_res, 'sliced': []}

    if not dry_run and not shutil.which('ffmpeg'):
        raise RuntimeError('ffmpeg is not installed on PATH (required for slice-clips without --dry-run)')
    if not dry_run and burn_subtitles and not ffmpeg_has_filter('subtitles'):
        raise RuntimeError(
            'Installed ffmpeg lacks the libass "subtitles" filter required for --burn-subtitles; '
            're-run without --burn-subtitles to emit clean MP4 + rebased sidecar .srt files, or install an ffmpeg build with libass.'
        )

    _, cues = parse_subtitle_cues(subtitle_path)
    out_root = out_dir.expanduser().resolve()
    if not dry_run:
        out_root.mkdir(parents=True, exist_ok=True)

    outputs: list[dict] = []
    for clip in plan_res['validClips']:
        cid = clip['clipId']
        out_mp4 = out_root / f'{cid}.mp4'
        out_srt = out_root / f'{cid}.srt'
        srt_text = render_rebased_srt(cues, clip['from'], clip['to'])
        cmd = build_slice_ffmpeg_cmd(
            video_resolved,
            out_mp4,
            clip['startSec'],
            clip['durationSec'],
            aspect=aspect,
            burn_srt=(out_srt if burn_subtitles else None),
        )
        if not dry_run:
            out_srt.write_text(srt_text, encoding='utf-8')
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=300)
            if proc.returncode != 0:
                raise RuntimeError(f'ffmpeg failed for {cid}: {proc.stderr.strip()}')
        outputs.append({
            **clip,
            'videoPath': str(out_mp4),
            'srtPath': str(out_srt),
            'aspect': aspect,
            'burnSubtitles': burn_subtitles,
            'ffmpegCommand': cmd,
            'rebasedSrtCueCount': clip['cueCount'],
        })

    manifest_path = out_root / 'clips-manifest.json'
    result = {
        'ok': True,
        'dryRun': dry_run,
        'sourceVideo': str(video_resolved),
        'sourceSubtitle': str(subtitle_path.expanduser().resolve()),
        'outDir': str(out_root),
        'clipCount': len(outputs),
        'sliced': outputs,
    }
    if not dry_run:
        manifest_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        result['manifestPath'] = str(manifest_path)
    return result


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


def _load_plan_file(plan_path: Path) -> list[dict]:
    p = plan_path.expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(f'Clip plan file not found: {p}')
    doc = json.loads(p.read_text(encoding='utf-8'))
    if isinstance(doc, dict) and isinstance(doc.get('clips'), list):
        return doc['clips']
    if isinstance(doc, list):
        return doc
    raise ValueError('Clip plan JSON must be a list or an object with a "clips" array')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Video probe, SRT/VTT validator, duration estimator, and line-indexed clip slicer.')
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

    p_idx = sub.add_parser('index-transcript', help='Emit 0-indexed SRT/VTT lines ("index [start - end] text") for exact clip selection.')
    p_idx.add_argument('subtitle', help='Path to .srt or .vtt subtitle file.')
    p_idx.add_argument('--text-only', action='store_true', help='Print numbered lines directly instead of JSON.')

    p_plan = sub.add_parser('plan-clips', help='Validate line-indexed clip ranges (bounds, duration, zero overlap).')
    p_plan.add_argument('subtitle', help='Path to .srt or .vtt subtitle file.')
    p_plan.add_argument('--plan', required=True, help='JSON file with [{"from": int, "to": int, "title": str, "caption"?: str}].')
    p_plan.add_argument('--min-sec', type=float, default=20.0, help='Minimum clip duration in seconds (default 20).')
    p_plan.add_argument('--max-sec', type=float, default=90.0, help='Maximum clip duration in seconds (default 90).')
    p_plan.add_argument('--max-clips', type=int, default=8, help='Maximum clips per source video (default 8).')

    p_slice = sub.add_parser('slice-clips', help='Validate clip plan, generate rebased SRTs, and slice vertical/source MP4s via local ffmpeg.')
    p_slice.add_argument('video', help='Path to source long-form video file.')
    p_slice.add_argument('subtitle', help='Path to .srt or .vtt subtitle file.')
    p_slice.add_argument('--plan', required=True, help='JSON file with line-indexed clip selections.')
    p_slice.add_argument('--out-dir', required=True, help='Directory to write sliced MP4, rebased SRT, and clips-manifest.json.')
    p_slice.add_argument('--min-sec', type=float, default=20.0)
    p_slice.add_argument('--max-sec', type=float, default=90.0)
    p_slice.add_argument('--max-clips', type=int, default=8)
    p_slice.add_argument('--aspect', choices=['9:16', 'source'], default='9:16', help='Output aspect ratio (default 9:16 vertical crop).')
    p_slice.add_argument('--burn-subtitles', action='store_true', help='Burn rebased subtitles into the rendered MP4.')
    p_slice.add_argument('--dry-run', action='store_true', help='Validate plan and preview ffmpeg commands without writing files.')

    args = ap.parse_args(argv)
    try:
        if args.cmd == 'probe':
            res = probe_video(Path(args.video), measure_loudness=args.loudness)
        elif args.cmd == 'validate-srt':
            res = validate_srt(Path(args.srt), max_cjk_chars=args.max_cjk_chars, max_en_chars=args.max_en_chars)
        elif args.cmd == 'estimate-duration':
            p = Path(args.script).expanduser().resolve()
            if not p.is_file():
                raise FileNotFoundError(f'Script file not found: {p}')
            res = estimate_duration(p.read_text(encoding='utf-8'), cn_cpm=args.cn_cpm, en_wpm=args.en_wpm)
        elif args.cmd == 'index-transcript':
            res = index_transcript(Path(args.subtitle))
            if args.text_only:
                print('\n'.join(res['formattedLines']))
                return 0
        elif args.cmd == 'plan-clips':
            res = plan_clips(
                Path(args.subtitle),
                _load_plan_file(Path(args.plan)),
                min_sec=args.min_sec,
                max_sec=args.max_sec,
                max_clips=args.max_clips,
            )
        else:
            res = slice_clips(
                Path(args.video),
                Path(args.subtitle),
                _load_plan_file(Path(args.plan)),
                Path(args.out_dir),
                min_sec=args.min_sec,
                max_sec=args.max_sec,
                max_clips=args.max_clips,
                aspect=args.aspect,
                burn_subtitles=args.burn_subtitles,
                dry_run=args.dry_run,
            )
    except (OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, indent=2, ensure_ascii=False))
        return 2

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
