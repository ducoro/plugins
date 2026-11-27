#!/usr/bin/env python3
"""Deterministic snapshot normalization, semantic change classification, and honest no_material_change detection."""
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
    """Produce a noise-resistant canonical view so cosmetic/timestamp/engagement churn never fakes a change."""
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
    if kind == 'github_repo_activity':
        commits = [
            {'sha': c.get('sha', ''), 'message': normalize_line(c.get('message', '')), 'author': c.get('author', '')}
            for c in structured.get('commits', [])
        ]
        issues = [
            {
                'number': int(i.get('number', 0)),
                'title': normalize_line(i.get('title', '')),
                'state': i.get('state', ''),
                'author': i.get('author', ''),
                'authorAssociation': i.get('authorAssociation', ''),
                'labels': sorted(set(i.get('labels', []))),
            }
            for i in structured.get('issues', [])
        ]
        prs = [
            {
                'number': int(p.get('number', 0)),
                'title': normalize_line(p.get('title', '')),
                'state': p.get('state', ''),
                'author': p.get('author', ''),
                'authorAssociation': p.get('authorAssociation', ''),
            }
            for p in structured.get('prs', [])
        ]
        return {'repo': structured.get('repo', ''), 'commits': commits, 'issues': issues, 'prs': prs}
    if kind == 'github_file':
        lines = [normalize_line(ln) for ln in structured.get('lines', []) if normalize_line(ln)]
        return {
            'repo': structured.get('repo', ''),
            'path': structured.get('path', ''),
            'ref': structured.get('ref', 'default'),
            'blobSha': structured.get('blobSha', ''),
            'lines': lines,
        }
    if kind == 'github_trending':
        entries = [
            {'rank': int(e.get('rank', idx + 1)), 'repo': e.get('repo', ''), 'language': e.get('language', '')}
            for idx, e in enumerate(structured.get('entries', []))
        ]
        return {'since': structured.get('since', 'daily'), 'language': structured.get('language', ''), 'entries': entries}
    if kind == 'producthunt':
        posts = [
            {
                'name': normalize_line(p.get('name', '')),
                'url': p.get('url', ''),
                'tagline': normalize_line(p.get('tagline', '')),
            }
            for p in structured.get('posts', [])
        ]
        return {'mode': structured.get('mode', 'rss'), 'posts': posts}
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


def extract_signals(kind: str, structured: dict) -> dict:
    """Extract non-content signals (discussion counts, engagement counters, ordered keys) for changeKind classification."""
    discussions: dict[str, int] = {}
    engagement: dict[str, int | float] = {}
    ordered_keys: list[str] = []

    if kind == 'hn_algolia':
        for h in structured.get('hits', []):
            key = str(h.get('hnUrl') or h.get('url') or h.get('title') or '')
            if key:
                ordered_keys.append(key)
                discussions[key] = int(h.get('comments', 0) or 0)
                engagement[key] = int(h.get('points', 0) or 0)
    elif kind == 'github_repo_activity':
        for c in structured.get('commits', []):
            if c.get('sha'):
                ordered_keys.append(f'commit:{c["sha"]}')
        for i in structured.get('issues', []):
            k = f'issue:{i.get("number")}'
            discussions[k] = int(i.get('comments', 0) or 0)
        for p in structured.get('prs', []):
            k = f'pr:{p.get("number")}'
            discussions[k] = int(p.get('comments', 0) or 0)
    elif kind == 'github_trending':
        for e in structured.get('entries', []):
            repo = str(e.get('repo', ''))
            if repo:
                ordered_keys.append(repo)
                if e.get('stars') is not None:
                    engagement[f'{repo}:stars'] = int(e['stars'])
                if e.get('periodStars') is not None:
                    engagement[f'{repo}:period'] = int(e['periodStars'])
    elif kind == 'producthunt':
        for p in structured.get('posts', []):
            key = str(p.get('url') or p.get('name') or '')
            if key:
                ordered_keys.append(key)
                if 'commentsCount' in p:
                    discussions[f'{key}:comments'] = int(p.get('commentsCount', 0) or 0)
                if 'reviewsCount' in p:
                    discussions[f'{key}:reviews'] = int(p.get('reviewsCount', 0) or 0)
                if 'votesCount' in p:
                    engagement[key] = int(p.get('votesCount', 0) or 0)
    elif kind == 'rss':
        for e in structured.get('entries', []):
            key = str(e.get('url') or e.get('title') or '')
            if key:
                ordered_keys.append(key)
    elif kind == 'github_releases':
        for r in structured.get('releases', []):
            key = str(r.get('tag') or r.get('url') or '')
            if key:
                ordered_keys.append(key)
    elif kind == 'appstore_ios':
        if structured.get('userRatingCount') is not None:
            engagement['userRatingCount'] = int(structured['userRatingCount'])

    return {'discussions': discussions, 'engagement': engagement, 'orderedKeys': ordered_keys}


def _is_trailing_coverage_expansion(kind: str, prev_canonical: dict, curr_canonical: dict) -> bool:
    """Detect when a wider fetch limit only reveals older trailing items while the prior prefix is unchanged."""
    list_key_map = {
        'hn_algolia': 'hits',
        'rss': 'entries',
        'github_releases': 'releases',
        'producthunt': 'posts',
        'sec_edgar': 'filings',
    }
    list_key = list_key_map.get(kind)
    if not list_key:
        return False
    prev_list = prev_canonical.get(list_key)
    curr_list = curr_canonical.get(list_key)
    if not isinstance(prev_list, list) or not isinstance(curr_list, list):
        return False
    if not prev_list or len(curr_list) <= len(prev_list):
        return False
    # All non-list metadata fields must remain identical
    for k in set(prev_canonical.keys()) | set(curr_canonical.keys()):
        if k == list_key:
            continue
        if prev_canonical.get(k) != curr_canonical.get(k):
            return False
    return curr_list[:len(prev_list)] == prev_list


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
    if kind == 'github_repo_activity':
        prev_commits = {c.get('sha'): c for c in prev.get('commits', []) if c.get('sha')}
        added_commits = [c for c in curr.get('commits', []) if c.get('sha') not in prev_commits][:20]
        prev_issues = {i.get('number'): i for i in prev.get('issues', [])}
        added_issues = [i for i in curr.get('issues', []) if i.get('number') not in prev_issues][:20]
        updated_issues = [
            {'number': i['number'], 'before': prev_issues[i['number']], 'after': i}
            for i in curr.get('issues', [])
            if i.get('number') in prev_issues and prev_issues[i['number']] != i
        ][:20]
        prev_prs = {p.get('number'): p for p in prev.get('prs', [])}
        added_prs = [p for p in curr.get('prs', []) if p.get('number') not in prev_prs][:20]
        updated_prs = [
            {'number': p['number'], 'before': prev_prs[p['number']], 'after': p}
            for p in curr.get('prs', [])
            if p.get('number') in prev_prs and prev_prs[p['number']] != p
        ][:20]
        return {
            'addedCommits': added_commits,
            'addedIssues': added_issues,
            'updatedIssues': updated_issues,
            'addedPrs': added_prs,
            'updatedPrs': updated_prs,
        }
    if kind == 'github_file':
        prev_set = set(prev.get('lines', []))
        curr_set = set(curr.get('lines', []))
        return {
            'path': curr.get('path', ''),
            'previousSha': prev.get('blobSha', ''),
            'currentSha': curr.get('blobSha', ''),
            'addedLines': [ln for ln in curr.get('lines', []) if ln not in prev_set][:30],
            'removedLines': [ln for ln in prev.get('lines', []) if ln not in curr_set][:30],
        }
    if kind == 'github_trending':
        prev_ranks = {e['repo']: e['rank'] for e in prev.get('entries', []) if e.get('repo')}
        curr_ranks = {e['repo']: e['rank'] for e in curr.get('entries', []) if e.get('repo')}
        entered = [e['repo'] for e in curr.get('entries', []) if e.get('repo') and e['repo'] not in prev_ranks]
        dropped = [e['repo'] for e in prev.get('entries', []) if e.get('repo') and e['repo'] not in curr_ranks]
        rank_moves = [
            {
                'repo': repo,
                'previousRank': prev_ranks[repo],
                'currentRank': curr_ranks[repo],
                'delta': prev_ranks[repo] - curr_ranks[repo],
            }
            for repo in curr_ranks
            if repo in prev_ranks and prev_ranks[repo] != curr_ranks[repo]
        ]
        return {'entered': entered, 'dropped': dropped, 'rankMoves': rank_moves}
    if kind == 'producthunt':
        prev_urls = {p.get('url') or p.get('name') for p in prev.get('posts', [])}
        curr_urls = {p.get('url') or p.get('name') for p in curr.get('posts', [])}
        return {
            'addedPosts': [p for p in curr.get('posts', []) if (p.get('url') or p.get('name')) not in prev_urls][:20],
            'removedPosts': [p for p in prev.get('posts', []) if (p.get('url') or p.get('name')) not in curr_urls][:20],
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
    discussion_updates = []
    engagement_only = []
    coverage_expanded = []
    unchanged = []
    skipped_failed = []
    deduped = []

    for rec in capture.get('records', []):
        entity = rec.get('entitySlug', 'unknown')
        source_id = rec.get('sourceId', 'unknown')
        kind = rec.get('kind', 'unknown')
        if not rec.get('ok'):
            fail_entry = {'entitySlug': entity, 'sourceId': source_id, 'error': rec.get('error', '')}
            if rec.get('errorKind'):
                fail_entry['errorKind'] = rec['errorKind']
            if rec.get('httpStatus') is not None:
                fail_entry['httpStatus'] = rec['httpStatus']
            skipped_failed.append(fail_entry)
            continue

        structured = rec.get('structured') or {}
        canonical = canonicalize_structured(kind, structured)
        signals = extract_signals(kind, structured)
        digest = stable_hash(canonical)
        snap_path = workspace / 'snapshots' / entity / f'{source_id}.json'

        def _write_snapshot() -> None:
            snap_path.parent.mkdir(parents=True, exist_ok=True)
            snap_path.write_text(
                json.dumps({
                    'entitySlug': entity, 'sourceId': source_id, 'kind': kind,
                    'url': rec.get('url', ''), 'digest': digest,
                    'observedAt': rec.get('observedAt', utc_now()),
                    'canonical': canonical, 'signals': signals,
                }, indent=2, ensure_ascii=False) + '\n',
                encoding='utf-8',
            )

        if not snap_path.is_file():
            baselines_created.append({
                'entitySlug': entity, 'sourceId': source_id, 'kind': kind,
                'url': rec.get('url', ''), 'digest': digest, 'observedAt': rec.get('observedAt', utc_now()),
            })
            if update_baselines:
                _write_snapshot()
            continue

        prev_doc = json.loads(snap_path.read_text(encoding='utf-8'))
        prev_digest = prev_doc.get('digest', '')
        prev_canonical = prev_doc.get('canonical') or {}
        prev_signals = prev_doc.get('signals') or {}

        if prev_digest == digest:
            prev_disc = prev_signals.get('discussions') or {}
            curr_disc = signals.get('discussions') or {}
            disc_growth = {
                k: {'before': prev_disc[k], 'after': curr_disc[k]}
                for k in curr_disc
                if k in prev_disc and curr_disc[k] > prev_disc[k]
            }
            prev_eng = prev_signals.get('engagement') or {}
            curr_eng = signals.get('engagement') or {}
            eng_delta = {
                k: {'before': prev_eng[k], 'after': curr_eng[k]}
                for k in curr_eng
                if k in prev_eng and curr_eng[k] != prev_eng[k]
            }
            if disc_growth:
                discussion_updates.append({
                    'entitySlug': entity, 'sourceId': source_id, 'kind': kind,
                    'changeKind': 'discussion_active', 'url': rec.get('url', ''),
                    'observedAt': rec.get('observedAt', utc_now()),
                    'discussionGrowth': disc_growth,
                })
                if update_baselines:
                    _write_snapshot()
            elif eng_delta:
                engagement_only.append({
                    'entitySlug': entity, 'sourceId': source_id, 'kind': kind,
                    'changeKind': 'engagement_only', 'digest': digest,
                    'engagementDelta': eng_delta,
                })
                if update_baselines:
                    _write_snapshot()
            else:
                unchanged.append({'entitySlug': entity, 'sourceId': source_id, 'digest': digest})
            continue

        if _is_trailing_coverage_expansion(kind, prev_canonical, canonical):
            coverage_expanded.append({
                'entitySlug': entity, 'sourceId': source_id, 'kind': kind,
                'changeKind': 'coverage_expanded', 'url': rec.get('url', ''),
                'observedAt': rec.get('observedAt', utc_now()),
                'previousDigest': prev_digest, 'currentDigest': digest,
            })
            if update_baselines:
                _write_snapshot()
            continue

        change_fp = stable_hash({'entity': entity, 'sourceId': source_id, 'from': prev_digest, 'to': digest})
        diff_detail = compute_diff_summary(kind, prev_canonical, canonical)
        entry = {
            'changeFingerprint': change_fp,
            'changeKind': 'content_changed',
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
            _write_snapshot()

    ok_count = (
        len(baselines_created) + len(material_changes) + len(discussion_updates)
        + len(engagement_only) + len(coverage_expanded) + len(unchanged) + len(deduped)
    )
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
        'discussionUpdateCount': len(discussion_updates),
        'engagementOnlyCount': len(engagement_only),
        'coverageExpandedCount': len(coverage_expanded),
        'baselineCreatedCount': len(baselines_created),
        'unchangedCount': len(unchanged),
        'dedupedCount': len(deduped),
        'failedCount': failed_count,
        'materialChanges': material_changes,
        'discussionUpdates': discussion_updates,
        'engagementOnly': engagement_only,
        'coverageExpanded': coverage_expanded,
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
