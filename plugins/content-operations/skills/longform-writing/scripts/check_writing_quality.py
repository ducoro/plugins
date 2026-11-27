#!/usr/bin/env python3
"""Zero-dependency physical text telemetry probe and cross-platform n-gram similarity checker."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

NORM_RE = re.compile(r'[^\w\u4e00-\u9fff]+')


def strip_variant_header(text: str) -> str:
    m = re.match(r'^\s*```json\s*\n.*?\n```\s*\n?', text, re.S)
    return text[m.end():] if m else text


def strip_code_blocks(text: str) -> str:
    return re.sub(r'```.*?```', '', text, flags=re.S)


def char_ngrams(text: str, n: int = 3) -> set[str]:
    norm = NORM_RE.sub('', strip_code_blocks(strip_variant_header(text))).lower()
    if len(norm) < n:
        return {norm} if norm else set()
    return {norm[i:i + n] for i in range(len(norm) - n + 1)}


def top_repeated_ngrams(text: str, n: int = 4, min_count: int = 3, limit: int = 10) -> list[dict]:
    """Return objective high-frequency character n-grams inside prose (no wordlists or style scoring)."""
    norm = NORM_RE.sub('', text).lower()
    if len(norm) < n:
        return []
    counts = Counter(norm[i:i + n] for i in range(len(norm) - n + 1))
    repeated = [(gram, cnt) for gram, cnt in counts.items() if cnt >= min_count]
    repeated.sort(key=lambda item: (-item[1], item[0]))
    return [{'ngram': gram, 'count': cnt} for gram, cnt in repeated[:limit]]


def probe_text(raw_text: str, ngram_len: int = 4) -> dict:
    """Measure purely objective physical text telemetry (length, paragraph/sentence distribution, n-gram repetition)."""
    body = strip_code_blocks(strip_variant_header(raw_text)).replace('\r\n', '\n')
    prose = re.sub(r'^#{1,6}\s+.*$', '', body, flags=re.M)
    prose = re.sub(r'^:::\w*.*$', '', prose, flags=re.M)

    paragraphs = [
        p.strip()
        for p in re.split(r'\n\s*\n+', prose)
        if p.strip()
    ]
    para_lengths = [len(re.sub(r'\s+', '', p)) for p in paragraphs]
    plain_chars = sum(para_lengths) if para_lengths else len(re.sub(r'\s+', '', prose))
    avg_para_chars = round(sum(para_lengths) / max(len(para_lengths), 1), 1) if para_lengths else 0.0
    max_para_chars = max(para_lengths) if para_lengths else 0

    sentences = [s.strip() for s in re.split(r'[。！？!?\n]+', prose) if len(s.strip()) >= 2]
    sent_lengths = [len(re.sub(r'\s+', '', s)) for s in sentences]
    avg_sent_chars = round(sum(sent_lengths) / max(len(sent_lengths), 1), 1) if sent_lengths else 0.0
    short_sentences = [s for s in sentences if len(s) <= 8]
    short_ratio = round(len(short_sentences) / max(len(sentences), 1), 3) if sentences else 0.0

    repeated_openers = 0
    for idx in range(2, len(sentences)):
        a, b, c = sentences[idx - 2][:3], sentences[idx - 1][:3], sentences[idx][:3]
        if a and a == b == c:
            repeated_openers += 1

    return {
        'stats': {
            'charCount': plain_chars,
            'paragraphCount': len(paragraphs),
            'avgParagraphChars': avg_para_chars,
            'maxParagraphChars': max_para_chars,
            'sentenceCount': len(sentences),
            'avgSentenceChars': avg_sent_chars,
            'shortSentenceCount': len(short_sentences),
            'shortSentenceRatio': short_ratio,
            'repeatedOpenerRuns': repeated_openers,
            'repeatedNgrams': top_repeated_ngrams(prose, n=ngram_len),
        },
        'note': 'Objective physical text telemetry only; editorial judgment, fact verification, and style fit belong to the model and independent reviewers.',
    }


def jaccard_similarity(a: str, b: str, n: int = 3) -> float:
    sa, sb = char_ngrams(a, n), char_ngrams(b, n)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Objective physical text telemetry probe & cross-platform n-gram similarity checker.')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_probe = sub.add_parser('probe', help='Measure objective length, paragraph/sentence distribution, and n-gram repetition.')
    p_probe.add_argument('file', help='Path to Markdown or text draft.')
    p_probe.add_argument('-n', '--ngram', type=int, default=4, help='Character n-gram length for repetition telemetry (default 4).')
    p_probe.add_argument('--json', action='store_true')

    p_sim = sub.add_parser('similarity', help='Check pairwise character n-gram Jaccard similarity across multi-platform variants.')
    p_sim.add_argument('files', nargs='+', help='Two or more draft/variant files to compare.')
    p_sim.add_argument('-n', type=int, default=3, help='Character n-gram length (default 3).')
    p_sim.add_argument('--threshold', type=float, default=0.45, help='Max recommended similarity for cross-platform rewrites.')
    p_sim.add_argument('--fail-on-exceed', action='store_true', help='Exit non-zero if max similarity exceeds --threshold.')
    p_sim.add_argument('--json', action='store_true')

    args = ap.parse_args(argv)

    if args.cmd == 'probe':
        path = Path(args.file).expanduser().resolve()
        if not path.is_file():
            print(f'Error: file not found: {path}', file=sys.stderr)
            return 1
        report = probe_text(path.read_text(encoding='utf-8'), ngram_len=max(2, args.ngram))
        report['file'] = str(path)
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            st = report['stats']
            print(
                f"{path.name}: {st['charCount']} chars, {st['paragraphCount']} paras "
                f"(avg {st['avgParagraphChars']}), {st['sentenceCount']} sentences "
                f"(avg {st['avgSentenceChars']}, short ratio {st['shortSentenceRatio']:.1%}), "
                f"repeated opener runs={st['repeatedOpenerRuns']}"
            )
        return 0

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
