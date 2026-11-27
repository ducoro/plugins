"""Unit, local HTTP roundtrip, and Class-A/B formal verification tests for market-intel."""
from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import itertools
import json
from pathlib import Path
import ssl
import tempfile
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / 'plugins/market-intel'
SCRIPTS = PLUGIN_ROOT / 'scripts'


def load_mod(name: str):
    spec = importlib.util.spec_from_file_location(f'mi_{name}', SCRIPTS / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


init_workspace = load_mod('init_workspace')
fetch_sources = load_mod('fetch_sources')
snapshot_diff = load_mod('snapshot_diff')
evidence_gate = load_mod('evidence_gate')
build_boards = load_mod('build_boards')


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


class _MockIntelHandler(BaseHTTPRequestHandler):
    routes: dict[str, tuple[int, str, str]] = {}

    def do_GET(self):
        status, ctype, body = self.routes.get(self.path, (404, 'text/plain', 'not found'))
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.end_headers()
        self.wfile.write(body.encode('utf-8'))

    def log_message(self, format, *args):
        return


class MarketIntelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name) / 'market-intel'
        init_workspace.init_workspace(self.ws)

    def test_init_workspace_does_not_create_boards_dir(self):
        self.assertFalse((self.ws / 'boards').exists())
        for expected in ('captures', 'snapshots', 'entities', 'battlecards', 'briefs'):
            self.assertTrue((self.ws / expected).is_dir())
        self.assertTrue((self.ws / 'watchlist.json').is_file())
        self.assertTrue((self.ws / 'seen-events.json').is_file())
        self.assertTrue((self.ws / 'events.jsonl').is_file())

    def test_http_roundtrip_all_keyless_adapters_and_board_projection(self):
        routes = {
            '/pricing': (200, 'text/html', '<html><head><title>Acme Pricing</title><script>var nonce=abc123;</script></head><body><h1>Pro Plan</h1><p>$29/mo</p><p>Updated 2026-11-25T10:00:00Z</p></body></html>'),
            '/feed.xml': (200, 'application/atom+xml', '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><title>v2 Launch</title><link href="https://acme.example/blog/v2"/><updated>2026-11-25T09:00:00Z</updated></entry></feed>'),
            '/gh': (200, 'application/json', json.dumps([{'tag_name': 'v2.1.0', 'name': 'Release 2.1', 'published_at': '2026-11-25T08:00:00Z', 'html_url': 'https://github.com/acme/cli/releases/tag/v2.1.0', 'body': 'Fast sync'}])),
            '/itunes': (200, 'application/json', json.dumps({'resultCount': 1, 'results': [{'trackName': 'Acme iOS', 'version': '4.2.0', 'currentVersionReleaseDate': '2026-11-24T00:00:00Z', 'averageUserRating': 4.62, 'userRatingCount': 1200, 'trackViewUrl': 'https://apps.apple.com/us/app/acme/id123', 'releaseNotes': 'Bug fixes'}]})),
            '/npm': (200, 'application/json', json.dumps({'version': '3.0.1', 'description': 'Acme SDK', 'homepage': 'https://acme.example'})),
            '/pypi': (200, 'application/json', json.dumps({'info': {'version': '1.8.0', 'summary': 'Acme Py', 'package_url': 'https://pypi.org/project/acme-py/', 'requires_python': '>=3.10'}})),
            '/gh_jobs': (200, 'application/json', json.dumps({'jobs': [{'title': 'Staff AI Engineer'}, {'title': 'Enterprise AE'}]})),
            '/ashby': (200, 'application/json', json.dumps({'jobs': [{'title': 'Design Engineer', 'department': 'Product'}]})),
            '/lever': (200, 'application/json', json.dumps([{'text': 'Security Architect'}])),
            '/sec': (200, 'application/json', json.dumps({'name': 'ACME CORP', 'filings': {'recent': {'form': ['8-K', '4'], 'filingDate': ['2026-11-20', '2026-11-19'], 'accessionNumber': ['0001-26-000010', '0001-26-000009'], 'primaryDocument': ['k8.htm', 'f4.htm']}}})),
            '/hn': (200, 'application/json', json.dumps({'hits': [{'objectID': '99999', 'title': 'Show HN: Acme 2.1', 'url': 'https://acme.example/v2', 'points': 142, 'num_comments': 48, 'created_at': '2026-11-25T07:00:00Z'}]})),
        }
        _MockIntelHandler.routes = routes
        srv = ThreadingHTTPServer(('127.0.0.1', 0), _MockIntelHandler)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        self.addCleanup(srv.shutdown)
        self.addCleanup(srv.server_close)

        base = f'http://127.0.0.1:{port}'
        watchlist = {
            'schemaVersion': 'market-intel-watchlist/1',
            'updatedAt': utc_now(),
            'entities': [{
                'slug': 'acme',
                'name': 'Acme Corp',
                'category': 'direct-competitor',
                'sources': [
                    {'id': 'pricing', 'kind': 'webpage', 'url': f'{base}/pricing'},
                    {'id': 'blog', 'kind': 'rss', 'url': f'{base}/feed.xml'},
                    {'id': 'releases', 'kind': 'github_releases', 'repo': 'acme/cli', 'apiUrl': f'{base}/gh'},
                    {'id': 'ios', 'kind': 'appstore_ios', 'appId': '123', 'apiUrl': f'{base}/itunes'},
                    {'id': 'npm', 'kind': 'npm', 'package': 'acme-sdk', 'apiUrl': f'{base}/npm'},
                    {'id': 'pypi', 'kind': 'pypi', 'package': 'acme-py', 'apiUrl': f'{base}/pypi'},
                    {'id': 'jobs_gh', 'kind': 'greenhouse_jobs', 'boardToken': 'acme', 'apiUrl': f'{base}/gh_jobs'},
                    {'id': 'jobs_ashby', 'kind': 'ashby_jobs', 'boardSlug': 'acme', 'apiUrl': f'{base}/ashby'},
                    {'id': 'jobs_lever', 'kind': 'lever_jobs', 'siteSlug': 'acme', 'apiUrl': f'{base}/lever'},
                    {'id': 'sec', 'kind': 'sec_edgar', 'cik': '12345', 'apiUrl': f'{base}/sec'},
                    {'id': 'hn', 'kind': 'hn_algolia', 'query': 'acme', 'apiUrl': f'{base}/hn'},
                ],
            }],
        }
        (self.ws / 'watchlist.json').write_text(json.dumps(watchlist), encoding='utf-8')

        capture = fetch_sources.fetch_watchlist(self.ws)
        self.assertEqual(capture['okCount'], 11)
        self.assertEqual(capture['failedCount'], 0)

        # Step 1: baseline initialized
        diff1 = snapshot_diff.diff_capture(self.ws, capture)
        self.assertEqual(diff1['outcome'], 'baseline_initialized')
        self.assertEqual(diff1['baselineCreatedCount'], 11)
        self.assertFalse(diff1['partialFailure'])

        # Step 2: timestamp/nonce churn only -> MUST be honest no_material_change
        routes['/pricing'] = (200, 'text/html', '<html><head><title>Acme Pricing</title><script>var nonce=xyz999;</script></head><body><h1>Pro Plan</h1><p>$29/mo</p><p>Updated 2026-11-25T15:59:59Z</p></body></html>')
        cap2 = fetch_sources.fetch_watchlist(self.ws)
        diff2 = snapshot_diff.diff_capture(self.ws, cap2)
        self.assertEqual(diff2['outcome'], 'no_material_change')
        self.assertEqual(diff2['materialChangeCount'], 0)

        # Step 3: real price jump $29 -> $49 -> material_change
        routes['/pricing'] = (200, 'text/html', '<html><head><title>Acme Pricing</title></head><body><h1>Pro Plan</h1><p>$49/mo</p></body></html>')
        cap3 = fetch_sources.fetch_watchlist(self.ws)
        diff3 = snapshot_diff.diff_capture(self.ws, cap3)
        self.assertEqual(diff3['outcome'], 'material_change')
        self.assertEqual(diff3['materialChangeCount'], 1)
        self.assertIn('$49/mo', diff3['materialChanges'][0]['diff']['addedLines'])

        # Step 4: gate grounded claim + idempotent commit + board projection
        candidates = [{
            'entitySlug': 'acme',
            'severity': 'high',
            'category': 'pricing',
            'summary': 'Acme raised Pro Plan pricing from $29/mo to $49/mo.',
            'evidenceUrls': [f'{base}/pricing?utm_source=test'],
            'observedAt': utc_now(),
            'quote': 'Pro Plan $49/mo',
        }]
        gate1 = evidence_gate.gate_candidates(self.ws, cap3, candidates, commit_events=True)
        self.assertEqual(gate1['outcome'], 'verified_events')
        self.assertEqual(gate1['committedCount'], 1)
        # Re-committing same event is idempotent (0 new rows)
        gate2 = evidence_gate.gate_candidates(self.ws, cap3, candidates, commit_events=True)
        self.assertEqual(gate2['committedCount'], 0)

        # Board projection writes real data into an external Space board dir
        board_dir = Path(self.tmp.name) / 'space-boards/radar-board'
        radar_data = build_boards.project_board(self.ws, 'radar-board', board_dir)
        payload = json.loads(radar_data.read_text(encoding='utf-8'))
        self.assertEqual(payload['summary']['eventCount'], 1)
        self.assertEqual(payload['summary']['highSeverityCount'], 1)

    def test_fetch_sources_catches_timeout_and_ssl_errors_without_crashing_batch(self):
        watchlist = {
            'schemaVersion': 'market-intel-watchlist/1',
            'updatedAt': utc_now(),
            'entities': [{
                'slug': 'acme',
                'name': 'Acme Corp',
                'sources': [
                    {'id': 'timeout-src', 'kind': 'webpage', 'url': 'https://timeout.example/pricing'},
                    {'id': 'ssl-src', 'kind': 'webpage', 'url': 'https://badssl.example/pricing'},
                    {'id': 'ok-src', 'kind': 'webpage', 'url': 'https://ok.example/pricing'},
                ],
            }],
        }
        (self.ws / 'watchlist.json').write_text(json.dumps(watchlist), encoding='utf-8')

        def fake_http_get(url: str, **kwargs):
            if 'timeout.example' in url:
                raise TimeoutError('timed out waiting for origin')
            if 'badssl.example' in url:
                raise ssl.SSLError('TLS handshake failed')
            return 200, '<html><body><h1>Pro Plan</h1><p>$49/mo</p></body></html>'

        with mock.patch.object(fetch_sources, 'http_get', side_effect=fake_http_get):
            cap = fetch_sources.fetch_watchlist(self.ws)

        self.assertEqual(cap['totalSources'], 3)
        self.assertEqual(cap['okCount'], 1)
        self.assertEqual(cap['failedCount'], 2)
        by_id = {r['sourceId']: r for r in cap['records']}
        self.assertFalse(by_id['timeout-src']['ok'])
        self.assertIn('timed out', by_id['timeout-src']['error'])
        self.assertFalse(by_id['ssl-src']['ok'])
        self.assertIn('TLS', by_id['ssl-src']['error'])
        self.assertTrue(by_id['ok-src']['ok'])

        # Merge captures helper combines per-entity shards cleanly
        shard_a = self.ws / 'captures/a.json'
        shard_b = self.ws / 'captures/b.json'
        shard_a.write_text(json.dumps({**cap, 'records': cap['records'][:1]}), encoding='utf-8')
        shard_b.write_text(json.dumps({**cap, 'records': cap['records'][1:]}), encoding='utf-8')
        merged = fetch_sources.merge_captures(self.ws, [shard_a, shard_b])
        self.assertEqual(merged['totalSources'], 3)
        self.assertEqual(merged['okCount'], 1)
        self.assertEqual(merged['failedCount'], 2)

    def test_snapshot_diff_capture_failed_and_partial_failure_never_silently_swallow_errors(self):
        all_failed_capture = {
            'schemaVersion': 'market-intel-signal/1',
            'generatedAt': utc_now(),
            'records': [
                {'entitySlug': 'acme', 'sourceId': 'pricing', 'kind': 'webpage', 'ok': False, 'error': 'TimeoutError'},
                {'entitySlug': 'acme', 'sourceId': 'releases', 'kind': 'github_releases', 'ok': False, 'error': 'SSLError'},
            ],
        }
        diff_fail = snapshot_diff.diff_capture(self.ws, all_failed_capture)
        self.assertEqual(diff_fail['outcome'], 'capture_failed')
        self.assertEqual(diff_fail['okCount'], 0)
        self.assertEqual(diff_fail['failedCount'], 2)
        self.assertFalse(diff_fail['partialFailure'])

        partial_capture = {
            'schemaVersion': 'market-intel-signal/1',
            'generatedAt': utc_now(),
            'records': [
                {'entitySlug': 'acme', 'sourceId': 'pricing', 'kind': 'webpage', 'ok': True, 'url': 'https://acme.example/pricing', 'observedAt': utc_now(), 'structured': {'title': 'Pricing', 'lines': ['Pro Plan', '$49/mo']}},
                {'entitySlug': 'acme', 'sourceId': 'releases', 'kind': 'github_releases', 'ok': False, 'error': 'HTTP 503'},
            ],
        }
        diff_partial = snapshot_diff.diff_capture(self.ws, partial_capture)
        self.assertEqual(diff_partial['outcome'], 'baseline_initialized')
        self.assertEqual(diff_partial['okCount'], 1)
        self.assertEqual(diff_partial['failedCount'], 1)
        self.assertTrue(diff_partial['partialFailure'])

    def test_class_a_exhaustive_evidence_gate_invariants_and_fault_injection(self):
        """Class A exhaustive proof: all 2^6 combinations of grounding dimensions obey strict fail-closed rejection."""
        (self.ws / 'watchlist.json').write_text(
            json.dumps({'schemaVersion': 'market-intel-watchlist/1', 'updatedAt': utc_now(), 'entities': [{'slug': 'acme', 'name': 'Acme', 'sources': []}]}),
            encoding='utf-8',
        )
        capture = {
            'schemaVersion': 'market-intel-signal/1',
            'generatedAt': utc_now(),
            'records': [{
                'entitySlug': 'acme',
                'sourceId': 'p',
                'kind': 'webpage',
                'ok': True,
                'url': 'https://acme.example/pricing',
                'observedAt': utc_now(),
                'structured': {'title': 'Acme Pricing', 'lines': ['Pro Plan is now $49/mo']},
            }],
        }

        checked = 0
        for valid_entity, valid_sev, valid_cat, valid_quote, valid_ts, url_in_pool in itertools.product([False, True], repeat=6):
            checked += 1
            cand = {
                'entitySlug': 'acme' if valid_entity else 'ghost-co',
                'severity': 'high' if valid_sev else 'extreme',
                'category': 'pricing' if valid_cat else 'rumor',
                'summary': 'Acme changed pricing tier structure.',
                'quote': 'Pro Plan is now $49/mo' if valid_quote else '',
                'observedAt': utc_now() if valid_ts else 'yesterday',
                'evidenceUrls': ['https://acme.example/pricing'] if url_in_pool else ['https://fabricated.example/hallucinated'],
            }
            res = evidence_gate.gate_candidates(self.ws, capture, [cand])
            should_pass = all((valid_entity, valid_sev, valid_cat, valid_quote, valid_ts, url_in_pool))
            if should_pass:
                self.assertEqual(res['acceptedCount'], 1)
                self.assertEqual(res['rejectedCount'], 0)
            else:
                self.assertEqual(res['acceptedCount'], 0)
                self.assertEqual(res['rejectedCount'], 1)
                self.assertEqual(res['outcome'], 'no_verified_events')

        self.assertEqual(checked, 64)

        # Fault injection: stale capture (>24h) must fail closed
        stale_cap = {**capture, 'generatedAt': '2020-01-01T00:00:00Z'}
        with self.assertRaises(ValueError):
            evidence_gate.gate_candidates(self.ws, stale_cap, [])

        # Triangulation guard: claiming triangulated with only 1 source kind MUST be rejected;
        # combining 2 distinct source kinds (webpage + greenhouse_jobs) earns confidence="triangulated".
        multi_cap = {
            'schemaVersion': 'market-intel-signal/1',
            'generatedAt': utc_now(),
            'records': [
                {
                    'entitySlug': 'acme', 'sourceId': 'p', 'kind': 'webpage', 'ok': True,
                    'url': 'https://acme.example/pricing', 'observedAt': utc_now(),
                    'structured': {'title': 'Pricing', 'lines': ['Pro Plan $49/mo']},
                },
                {
                    'entitySlug': 'acme', 'sourceId': 'j', 'kind': 'greenhouse_jobs', 'ok': True,
                    'url': 'https://boards.greenhouse.io/acme', 'observedAt': utc_now(),
                    'structured': {'openCount': 4, 'sampleTitles': ['Enterprise AE', 'Solutions Architect']},
                },
            ],
        }
        overclaimed = [{
            'entitySlug': 'acme', 'severity': 'high', 'category': 'pricing',
            'confidence': 'triangulated',
            'summary': 'Overclaimed upmarket shift from one source only.',
            'quote': 'Pro Plan $49/mo', 'observedAt': utc_now(),
            'evidenceUrls': ['https://acme.example/pricing'],
        }]
        self.assertEqual(evidence_gate.gate_candidates(self.ws, multi_cap, overclaimed)['rejectedCount'], 1)

        corroborated = [{
            'entitySlug': 'acme', 'severity': 'high', 'category': 'positioning',
            'confidence': 'triangulated',
            'summary': 'Acme is moving upmarket (pricing jump + Enterprise AE hiring).',
            'quote': 'Pro Plan $49/mo', 'observedAt': utc_now(),
            'evidenceUrls': ['https://acme.example/pricing', 'https://boards.greenhouse.io/acme'],
        }]
        ok_tri = evidence_gate.gate_candidates(self.ws, multi_cap, corroborated)
        self.assertEqual(ok_tri['acceptedCount'], 1)
        self.assertEqual(ok_tri['accepted'][0]['confidence'], 'triangulated')
        self.assertEqual(ok_tri['accepted'][0]['sourceKinds'], ['greenhouse_jobs', 'webpage'])

    def test_evidence_gate_entity_isolation_empty_watchlist_quote_and_local_ref(self):
        # 1. Fail-closed when watchlist has zero entities
        empty_cap = {
            'schemaVersion': 'market-intel-signal/1',
            'generatedAt': utc_now(),
            'records': [{
                'entitySlug': 'acme', 'sourceId': 'p', 'kind': 'webpage', 'ok': True,
                'url': 'https://acme.example/pricing', 'observedAt': utc_now(),
                'structured': {'lines': ['Pro Plan $49/mo']},
            }],
        }
        empty_res = evidence_gate.gate_candidates(self.ws, empty_cap, [{
            'entitySlug': 'acme', 'severity': 'high', 'category': 'pricing',
            'summary': 'Acme pricing change without registered watchlist.',
            'evidenceUrls': ['https://acme.example/pricing'],
            'observedAt': utc_now(), 'quote': 'Pro Plan $49/mo',
        }])
        self.assertEqual(empty_res['rejectedCount'], 1)
        self.assertIn('no registered entities', empty_res['rejected'][0]['errors'][0].lower())

        # Register two distinct entities: acme and rival
        (self.ws / 'watchlist.json').write_text(
            json.dumps({
                'schemaVersion': 'market-intel-watchlist/1',
                'updatedAt': utc_now(),
                'entities': [
                    {'slug': 'acme', 'name': 'Acme Corp', 'sources': []},
                    {'slug': 'rival', 'name': 'Rival Inc', 'sources': []},
                ],
            }),
            encoding='utf-8',
        )
        two_entity_cap = {
            'schemaVersion': 'market-intel-signal/1',
            'generatedAt': utc_now(),
            'records': [
                {
                    'entitySlug': 'acme', 'sourceId': 'p', 'kind': 'webpage', 'ok': True,
                    'url': 'https://acme.example/pricing', 'observedAt': utc_now(),
                    'structured': {'lines': ['Pro Plan $49/mo']},
                },
                {
                    'entitySlug': 'rival', 'sourceId': 'j', 'kind': 'greenhouse_jobs', 'ok': True,
                    'url': 'https://boards.greenhouse.io/rival', 'observedAt': utc_now(),
                    'structured': {'openCount': 6, 'sampleTitles': ['Enterprise AE']},
                },
                {
                    'entitySlug': 'acme', 'sourceId': 'x', 'kind': 'connector:x', 'ok': True,
                    'url': 'https://x.com/acme/status/12345', 'observedAt': utc_now(),
                    'structured': {'excerpt': 'SSO now included on Pro tier.'},
                },
            ],
        }

        # 2. Cross-entity URL borrowing MUST be rejected (cannot borrow rival's URL to pass or triangulate)
        cross_entity = evidence_gate.gate_candidates(self.ws, two_entity_cap, [{
            'entitySlug': 'acme', 'severity': 'high', 'category': 'positioning',
            'confidence': 'triangulated',
            'summary': 'Acme allegedly hiring Enterprise AE using Rival URL.',
            'evidenceUrls': ['https://acme.example/pricing', 'https://boards.greenhouse.io/rival'],
            'observedAt': utc_now(), 'quote': 'Pro Plan $49/mo',
        }])
        self.assertEqual(cross_entity['rejectedCount'], 1)
        self.assertTrue(any('another entity' in e.lower() for e in cross_entity['rejected'][0]['errors']))

        # 3. Fabricated quote not present in captured text MUST be rejected
        bad_quote = evidence_gate.gate_candidates(self.ws, two_entity_cap, [{
            'entitySlug': 'acme', 'severity': 'high', 'category': 'pricing',
            'summary': 'Acme pricing change with hallucinated quote.',
            'evidenceUrls': ['https://acme.example/pricing'],
            'observedAt': utc_now(), 'quote': 'Enterprise Plan cut to $19/mo',
        }])
        self.assertEqual(bad_quote['rejectedCount'], 1)
        self.assertTrue(any('quote excerpt not found' in e.lower() for e in bad_quote['rejected'][0]['errors']))

        # 4. Connector record + webpage for same entity earns triangulated
        connector_tri = evidence_gate.gate_candidates(self.ws, two_entity_cap, [{
            'entitySlug': 'acme', 'severity': 'high', 'category': 'pricing',
            'confidence': 'triangulated',
            'summary': 'Acme updated Pro pricing and announced SSO via X connector.',
            'evidenceUrls': ['https://acme.example/pricing', 'https://x.com/acme/status/12345'],
            'observedAt': utc_now(), 'quote': 'SSO now included on Pro tier.',
        }])
        self.assertEqual(connector_tri['acceptedCount'], 1)
        self.assertEqual(connector_tri['accepted'][0]['confidence'], 'triangulated')
        self.assertEqual(connector_tri['accepted'][0]['sourceKinds'], ['connector:x', 'webpage'])

        # 5. LocalRef support: exists inside <data-dir>, quote verified, blocks path traversal
        doc_path = self.ws / 'entities/acme/local-docs/q3-call.txt'
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text('Customer reported Acme renewal jumped 35% year over year.\n', encoding='utf-8')

        local_only = evidence_gate.gate_candidates(self.ws, two_entity_cap, [{
            'entitySlug': 'acme', 'severity': 'medium', 'category': 'pricing',
            'summary': 'Customer call notes report 35% Acme renewal increase.',
            'evidenceUrls': [],
            'localRef': 'entities/acme/local-docs/q3-call.txt',
            'observedAt': utc_now(), 'quote': 'Acme renewal jumped 35%',
        }])
        self.assertEqual(local_only['acceptedCount'], 1)
        self.assertEqual(local_only['accepted'][0]['localRef'], 'entities/acme/local-docs/q3-call.txt')
        self.assertEqual(local_only['accepted'][0]['sourceKinds'], ['local_doc'])

        # Webpage + localRef => triangulated
        local_plus_web = evidence_gate.gate_candidates(self.ws, two_entity_cap, [{
            'entitySlug': 'acme', 'severity': 'high', 'category': 'pricing',
            'confidence': 'triangulated',
            'summary': 'Public Pro price rise corroborated by renewal call transcript.',
            'evidenceUrls': ['https://acme.example/pricing'],
            'localRef': 'entities/acme/local-docs/q3-call.txt',
            'observedAt': utc_now(), 'quote': 'Acme renewal jumped 35%',
        }])
        self.assertEqual(local_plus_web['acceptedCount'], 1)
        self.assertEqual(local_plus_web['accepted'][0]['confidence'], 'triangulated')
        self.assertEqual(local_plus_web['accepted'][0]['sourceKinds'], ['local_doc', 'webpage'])

        # Traversal or missing localRef MUST fail closed
        traversal = evidence_gate.gate_candidates(self.ws, two_entity_cap, [{
            'entitySlug': 'acme', 'severity': 'low', 'category': 'filing',
            'summary': 'Attempted path traversal outside data dir.',
            'evidenceUrls': [],
            'localRef': '../outside.txt',
            'observedAt': utc_now(), 'quote': 'outside quote',
        }])
        self.assertEqual(traversal['rejectedCount'], 1)

    def test_build_boards_latest_event_sorting_and_battlecard_count_consistency(self):
        (self.ws / 'watchlist.json').write_text(
            json.dumps({
                'schemaVersion': 'market-intel-watchlist/1',
                'updatedAt': utc_now(),
                'entities': [
                    {'slug': 'acme', 'name': 'Acme Corp', 'category': 'direct-competitor', 'sources': []},
                    {'slug': 'beta', 'name': 'Beta Labs', 'category': 'adjacent', 'sources': []},
                ],
            }),
            encoding='utf-8',
        )
        # Write events out of chronological order (newer first, older second)
        events = [
            {
                'eventId': '2222222222222222', 'entitySlug': 'acme', 'severity': 'high', 'category': 'pricing',
                'confidence': 'triangulated', 'sourceKinds': ['greenhouse_jobs', 'webpage'],
                'summary': 'Newer 2026-11-26 pricing change', 'evidenceUrls': ['https://acme.example/pricing'],
                'observedAt': '2026-11-26T12:00:00Z', 'quote': 'Pro Plan $49/mo',
            },
            {
                'eventId': '1111111111111111', 'entitySlug': 'acme', 'severity': 'low', 'category': 'release',
                'confidence': 'single_source', 'sourceKinds': ['github_releases'],
                'summary': 'Older 2026-11-20 minor patch', 'evidenceUrls': ['https://github.com/acme/cli/releases'],
                'observedAt': '2026-11-20T08:00:00Z', 'quote': 'v2.0.1 patch',
            },
        ]
        (self.ws / 'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events) + '\n', encoding='utf-8')
        # Battlecard populated via oneLiner + gaps + evidenceUrls (without pricingSummary/strengths)
        (self.ws / 'battlecards/acme.json').write_text(
            json.dumps({
                'slug': 'acme',
                'threatLevel': 'high',
                'oneLiner': 'Developer workflow suite moving upmarket.',
                'gaps': ['No offline mode'],
                'evidenceUrls': ['https://acme.example/pricing'],
            }),
            encoding='utf-8',
        )

        bc_payload = build_boards.build_battlecard_payload(self.ws)
        self.assertEqual(bc_payload['summary']['entityCount'], 2)
        self.assertEqual(bc_payload['summary']['battlecardCount'], 1)
        acme_card = next(c for c in bc_payload['cards'] if c['slug'] == 'acme')
        self.assertEqual(acme_card['latestEvent'], 'Newer 2026-11-26 pricing change')
        self.assertEqual(acme_card['gaps'], ['No offline mode'])
        self.assertEqual(acme_card['evidenceUrls'], ['https://acme.example/pricing'])

    def test_board_assets_and_bridge_contracts(self):
        css = (PLUGIN_ROOT / 'assets/boards/shared/board-ui.css').read_text(encoding='utf-8')
        js = (PLUGIN_ROOT / 'assets/boards/shared/board-sdk-bridge.js').read_text(encoding='utf-8')
        radar_html = (PLUGIN_ROOT / 'assets/boards/radar-board/index.html').read_text(encoding='utf-8')
        bc_html = (PLUGIN_ROOT / 'assets/boards/battlecard-board/index.html').read_text(encoding='utf-8')

        self.assertIn('market-intel', css.splitlines()[0])
        self.assertIn('market-intel', js.splitlines()[0])
        self.assertIn('onDisplayChange', js)
        self.assertIn('assets/board-sdk-bridge.js', js)
        self.assertIn('assets/board-ui.css', js)
        self.assertNotIn('id="kpi-high" class="ui-kpi-value" data-tone="warning"', radar_html)
        self.assertIn('sourceKinds', radar_html)
        self.assertIn('confidence', radar_html)
        self.assertIn('strengths', bc_html)
        self.assertIn('gaps', bc_html)
        self.assertIn('evidenceUrls', bc_html)


if __name__ == '__main__':
    unittest.main()
