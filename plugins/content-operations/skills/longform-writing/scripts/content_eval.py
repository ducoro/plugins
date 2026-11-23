#!/usr/bin/env python3
"""Deterministic 5-dimension editorial evaluation and publishability gate (zero dependencies)."""
from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path
import re
import sys

DIMENSIONS = ('accuracy', 'viewpoint', 'usefulness', 'voice', 'readability')
DECISIONS = ('pass', 'revise', 'needs_input')


def _headings(text: str) -> list[str]:
    return [m.strip() for m in re.findall(r'^##\s+(.+)$', text, re.MULTILINE)]


def build_report(draft: str, final: str, assessment: dict) -> dict:
    """Compute publishability and revision delta from draft, final, and a 5-dimension assessment."""
    if not draft.strip() or not final.strip():
        raise ValueError('Both draft and final text must be non-empty.')
    decision = assessment.get('decision')
    if decision not in DECISIONS:
        raise ValueError(f'decision must be one of: {", ".join(DECISIONS)}')

    dimensions = assessment.get('dimensions')
    if not isinstance(dimensions, dict):
        raise ValueError('assessment.dimensions must be an object with five 1–5 scores.')
    normalized: dict[str, float] = {}
    for name in DIMENSIONS:
        score = dimensions.get(name)
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not 1 <= score <= 5:
            raise ValueError(f'dimension "{name}" must be a number between 1 and 5.')
        normalized[name] = float(score)

    blockers = assessment.get('blockers', [])
    major_issues = assessment.get('majorIssues', assessment.get('major_issues', []))
    if not isinstance(blockers, list) or not isinstance(major_issues, list):
        raise ValueError('blockers and majorIssues must be arrays.')

    pass_number = assessment.get('passNumber', assessment.get('pass_number', 1))
    if not isinstance(pass_number, int) or isinstance(pass_number, bool) or pass_number not in (1, 2):
        raise ValueError('passNumber must be 1 or 2 (maximum two editorial passes).')

    ratio = difflib.SequenceMatcher(None, draft, final, autojunk=False).ratio()
    average = round(sum(normalized.values()) / len(normalized), 2)
    minimum = min(normalized.values())
    publishable = (decision == 'pass') and (not blockers) and (minimum >= 3.0) and (average >= 4.0)

    failure_reasons: list[str] = []
    if decision != 'pass':
        failure_reasons.append(f'decision is "{decision}" (must be "pass")')
    if blockers:
        failure_reasons.append(f'{len(blockers)} blocker(s) remain')
    if minimum < 3.0:
        low = [k for k, v in normalized.items() if v < 3.0]
        failure_reasons.append(f'dimension(s) below 3.0: {", ".join(low)}')
    if average < 4.0:
        failure_reasons.append(f'dimension average {average} is below 4.0')

    return {
        'version': 1,
        'decision': decision,
        'passNumber': pass_number,
        'publishable': publishable,
        'failureReasons': failure_reasons,
        'dimensions': normalized,
        'dimensionAverage': average,
        'dimensionMinimum': minimum,
        'blockers': blockers,
        'majorIssues': major_issues,
        'notes': str(assessment.get('notes', '')),
        'draftChars': len(draft),
        'finalChars': len(final),
        'editRatio': round(1.0 - ratio, 4),
        'structureChanged': _headings(draft) != _headings(final),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Generate a deterministic 5-dimension editorial evaluation report.')
    ap.add_argument('--draft', required=True, help='Path to initial draft Markdown.')
    ap.add_argument('--final', required=True, help='Path to revised final Markdown.')
    ap.add_argument('--assessment', required=True, help='Path to JSON assessment file.')
    ap.add_argument('-o', '--output', help='Optional path to write review-report.json.')
    ap.add_argument('--json', action='store_true', help='Print JSON report to stdout.')
    ap.add_argument('--strict', action='store_true', help='Exit non-zero when publishable is false.')
    args = ap.parse_args(argv)

    try:
        draft = Path(args.draft).expanduser().resolve().read_text(encoding='utf-8')
        final = Path(args.final).expanduser().resolve().read_text(encoding='utf-8')
        assessment = json.loads(Path(args.assessment).expanduser().resolve().read_text(encoding='utf-8'))
        if not isinstance(assessment, dict):
            raise ValueError('assessment file must contain a JSON object.')
        report = build_report(draft, final, assessment)
        rendered = json.dumps(report, indent=2, ensure_ascii=False)
        if args.output:
            out_path = Path(args.output).expanduser().resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered + '\n', encoding='utf-8')
        if args.json or not args.output:
            print(rendered)
        else:
            status = 'PUBLISHABLE' if report['publishable'] else 'NOT_PUBLISHABLE'
            print(f'Editorial eval: {status} (avg={report["dimensionAverage"]}, min={report["dimensionMinimum"]}, editRatio={report["editRatio"]})')
        return 1 if (args.strict and not report['publishable']) else 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
