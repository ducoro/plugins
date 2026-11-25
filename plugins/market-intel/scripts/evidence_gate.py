#!/usr/bin/env python3
"""Grounded evidence gate for market-intel claims: rejects fabricated URLs, missing timestamps, or empty quotes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import urllib.parse

ALLOWED_SEVERITIES = {'high', 'medium', 'low'}
ALLOWED_CATEGORIES = {'pricing', 'release', 'hiring', 'filing', 'outage', 'positioning', 'community'}
TRACKING_PARAMS = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'ref', 'fbclid', 'gclid'}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def canonicalize_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        return ''
    qs = [
        (k, v)
        for k, v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
        if k.lower() not in TRACKING_PARAMS
    ]
    qs.sort()
    path = parsed.path.rstrip('/') or '/'
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, urllib.parse.urlencode(qs), ''))


def is_valid_iso_timestamp(value: str) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        dt = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
        return dt.tzinfo is not None
    except ValueError:
        return False


def collect_capture_url_kinds(capture: dict) -> dict[str, set[str]]:
    url_kinds: dict[str, set[str]] = {}

    def walk(obj: object, kind: str) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in {'url', 'hnUrl', 'homepage'} and isinstance(v, str):
                    c = canonicalize_url(v)
                    if c:
                        url_kinds.setdefault(c, set()).add(kind)
                else:
                    walk(v, kind)
        elif isinstance(obj, list):
            for item in obj:
                walk(item, kind)

    for rec in capture.get('records', []):
        if rec.get('ok'):
            walk(rec, str(rec.get('kind') or 'unknown'))
    return url_kinds


def collect_capture_urls(capture: dict) -> set[str]:
    return set(collect_capture_url_kinds(capture).keys())


def compute_event_id(entity: str, category: str, summary: str, urls: list[str]) -> str:
    key = json.dumps({'entity': entity, 'category': category, 'summary': summary.strip().lower(), 'urls': sorted(urls)}, sort_keys=True)
    return hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]


def gate_candidates(
    workspace: Path,
    capture: dict,
    candidates: list[dict],
    *,
    commit_events: bool = False,
    max_capture_age_hours: float = 24.0,
) -> dict:
    workspace = workspace.expanduser().resolve()
    if capture.get('schemaVersion') != 'market-intel-signal/1':
        raise ValueError('Invalid capture schemaVersion; expected market-intel-signal/1')
    gen_at = capture.get('generatedAt', '')
    if not is_valid_iso_timestamp(gen_at):
        raise ValueError('Capture generatedAt is missing or not a timezone-aware ISO timestamp')
    age_hours = (datetime.now(timezone.utc) - datetime.fromisoformat(gen_at.replace('Z', '+00:00'))).total_seconds() / 3600.0
    if age_hours > max_capture_age_hours:
        raise ValueError(f'Capture is stale ({age_hours:.1f}h > {max_capture_age_hours}h); refresh sources first')

    watchlist_path = workspace / 'watchlist.json'
    watchlist = json.loads(watchlist_path.read_text(encoding='utf-8')) if watchlist_path.is_file() else {'entities': []}
    known_entities = {e['slug'] for e in watchlist.get('entities', [])}
    url_kinds_map = collect_capture_url_kinds(capture)
    valid_urls = set(url_kinds_map.keys())

    accepted = []
    rejected = []

    for idx, cand in enumerate(candidates):
        errors = []
        entity = str(cand.get('entitySlug', '')).strip()
        severity = str(cand.get('severity', '')).strip().lower()
        category = str(cand.get('category', '')).strip().lower()
        summary = str(cand.get('summary', '')).strip()
        quote = str(cand.get('quote', '')).strip()
        observed_at = str(cand.get('observedAt', '')).strip()
        claimed_conf = str(cand.get('confidence', '')).strip().lower()
        raw_urls = cand.get('evidenceUrls')

        if not entity or (known_entities and entity not in known_entities):
            errors.append(f'Unknown or empty entitySlug: {entity!r}')
        if severity not in ALLOWED_SEVERITIES:
            errors.append(f'Invalid severity: {severity!r}')
        if category not in ALLOWED_CATEGORIES:
            errors.append(f'Invalid category: {category!r}')
        if len(summary) < 8:
            errors.append('Summary must be at least 8 characters')
        if len(quote) < 5:
            errors.append('Verbatim quote excerpt is required (>= 5 chars)')
        if not is_valid_iso_timestamp(observed_at):
            errors.append('observedAt must be a timezone-aware ISO-8601 timestamp')

        norm_urls = []
        observed_kinds: set[str] = set()
        if not isinstance(raw_urls, list) or not raw_urls:
            errors.append('evidenceUrls must be a non-empty list')
        else:
            for u in raw_urls:
                cu = canonicalize_url(str(u))
                if not cu:
                    errors.append(f'Invalid HTTP(S) evidence URL: {u!r}')
                elif cu not in valid_urls:
                    errors.append(f'Fabricated or uncaptured evidence URL not found in capture pool: {u!r}')
                else:
                    norm_urls.append(cu)
                    observed_kinds.update(url_kinds_map.get(cu, set()))

        computed_conf = 'triangulated' if len(observed_kinds) >= 2 else 'single_source'
        if claimed_conf == 'triangulated' and computed_conf != 'triangulated':
            errors.append('Claimed confidence="triangulated" requires >= 2 distinct captured source kinds')

        if errors:
            rejected.append({'index': idx, 'entitySlug': entity, 'errors': errors})
        else:
            event_id = compute_event_id(entity, category, summary, norm_urls)
            accepted.append({
                'eventId': event_id,
                'entitySlug': entity,
                'severity': severity,
                'category': category,
                'confidence': computed_conf,
                'sourceKinds': sorted(observed_kinds),
                'summary': summary,
                'evidenceUrls': sorted(set(norm_urls)),
                'observedAt': observed_at,
                'quote': quote,
                'verifiedAt': utc_now(),
            })

    committed = 0
    if commit_events and accepted:
        events_path = workspace / 'events.jsonl'
        existing_ids = set()
        if events_path.is_file():
            for line in events_path.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    existing_ids.add(json.loads(line).get('eventId'))
                except json.JSONDecodeError:
                    continue
        with events_path.open('a', encoding='utf-8') as fh:
            for ev in accepted:
                if ev['eventId'] not in existing_ids:
                    fh.write(json.dumps(ev, ensure_ascii=False) + '\n')
                    existing_ids.add(ev['eventId'])
                    committed += 1

    outcome = 'verified_events' if accepted else 'no_verified_events'
    return {
        'schemaVersion': 'market-intel-gate/1',
        'outcome': outcome,
        'acceptedCount': len(accepted),
        'rejectedCount': len(rejected),
        'committedCount': committed,
        'accepted': accepted,
        'rejected': rejected,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Verify candidate market-intel claims against captured evidence.')
    parser.add_argument('workspace', help='Path to market-intel workspace')
    parser.add_argument('--capture', required=True, help='Path to capture JSON')
    parser.add_argument('--candidates', required=True, help='Path to candidate claims JSON array')
    parser.add_argument('--commit-events', action='store_true', help='Append verified events idempotently to events.jsonl')
    parser.add_argument('--max-age-hours', type=float, default=24.0)
    args = parser.parse_args()

    capture = json.loads(Path(args.capture).expanduser().resolve().read_text(encoding='utf-8'))
    candidates = json.loads(Path(args.candidates).expanduser().resolve().read_text(encoding='utf-8'))
    if isinstance(candidates, dict) and 'candidates' in candidates:
        candidates = candidates['candidates']
    result = gate_candidates(
        Path(args.workspace),
        capture,
        candidates,
        commit_events=args.commit_events,
        max_capture_age_hours=args.max_age_hours,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result['rejectedCount'] == 0 else 2


if __name__ == '__main__':
    raise SystemExit(main())
