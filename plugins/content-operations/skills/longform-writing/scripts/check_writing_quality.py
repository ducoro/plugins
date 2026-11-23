#!/usr/bin/env python3
"""Zero-dependency writing quality risk checker (mechanical AI-isms + cross-platform similarity gate)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

CLICHE_PHRASES_ZH = [
    '首先', '其次', '再者', '最后', '总之', '综上所述', '总而言之',
    '此外', '另外', '与此同时', '不仅如此', '更重要的是', '在此基础上',
    '值得注意的是', '需要指出的是', '不可否认', '毋庸置疑', '众所周知',
    '显而易见', '从某种意义上说', '至关重要', '不言而喻', '具有重要意义',
    '发挥着重要作用', '意义深远', '影响深远', '引发了广泛关注', '引起了热烈讨论',
    '总的来说', '综合来看', '由此可见', '不难发现', '通过以上分析', '正如我们所看到的',
]

CLICHE_PHRASES_EN = [
    'in today\'s fast-paced world', 'in conclusion', 'it is worth noting',
    'needless to say', 'delve into', 'game-changer', 'revolutionize',
    'unlock the full potential', 'tapestry of', 'at the end of the day',
    'navigating the landscape', 'ever-evolving landscape', 'it goes without saying',
]

HEDGE_ADVERBS = ['非常', '极其', '极大地', '深刻地', '显著地', '全面地', '有效地', '真正地', 'literally', 'fundamentally', 'seamlessly']

EVIDENCE_PATTERNS = [
    re.compile(r'https?://\S+'),
    re.compile(r'20[12]\d\s*年|\b20[12]\d(?:-\d{2})?\b'),
    re.compile(r'\d+(?:\.\d+)?%'),
    re.compile(r'(?:亿|万)\s*(?:美元|元|人民币|用户|次)|\$\d[\d,.]*[KMBkmb]?'),
    re.compile(r'(?:据|根据|来自)\s*[\u4e00-\u9fffA-Za-z0-9]{2,12}(?:报告|数据|研究|财报|公告|文档)'),
]

NORM_RE = re.compile(r'[^\w\u4e00-\u9fff]+')


def strip_variant_header(text: str) -> str:
    m = re.match(r'^\s*```json\s*\n.*?\n```\s*\n?', text, re.S)
    return text[m.end():] if m else text


def strip_code_blocks(text: str) -> str:
    return re.sub(r'```.*?```', '', text, flags=re.S)


def score_text(raw_text: str) -> dict:
    """Run mechanical style-risk checks (never claims to prove human vs AI authorship or verify facts)."""
    body = strip_code_blocks(strip_variant_header(raw_text))
    lines = body.splitlines()
    plain_chars = len(re.sub(r'\s+', '', body))

    # 1. Cliche / filler phrases
    cliche_hits = []
    for phrase in CLICHE_PHRASES_ZH:
        count = body.count(phrase)
        if count:
            cliche_hits.append({'phrase': phrase, 'count': count})
    lower_body = body.lower()
    for phrase in CLICHE_PHRASES_EN:
        count = lower_body.count(phrase)
        if count:
            cliche_hits.append({'phrase': phrase, 'count': count})
    total_cliches = sum(h['count'] for h in cliche_hits)

    # 2. Excessive filler adverbs
    adverb_count = sum(lower_body.count(w.lower()) for w in HEDGE_ADVERBS)

    # 3. Split sentences & measure fragment ratio + repeated openers
    prose = re.sub(r'^#{1,6}\s+.*$', '', body, flags=re.M)
    prose = re.sub(r'^:::\w*.*$', '', prose, flags=re.M)
    sentences = [s.strip() for s in re.split(r'[。！？!?\n]+', prose) if len(s.strip()) >= 2]
    short_fragments = [s for s in sentences if len(s) <= 8]
    fragment_ratio = round(len(short_fragments) / max(len(sentences), 1), 3)

    repeated_openers = 0
    for idx in range(2, len(sentences)):
        a, b, c = sentences[idx - 2][:3], sentences[idx - 1][:3], sentences[idx][:3]
        if a and a == b == c:
            repeated_openers += 1

    # 4. Concrete evidence / source anchor signals
    evidence_hits = sum(len(rx.findall(body)) for rx in EVIDENCE_PATTERNS)

    # 5. Parallel "不是X，而是Y" overuse
    not_but_count = len(re.findall(r'不是[^，。！？\n]{1,18}，而是', body))

    # 6. Compute risk flags & 0-100 readability/hygiene index (100 = cleanest mechanical style)
    findings = []
    penalty = 0
    if total_cliches >= 3:
        penalty += min(35, total_cliches * 5)
        findings.append({
            'rule': 'cliche_density',
            'level': 'WARN' if total_cliches < 6 else 'HIGH',
            'count': total_cliches,
            'message': f'Found {total_cliches} formulaic transition/filler phrases; tighten openings and transitions',
            'topMatches': sorted(cliche_hits, key=lambda x: -x['count'])[:8],
        })
    if not_but_count >= 3:
        penalty += min(15, not_but_count * 4)
        findings.append({
            'rule': 'contrast_template_overuse',
            'level': 'WARN',
            'count': not_but_count,
            'message': f'Repeated "不是…而是…" antithesis pattern {not_but_count} times; vary sentence structure',
        })
    if repeated_openers >= 1:
        penalty += min(15, repeated_openers * 6)
        findings.append({
            'rule': 'repetitive_openers',
            'level': 'WARN',
            'count': repeated_openers,
            'message': f'Detected {repeated_openers} run(s) of 3+ consecutive sentences with identical openings',
        })
    if len(sentences) >= 8 and fragment_ratio > 0.35:
        penalty += 12
        findings.append({
            'rule': 'choppy_fragments',
            'level': 'WARN',
            'count': len(short_fragments),
            'message': f'Short fragment ratio is {fragment_ratio:.0%} ({len(short_fragments)}/{len(sentences)}); vary rhythm',
        })
    if adverb_count >= 5:
        penalty += min(12, adverb_count * 2)
        findings.append({
            'rule': 'filler_adverbs',
            'level': 'WARN',
            'count': adverb_count,
            'message': f'Found {adverb_count} abstract intensifier adverbs; replace with concrete numbers or observations',
        })
    if plain_chars >= 400 and evidence_hits == 0:
        penalty += 15
        findings.append({
            'rule': 'weak_evidence_anchors',
            'level': 'WARN',
            'count': 0,
            'message': 'No dates, numbers, percentages, or named source citations found in a >=400-char piece',
        })

    score = max(0, 100 - penalty)
    return {
        'score': score,
        'passRecommended': score >= 75,
        'stats': {
            'charCount': plain_chars,
            'sentenceCount': len(sentences),
            'clicheCount': total_cliches,
            'contrastPatternCount': not_but_count,
            'adverbCount': adverb_count,
            'fragmentRatio': fragment_ratio,
            'evidenceAnchors': evidence_hits,
        },
        'findings': findings,
        'disclaimer': 'Mechanical style-risk check only; does not verify factual truth or prove authorship.',
    }


def char_ngrams(text: str, n: int = 3) -> set[str]:
    norm = NORM_RE.sub('', strip_code_blocks(strip_variant_header(text))).lower()
    if len(norm) < n:
        return {norm} if norm else set()
    return {norm[i:i + n] for i in range(len(norm) - n + 1)}


def jaccard_similarity(a: str, b: str, n: int = 3) -> float:
    sa, sb = char_ngrams(a, n), char_ngrams(b, n)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Mechanical writing quality & cross-platform rewrite similarity checker.')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_score = sub.add_parser('score', help='Check one draft for mechanical style risks (cliches, rhythm, evidence density).')
    p_score.add_argument('file', help='Path to Markdown or text draft.')
    p_score.add_argument('--min-score', type=int, default=0, help='Optional exit non-zero threshold (default 0 = advisory).')
    p_score.add_argument('--json', action='store_true')

    p_sim = sub.add_parser('similarity', help='Check pairwise 3-gram Jaccard similarity across multi-platform variants.')
    p_sim.add_argument('files', nargs='+', help='Two or more draft/variant files to compare.')
    p_sim.add_argument('-n', type=int, default=3, help='Character n-gram length (default 3).')
    p_sim.add_argument('--threshold', type=float, default=0.45, help='Max recommended similarity for cross-platform rewrites.')
    p_sim.add_argument('--fail-on-exceed', action='store_true', help='Exit non-zero if max similarity exceeds --threshold.')
    p_sim.add_argument('--json', action='store_true')

    args = ap.parse_args(argv)

    if args.cmd == 'score':
        path = Path(args.file).expanduser().resolve()
        if not path.is_file():
            print(f'Error: file not found: {path}', file=sys.stderr)
            return 1
        report = score_text(path.read_text(encoding='utf-8'))
        report['file'] = str(path)
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print(f"Writing quality hygiene score: {report['score']}/100 ({path.name})")
            for f in report['findings']:
                print(f"  [{f['level']}] {f['rule']}: {f['message']}")
        return 1 if args.min_score and report['score'] < args.min_score else 0

    if len(args.files) < 2:
        print('Error: similarity requires at least 2 files', file=sys.stderr)
        return 1
    paths = [Path(f).expanduser().resolve() for f in args.files]
    for p in paths:
        if not p.is_file():
            print(f'Error: file not found: {p}', file=sys.stderr)
            return 1
    texts = [p.read_text(encoding='utf-8') for p in paths]
    pairs = []
    max_sim = 0.0
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            sim = round(jaccard_similarity(texts[i], texts[j], n=args.n), 4)
            max_sim = max(max_sim, sim)
            pairs.append({'fileA': paths[i].name, 'fileB': paths[j].name, 'similarity': sim})
    exceeds = max_sim > args.threshold
    report = {'maxSimilarity': max_sim, 'threshold': args.threshold, 'exceedsThreshold': exceeds, 'pairs': pairs}
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        status = 'EXCEEDS' if exceeds else 'OK'
        print(f'Max pairwise {args.n}-gram similarity: {max_sim:.4f} (threshold {args.threshold}) [{status}]')
        for pair in pairs:
            print(f"  - {pair['fileA']} vs {pair['fileB']}: {pair['similarity']:.4f}")
    return 1 if (args.fail_on_exceed and exceeds) else 0


if __name__ == '__main__':
    sys.exit(main())
