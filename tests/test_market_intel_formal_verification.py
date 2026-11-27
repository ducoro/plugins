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
    post_routes: dict[str, tuple[int, str, str]] = {}

    def do_GET(self):
        status, ctype, body = self.routes.get(self.path, (404, 'text/plain', 'not found'))
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.end_headers()
        self.wfile.write(body.encode('utf-8'))

    def do_POST(self):
        length = int(self.headers.get('Content-Length', '0') or '0')
        if length > 0:
            self.rfile.read(length)
        status, ctype, body = self.post_routes.get(self.path, (404, 'text/plain', 'not found'))
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

    def test_new_adapters_github_activity_file_trending_and_producthunt(self):
        import base64
        import os

        readme_v1 = base64.b64encode(b'# Acme CLI\nFast local workflow engine.\n').decode('ascii')
        readme_v2 = base64.b64encode(b'# Acme CLI\nFast local workflow engine.\nNow with team sync.\n').decode('ascii')

        trending_v1 = (
            '<html><body>'
            '<article class="Box-row"><h2><a href="/acme/agent-kit">acme / agent-kit</a></h2>'
            '<p class="col-9">Autonomous workflow runner</p>'
            '<span itemprop="programmingLanguage">TypeScript</span>'
            '<a href="/acme/agent-kit/stargazers">1,200</a>'
            '<span class="d-inline-block float-sm-right">210 stars today</span></article>'
            '<article class="Box-row"><h2><a href="/beta/local-ai">beta / local-ai</a></h2>'
            '<p class="col-9">Offline model router</p>'
            '<span itemprop="programmingLanguage">Rust</span>'
            '<a href="/beta/local-ai/stargazers">850</a>'
            '<span class="d-inline-block float-sm-right">140 stars today</span></article>'
            '</body></html>'
        )
        trending_v2 = (
            '<html><body>'
            '<article class="Box-row"><h2><a href="/beta/local-ai">beta / local-ai</a></h2>'
            '<p class="col-9">Offline model router</p>'
            '<span itemprop="programmingLanguage">Rust</span>'
            '<a href="/beta/local-ai/stargazers">990</a>'
            '<span class="d-inline-block float-sm-right">180 stars today</span></article>'
            '<article class="Box-row"><h2><a href="/gamma/mcp-hub">gamma / mcp-hub</a></h2>'
            '<p class="col-9">MCP connector registry</p>'
            '<span itemprop="programmingLanguage">Go</span>'
            '<a href="/gamma/mcp-hub/stargazers">410</a>'
            '<span class="d-inline-block float-sm-right">120 stars today</span></article>'
            '</body></html>'
        )
        ph_rss = (
            '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">'
            '<entry><title>FlowDesk</title><link href="https://www.producthunt.com/posts/flowdesk"/>'
            '<updated>2026-11-27T08:00:00Z</updated><summary>Run background workflows from chat</summary></entry>'
            '</feed>'
        )
        ph_graphql = json.dumps({
            'data': {
                'posts': {
                    'edges': [{
                        'node': {
                            'id': 'ph-101',
                            'name': 'FlowDesk',
                            'tagline': 'Run background workflows from chat',
                            'url': 'https://www.producthunt.com/posts/flowdesk',
                            'votesCount': 312,
                            'commentsCount': 24,
                            'reviewsCount': 5,
                            'reviewsRating': 4.8,
                            'createdAt': '2026-11-27T08:00:00Z',
                        }
                    }]
                }
            }
        })

        routes = {
            '/gh/commits': (200, 'application/json', json.dumps([
                {
                    'sha': 'aaaa1111bbbb2222cccc3333dddd4444eeee5555',
                    'html_url': 'https://github.com/acme/agent-kit/commit/aaaa1111',
                    'commit': {
                        'message': 'feat: add deterministic retry budget\n\ndetails',
                        'author': {'name': 'Alice', 'date': '2026-11-27T07:00:00Z'},
                    },
                }
            ])),
            '/gh/issues': (200, 'application/json', json.dumps([
                {
                    'number': 42,
                    'title': 'Linux daemon hangs after sleep',
                    'state': 'open',
                    'html_url': 'https://github.com/acme/agent-kit/issues/42',
                    'user': {'login': 'ext-user'},
                    'author_association': 'NONE',
                    'comments': 3,
                    'updated_at': '2026-11-27T08:00:00Z',
                    'labels': [{'name': 'bug'}],
                },
                {
                    'number': 43,
                    'title': 'fix: retry backoff timer',
                    'state': 'closed',
                    'html_url': 'https://github.com/acme/agent-kit/pull/43',
                    'user': {'login': 'maintainer-bob'},
                    'author_association': 'MEMBER',
                    'comments': 1,
                    'updated_at': '2026-11-27T08:30:00Z',
                    'labels': [],
                    'pull_request': {'url': 'https://api.github.com/repos/acme/agent-kit/pulls/43'},
                },
            ])),
            '/gh/readme': (200, 'application/json', json.dumps({
                'path': 'README.md',
                'sha': '1111111111111111111111111111111111111111',
                'size': 42,
                'encoding': 'base64',
                'type': 'file',
                'html_url': 'https://github.com/acme/agent-kit/blob/main/README.md',
                'content': readme_v1,
            })),
            '/gh/trending': (200, 'text/html', trending_v1),
            '/ph/feed': (200, 'application/atom+xml', ph_rss),
        }
        _MockIntelHandler.routes = routes
        _MockIntelHandler.post_routes = {
            '/ph/graphql': (200, 'application/json', ph_graphql),
        }
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
            'entities': [
                {
                    'slug': 'acme',
                    'name': 'Acme Agent Kit',
                    'category': 'direct-competitor',
                    'sources': [
                        {
                            'id': 'repo_activity',
                            'kind': 'github_repo_activity',
                            'repo': 'acme/agent-kit',
                            'commitsApiUrl': f'{base}/gh/commits',
                            'issuesApiUrl': f'{base}/gh/issues',
                        },
                        {
                            'id': 'readme',
                            'kind': 'github_file',
                            'repo': 'acme/agent-kit',
                            'path': 'README.md',
                            'apiUrl': f'{base}/gh/readme',
                        },
                    ],
                },
                {
                    'slug': 'github-trending-daily',
                    'name': 'GitHub Trending Daily',
                    'category': 'sector-radar',
                    'sources': [
                        {'id': 'trending_daily', 'kind': 'github_trending', 'since': 'daily', 'apiUrl': f'{base}/gh/trending'},
                    ],
                },
                {
                    'slug': 'producthunt-daily',
                    'name': 'Product Hunt Daily',
                    'category': 'sector-radar',
                    'sources': [
                        {'id': 'ph_rss', 'kind': 'producthunt', 'apiUrl': f'{base}/ph/feed'},
                    ],
                },
            ],
        }
        (self.ws / 'watchlist.json').write_text(json.dumps(watchlist), encoding='utf-8')

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('PRODUCTHUNT_TOKEN', None)
            cap1 = fetch_sources.fetch_watchlist(self.ws)

        self.assertEqual(cap1['okCount'], 4)
        self.assertEqual(cap1['failedCount'], 0)
        by_src = {r['sourceId']: r for r in cap1['records']}

        # Issues and PRs must be strictly separated, with external authorAssociation preserved
        act = by_src['repo_activity']['structured']
        self.assertEqual(len(act['commits']), 1)
        self.assertEqual(len(act['issues']), 1)
        self.assertEqual(len(act['prs']), 1)
        self.assertEqual(act['issues'][0]['number'], 42)
        self.assertEqual(act['issues'][0]['authorAssociation'], 'NONE')
        self.assertEqual(act['prs'][0]['number'], 43)

        # File blobSha and decoded lines captured
        readme = by_src['readme']['structured']
        self.assertEqual(readme['blobSha'], '1111111111111111111111111111111111111111')
        self.assertIn('# Acme CLI', readme['lines'])

        # Trending completeness and ordering
        tr = by_src['trending_daily']['structured']
        self.assertTrue(tr['complete'])
        self.assertEqual(tr['expectedCount'], 2)
        self.assertEqual([e['repo'] for e in tr['entries']], ['acme/agent-kit', 'beta/local-ai'])

        # Product Hunt RSS fallback works without token
        self.assertEqual(by_src['ph_rss']['structured']['mode'], 'rss')
        self.assertEqual(by_src['ph_rss']['structured']['posts'][0]['name'], 'FlowDesk')

        # Product Hunt GraphQL mode separates commentsCount (launch) from reviewsCount
        with mock.patch.dict(os.environ, {'PRODUCTHUNT_TOKEN': 'test-token-placeholder'}):
            ph_gql_rec = fetch_sources.fetch_single_source(
                'producthunt-daily',
                {'id': 'ph_gql', 'kind': 'producthunt', 'graphqlUrl': f'{base}/ph/graphql'},
            )
        self.assertTrue(ph_gql_rec['ok'])
        self.assertEqual(ph_gql_rec['structured']['mode'], 'graphql')
        self.assertEqual(ph_gql_rec['structured']['posts'][0]['commentsCount'], 24)
        self.assertEqual(ph_gql_rec['structured']['posts'][0]['reviewsCount'], 5)

        # Baseline diff
        diff1 = snapshot_diff.diff_capture(self.ws, cap1)
        self.assertEqual(diff1['outcome'], 'baseline_initialized')

        # Update README + trending ranks + add new commit -> material_change with structured diffs
        routes['/gh/readme'] = (200, 'application/json', json.dumps({
            'path': 'README.md',
            'sha': '2222222222222222222222222222222222222222',
            'size': 64,
            'encoding': 'base64',
            'type': 'file',
            'html_url': 'https://github.com/acme/agent-kit/blob/main/README.md',
            'content': readme_v2,
        }))
        routes['/gh/trending'] = (200, 'text/html', trending_v2)
        routes['/gh/commits'] = (200, 'application/json', json.dumps([
            {
                'sha': 'ffff9999eeee8888dddd7777cccc6666bbbb5555',
                'html_url': 'https://github.com/acme/agent-kit/commit/ffff9999',
                'commit': {
                    'message': 'feat: ship team sync protocol',
                    'author': {'name': 'Alice', 'date': '2026-11-28T00:00:00Z'},
                },
            },
            {
                'sha': 'aaaa1111bbbb2222cccc3333dddd4444eeee5555',
                'html_url': 'https://github.com/acme/agent-kit/commit/aaaa1111',
                'commit': {
                    'message': 'feat: add deterministic retry budget\n\ndetails',
                    'author': {'name': 'Alice', 'date': '2026-11-27T07:00:00Z'},
                },
            },
        ]))
        cap2 = fetch_sources.fetch_watchlist(self.ws)
        diff2 = snapshot_diff.diff_capture(self.ws, cap2)
        self.assertEqual(diff2['outcome'], 'material_change')
        self.assertEqual(diff2['materialChangeCount'], 3)
        by_change = {c['sourceId']: c for c in diff2['materialChanges']}
        self.assertEqual(by_change['repo_activity']['changeKind'], 'content_changed')
        self.assertEqual(len(by_change['repo_activity']['diff']['addedCommits']), 1)
        self.assertEqual(by_change['readme']['diff']['currentSha'], '2222222222222222222222222222222222222222')
        self.assertIn('Now with team sync.', by_change['readme']['diff']['addedLines'])
        self.assertEqual(by_change['trending_daily']['diff']['entered'], ['gamma/mcp-hub'])
        self.assertEqual(by_change['trending_daily']['diff']['dropped'], ['acme/agent-kit'])
        self.assertEqual(by_change['trending_daily']['diff']['rankMoves'][0]['repo'], 'beta/local-ai')
        self.assertEqual(by_change['trending_daily']['diff']['rankMoves'][0]['delta'], 1)

        # Incomplete trending HTML MUST fail closed as parse_error instead of faking dropped repos
        routes['/gh/trending'] = (200, 'text/html', '<html><body><article class="Box-row"><div>broken</div></article></body></html>')
        cap_broken = fetch_sources.fetch_watchlist(self.ws, entity_filter='github-trending-daily')
        self.assertEqual(cap_broken['failedCount'], 1)
        self.assertEqual(cap_broken['records'][0]['errorKind'], 'parse_error')

    def test_error_classification_and_semantic_change_kinds(self):
        import urllib.error

        # 1. Structured errorKind classification across all failure modes
        cases = [
            (urllib.error.HTTPError('https://x.test', 429, 'Too Many Requests', {}, None), 'rate_limited'),
            (urllib.error.HTTPError('https://x.test', 401, 'Unauthorized', {}, None), 'auth_required'),
            (urllib.error.HTTPError('https://x.test', 403, 'Forbidden', {}, None), 'access_denied'),
            (urllib.error.HTTPError('https://x.test', 403, 'API rate limit exceeded', {}, None), 'rate_limited'),
            (ValueError('Cloudflare captcha verification required'), 'challenge'),
            (TimeoutError('timed out'), 'network_timeout'),
            (json.JSONDecodeError('bad', 'x', 0), 'parse_error'),
        ]
        for exc, expected_kind in cases:
            with mock.patch.object(fetch_sources, 'http_get', side_effect=exc):
                rec = fetch_sources.fetch_single_source('acme', {'id': 's', 'kind': 'webpage', 'url': 'https://acme.example'})
                self.assertFalse(rec['ok'])
                self.assertEqual(rec['errorKind'], expected_kind, f'Expected {expected_kind} for {exc!r}, got {rec}')

        # 2. Semantic changeKind in snapshot_diff:
        #    engagement_only -> honest no_material_change (silent)
        #    discussion_active -> tracked in discussionUpdates without faking a brand-new post
        #    coverage_expanded -> tracked in coverageExpanded without faking today's material change
        base_hits = [
            {'title': 'Show HN: Acme 2.1', 'url': 'https://acme.example/v2', 'hnUrl': 'https://news.ycombinator.com/item?id=101', 'points': 100, 'comments': 20, 'createdAt': '2026-11-26T00:00:00Z'},
            {'title': 'Acme vs Beta', 'url': 'https://acme.example/vs', 'hnUrl': 'https://news.ycombinator.com/item?id=100', 'points': 50, 'comments': 10, 'createdAt': '2026-11-25T00:00:00Z'},
        ]
        cap_base = {
            'schemaVersion': 'market-intel-signal/1',
            'generatedAt': utc_now(),
            'records': [{
                'entitySlug': 'acme', 'sourceId': 'hn', 'kind': 'hn_algolia', 'ok': True,
                'url': 'https://hn.algolia.com/?q=acme', 'observedAt': utc_now(),
                'structured': {'query': 'acme', 'hits': base_hits},
            }],
        }
        d0 = snapshot_diff.diff_capture(self.ws, cap_base)
        self.assertEqual(d0['outcome'], 'baseline_initialized')

        # 2a. Points-only jitter -> engagement_only, outcome MUST remain no_material_change
        cap_points = {
            **cap_base,
            'records': [{
                **cap_base['records'][0],
                'structured': {'query': 'acme', 'hits': [
                    {**base_hits[0], 'points': 115},
                    base_hits[1],
                ]},
            }],
        }
        d_points = snapshot_diff.diff_capture(self.ws, cap_points)
        self.assertEqual(d_points['outcome'], 'no_material_change')
        self.assertEqual(d_points['materialChangeCount'], 0)
        self.assertEqual(d_points['engagementOnlyCount'], 1)

        # 2b. Comments increased on existing thread -> discussion_active, not material_change new post
        cap_comments = {
            **cap_base,
            'records': [{
                **cap_base['records'][0],
                'structured': {'query': 'acme', 'hits': [
                    {**base_hits[0], 'points': 115, 'comments': 38},
                    base_hits[1],
                ]},
            }],
        }
        d_comments = snapshot_diff.diff_capture(self.ws, cap_comments)
        self.assertEqual(d_comments['outcome'], 'no_material_change')
        self.assertEqual(d_comments['discussionUpdateCount'], 1)
        self.assertEqual(d_comments['discussionUpdates'][0]['changeKind'], 'discussion_active')

        # 2c. Wider limit reveals older trailing item while prefix is identical -> coverage_expanded
        cap_wider = {
            **cap_base,
            'records': [{
                **cap_base['records'][0],
                'structured': {'query': 'acme', 'hits': [
                    {**base_hits[0], 'points': 115, 'comments': 38},
                    base_hits[1],
                    {'title': 'Older Acme 1.0 post', 'url': 'https://acme.example/v1', 'hnUrl': 'https://news.ycombinator.com/item?id=90', 'points': 30, 'comments': 5, 'createdAt': '2026-10-01T00:00:00Z'},
                ]},
            }],
        }
        d_wider = snapshot_diff.diff_capture(self.ws, cap_wider)
        self.assertEqual(d_wider['outcome'], 'no_material_change')
        self.assertEqual(d_wider['materialChangeCount'], 0)
        self.assertEqual(d_wider['coverageExpandedCount'], 1)
        self.assertEqual(d_wider['coverageExpanded'][0]['changeKind'], 'coverage_expanded')

    def test_sector_radar_discovery_category_computer_use_and_battlecard_filtering(self):
        (self.ws / 'watchlist.json').write_text(
            json.dumps({
                'schemaVersion': 'market-intel-watchlist/1',
                'updatedAt': utc_now(),
                'entities': [
                    {'slug': 'acme', 'name': 'Acme Corp', 'category': 'direct-competitor', 'sources': []},
                    {'slug': 'github-trending-daily', 'name': 'GitHub Trending Daily', 'category': 'sector-radar', 'sources': []},
                ],
            }),
            encoding='utf-8',
        )
        capture = {
            'schemaVersion': 'market-intel-signal/1',
            'generatedAt': utc_now(),
            'records': [
                {
                    'entitySlug': 'github-trending-daily', 'sourceId': 'trending', 'kind': 'github_trending', 'ok': True,
                    'url': 'https://github.com/trending?since=daily', 'observedAt': utc_now(),
                    'structured': {
                        'entries': [{'rank': 1, 'repo': 'gamma/mcp-hub', 'url': 'https://github.com/gamma/mcp-hub', 'description': 'MCP connector registry'}],
                    },
                },
                {
                    'entitySlug': 'github-trending-daily', 'sourceId': 'cu-medium', 'kind': 'computer_use', 'ok': True,
                    'url': 'https://medium.com/@analyst/mcp-hub-review', 'observedAt': utc_now(),
                    'structured': {'excerpt': 'gamma/mcp-hub crossed 400 stars in 24 hours with active external PRs.'},
                },
            ],
        }
        gate = evidence_gate.gate_candidates(self.ws, capture, [{
            'entitySlug': 'github-trending-daily',
            'severity': 'medium',
            'category': 'discovery',
            'confidence': 'triangulated',
            'summary': 'New open-source project gamma/mcp-hub entered GitHub Trending #1 with corroborating analyst coverage.',
            'evidenceUrls': ['https://github.com/gamma/mcp-hub', 'https://medium.com/@analyst/mcp-hub-review'],
            'observedAt': utc_now(),
            'quote': 'gamma/mcp-hub crossed 400 stars in 24 hours',
        }], commit_events=True)
        self.assertEqual(gate['acceptedCount'], 1)
        self.assertEqual(gate['accepted'][0]['category'], 'discovery')
        self.assertEqual(gate['accepted'][0]['sourceKinds'], ['computer_use', 'github_trending'])

        # Radar board includes sector-radar entities & discovery events; battlecard board excludes sector-radar
        radar_payload = build_boards.build_radar_payload(self.ws)
        self.assertEqual(radar_payload['summary']['entityCount'], 2)
        self.assertEqual(radar_payload['summary']['eventCount'], 1)

        bc_payload = build_boards.build_battlecard_payload(self.ws)
        self.assertEqual([c['slug'] for c in bc_payload['cards']], ['acme'])
        self.assertEqual(bc_payload['summary']['entityCount'], 1)


if __name__ == '__main__':
    unittest.main()
