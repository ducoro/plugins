#!/usr/bin/env python3
"""Deterministic snapshot normalization, objective diffing, and honest no_material_change detection."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

VOLATILE_PATTERNS = [
    re.compile(r'\b20\d{2}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b'),
    re.compile(r'\bnonce=[A-Za-z0-9_-]+\b', re.I),
    re.compile(r'\bcsrf[_-]?token[=:][A-Za-z0-9._-]+\b', re.I),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def normalize_line(line: str) -> str:
    s = re.sub(r'\s+', ' ', line).strip()
    for pat in VOLATILE_PATTERNS:
        s = pat.sub('<TIMESTAMP_OR_NONCE>', s)
    return s


def canonicalize_structured(kind: str, structured: dict) -> dict:
    """Produce a noise-resistant canonical view so cosmetic/timestamp churn never fakes a change."""
    if kind == 'webpage':
        lines = [normalize_line(ln) for ln in structured.get('lines', [])]
        lines = [ln for ln in lines if ln]
        return {'title': normalize_line(str(structured.get('title', ''))), 'lines': lines}
    if kind in {'greenhouse_jobs', 'ashby_jobs', 'lever_jobs'}:
        return {
            'openCount': int(structured.get('openCount', 0)),
            'departments': sorted(set(structured.get('departments', []))),
            'sampleTitles': sorted(set(structured.get('sampleTitles', []))),
        }
    if kind == 'appstore_ios':
        # Ignore volatile single-review jitter unless version/releaseNotes or rating shifts materially
        rating = structured.get('averageUserRating')
        rounded_rating = round(float(rating), 1) if isinstance(rating, (int, float)) else None
        return {
            'trackName': structured.get('trackName', ''),
            'version': structured.get('version', ''),
            'currentVersionReleaseDate': structured.get('currentVersionReleaseDate', ''),
            'averageUserRatingRounded': rounded_rating,
            'releaseNotes': normalize_line(str(structured.get('releaseNotes', ''))),
        }
    if kind == 'github_releases':
        rels = [
            {'tag': r.get('tag', ''), 'name': r.get('name', ''), 'url': r.get('url', '')}
            for r in structured.get('releases', [])
        ]
        return {'repo': structured.get('repo', ''), 'releases': rels}
    if kind == 'sec_edgar':
        filings = [
            {'form': f.get('form', ''), 'filingDate': f.get('filingDate', ''), 'accessionNumber': f.get('accessionNumber', '')}
            for f in structured.get('filings', [])
        ]
        return {'cik': structured.get('cik', ''), 'filings': filings}
    if kind == 'rss':
        entries = [
            {'title': normalize_line(e.get('title', '')), 'url': e.get('url', '')}
            for e in structured.get('entries', [])
        ]
        return {'entries': entries}
    if kind == 'hn_algolia':
        hits = [
            {'title': normalize_line(h.get('title', '')), 'hnUrl': h.get('hnUrl', '')}
            for h in structured.get('hits', [])
        ]
        return {'query': structured.get('query', ''), 'hits': hits}
    return structured


def stable_hash(obj: object) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]


def compute_diff_summary(kind: str, prev: dict, curr: dict) -> dict:
    if kind == 'webpage':
        prev_set = set(prev.get('lines', []))
        curr_set = set(curr.get('lines', []))
        added = [ln for ln in curr.get('lines', []) if ln not in prev_set][:30]
        removed = [ln for ln in prev.get('lines', []) if ln not in curr_set][:30]
        return {'addedLines': added, 'removedLines': removed}
    if kind in {'greenhouse_jobs', 'ashby_jobs', 'lever_jobs'}:
        prev_roles = set(prev.get('sampleTitles', []))
        curr_roles = set(curr.get('sampleTitles', []))
        return {
            'previousOpenCount': prev.get('openCount', 0),
            'currentOpenCount': curr.get('openCount', 0),
            'addedRoles': sorted(curr_roles - prev_roles)[:30],
            'removedRoles': sorted(prev_roles - curr_roles)[:30],
        }
    changed_fields = {}
    for key in sorted(set(prev.keys()) | set(curr.keys())):
        if prev.get(key) != curr.get(key):
            changed_fields[key] = {'before': prev.get(key), 'after': curr.get(key)}
    return {'changedFields': changed_fields}


def diff_capture(workspace: Path, capture: dict, *, update_baselines: bool = True) -> dict:
    workspace = workspace.expanduser().resolve()
    if capture.get('schemaVersion') != 'market-intel-signal/1':
        raise ValueError('Invalid capture schemaVersion; expected market-intel-signal/1')

    seen_path = workspace / 'seen-events.json'
    seen = (
        json.loads(seen_path.read_text(encoding='utf-8'))
        if seen_path.is_file()
        else {'schemaVersion': 'market-intel-seen/1', 'updatedAt': utc_now(), 'fingerprints': {}}
    )
    fingerprints = seen.setdefault('fingerprints', {})

    baselines_created = []
    material_changes = []
    unchanged = []
    skipped_failed = []
    deduped = []

    for rec in capture.get('records', []):
        entity = rec.get('entitySlug', 'unknown')
        source_id = rec.get('sourceId', 'unknown')
        kind = rec.get('kind', 'unknown')
        if not rec.get('ok'):
            skipped_failed.append({'entitySlug': entity, 'sourceId': source_id, 'error': rec.get('error', '')})
            continue

        canonical = canonicalize_structured(kind, rec.get('structured') or {})
        digest = stable_hash(canonical)
        snap_path = workspace / 'snapshots' / entity / f'{source_id}.json'

        if not snap_path.is_file():
            baselines_created.append({
                'entitySlug': entity, 'sourceId': source_id, 'kind': kind,
                'url': rec.get('url', ''), 'digest': digest, 'observedAt': rec.get('observedAt', utc_now()),
            })
            if update_baselines:
                snap_path.parent.mkdir(parents=True, exist_ok=True)
                snap_path.write_text(
                    json.dumps({
                        'entitySlug': entity, 'sourceId': source_id, 'kind': kind,
                        'url': rec.get('url', ''), 'digest': digest,
                        'observedAt': rec.get('observedAt', utc_now()), 'canonical': canonical,
                    }, indent=2, ensure_ascii=False) + '\n',
                    encoding='utf-8',
                )
            continue

        prev_doc = json.loads(snap_path.read_text(encoding='utf-8'))
        prev_digest = prev_doc.get('digest', '')
        if prev_digest == digest:
            unchanged.append({'entitySlug': entity, 'sourceId': source_id, 'digest': digest})
            continue

        change_fp = stable_hash({'entity': entity, 'sourceId': source_id, 'from': prev_digest, 'to': digest})
        diff_detail = compute_diff_summary(kind, prev_doc.get('canonical') or {}, canonical)
        entry = {
            'changeFingerprint': change_fp,
            'entitySlug': entity,
            'sourceId': source_id,
            'kind': kind,
            'url': rec.get('url', ''),
            'observedAt': rec.get('observedAt', utc_now()),
            'previousDigest': prev_digest,
            'currentDigest': digest,
            'diff': diff_detail,
        }
        if change_fp in fingerprints:
            deduped.append(entry)
        else:
            material_changes.append(entry)
            if update_baselines:
                fingerprints[change_fp] = rec.get('observedAt', utc_now())

        if update_baselines:
            snap_path.write_text(
                json.dumps({
                    'entitySlug': entity, 'sourceId': source_id, 'kind': kind,
                    'url': rec.get('url', ''), 'digest': digest,
                    'observedAt': rec.get('observedAt', utc_now()), 'canonical': canonical,
                }, indent=2, ensure_ascii=False) + '\n',
                encoding='utf-8',
            )

    ok_count = len(baselines_created) + len(material_changes) + len(unchanged) + len(deduped)
    failed_count = len(skipped_failed)
    partial_failure = failed_count > 0 and ok_count > 0

    if update_baselines and ok_count > 0:
        seen['updatedAt'] = utc_now()
        seen_path.write_text(json.dumps(seen, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    if failed_count > 0 and ok_count == 0:
        outcome = 'capture_failed'
    elif material_changes:
        outcome = 'material_change'
    elif baselines_created:
        outcome = 'baseline_initialized'
    else:
        outcome = 'no_material_change'

    return {
        'schemaVersion': 'market-intel-diff/1',
        'generatedAt': utc_now(),
        'outcome': outcome,
        'okCount': ok_count,
        'partialFailure': partial_failure,
        'materialChangeCount': len(material_changes),
        'baselineCreatedCount': len(baselines_created),
        'unchangedCount': len(unchanged),
        'dedupedCount': len(deduped),
        'failedCount': failed_count,
        'materialChanges': material_changes,
        'baselinesCreated': baselines_created,
        'unchanged': unchanged,
        'deduped': deduped,
        'failed': skipped_failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Diff a market-intel capture against stored baselines.')
    parser.add_argument('data_dir', metavar='<data-dir>', help='Path to market-intel <data-dir>')
    parser.add_argument('--capture', required=True, help='Path to capture JSON from fetch_sources.py')
    parser.add_argument('--no-update', action='store_true', help='Dry-run diff without updating baseline snapshots')
    parser.add_argument('--out', default=None, help='Optional output JSON path')
    args = parser.parse_args()

    capture = json.loads(Path(args.capture).expanduser().resolve().read_text(encoding='utf-8'))
    result = diff_capture(Path(args.data_dir), capture, update_baselines=not args.no_update)
    text = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding='utf-8')
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
