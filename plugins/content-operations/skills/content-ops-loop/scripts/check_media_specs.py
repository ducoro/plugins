#!/usr/bin/env python3
"""Validate all platform variants inside a draft directory against per-platform specs.json."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

from image_ops import probe_image_stdlib

SKILLS_ROOT = Path(__file__).resolve().parents[2]
JSON_FENCE_RE = re.compile(r'```json\s*(\{.*?\})\s*```', re.S)
URL_RE = re.compile(r'https?://\S+')
PLACEHOLDER_RE = re.compile(
    r'\b(?:TODO|TBD|FIXME)\b|\[\s*(?:insert|todo|placeholder|待补充|待填)[^\]]*\]|\{\{[^}]+\}\}',
    re.I,
)


def load_platform_spec(platform: str) -> dict | None:
    spec_path = SKILLS_ROOT / f'platform-{platform}' / 'references' / 'specs.json'
    if not spec_path.is_file():
        return None
    return json.loads(spec_path.read_text(encoding='utf-8'))


def resolve_effective_spec(spec: dict, channel: str) -> tuple[dict, dict, list[str], dict]:
    """Merge optional apiOverrides onto base browser/platform rules when channel == 'api'."""
    limits = dict(spec.get('contentLimits') or {})
    media_rules = dict(spec.get('mediaRules') or {})
    req_options = list(spec.get('requiredOptions') or [])
    topic_rules = dict(spec.get('topic') or {})
    if channel == 'api':
        overrides = spec.get('apiOverrides') or {}
        limits.update(overrides.get('contentLimits') or {})
        media_rules.update(overrides.get('mediaRules') or {})
        topic_rules.update(overrides.get('topic') or {})
        if 'requiredOptions' in overrides:
            req_options = list(overrides['requiredOptions'])
    return limits, media_rules, req_options, topic_rules


def parse_variant(path: Path) -> tuple[dict, str, str]:
    raw_bytes = path.read_bytes()
    variant_hash = hashlib.sha256(raw_bytes).hexdigest()[:16]
    raw = raw_bytes.decode('utf-8')
    if path.suffix == '.json':
        data = json.loads(raw)
        return data, str(data.get('body', '')), variant_hash
    match = JSON_FENCE_RE.search(raw)
    if not match:
        raise ValueError(f'{path.name}: missing leading ```json metadata block')
    meta = json.loads(match.group(1))
    body = raw[match.end():].strip()
    if not body and isinstance(meta.get('body'), str):
        body = meta['body']
    return meta, body, variant_hash


def x_char_weight(ch: str) -> int:
    cp = ord(ch)
    if cp <= 0x10FF or (0x2000 <= cp <= 0x200D) or (0x2010 <= cp <= 0x201F) or (0x2032 <= cp <= 0x2037):
        return 1
    return 2


def weighted_length(text: str, tco_len: int | None, platform: str = '') -> int:
    replaced = URL_RE.sub('x' * tco_len, text) if tco_len else text
    if platform == 'x-twitter':
        return sum(x_char_weight(ch) for ch in replaced)
    return len(replaced)


def format_allowed(detected_fmt: str, suffix_ext: str, allowed: set[str]) -> bool:
    if not allowed:
        return True
    norm = lambda x: 'jpg' if x == 'jpeg' else x
    norm_allowed = {norm(f) for f in allowed}
    if detected_fmt in ('png', 'jpeg', 'jpg', 'gif', 'webp'):
        return norm(detected_fmt) in norm_allowed
    return norm(suffix_ext) in norm_allowed


def probe_video_ffprobe(path: Path) -> dict | None:
    """Use local ffprobe when available on real non-stub video files; return None otherwise."""
    if not shutil.which('ffprobe') or path.stat().st_size < 1024:
        return None
    proc = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', str(path)],
        capture_output=True, text=True, check=False, timeout=15,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    fmt = data.get('format') or {}
    vstream = next((s for s in (data.get('streams') or []) if s.get('codec_type') == 'video'), None)
    if not vstream:
        return None
    dur_raw = fmt.get('duration') or vstream.get('duration')
    try:
        duration = float(dur_raw) if dur_raw is not None else None
    except ValueError:
        duration = None
    return {
        'durationSec': round(duration, 2) if duration is not None else None,
        'width': vstream.get('width'),
        'height': vstream.get('height'),
        'codec': vstream.get('codec_name'),
    }


def validate_variant(
    draft_dir: Path,
    variant_path: Path,
    channel: str = 'browser',
    allow_placeholders: bool = False,
) -> dict:
    issues: list[dict] = []
    warnings: list[dict] = []
    try:
        meta, body, variant_hash = parse_variant(variant_path)
    except Exception as exc:
        return {
            'platform': variant_path.stem,
            'file': f'variants/{variant_path.name}',
            'specStatus': 'fail',
            'variantHash': None,
            'issues': [{'code': 'invalid_variant', 'message': str(exc)}],
            'warnings': [],
        }

    platform = meta.get('platform') or variant_path.stem
    eff_channel = str(meta.get('channel') or channel).lower()
    spec = load_platform_spec(platform)
    if not spec:
        return {
            'platform': platform,
            'file': f'variants/{variant_path.name}',
            'channel': eff_channel,
            'specStatus': 'warn',
            'variantHash': variant_hash,
            'issues': [{'code': 'missing_spec', 'message': f'No specs.json found for platform-{platform}'}],
            'warnings': [],
        }

    limits, media_rules, req_options, topic_rules = resolve_effective_spec(spec, eff_channel)
    recs = spec.get('recommendations') or {}
    tco_len = limits.get('tcoUrlLength')

    mode = meta.get('mode', 'text')
    allowed_modes = limits.get('modes', [])
    if allowed_modes and mode not in allowed_modes:
        issues.append({'code': 'unsupported_content_mode', 'message': f'Mode "{mode}" not in {allowed_modes} ({eff_channel} channel)'})

    # Apply mode-specific hard limits (WeChat newspic / YouTube shorts)
    min_images = 0
    if mode == 'newspic' and isinstance(limits.get('newspicLimits'), dict):
        nl = limits['newspicLimits']
        limits = {**limits, **{k: v for k, v in nl.items() if k in ('maxTitleLength', 'maxBodyLength', 'maxImages')}}
        min_images = int(nl.get('minImages', 1))
    elif mode == 'shorts' and isinstance(limits.get('shortsLimits'), dict):
        sl = limits['shortsLimits']
        if 'maxVideoDurationSec' in sl:
            media_rules = {**media_rules, 'maxVideoDurationSec': sl['maxVideoDurationSec']}

    title = str(meta.get('title', '') or '')
    max_title = limits.get('maxTitleLength')
    if max_title is not None and len(title) > max_title:
        issues.append({'code': 'too_big', 'field': 'title', 'message': f'Title length {len(title)} exceeds max {max_title}'})

    if not allow_placeholders:
        for fname, text_val in (('title', title), ('body', body)):
            m_ph = PLACEHOLDER_RE.search(text_val)
            if m_ph:
                issues.append({'code': 'unfinished_placeholder', 'field': fname, 'message': f'Unfinished placeholder "{m_ph.group(0)}" in {fname}'})

    topics = meta.get('topics', []) or []
    if topics and not topic_rules.get('supported', True):
        issues.append({'code': 'invalid_option', 'field': 'topic', 'message': f'{platform} does not support topics'})
    max_topic_count = topic_rules.get('maxCount')
    if max_topic_count is not None and len(topics) > max_topic_count:
        issues.append({'code': 'too_big', 'field': 'topic', 'message': f'Topic count {len(topics)} exceeds max {max_topic_count}'})
    rec_topics = recs.get('maxTopicCount')
    if rec_topics is not None and len(topics) > rec_topics:
        warnings.append({'code': 'topic_count_advisory', 'field': 'topic', 'message': f'{len(topics)} topics attached; platform norm recommends <= {rec_topics}'})
    max_topic_len = topic_rules.get('maxTotalLength')
    if max_topic_len is not None and sum(len(str(t)) for t in topics) > max_topic_len:
        issues.append({'code': 'too_big', 'field': 'topic', 'message': f'Total topic length exceeds max {max_topic_len}'})

    options = meta.get('options') or {}
    norm_body = body.replace('\r\n', '\n').replace('\r', '\n')
    thread_parts = None
    if isinstance(meta.get('threads'), list) and meta['threads']:
        thread_parts = [str(p).strip() for p in meta['threads']]
    elif platform in ('x-twitter', 'threads') and re.search(r'\n---\s*\n', norm_body):
        thread_parts = [p.strip() for p in re.split(r'\n---\s*\n', norm_body) if p.strip()]

    skip_x_280 = platform == 'x-twitter' and bool(options.get('long_post'))
    max_body = None if skip_x_280 else limits.get('maxBodyLength')
    max_total = None if skip_x_280 else limits.get('maxTotalTextLength')
    if thread_parts:
        for idx, part in enumerate(thread_parts, start=1):
            plen = weighted_length(part, tco_len, platform)
            cap = max_total or max_body
            if cap is not None and plen > cap:
                issues.append({'code': 'too_big', 'field': 'body', 'message': f'Thread item #{idx} length {plen} exceeds max {cap}'})
    else:
        blen = weighted_length(norm_body, tco_len, platform)
        if max_body is not None and blen > max_body:
            issues.append({'code': 'too_big', 'field': 'body', 'message': f'Body length {blen} exceeds max {max_body}'})
        if max_total is not None:
            combined_len = len(title) + blen
            if not topic_rules.get('nativeField', False) and topics:
                combined_len += sum(len(str(t)) + 2 for t in topics)
            if combined_len > max_total:
                issues.append({'code': 'too_big', 'field': 'text', 'message': f'Combined text length {combined_len} exceeds max {max_total}'})

    first_reply = options.get('firstReply')
    if first_reply is not None and first_reply != '':
        if not isinstance(first_reply, str):
            issues.append({'code': 'invalid_option', 'field': 'firstReply', 'message': 'options.firstReply must be a string'})
        else:
            fr_text = first_reply.replace('\r\n', '\n').replace('\r', '\n').strip()
            if not allow_placeholders:
                m_fr_ph = PLACEHOLDER_RE.search(fr_text)
                if m_fr_ph:
                    issues.append({'code': 'unfinished_placeholder', 'field': 'firstReply', 'message': f'Unfinished placeholder "{m_fr_ph.group(0)}" in firstReply'})
            fr_cap = max_total or max_body
            if fr_cap is not None:
                fr_len = weighted_length(fr_text, tco_len, platform)
                if fr_len > fr_cap:
                    issues.append({'code': 'too_big', 'field': 'firstReply', 'message': f'options.firstReply length {fr_len} exceeds max {fr_cap}'})

    if platform in ('x-twitter', 'linkedin') and not skip_x_280:
        root_text = thread_parts[0] if thread_parts else norm_body
        if URL_RE.search(root_text) and not str(first_reply or '').strip():
            plat_label = 'X' if platform == 'x-twitter' else 'LinkedIn'
            warnings.append({
                'code': 'outbound_link_in_root',
                'field': 'body',
                'message': f'Root {plat_label} post contains an external URL; consider moving links to options.firstReply to preserve feed reach.',
            })

    for req_opt in req_options:
        if req_opt not in options or options[req_opt] in (None, ''):
            issues.append({'code': 'required', 'field': 'option', 'message': f'Required {eff_channel} option "{req_opt}" is missing'})
    if platform == 'bilibili' and options.get('copyright') == 2 and not str(options.get('source') or '').strip():
        issues.append({'code': 'required', 'field': 'option', 'message': 'Bilibili reprint (copyright=2) requires options.source'})

    media = meta.get('media', []) or []
    images = [m for m in media if m.get('type') == 'image']
    videos = [m for m in media if m.get('type') == 'video']
    docs = [m for m in media if m.get('type') == 'document']
    if images and videos and not limits.get('allowMixedMedia', False):
        issues.append({'code': 'invalid_combination', 'field': 'media', 'message': 'Cannot mix images and videos in one post'})

    if mode == 'image_text' and not images:
        issues.append({'code': 'required', 'field': 'image', 'message': 'image_text mode requires at least 1 image'})
    if mode == 'newspic' and len(images) < min_images:
        issues.append({'code': 'required', 'field': 'image', 'message': f'newspic mode requires at least {min_images} image(s)'})
    if mode in ('video', 'shorts') and not videos:
        issues.append({'code': 'required', 'field': 'video', 'message': f'{mode} mode requires 1 video'})
    if mode == 'document' and not docs:
        issues.append({'code': 'required', 'field': 'document', 'message': 'document mode requires 1 PDF document'})

    max_images = limits.get('maxImages')
    if max_images is not None and len(images) > max_images:
        issues.append({'code': 'too_big', 'field': 'image', 'message': f'Image count {len(images)} exceeds max {max_images}'})
    max_videos = limits.get('maxVideos')
    if max_videos is not None and len(videos) > max_videos:
        issues.append({'code': 'too_big', 'field': 'video', 'message': f'Video count {len(videos)} exceeds max {max_videos}'})
    max_docs = limits.get('maxDocuments')
    if max_docs is not None and len(docs) > max_docs:
        issues.append({'code': 'too_big', 'field': 'document', 'message': f'Document count {len(docs)} exceeds max {max_docs}'})

    allowed_img_fmts = {f.lower() for f in media_rules.get('imageFormats', [])}
    max_img_bytes = media_rules.get('maxImageSizeBytes')
    max_gif_bytes = media_rules.get('maxGifSizeBytes')
    aspect_rule = media_rules.get('aspectRatio')
    skip_aspect = platform == 'instagram' and str(options.get('media_type', '')).upper() in ('STORIES', 'REELS')

    for idx, img in enumerate(images):
        rel = img.get('path')
        if not rel:
            issues.append({'code': 'required', 'field': 'image', 'message': f'Image[{idx}] missing path'})
            continue
        p = draft_dir / rel
        if not p.is_file():
            issues.append({'code': 'media_unreachable', 'field': 'image', 'message': f'Missing local file: {rel}'})
            continue
        info = probe_image_stdlib(p)
        ext = info['format'].lower()
        if not format_allowed(ext, p.suffix.lstrip('.').lower(), allowed_img_fmts):
            issues.append({'code': 'unsupported_format', 'field': 'image', 'message': f'{rel}: detected format "{ext}" not in {sorted(allowed_img_fmts)}'})
        size_cap = max_gif_bytes if (ext == 'gif' and max_gif_bytes) else max_img_bytes
        if size_cap and info['sizeBytes'] > size_cap:
            issues.append({'code': 'too_big', 'field': 'image', 'message': f'{rel}: {info["sizeBytes"]} bytes exceeds max {size_cap}'})
        if aspect_rule and not skip_aspect and info['aspectRatio'] is not None:
            rmin, rmax = aspect_rule.get('min'), aspect_rule.get('max')
            if rmin is not None and info['aspectRatio'] < rmin:
                issues.append({'code': 'too_small', 'field': 'image', 'message': f'{rel}: aspect ratio {info["aspectRatio"]} below min {rmin}'})
            if rmax is not None and info['aspectRatio'] > rmax:
                issues.append({'code': 'too_big', 'field': 'image', 'message': f'{rel}: aspect ratio {info["aspectRatio"]} exceeds max {rmax}'})

    cover = meta.get('cover')
    cover_rel = cover if isinstance(cover, str) and cover else (cover.get('path') if isinstance(cover, dict) else None)
    if cover_rel:
        cp = draft_dir / cover_rel
        if not cp.is_file():
            issues.append({'code': 'media_unreachable', 'field': 'cover', 'message': f'Missing cover file: {cover_rel}'})
        else:
            cinfo = probe_image_stdlib(cp)
            cext = cinfo['format'].lower()
            if not format_allowed(cext, cp.suffix.lstrip('.').lower(), allowed_img_fmts):
                issues.append({'code': 'unsupported_format', 'field': 'cover', 'message': f'{cover_rel}: detected format "{cext}" not in {sorted(allowed_img_fmts)}'})
            if max_img_bytes and cinfo['sizeBytes'] > max_img_bytes:
                issues.append({'code': 'too_big', 'field': 'cover', 'message': f'{cover_rel}: {cinfo["sizeBytes"]} bytes exceeds max {max_img_bytes}'})
            cov_ar = recs.get('coverAspectRatio')
            if cov_ar and cinfo['aspectRatio'] is not None:
                if cinfo['aspectRatio'] < cov_ar['min'] or cinfo['aspectRatio'] > cov_ar['max']:
                    warnings.append({'code': 'cover_ratio_advisory', 'field': 'cover', 'message': f'{cover_rel}: ratio {cinfo["aspectRatio"]} outside recommended {cov_ar["min"]}..{cov_ar["max"]}'})

    allowed_doc_fmts = {f.lower() for f in media_rules.get('documentFormats', ['pdf'])}
    max_doc_bytes = media_rules.get('maxDocumentSizeBytes')
    for idx, doc in enumerate(docs):
        rel = doc.get('path')
        if not rel:
            issues.append({'code': 'required', 'field': 'document', 'message': f'Document[{idx}] missing path'})
            continue
        p = draft_dir / rel
        if not p.is_file():
            issues.append({'code': 'media_unreachable', 'field': 'document', 'message': f'Missing local file: {rel}'})
            continue
        ext = p.suffix.lstrip('.').lower()
        if allowed_doc_fmts and ext not in allowed_doc_fmts:
            issues.append({'code': 'unsupported_format', 'field': 'document', 'message': f'{rel}: format "{ext}" not in {sorted(allowed_doc_fmts)}'})
        if max_doc_bytes and p.stat().st_size > max_doc_bytes:
            issues.append({'code': 'too_big', 'field': 'document', 'message': f'{rel}: exceeds max {max_doc_bytes} bytes'})

    allowed_vid_fmts = {f.lower() for f in media_rules.get('videoFormats', [])}
    max_vid_bytes = media_rules.get('maxVideoSizeBytes')
    min_dur = media_rules.get('minVideoDurationSec')
    max_dur = media_rules.get('maxVideoDurationSec')
    for idx, vid in enumerate(videos):
        rel = vid.get('path')
        probed_vid = None
        if not rel:
            issues.append({'code': 'required', 'field': 'video', 'message': f'Video[{idx}] missing path'})
        else:
            p = draft_dir / rel
            if not p.is_file():
                issues.append({'code': 'media_unreachable', 'field': 'video', 'message': f'Missing local file: {rel}'})
            else:
                ext = p.suffix.lstrip('.').lower()
                if allowed_vid_fmts and ext not in allowed_vid_fmts:
                    issues.append({'code': 'unsupported_format', 'field': 'video', 'message': f'{rel}: format "{ext}" not in {sorted(allowed_vid_fmts)}'})
                if max_vid_bytes and p.stat().st_size > max_vid_bytes:
                    issues.append({'code': 'too_big', 'field': 'video', 'message': f'{rel}: exceeds max {max_vid_bytes} bytes'})
                probed_vid = probe_video_ffprobe(p)
        dur = (probed_vid or {}).get('durationSec') if (probed_vid and probed_vid.get('durationSec') is not None) else vid.get('durationSec')
        if dur is not None:
            if min_dur is not None and dur < min_dur:
                issues.append({'code': 'invalid_duration', 'field': 'video', 'message': f'Video[{idx}] duration {dur}s below min {min_dur}s'})
            if max_dur is not None and dur > max_dur:
                issues.append({'code': 'invalid_duration', 'field': 'video', 'message': f'Video[{idx}] duration {dur}s exceeds max {max_dur}s'})

    return {
        'platform': platform,
        'file': f'variants/{variant_path.name}',
        'channel': eff_channel,
        'mode': mode,
        'specStatus': 'pass' if not issues else 'fail',
        'variantHash': variant_hash,
        'issues': issues,
        'warnings': warnings,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Validate draft variants against per-platform specs.json.')
    parser.add_argument('draft_dir', help='Path to content-ops/drafts/<draft-id>.')
    parser.add_argument('--channel', choices=['browser', 'api'], default='browser', help='Delivery channel (browser default; api activates apiOverrides).')
    parser.add_argument('--allow-placeholders', action='store_true', help='Skip unfinished placeholder scan for work-in-progress drafts.')
    parser.add_argument('--update-meta', action='store_true', help='Write validation results and variantHash back to meta.json.')
    args = parser.parse_args(argv)

    draft_dir = Path(args.draft_dir).expanduser().resolve()
    variants_dir = draft_dir / 'variants'
    if not variants_dir.is_dir():
        print(f'Missing variants directory: {variants_dir}', file=sys.stderr)
        return 1

    results = [
        validate_variant(draft_dir, path, channel=args.channel, allow_placeholders=args.allow_placeholders)
        for path in sorted(variants_dir.iterdir())
        if path.is_file() and path.suffix in ('.md', '.json')
    ]

    if args.update_meta and (draft_dir / 'meta.json').is_file():
        meta_path = draft_dir / 'meta.json'
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        variants_map = meta.setdefault('variants', {})
        for res in results:
            prev = variants_map.get(res['platform'], {}) if isinstance(variants_map.get(res['platform']), dict) else {}
            variants_map[res['platform']] = {
                'file': res['file'],
                'mode': res.get('mode', 'text'),
                'specStatus': res['specStatus'],
                'publishState': prev.get('publishState', 'unscheduled'),
                'variantHash': res['variantHash'],
                'issues': res['issues'],
                'warnings': res.get('warnings', []),
            }
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    print(json.dumps({'draftDir': str(draft_dir), 'channel': args.channel, 'results': results}, indent=2, ensure_ascii=False))
    return 1 if any(r['specStatus'] == 'fail' for r in results) else 0


if __name__ == '__main__':
    sys.exit(main())
