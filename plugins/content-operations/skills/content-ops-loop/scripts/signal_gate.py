#!/usr/bin/env python3
"""Deterministic provenance, deduplication, hard signal-floor gate, and watchlist state.

Strong models and subagents own semantic judgment (relevance, clustering, best takes, platform angles).
This script enforces hard invariants that must never slip:
  1. ingest: envelope schema/TTL checks, strict http(s) URL + ISO date grounding, canonical URL
     deduplication (keep-richest), window filtering, and incremental seen-URL delta.
  2. gate: verifies every model-proposed topic cites real ingested URLs (blocks hallucinated links),
     enforces multi-source / primary-source / strong-engagement floor (with anti-cheat junkShape
     seed-source rule), and returns explicit `nothing_solid` when nothing clears the bar.
  3. watchlist: lightweight JSON tracking for recurring autonomous scans.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import urllib.parse

ENVELOPE_SCHEMA = 'content-ops-signal-envelope/1'
POOL_SCHEMA = 'content-ops-signal-pool/1'
VALID_REGIONS = {'cn', 'global'}
MAX_ENVELOPE_ITEMS = 1000
SEEN_RETENTION_DAYS = 90
TRACKING_PARAMS = {
    'fbclid', 'gclid', 'dclid', 'msclkid', 'mc_cid', 'mc_eid',
    'ref', 'ref_src', 'ref_url', 'source', 'spm', 'from', 'isappinstalled',
    'share_token', 'si', 'feature', 'ved', 'igsh', 'igshid', '_hsenc', '_hsmi',
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_iso(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if len(raw) == 10 and raw[4] == '-' and raw[7] == '-':
        raw = f'{raw}T00:00:00Z'
    try:
        dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _emit(payload: dict, output: str | None = None) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if output:
        out_path = Path(output).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + '\n', encoding='utf-8')
    print(text)

def _add_sorted(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)
        items.sort()

def canonicalize_url(url: str | None) -> str | None:
    if not url or not isinstance(url, str) or not url.strip():
        return None
    parsed = urllib.parse.urlsplit(url.strip())
    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower() if parsed.hostname else ''
    if scheme not in ('http', 'https') or not parsed.netloc or not host or ('.' not in host and host != 'localhost'):
        return None
    port = parsed.port
    default_port = (scheme == 'http' and port == 80) or (scheme == 'https' and port == 443)
    netloc = host if (port is None or default_port) else f'{host}:{port}'
    path = (parsed.path or '/').rstrip('/') or '/'
    kept = sorted(
        (k, v) for k, v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
        if not k.lower().startswith('utm_') and k.lower() not in TRACKING_PARAMS
    )
    return urllib.parse.urlunsplit((scheme, netloc, path, urllib.parse.urlencode(kept), ''))

def _merge_comments(existing: list[dict], incoming: list[dict]) -> list[dict]:
    by_key: dict[str, dict] = {}
    for c in list(existing or []) + list(incoming or []):
        text = str(c.get('text') or '').strip() if isinstance(c, dict) else ''
        if not text:
            continue
        key, likes = text[:120].lower(), int(c.get('likes') or 0)
        if key not in by_key or likes > int(by_key[key].get('likes') or 0):
            by_key[key] = {'author': str(c.get('author') or '').strip(), 'text': text, 'likes': likes}
    return sorted(by_key.values(), key=lambda c: (-int(c['likes']), c['text']))[:10]

def _normalize_engagement(raw: dict | None, hot: int | float | None = None) -> dict[str, float]:
    eng = raw if isinstance(raw, dict) else {}
    out: dict[str, float] = {}
    for key in ('likes', 'comments', 'shares', 'views', 'score', 'volume24hr'):
        if eng.get(key) is not None:
            try:
                out[key] = float(eng[key])
            except (TypeError, ValueError):
                pass
    if hot is not None and 'score' not in out:
        try:
            out['score'] = float(hot)
        except (TypeError, ValueError):
            pass
    return out

def _load_seen(ws: Path) -> dict[str, str]:
    path = ws / 'inbox' / 'seen-signals.json'
    if not path.is_file():
        return {}
    try:
        seen = json.loads(path.read_text(encoding='utf-8')).get('seen', {})
        return seen if isinstance(seen, dict) else {}
    except (OSError, ValueError):
        return {}

def _save_seen(ws: Path, seen: dict[str, str], now: datetime) -> None:
    cutoff = now - timedelta(days=SEEN_RETENTION_DAYS)
    pruned = {u: ts for u, ts in seen.items() if (parse_iso(ts) is None or parse_iso(ts) >= cutoff)}
    path = ws / 'inbox' / 'seen-signals.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'version': 1, 'updatedAt': iso_utc(now), 'seen': pruned}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def validate_envelope(doc: object, label: str, now: datetime, max_age_hours: float) -> list[str]:
    if not isinstance(doc, dict):
        return [f'{label}: envelope must be a JSON object']
    errs: list[str] = []
    if doc.get('schema') != ENVELOPE_SCHEMA:
        errs.append(f'{label}: invalid schema "{doc.get("schema")}" (expected "{ENVELOPE_SCHEMA}")')
    if doc.get('region') not in VALID_REGIONS:
        errs.append(f'{label}: invalid region "{doc.get("region")}" (expected cn or global)')
    gen = parse_iso(doc.get('generatedAt'))
    if gen is None:
        errs.append(f'{label}: missing or invalid ISO generatedAt')
    else:
        age_h = (now - gen).total_seconds() / 3600.0
        if age_h > max_age_hours:
            errs.append(f'{label}: stale envelope ({age_h:.1f}h old > {max_age_hours:g}h TTL)')
        if age_h < -0.25:
            errs.append(f'{label}: generatedAt is in the future ({doc.get("generatedAt")})')
    items = doc.get('items')
    if not isinstance(items, list):
        errs.append(f'{label}: "items" must be a list')
    elif len(items) > MAX_ENVELOPE_ITEMS:
        errs.append(f'{label}: too many items ({len(items)} > {MAX_ENVELOPE_ITEMS})')
    return errs


def cmd_ingest(args: argparse.Namespace) -> int:
    now = utc_now()
    cutoff = now - timedelta(days=max(1, args.window_days))
    ws = Path(args.workspace).expanduser().resolve() if args.workspace else None
    seen_map = _load_seen(ws) if ws else {}

    envelopes: list[tuple[str, dict]] = []
    envelope_errors: list[str] = []
    for raw_in in args.input:
        if raw_in == '-':
            label, raw_text = '<stdin>', sys.stdin.read()
        else:
            p = Path(raw_in).expanduser().resolve()
            label = str(p)
            if not p.is_file():
                envelope_errors.append(f'{label}: file not found')
                continue
            raw_text = p.read_text(encoding='utf-8')
        try:
            doc = json.loads(raw_text)
        except ValueError as exc:
            envelope_errors.append(f'{label}: invalid JSON ({exc})')
            continue
        errs = validate_envelope(doc, label, now, args.max_age_hours)
        if errs:
            envelope_errors.extend(errs)
        else:
            envelopes.append((label, doc))

    if envelope_errors:
        _emit({'schema': POOL_SCHEMA, 'ok': False, 'errors': envelope_errors})
        return 2

    regions = {doc['region'] for _, doc in envelopes}
    if len(regions) > 1 and not args.allow_mixed_regions:
        _emit({'schema': POOL_SCHEMA, 'ok': False, 'errors': [f'mixed regions in single ingest batch: {sorted(regions)} (keep cn and global isolated or pass --allow-mixed-regions)']})
        return 2

    dropped_reasons: dict[str, int] = {}
    rejected_rows: list[dict] = []
    raw_count = accepted_count = 0
    by_url: dict[str, dict] = {}

    def drop(reason: str, label: str, idx: int, title: str = '') -> None:
        dropped_reasons[reason] = dropped_reasons.get(reason, 0) + 1
        if len(rejected_rows) < 25:
            rejected_rows.append({'envelope': label, 'index': idx, 'reason': reason, 'title': title[:80]})

    for label, env in envelopes:
        env_src = str(env.get('source') or '').strip()
        env_prov = str(env.get('provenance') or 'public_api').strip()
        for idx, row in enumerate(env.get('items', [])):
            raw_count += 1
            if not isinstance(row, dict):
                drop('row_not_object', label, idx)
                continue
            title = str(row.get('title') or '').strip()
            if not title:
                drop('missing_title', label, idx)
                continue
            canon = canonicalize_url(row.get('url'))
            if not canon:
                drop('invalid_url', label, idx, title)
                continue
            pub_dt = parse_iso(row.get('publishedAt'))
            if pub_dt is None:
                drop('invalid_published_at', label, idx, title)
                continue
            if not args.keep_stale and pub_dt < cutoff:
                drop('out_of_window', label, idx, title)
                continue

            accepted_count += 1
            src = str(row.get('source') or env_src or 'unknown').strip().lower()
            prov = str(row.get('provenance') or env_prov or 'public_api').strip().lower()
            is_seed, is_primary = bool(row.get('isSeedListing', True)), bool(row.get('isPrimarySource', False))
            eng = _normalize_engagement(row.get('engagement'), row.get('hot'))
            hot_norm = float(row.get('hotNormalized') or 0.0)
            snippet = str(row.get('snippet') or '').strip()[:1000]
            author = str(row.get('author') or '').strip()
            comments = row.get('topComments') if isinstance(row.get('topComments'), list) else []

            existing = by_url.get(canon)
            if existing is None:
                by_url[canon] = {
                    'canonicalUrl': canon, 'url': str(row.get('url')).strip(), 'title': title,
                    'snippet': snippet, 'author': author, 'publishedAt': iso_utc(pub_dt),
                    'sources': [src], 'seedSources': [src] if is_seed else [], 'provenances': [prov],
                    'isSeedListing': is_seed, 'isPrimarySource': is_primary,
                    'hotNormalized': round(hot_norm, 1), 'engagement': eng,
                    'topComments': _merge_comments([], comments),
                }
            else:
                _add_sorted(existing['sources'], src)
                if is_seed:
                    _add_sorted(existing['seedSources'], src)
                _add_sorted(existing['provenances'], prov)
                existing['isSeedListing'] |= is_seed
                existing['isPrimarySource'] |= is_primary
                existing['hotNormalized'] = round(max(existing['hotNormalized'], hot_norm), 1)
                if len(snippet) > len(existing['snippet']):
                    existing['snippet'] = snippet
                if not existing['author'] and author:
                    existing['author'] = author
                prev_dt = parse_iso(existing['publishedAt'])
                if prev_dt and pub_dt < prev_dt:
                    existing['publishedAt'] = iso_utc(pub_dt)
                for k, v in eng.items():
                    existing['engagement'][k] = max(float(existing['engagement'].get(k, 0.0)), v)
                existing['topComments'] = _merge_comments(existing['topComments'], comments)

    skipped_seen = 0
    items: list[dict] = []
    for canon, item in by_url.items():
        if ws and not args.include_seen and canon in seen_map:
            skipped_seen += 1
            continue
        item['distinctSources'] = len(item['sources'])
        item['seedSourceCount'] = len(item['seedSources'])
        items.append(item)
    items.sort(key=lambda x: (-x['distinctSources'], -x['hotNormalized'], x['title']))

    if ws and args.mark_seen:
        stamp = iso_utc(now)
        for canon in by_url:
            seen_map[canon] = stamp
        _save_seen(ws, seen_map, now)

    region_out = 'mixed' if len(regions) > 1 else (next(iter(regions)) if regions else 'global')
    _emit({
        'schema': POOL_SCHEMA, 'ok': True, 'generatedAt': iso_utc(now),
        'region': region_out, 'windowDays': args.window_days,
        'stats': {
            'envelopesRead': len(envelopes), 'rawItems': raw_count, 'accepted': accepted_count,
            'deduped': len(by_url), 'skippedSeen': skipped_seen, 'deltaCount': len(items),
            'dropped': sum(dropped_reasons.values()), 'droppedReasons': dropped_reasons,
        },
        'rejectedRows': rejected_rows, 'items': items,
    }, args.output)
    return 0


def _has_strong_engagement(items: list[dict], score_floor: float, min_likes: float = 100.0, min_comments: float = 40.0, min_score: float = 150.0, min_volume: float = 50000.0) -> bool:
    for item in items:
        eng = item.get('engagement') or {}
        if (float(item.get('hotNormalized') or 0) >= score_floor or float(eng.get('likes') or 0) >= min_likes
                or float(eng.get('comments') or 0) >= min_comments or float(eng.get('score') or 0) >= min_score
                or float(eng.get('volume24hr') or 0) >= min_volume):
            return True
    return False

def cmd_gate(args: argparse.Namespace) -> int:
    pool_doc = json.loads(Path(args.pool).expanduser().resolve().read_text(encoding='utf-8'))
    if pool_doc.get('schema') != POOL_SCHEMA or not isinstance(pool_doc.get('items'), list):
        _emit({'ok': False, 'error': f'Invalid pool file (expected schema "{POOL_SCHEMA}")'})
        return 2
    pool_by_url = {it['canonicalUrl']: it for it in pool_doc['items'] if isinstance(it, dict) and it.get('canonicalUrl')}
    cand_doc = json.loads(Path(args.candidates).expanduser().resolve().read_text(encoding='utf-8'))
    candidates = cand_doc.get('candidates') if isinstance(cand_doc, dict) else cand_doc
    if not isinstance(candidates, list):
        _emit({'ok': False, 'error': 'Candidates JSON must be a list or {"candidates": [...]}'})
        return 2
    passed, rejected, provenance_violations = [], [], 0
    for idx, cand in enumerate(candidates):
        if not isinstance(cand, dict):
            rejected.append({'index': idx, 'title': '', 'reasons': ['candidate_not_object']})
            continue
        title, raw_urls, reasons = str(cand.get('title') or '').strip(), cand.get('evidenceUrls') or [], []
        if not title:
            reasons.append('missing_title')
        if not isinstance(raw_urls, list) or not raw_urls:
            reasons.append('missing_evidence_urls')
            provenance_violations += 1
        matched, ungrounded = [], []
        for u in (raw_urls if isinstance(raw_urls, list) else []):
            canon = canonicalize_url(u)
            (matched.append(pool_by_url[canon]) if (canon and canon in pool_by_url) else ungrounded.append(str(u)))
        if ungrounded:
            provenance_violations += 1
            reasons.append(f'ungrounded_urls: {", ".join(ungrounded)}')
        all_sources = {s for mi in matched for s in (mi.get('sources') or [])}
        seed_sources = {s for mi in matched for s in (mi.get('seedSources') or [])}
        max_norm = max((float(mi.get('hotNormalized') or 0.0) for mi in matched), default=0.0)
        primary = bool(cand.get('isPrimarySource', False)) or any(mi.get('isPrimarySource') for mi in matched)
        junk_shape = bool(cand.get('junkShape', False))
        strong_eng = _has_strong_engagement(matched, args.single_source_floor, args.min_likes, args.min_comments, args.min_score, args.min_volume)
        if not reasons:
            if junk_shape:
                if len(seed_sources) < 2:
                    reasons.append('junk_shape_requires_multi_seed_sources')
            elif not (len(all_sources) >= 2 or primary or strong_eng):
                reasons.append(f'below_signal_floor (distinctSources={len(all_sources)}, primary={primary}, maxHotNormalized={max_norm:.1f})')
        enriched = dict(cand)
        enriched['verifiedMetrics'] = {
            'distinctSources': len(all_sources), 'sources': sorted(all_sources),
            'seedSourceCount': len(seed_sources), 'seedSources': sorted(seed_sources),
            'isPrimarySource': primary, 'maxHotNormalized': round(max_norm, 1),
            'strongEngagement': strong_eng, 'junkShape': junk_shape,
        }
        if reasons:
            enriched['rejectionReasons'] = reasons
            rejected.append(enriched)
        else:
            passed.append(enriched)
    weak_signal = None
    if not passed:
        grounded = [r for r in rejected if not any(m.startswith('ungrounded_urls') or m == 'missing_evidence_urls' for m in r.get('rejectionReasons', []))]
        if grounded:
            grounded.sort(key=lambda r: (-r['verifiedMetrics']['distinctSources'], -r['verifiedMetrics']['maxHotNormalized']))
            top = grounded[0]
            weak_signal = {'title': top.get('title'), 'verifiedMetrics': top['verifiedMetrics'], 'rejectionReasons': top['rejectionReasons']}
    _emit({
        'ok': provenance_violations == 0, 'outcome': 'solid' if passed else 'nothing_solid',
        'region': pool_doc.get('region'),
        'counts': {'submitted': len(candidates), 'passed': len(passed), 'rejected': len(rejected), 'provenanceViolations': provenance_violations},
        'passed': passed, 'rejected': rejected, 'weakSignal': weak_signal,
    }, args.output)
    return 2 if (args.strict and provenance_violations > 0) else 0


def cmd_watchlist(args: argparse.Namespace) -> int:
    path = Path(args.workspace).expanduser().resolve() / 'watchlist.json'
    doc = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'version': 1, 'tracks': []}
    tracks: list[dict] = doc.setdefault('tracks', [])

    def save() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    if args.wl_action == 'list':
        _emit(doc)
        return 0
    if args.wl_action == 'add':
        now_str = iso_utc(utc_now())
        entry = {
            'id': args.id.strip(), 'query': args.query.strip(), 'region': args.region,
            'cadence': args.cadence, 'platforms': [p.strip() for p in (args.platforms or '').split(',') if p.strip()],
            'notes': (args.notes or '').strip(), 'enabled': True, 'createdAt': now_str,
            'lastRunAt': None, 'lastOutcome': None, 'lastNewSignals': 0,
        }
        updated = False
        for i, t in enumerate(tracks):
            if t.get('id') == entry['id']:
                for keep in ('createdAt', 'lastRunAt', 'lastOutcome', 'lastNewSignals'):
                    entry[keep] = t.get(keep, entry[keep])
                tracks[i], updated = entry, True
                break
        if not updated:
            tracks.append(entry)
        save()
        _emit({'ok': True, 'action': 'updated' if updated else 'added', 'track': entry})
        return 0
    if args.wl_action == 'remove':
        before = len(tracks)
        doc['tracks'] = [t for t in tracks if t.get('id') != args.id]
        if len(doc['tracks']) == before:
            _emit({'ok': False, 'error': f'Track "{args.id}" not found'})
            return 1
        save()
        _emit({'ok': True, 'removed': args.id})
        return 0
    if args.wl_action == 'mark-run':
        for t in tracks:
            if t.get('id') == args.id:
                t['lastRunAt'], t['lastNewSignals'], t['lastOutcome'] = iso_utc(utc_now()), args.new_signals, args.outcome
                save()
                _emit({'ok': True, 'track': t})
                return 0
        _emit({'ok': False, 'error': f'Track "{args.id}" not found'})
        return 1
    if args.wl_action == 'due':
        now = utc_now()
        due = [
            t for t in tracks
            if t.get('enabled', True)
            and (parse_iso(t.get('lastRunAt')) is None or (now - parse_iso(t.get('lastRunAt'))) >= timedelta(days=7 if t.get('cadence') == 'weekly' else 1))
        ]
        _emit({'dueCount': len(due), 'tracks': due})
        return 0
    return 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description='Hard provenance, dedupe, signal-floor gate, and watchlist state.')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_ing = sub.add_parser('ingest', help='Validate envelopes, normalize URLs, dedupe (keep-richest), and compute delta.')
    p_ing.add_argument('--input', action='append', required=True, help='Envelope JSON file path (repeatable; "-" for stdin).')
    p_ing.add_argument('--workspace', help='Optional content-ops workspace for seen-signals.json delta filtering.')
    p_ing.add_argument('--window-days', type=int, default=30, help='Max signal age in days (default 30).')
    p_ing.add_argument('--max-age-hours', type=float, default=6.0, help='Max envelope TTL in hours (default 6).')
    p_ing.add_argument('--keep-stale', action='store_true', help='Keep items older than --window-days.')
    p_ing.add_argument('--include-seen', action='store_true', help='Include URLs already in inbox/seen-signals.json.')
    p_ing.add_argument('--mark-seen', action='store_true', help='Persist accepted URLs into inbox/seen-signals.json.')
    p_ing.add_argument('--allow-mixed-regions', action='store_true', help='Allow combining cn and global envelopes for cross-border creators.')
    p_ing.add_argument('--output', help='Optional output JSON path for signal pool.')
    p_ing.set_defaults(func=cmd_ingest)

    p_gate = sub.add_parser('gate', help='Verify model-proposed candidates against pool and hard signal floor.')
    p_gate.add_argument('--pool', required=True, help='Signal pool JSON produced by `ingest`.')
    p_gate.add_argument('--candidates', required=True, help='Model-curated candidates JSON.')
    p_gate.add_argument('--single-source-floor', type=float, default=80.0, help='Min hotNormalized for single-source pass (default 80).')
    p_gate.add_argument('--min-likes', type=float, default=100.0, help='Strong-engagement likes threshold (default 100).')
    p_gate.add_argument('--min-comments', type=float, default=40.0, help='Strong-engagement comments threshold (default 40).')
    p_gate.add_argument('--min-score', type=float, default=150.0, help='Strong-engagement score threshold (default 150).')
    p_gate.add_argument('--min-volume', type=float, default=50000.0, help='Strong-engagement 24h volume threshold (default 50000).')
    p_gate.add_argument('--strict', action='store_true', help='Exit 2 if any candidate cites an ungrounded URL.')
    p_gate.add_argument('--output', help='Optional output JSON path for gate report.')
    p_gate.set_defaults(func=cmd_gate)

    p_wl = sub.add_parser('watchlist', help='Manage lightweight watchlist.json for scheduled recurring radar scans.')
    p_wl.add_argument('workspace', help='Path to the content-ops workspace.')
    wl_sub = p_wl.add_subparsers(dest='wl_action', required=True)
    wl_sub.add_parser('list', help='List all watchlist tracks.')
    wl_sub.add_parser('due', help='List enabled tracks due for their next scan.')
    p_add = wl_sub.add_parser('add', help='Add or update a watchlist track.')
    p_add.add_argument('--id', required=True, help='Kebab-case track ID.')
    p_add.add_argument('--query', required=True, help='Topic, competitor, or entity to monitor.')
    p_add.add_argument('--region', choices=('cn', 'global'), required=True, help='Market region (cn or global).')
    p_add.add_argument('--cadence', choices=('daily', 'weekly'), default='daily', help='Scan cadence.')
    p_add.add_argument('--platforms', default='', help='Comma-separated target platform slugs.')
    p_add.add_argument('--notes', default='', help='Optional operator notes.')
    p_rm = wl_sub.add_parser('remove', help='Remove a track by ID.')
    p_rm.add_argument('--id', required=True, help='Track ID to remove.')
    p_mr = wl_sub.add_parser('mark-run', help='Record completion of a scheduled scan.')
    p_mr.add_argument('--id', required=True, help='Track ID.')
    p_mr.add_argument('--new-signals', type=int, default=0, help='Count of net-new delta signals found.')
    p_mr.add_argument('--outcome', choices=('solid', 'nothing_solid'), default='solid', help='Gate outcome.')
    p_wl.set_defaults(func=cmd_watchlist)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
