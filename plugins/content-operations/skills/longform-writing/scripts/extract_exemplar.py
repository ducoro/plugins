#!/usr/bin/env python3
"""Zero-dependency style exemplar library: extract structural & rhythmic fingerprints (never copy claims/anecdotes)."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

CATEGORIES = ['tech-opinion', 'story-emotional', 'list-practical', 'hot-take', 'general']
STORY_MARKERS = ['那天', '那年', '记得', '后来', '当时', '第一次', '突然', '终于']
TRANSITION_WORDS = ['但是', '不过', '然而', '话说回来', '换个角度', '反过来看', '但真正']
DATA_PATTERNS = [re.compile(r'\d+(?:\.\d+)?%'), re.compile(r'20[12]\d\s*年'), re.compile(r'https?://\S+')]


def strip_variant_header(text: str) -> str:
    m = re.match(r'^\s*```json\s*\n.*?\n```\s*\n?', text, re.S)
    return text[m.end():] if m else text


def extract_exemplar(
    raw_text: str,
    source: str = '',
    category: str = '',
    *,
    user_authored: bool = False,
    framework: str = '',
) -> dict:
    clean = strip_variant_header(raw_text).replace('\r\n', '\n').strip()
    title_m = re.search(r'^#\s+(.+)$', clean, re.M)
    title = title_m.group(1).strip() if title_m else ''
    h2s = re.findall(r'^##\s+(.+)$', clean, re.M)
    paras = [
        p.strip()
        for p in re.split(r'\n\s*\n+', re.sub(r'```.*?```', '', clean, flags=re.S))
        if p.strip() and not p.strip().startswith('#')
    ]
    plain_chars = sum(len(re.sub(r'\s+', '', p)) for p in paras)
    avg_para_len = round(plain_chars / max(len(paras), 1), 1)
    sentences = [s.strip() for p in paras for s in re.split(r'[。！？!?\n]+', p) if len(s.strip()) >= 2]
    short_ratio = round(sum(1 for s in sentences if len(s) <= 15) / max(len(sentences), 1), 3)

    # Opening hook & closing cadence (<= 240 chars each)
    opening_parts, total = [], 0
    for p in paras:
        if total + len(p) > 240 and opening_parts:
            break
        opening_parts.append(p)
        total += len(p)
    closing_parts, total = [], 0
    for p in reversed(paras):
        if total + len(p) > 240 and closing_parts:
            break
        closing_parts.insert(0, p)
        total += len(p)

    # Transition / pivot sample
    best_pivot, best_hits = '', 0
    for p in paras:
        if len(p) < 20:
            continue
        hits = sum(p.count(w) for w in TRANSITION_WORDS)
        if hits > best_hits:
            best_hits = hits
            best_pivot = p[:240]

    # Auto category
    if not category:
        data_hits = sum(len(rx.findall(clean)) for rx in DATA_PATTERNS)
        story_hits = sum(clean.count(w) for w in STORY_MARKERS)
        list_hits = len(re.findall(r'^(?:[-*+]\s+|\d+\.\s+)', clean, re.M))
        if list_hits >= 5 and len(h2s) >= 2:
            category = 'list-practical'
        elif data_hits >= 3:
            category = 'tech-opinion'
        elif story_hits >= 3:
            category = 'story-emotional'
        elif plain_chars <= 1400:
            category = 'hot-take'
        else:
            category = 'general'

    eid = hashlib.sha256(f'{title}|{source}|{plain_chars}'.encode('utf-8')).hexdigest()[:10]
    ownership = 'user' if user_authored else 'third_party'
    authenticity = 'user_authored' if user_authored else 'third_party_reference'
    return {
        'id': eid,
        'title': title or '(untitled)',
        'source': source,
        'category': category if category in CATEGORIES else 'general',
        'framework': framework.strip() or category,
        'ownership': ownership,
        'authenticity': authenticity,
        'allowedUses': ['style', 'structure'],
        'personalMaterialsReusable': False,
        'fingerprint': {
            'charCount': plain_chars,
            'paragraphCount': len(paras),
            'avgParagraphChars': avg_para_len,
            'shortSentenceRatio': short_ratio,
            'h2Count': len(h2s),
            'headingOutline': h2s[:8],
        },
        'cadenceSamples': {
            'openingHook': '\n\n'.join(opening_parts)[:260],
            'transitionPivot': best_pivot,
            'closingBeat': '\n\n'.join(closing_parts)[:260],
        },
        'usageBoundary': 'Allowed for style and structure calibration only; personalMaterialsReusable is always false (never copy personal experiences or claims even from user-authored old articles).',
        'addedAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }


def load_store(path: Path) -> dict:
    if not path.is_file():
        return {'version': 1, 'exemplars': []}
    return json.loads(path.read_text(encoding='utf-8'))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Build and inspect a style exemplar library (structure & rhythm only).')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_add = sub.add_parser('add', help='Extract style fingerprint from one or more Markdown articles into <workspace>/style/exemplars.json.')
    p_add.add_argument('workspace', help='Path to content-ops workspace.')
    p_add.add_argument('files', nargs='+', help='Markdown article file(s).')
    p_add.add_argument('--source', default='', help='Source label or publication name.')
    p_add.add_argument('--category', default='', choices=['', *CATEGORIES])
    p_add.add_argument('--framework', default='', help='Optional writing framework tag (opinion, pain-point, checklist, story, comparison, trend-brief, retro).')
    p_add.add_argument('--user-authored', action='store_true', help='Mark exemplar ownership=user (only when explicitly confirmed as authored/edited by the user).')
    p_add.add_argument('--json', action='store_true')

    p_ls = sub.add_parser('list', help='List saved exemplars in <workspace>/style/exemplars.json.')
    p_ls.add_argument('workspace')
    p_ls.add_argument('--category', default='')
    p_ls.add_argument('--ownership', default='', choices=['', 'user', 'third_party'])
    p_ls.add_argument('--framework', default='')
    p_ls.add_argument('--limit', type=int, default=0, help='Optional max count (recommended <= 2 when injecting into prompts).')
    p_ls.add_argument('--json', action='store_true')

    args = ap.parse_args(argv)
    ws = Path(args.workspace).expanduser().resolve()
    store_path = ws / 'style' / 'exemplars.json'
    store = load_store(store_path)

    if args.cmd == 'add':
        by_id = {e['id']: e for e in store.get('exemplars', [])}
        added = []
        for raw_f in args.files:
            fp = Path(raw_f).expanduser().resolve()
            if not fp.is_file():
                print(f'Error: file not found: {fp}', file=sys.stderr)
                return 1
            ex = extract_exemplar(
                fp.read_text(encoding='utf-8'),
                source=args.source or fp.stem,
                category=args.category,
                user_authored=args.user_authored,
                framework=args.framework,
            )
            by_id[ex['id']] = ex
            added.append(ex)
        store['exemplars'] = list(by_id.values())
        store_path.parent.mkdir(parents=True, exist_ok=True)
        store_path.write_text(json.dumps(store, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        out = {'addedCount': len(added), 'exemplars': added, 'storePath': str(store_path)}
        print(json.dumps(out, indent=2, ensure_ascii=False) if args.json else f'Saved {len(added)} exemplar(s) -> {store_path}')
        return 0

    rows = store.get('exemplars', [])
    for r in rows:
        r.setdefault('ownership', 'third_party')
        r.setdefault('allowedUses', ['style', 'structure'])
        r.setdefault('personalMaterialsReusable', False)
    if args.category:
        rows = [r for r in rows if r.get('category') == args.category]
    if args.ownership:
        rows = [r for r in rows if r.get('ownership') == args.ownership]
    if args.framework:
        rows = [r for r in rows if str(r.get('framework', '')).lower() == args.framework.lower()]
    if args.limit > 0:
        rows = rows[:args.limit]
    if args.json:
        print(json.dumps({'count': len(rows), 'exemplars': rows}, indent=2, ensure_ascii=False))
    else:
        print(f'Exemplars ({len(rows)}):')
        for r in rows:
            fp = r['fingerprint']
            print(f"  - [{r['category']}|{r['ownership']}] {r['id']} | {r['title']} ({fp['charCount']} chars, avg para {fp['avgParagraphChars']})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
