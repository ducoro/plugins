#!/usr/bin/env python3
"""Grounded evidence gate for market-intel claims: enforces entity isolation, URL/localRef grounding, and quote matching."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.parse

ALLOWED_SEVERITIES = {'high', 'medium', 'low'}
ALLOWED_CATEGORIES = {'pricing', 'release', 'hiring', 'filing', 'outage', 'positioning', 'community', 'discovery'}
TRACKING_PARAMS = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'ref', 'fbclid', 'gclid'}
_URL_KEYS = {'url', 'hnUrl', 'homepage'}
_META_SKIP_KEYS = {'entitySlug', 'sourceId', 'kind', 'ok', 'observedAt', 'error'}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def normalize_text(text: str) -> str:
    return re.sub(r'\s+', ' ', str(text)).strip().lower()


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


def _normalize_local_ref(workspace: Path, raw_ref: str) -> tuple[str | None, Path | None, str | None]:
    ref = str(raw_ref).strip().replace('\\', '/')
    if not ref:
        return None, None, 'localRef must be a non-empty relative path'
    rel_path = Path(ref)
    if rel_path.is_absolute() or '..' in rel_path.parts:
        return None, None, f'localRef must be a relative path inside <data-dir>: {raw_ref!r}'
    resolved = (workspace / rel_path).resolve()
    if not resolved.is_relative_to(workspace):
        return None, None, f'localRef escapes <data-dir>: {raw_ref!r}'
    if not resolved.is_file():
        return None, None, f'localRef file does not exist in <data-dir>: {raw_ref!r}'
    return resolved.relative_to(workspace).as_posix(), resolved, None


def _extract_record_text(rec: dict) -> str:
    tokens: list[str] = []

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in _META_SKIP_KEYS:
                    continue
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
        elif isinstance(obj, bool) or obj is None:
            return
        elif isinstance(obj, (str, int, float)):
            s = str(obj).strip()
            if s:
                tokens.append(s)

    walk(rec)
    return normalize_text(' '.join(tokens))


def _collect_urls_in_obj(obj: object) -> set[str]:
    found: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k in _URL_KEYS and isinstance(v, str):
                    c = canonicalize_url(v)
                    if c:
                        found.add(c)
                else:
                    walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(obj)
    return found


def collect_entity_capture_evidence(capture: dict) -> tuple[dict[str, dict], set[str]]:
    """Index captured URLs, localRefs, source kinds, and normalized text strictly isolated per entitySlug."""
    by_entity: dict[str, dict] = {}
    all_urls: set[str] = set()

    for rec in capture.get('records', []):
        if not isinstance(rec, dict) or not rec.get('ok'):
            continue
        entity = str(rec.get('entitySlug') or '').strip()
        kind = str(rec.get('kind') or 'unknown').strip() or 'unknown'
        if not entity:
            continue
        bucket = by_entity.setdefault(entity, {
            'url_kinds': {},
            'url_texts': {},
            'local_ref_kinds': {},
            'local_ref_texts': {},
        })
        rec_text = _extract_record_text(rec)
        rec_urls = _collect_urls_in_obj(rec)
        for cu in rec_urls:
            all_urls.add(cu)
            bucket['url_kinds'].setdefault(cu, set()).add(kind)
            if rec_text:
                bucket['url_texts'].setdefault(cu, []).append(rec_text)
        raw_local_ref = rec.get('localRef')
        if isinstance(raw_local_ref, str) and raw_local_ref.strip():
            norm_ref = Path(raw_local_ref.strip().replace('\\', '/')).as_posix().lstrip('./')
            bucket['local_ref_kinds'].setdefault(norm_ref, set()).add(kind)
            if rec_text:
                bucket['local_ref_texts'].setdefault(norm_ref, []).append(rec_text)

    return by_entity, all_urls


def collect_capture_url_kinds(capture: dict) -> dict[str, set[str]]:
    """Aggregate URL -> kinds across all records (diagnostic helper; gate_candidates isolates per entity)."""
    by_entity, _ = collect_entity_capture_evidence(capture)
    merged: dict[str, set[str]] = {}
    for bucket in by_entity.values():
        for cu, kinds in bucket['url_kinds'].items():
            merged.setdefault(cu, set()).update(kinds)
    return merged


def collect_capture_urls(capture: dict) -> set[str]:
    return set(collect_capture_url_kinds(capture).keys())


def compute_event_id(entity: str, category: str, summary: str, urls: list[str], local_ref: str = '') -> str:
    payload: dict[str, object] = {
        'entity': entity,
        'category': category,
        'summary': summary.strip().lower(),
        'urls': sorted(urls),
    }
    if local_ref:
        payload['localRef'] = local_ref
    key = json.dumps(payload, sort_keys=True)
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
    known_entities = {
        str(e.get('slug', '')).strip()
        for e in watchlist.get('entities', [])
        if isinstance(e, dict) and str(e.get('slug', '')).strip()
    }
    evidence_by_entity, all_capture_urls = collect_entity_capture_evidence(capture)

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
        raw_local_ref = cand.get('localRef')

        if not known_entities:
            errors.append('Watchlist has no registered entities; register entities in watchlist.json before gating claims')
        elif not entity or entity not in known_entities:
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

        entity_bucket = evidence_by_entity.get(entity, {
            'url_kinds': {},
            'url_texts': {},
            'local_ref_kinds': {},
            'local_ref_texts': {},
        })
        entity_url_kinds: dict[str, set[str]] = entity_bucket['url_kinds']
        entity_url_texts: dict[str, list[str]] = entity_bucket['url_texts']
        entity_local_kinds: dict[str, set[str]] = entity_bucket['local_ref_kinds']
        entity_local_texts: dict[str, list[str]] = entity_bucket['local_ref_texts']

        norm_urls: list[str] = []
        observed_kinds: set[str] = set()
        matched_texts: list[str] = []
        norm_local_ref = ''

        has_urls_input = raw_urls is not None and raw_urls != []
        has_local_ref_input = isinstance(raw_local_ref, str) and bool(raw_local_ref.strip())

        if raw_urls is not None and not isinstance(raw_urls, list):
            errors.append('evidenceUrls must be a list of HTTP(S) URLs')
        elif not has_urls_input and not has_local_ref_input:
            errors.append('At least one verified evidenceUrl or existing localRef is required')

        if isinstance(raw_urls, list):
            for u in raw_urls:
                cu = canonicalize_url(str(u))
                if not cu:
                    errors.append(f'Invalid HTTP(S) evidence URL: {u!r}')
                elif cu in entity_url_kinds:
                    norm_urls.append(cu)
                    observed_kinds.update(entity_url_kinds[cu])
                    matched_texts.extend(entity_url_texts.get(cu, []))
                elif cu in all_capture_urls:
                    errors.append(f'Cross-entity evidence URL belongs to another entity, not {entity!r}: {u!r}')
                else:
                    errors.append(f'Fabricated or uncaptured evidence URL not found in capture pool: {u!r}')

        if raw_local_ref is not None and str(raw_local_ref).strip():
            rel_norm, resolved_file, ref_err = _normalize_local_ref(workspace, str(raw_local_ref))
            if ref_err:
                errors.append(ref_err)
            else:
                assert rel_norm is not None and resolved_file is not None
                norm_local_ref = rel_norm
                observed_kinds.update(entity_local_kinds.get(rel_norm, {'local_doc'}))
                matched_texts.extend(entity_local_texts.get(rel_norm, []))
                try:
                    file_text = resolved_file.read_bytes().decode('utf-8', errors='replace')
                    norm_file_text = normalize_text(file_text)
                    if norm_file_text:
                        matched_texts.append(norm_file_text)
                except OSError as exc:
                    errors.append(f'Unable to read localRef {rel_norm!r}: {exc}')

        if len(quote) >= 5 and matched_texts:
            norm_quote = normalize_text(quote)
            combined_text = ' '.join(matched_texts)
            if not any(norm_quote in t for t in matched_texts) and norm_quote not in combined_text:
                errors.append('Quote excerpt not found in referenced capture records or localRef')

        computed_conf = 'triangulated' if len(observed_kinds) >= 2 else 'single_source'
        if claimed_conf == 'triangulated' and computed_conf != 'triangulated':
            errors.append('Claimed confidence="triangulated" requires >= 2 distinct captured source kinds for this entity')

        if errors:
            rejected.append({'index': idx, 'entitySlug': entity, 'errors': errors})
        else:
            event_id = compute_event_id(entity, category, summary, norm_urls, local_ref=norm_local_ref)
            event_doc = {
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
            }
            if norm_local_ref:
                event_doc['localRef'] = norm_local_ref
            accepted.append(event_doc)

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
    parser.add_argument('data_dir', metavar='<data-dir>', help='Path to market-intel <data-dir>')
    parser.add_argument('--capture', required=True, help='Path to capture JSON')
    parser.add_argument('--candidates', required=True, help='Path to candidate claims JSON array or {"candidates": [...]}')
    parser.add_argument('--commit-events', action='store_true', help='Append verified events idempotently to events.jsonl')
    parser.add_argument('--max-age-hours', type=float, default=24.0)
    args = parser.parse_args()

    capture = json.loads(Path(args.capture).expanduser().resolve().read_text(encoding='utf-8'))
    candidates = json.loads(Path(args.candidates).expanduser().resolve().read_text(encoding='utf-8'))
    if isinstance(candidates, dict) and 'candidates' in candidates:
        candidates = candidates['candidates']
    result = gate_candidates(
        Path(args.data_dir),
        capture,
        candidates,
        commit_events=args.commit_events,
        max_capture_age_hours=args.max_age_hours,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result['rejectedCount'] == 0 else 2


if __name__ == '__main__':
    raise SystemExit(main())
