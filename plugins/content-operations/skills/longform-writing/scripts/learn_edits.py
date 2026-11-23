#!/usr/bin/env python3
"""Zero-dependency edit-learning flywheel: diff AI drafts vs human-edited finals into cautious style rules."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys


def strip_variant_header(text: str) -> str:
    m = re.match(r'^\s*```json\s*\n.*?\n```\s*\n?', text, re.S)
    return text[m.end():] if m else text


def split_paragraphs(text: str) -> list[str]:
    clean = strip_variant_header(text).replace('\r\n', '\n').strip()
    return [p.strip() for p in re.split(r'\n\s*\n+', clean) if p.strip()]


def extract_h1(text: str) -> str:
    for line in strip_variant_header(text).splitlines():
        s = line.strip()
        if s.startswith('# ') and not s.startswith('## '):
            return s[2:].strip()
    return ''


def normalize_key(kind: str, before: str, after: str, scope: str = 'global', scope_value: str = '') -> str:
    raw = f'{kind}|{scope}|{scope_value.strip().lower()}|{before.strip()[:80]}|{after.strip()[:80]}'
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12]


def extract_lessons(draft_text: str, final_text: str) -> list[dict]:
    lessons: list[dict] = []
    t_before, t_after = extract_h1(draft_text), extract_h1(final_text)
    if t_before and t_after and t_before != t_after:
        lessons.append({
            'type': 'title',
            'before': t_before[:120],
            'after': t_after[:120],
            'summary': f'Title tightened/changed: "{t_before[:50]}" -> "{t_after[:50]}"',
        })

    p_before = [p for p in split_paragraphs(draft_text) if not p.startswith('# ')]
    p_after = [p for p in split_paragraphs(final_text) if not p.startswith('# ')]
    matcher = difflib.SequenceMatcher(None, p_before, p_after)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            continue
        if tag == 'delete':
            for p in p_before[i1:i2]:
                lessons.append({
                    'type': 'para_delete',
                    'before': p[:160],
                    'after': '',
                    'summary': f'Removed paragraph starting with "{p[:48]}"',
                })
        elif tag == 'insert':
            for p in p_after[j1:j2]:
                lessons.append({
                    'type': 'para_add',
                    'before': '',
                    'after': p[:160],
                    'summary': f'Added paragraph starting with "{p[:48]}"',
                })
        elif tag == 'replace':
            b_chunk = p_before[i1:i2]
            a_chunk = p_after[j1:j2]
            if len(b_chunk) != len(a_chunk):
                lessons.append({
                    'type': 'structure',
                    'before': ' / '.join(p[:60] for p in b_chunk[:2]),
                    'after': ' / '.join(p[:60] for p in a_chunk[:2]),
                    'summary': f'Restructured {len(b_chunk)} paragraph(s) into {len(a_chunk)} paragraph(s)',
                })
            for pb, pa in zip(b_chunk, a_chunk):
                ratio = difflib.SequenceMatcher(None, pb, pa).ratio()
                if ratio >= 0.55:
                    lessons.append({
                        'type': 'word_sub',
                        'before': pb[:160],
                        'after': pa[:160],
                        'summary': f'Word/phrasing polish (similarity {ratio:.2f})',
                    })
                else:
                    lessons.append({
                        'type': 'tone',
                        'before': pb[:160],
                        'after': pa[:160],
                        'summary': f'Substantial tone/angle rewrite (similarity {ratio:.2f})',
                    })
    return lessons


VALID_SCOPES = ('global', 'content_type', 'framework', 'persona')
HALF_LIFE_DAYS = 60.0


def _parse_dt(ts: str | None) -> datetime:
    if not ts:
        return datetime.now(timezone.utc)
    raw = str(ts).strip()
    if len(raw) == 10:
        return datetime.strptime(raw, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(raw.replace('Z', '+00:00')).astimezone(timezone.utc)


def compute_confidence(occurrences: int, promoted: bool) -> float:
    if promoted:
        return 1.0
    return round(min(0.95, 0.35 + 0.25 * max(0, occurrences - 1)), 2)


def compute_decayed_score(occurrences: int, last_seen: str | None, as_of: datetime, promoted: bool) -> float:
    """Compute time-decayed effective rule strength (0-10); rules below 2.0 expire unless human-confirmed."""
    if promoted:
        return 10.0
    base = min(10.0, 3.0 * max(1, occurrences))
    age_days = max(0.0, (as_of - _parse_dt(last_seen)).total_seconds() / 86400.0)
    decay = 0.5 ** (age_days / HALF_LIFE_DAYS)
    return round(base * decay, 2)


def matches_scope(item: dict, *, content_type: str = '', framework: str = '', persona: str = '', platform: str = '') -> bool:
    item_plat = str(item.get('platform') or 'all')
    if platform and platform != 'all' and item_plat not in ('all', platform):
        return False
    scope = str(item.get('scope') or 'global')
    val = str(item.get('scopeValue') or '').strip().lower()
    if scope == 'global' or not val:
        return True
    if scope == 'content_type':
        return bool(content_type) and content_type.strip().lower() == val
    if scope == 'framework':
        return bool(framework) and framework.strip().lower() == val
    if scope == 'persona':
        return bool(persona) and persona.strip().lower() == val
    return False


def load_store(path: Path) -> dict:
    if not path.is_file():
        return {'version': 1, 'lessons': []}
    return json.loads(path.read_text(encoding='utf-8'))


def save_store(path: Path, store: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def evaluate_lessons(
    store: dict,
    *,
    min_occurrences: int,
    as_of: datetime,
    content_type: str = '',
    framework: str = '',
    persona: str = '',
    platform: str = '',
) -> tuple[list[dict], list[dict], list[dict]]:
    standing: list[dict] = []
    candidates: list[dict] = []
    expired: list[dict] = []
    for raw in store.get('lessons', []):
        item = dict(raw)
        promoted = bool(item.get('promoted') or item.get('confirmed'))
        occ = int(item.get('occurrences', 1))
        score = compute_decayed_score(occ, item.get('lastSeen'), as_of, promoted)
        item['effectiveScore'] = score
        item['hard'] = bool(promoted or (occ >= min_occurrences and score >= 5.0))
        if score < 2.0 and not promoted:
            item['status'] = 'expired'
            expired.append(item)
            continue
        if not matches_scope(item, content_type=content_type, framework=framework, persona=persona, platform=platform):
            continue
        if item['hard']:
            item['status'] = 'standing'
            standing.append(item)
        else:
            item['status'] = 'advisory'
            candidates.append(item)
    return standing, candidates, expired


def render_playbook(standing: list[dict], candidates: list[dict], expired_count: int) -> str:
    lines = [
        '# Style Playbook (Learned From Human Edits)',
        '',
        '> Rules require `occurrences >= 2` with active time-decayed score `>= 5.0` (or explicit human confirmation) in the same scope.',
        '> Re-run `learn_edits.py summarize --json` before drafting rather than trusting stale cached scores.',
        '',
        '## Standing Rules (`hard: true`)',
    ]
    if not standing:
        lines.append('- _(No active standing rules yet. Keep recording human-edited pairs or promote a confirmed lesson.)_')
    else:
        for item in sorted(standing, key=lambda x: (-float(x.get('effectiveScore', 0)), x.get('id', ''))):
            scope_lbl = item.get('scope', 'global') + (f":{item['scopeValue']}" if item.get('scopeValue') else '')
            plat = item.get('platform') or 'all'
            note = f" — Note: {item['note']}" if item.get('note') else ''
            lines.append(
                f"- **[{item['type']}] ({plat} | {scope_lbl}, x{item['occurrences']}, score {item['effectiveScore']})** `{item['id']}`: {item['summary']}{note}"
            )
    lines.extend(['', '## Advisory Candidates (Single-Occurrence / Soft Reference Only)'])
    if not candidates:
        lines.append('- _(None)_')
    else:
        for item in candidates[-20:]:
            scope_lbl = item.get('scope', 'global') + (f":{item['scopeValue']}" if item.get('scopeValue') else '')
            plat = item.get('platform') or 'all'
            lines.append(f"- [{item['type']}] ({plat} | {scope_lbl}, x{item['occurrences']}, score {item['effectiveScore']}) `{item['id']}`: {item['summary']}")
    if expired_count:
        lines.extend(['', f'_({expired_count} aged rule(s) decayed below 2.0 and were excluded.)_'])
    lines.append('')
    return '\n'.join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Learn recurring human writing preferences by diffing AI drafts vs finals.')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_rec = sub.add_parser('record', help='Diff an AI draft against a human-edited final and store scoped lessons.')
    p_rec.add_argument('workspace', help='Path to content-ops workspace directory.')
    p_rec.add_argument('--draft', required=True, help='Path to original AI draft file.')
    p_rec.add_argument('--final', required=True, help='Path to human-edited final file.')
    p_rec.add_argument('--platform', default='all', help='Platform scope (e.g. wechat-official, xiaohongshu, all).')
    p_rec.add_argument('--scope', choices=VALID_SCOPES, default='global', help='Narrowest true rule scope (default global).')
    p_rec.add_argument('--scope-value', default='', help='Value for non-global scope (e.g. tutorial, opinion, cold-analyst).')
    p_rec.add_argument('--confirmed', action='store_true', help='Mark as explicitly confirmed long-term preference.')
    p_rec.add_argument('--note', default='', help='Optional human explanation for why the edit was made.')
    p_rec.add_argument('--json', action='store_true')

    p_sum = sub.add_parser('summarize', help='Recompute decayed lesson scores, filter by scope, and optionally write style-playbook.md.')
    p_sum.add_argument('workspace', help='Path to content-ops workspace directory.')
    p_sum.add_argument('--min-occurrences', type=int, default=2, help='Occurrences required for standing rule promotion (default 2).')
    p_sum.add_argument('--promote-id', action='append', default=[], help='Explicitly promote a human-confirmed lesson id.')
    p_sum.add_argument('--content-type', default='', help='Filter rules matching this content_type (plus global).')
    p_sum.add_argument('--framework', default='', help='Filter rules matching this framework (plus global).')
    p_sum.add_argument('--persona', default='', help='Filter rules matching this persona (plus global).')
    p_sum.add_argument('--platform', default='', help='Filter rules matching this platform (plus all).')
    p_sum.add_argument('--as-of', default='', help='Optional evaluation date YYYY-MM-DD for deterministic decay scoring.')
    p_sum.add_argument('--write-playbook', action='store_true', help='Write <workspace>/style/style-playbook.md.')
    p_sum.add_argument('--json', action='store_true')

    args = ap.parse_args(argv)
    ws = Path(args.workspace).expanduser().resolve()
    store_path = ws / 'style' / 'lessons.json'
    playbook_path = ws / 'style' / 'style-playbook.md'
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    if args.cmd == 'record':
        if args.scope != 'global' and not args.scope_value.strip():
            print(f'Error: --scope-value is required when --scope is "{args.scope}".', file=sys.stderr)
            return 2
        draft_path = Path(args.draft).expanduser().resolve()
        final_path = Path(args.final).expanduser().resolve()
        for p in (draft_path, final_path):
            if not p.is_file():
                print(f'Error: file not found: {p}', file=sys.stderr)
                return 1
        extracted = extract_lessons(draft_path.read_text(encoding='utf-8'), final_path.read_text(encoding='utf-8'))
        store = load_store(store_path)
        by_id = {item['id']: item for item in store.get('lessons', [])}
        updated_ids = []
        scope_val = '' if args.scope == 'global' else args.scope_value.strip()
        for entry in extracted:
            lid = normalize_key(entry['type'], entry['before'], entry['after'], args.scope, scope_val)
            if lid in by_id:
                rec = by_id[lid]
                rec['occurrences'] = int(rec.get('occurrences', 1)) + 1
                rec['lastSeen'] = now
                if args.confirmed:
                    rec['promoted'] = True
                    rec['confirmed'] = True
                if args.note:
                    rec['note'] = args.note
                rec['confidence'] = compute_confidence(rec['occurrences'], bool(rec.get('promoted')))
            else:
                rec = {
                    'id': lid,
                    'type': entry['type'],
                    'platform': args.platform,
                    'scope': args.scope,
                    'scopeValue': scope_val,
                    'before': entry['before'],
                    'after': entry['after'],
                    'summary': entry['summary'],
                    'note': args.note,
                    'occurrences': 1,
                    'promoted': bool(args.confirmed),
                    'confirmed': bool(args.confirmed),
                    'confidence': compute_confidence(1, bool(args.confirmed)),
                    'firstSeen': now,
                    'lastSeen': now,
                }
                store.setdefault('lessons', []).append(rec)
                by_id[lid] = rec
            updated_ids.append(lid)
        save_store(store_path, store)
        out = {'recordedCount': len(extracted), 'lessonIds': updated_ids, 'scope': args.scope, 'scopeValue': scope_val, 'storePath': str(store_path)}
        print(json.dumps(out, indent=2, ensure_ascii=False) if args.json else f'Recorded {len(extracted)} edit lesson(s) -> {store_path}')
        return 0

    store = load_store(store_path)
    promoted_set = set(args.promote_id or [])
    if promoted_set:
        for item in store.get('lessons', []):
            if item['id'] in promoted_set:
                item['promoted'] = True
                item['confirmed'] = True
                item['confidence'] = compute_confidence(int(item.get('occurrences', 1)), True)
        save_store(store_path, store)

    as_of_dt = _parse_dt(args.as_of) if args.as_of else datetime.now(timezone.utc)
    standing, candidates, expired = evaluate_lessons(
        store,
        min_occurrences=args.min_occurrences,
        as_of=as_of_dt,
        content_type=args.content_type,
        framework=args.framework,
        persona=args.persona,
        platform=args.platform,
    )
    if args.write_playbook:
        playbook_path.parent.mkdir(parents=True, exist_ok=True)
        playbook_path.write_text(render_playbook(standing, candidates, len(expired)), encoding='utf-8')

    out = {
        'totalLessons': len(store.get('lessons', [])),
        'standingCount': len(standing),
        'candidateCount': len(candidates),
        'expiredCount': len(expired),
        'standingRules': standing,
        'advisoryCandidates': candidates,
        'playbookPath': str(playbook_path) if args.write_playbook else None,
    }
    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(f"Edit lessons: {out['totalLessons']} total ({out['standingCount']} standing, {out['candidateCount']} advisory, {out['expiredCount']} expired)")
        if args.write_playbook:
            print(f'Wrote {playbook_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
