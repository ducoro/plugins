"""Unit, local HTTP roundtrip, and Class-A/B formal verification tests for market-intel."""
from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import itertools
import json
from pathlib import Path
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'plugins/market-intel/scripts'


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

        # Board projection writes real data
        radar_data = build_boards.project_board(self.ws, 'radar-board', self.ws / 'boards/radar-board')
        payload = json.loads(radar_data.read_text(encoding='utf-8'))
        self.assertEqual(payload['summary']['eventCount'], 1)
        self.assertEqual(payload['summary']['highSeverityCount'], 1)

    def test_class_a_exhaustive_evidence_gate_invariants_and_fault_injection(self):
        """Class A exhaustive proof: all 2^6 combinations of grounding dimensions obey strict fail-closed rejection."""
        (self.ws / 'watchlist.json').write_text(
            json.dumps({'schemaVersion': 'market-intel-watchlist/1', 'updatedAt': utc_now(), 'entities': [{'slug': 'acme', 'name': 'Acme', 'sources': []}]}),
            encoding='utf-8',
        )
        capture = {
            'schemaVersion': 'market-intel-signal/1',
            'generatedAt': utc_now(),
            'records': [{'entitySlug': 'acme', 'sourceId': 'p', 'kind': 'webpage', 'ok': True, 'url': 'https://acme.example/pricing', 'observedAt': utc_now(), 'structured': {}}],
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
                {'entitySlug': 'acme', 'sourceId': 'p', 'kind': 'webpage', 'ok': True, 'url': 'https://acme.example/pricing', 'observedAt': utc_now(), 'structured': {}},
                {'entitySlug': 'acme', 'sourceId': 'j', 'kind': 'greenhouse_jobs', 'ok': True, 'url': 'https://boards.greenhouse.io/acme', 'observedAt': utc_now(), 'structured': {}},
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
            'quote': 'Pro Plan $49/mo + 4 Enterprise AE roles', 'observedAt': utc_now(),
            'evidenceUrls': ['https://acme.example/pricing', 'https://boards.greenhouse.io/acme'],
        }]
        ok_tri = evidence_gate.gate_candidates(self.ws, multi_cap, corroborated)
        self.assertEqual(ok_tri['acceptedCount'], 1)
        self.assertEqual(ok_tri['accepted'][0]['confidence'], 'triangulated')
        self.assertEqual(ok_tri['accepted'][0]['sourceKinds'], ['greenhouse_jobs', 'webpage'])


if __name__ == '__main__':
    unittest.main()
