"""Unit, local HTTP roundtrip, and Class-A/B formal verification tests for customer-support-ops."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import itertools
import json
import mailbox
from pathlib import Path
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'plugins/customer-support-ops/scripts'


def load_mod(name: str):
    spec = importlib.util.spec_from_file_location(f'cso_{name}', SCRIPTS / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


init_workspace = load_mod('init_workspace')
ingest_feedback = load_mod('ingest_feedback')
triage_gate = load_mod('triage_gate')
reply_guard = load_mod('reply_guard')
build_boards = load_mod('build_boards')


class _MockSupportHandler(BaseHTTPRequestHandler):
    routes: dict[str, tuple[int, str]] = {}

    def do_GET(self):
        status, body = self.routes.get(self.path, (404, '{}'))
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(body.encode('utf-8'))

    def log_message(self, format, *args):
        return


class CustomerSupportOpsFormalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name) / 'customer-support-ops'
        init_workspace.init_workspace(self.ws)

    def test_real_channels_http_eml_mbox_csv_triage_spikes_and_boards(self):
        _MockSupportHandler.routes = {
            '/gh': (200, json.dumps([
                {'number': 101, 'title': 'Production crash & cannot login', 'body': '500 error for all users', 'html_url': 'https://github.com/acme/app/issues/101', 'user': {'login': 'alice'}, 'labels': [{'name': 'bug'}], 'state': 'open', 'created_at': '2026-11-24T10:00:00Z'},
                {'number': 102, 'title': 'PR should be skipped', 'pull_request': {}, 'state': 'open', 'created_at': '2026-11-24T10:00:00Z'},
            ])),
        }
        srv = ThreadingHTTPServer(('127.0.0.1', 0), _MockSupportHandler)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        self.addCleanup(srv.server_close)

        gh_t = ingest_feedback.fetch_github_issues('acme/app', api_url=f'http://127.0.0.1:{port}/gh')
        self.assertEqual(len(gh_t), 1)

        # Connector/JSONL normalized review (e.g., from App Store Connect or Intercom)
        jsonl_path = Path(self.tmp.name) / 'connector.jsonl'
        jsonl_path.write_text(json.dumps({
            'channel': 'appstore_ios', 'externalId': 'rev-1', 'customer': 'bob',
            'subject': 'Double charged', 'body': 'Please refund immediately',
            'rating': 1, 'createdAt': '2026-11-25T05:00:00Z',
        }) + '\n', encoding='utf-8')
        conn_t = ingest_feedback.parse_jsonl_file(jsonl_path)
        self.assertEqual(len(conn_t), 1)

        # Real .eml + .mbox + .csv files
        eml_path = Path(self.tmp.name) / 'msg1.eml'
        eml_path.write_text('From: carol@example.com\nSubject: How to export CSV?\nDate: Tue, 24 Nov 2026 12:00:00 +0000\nMessage-ID: <m1@example.com>\n\nCould you show me where export is?\n', encoding='utf-8')
        mbox_path = Path(self.tmp.name) / 'archive.mbox'
        mb = mailbox.mbox(str(mbox_path))
        mb.add('From: dave@example.com\nSubject: Sync fails on macOS\nDate: Tue, 24 Nov 2026 13:00:00 +0000\nMessage-ID: <m2@example.com>\n\nSync hangs on startup.\n')
        mb.flush()
        mb.close()
        csv_path = Path(self.tmp.name) / 'zendesk.csv'
        csv_path.write_text('id,subject,description,requester,created_at\nZ-1,Sync fails on macOS,Stuck at 0%,eve@example.com,2026-11-24T14:00:00Z\nZ-2,Sync fails again,Freezes after update,frank@example.com,2026-11-24T15:00:00Z\n', encoding='utf-8')

        all_in = gh_t + conn_t + ingest_feedback.parse_eml_path(eml_path) + ingest_feedback.parse_mbox_file(mbox_path) + ingest_feedback.parse_csv_file(csv_path)
        res1 = ingest_feedback.merge_tickets(self.ws, all_in)
        self.assertEqual(res1['added'], 6)
        # Re-ingesting exact same batch must add 0 new tickets
        res2 = ingest_feedback.merge_tickets(self.ws, all_in)
        self.assertEqual(res2['added'], 0)

        # Assign rootCauseId to 3 recent sync tickets to verify spike detector
        t_path = self.ws / 'tickets/tickets.json'
        store = json.loads(t_path.read_text(encoding='utf-8'))
        for tid in ('email:m2@example.com', 'csv:Z-1', 'csv:Z-2'):
            store['tickets'][tid]['rootCauseId'] = 'macos-sync-hang'
        t_path.write_text(json.dumps(store), encoding='utf-8')

        now = datetime(2026, 11, 25, 16, 0, tzinfo=timezone.utc)
        report = triage_gate.run_triage(self.ws, now=now, write_report=True)
        self.assertEqual(report['openCountsByPriority']['P0'], 1)
        self.assertEqual(report['openCountsByPriority']['P1'], 1)
        self.assertGreaterEqual(report['slaBreachCount'], 2)
        self.assertEqual(report['spikeCount'], 1)
        self.assertEqual(report['spikes'][0]['rootCauseId'], 'macos-sync-hang')

        b1 = build_boards.project_board(self.ws, 'triage-sla-board', self.ws / 'boards/triage-sla-board')
        b2 = build_boards.project_board(self.ws, 'root-cause-board', self.ws / 'boards/root-cause-board')
        self.assertEqual(json.loads(b1.read_text())['summary']['escalationCount'], report['escalationCount'])
        self.assertEqual(json.loads(b2.read_text())['summary']['spikeCount'], 1)

    def test_class_a_exhaustive_risk_escalation_invariants(self):
        """Class A exhaustive proof: every combination of 5 risk flags obeys escalation & autoReplyAllowed=False."""
        policy = {'firstResponseHours': {'P0': 1, 'P1': 4, 'P2': 24, 'P3': 72}}
        now = datetime(2026, 11, 25, 16, 0, tzinfo=timezone.utc)
        checked = 0
        for outage, security, legal, refund, one_star, breached in itertools.product([False, True], repeat=6):
            checked += 1
            parts = []
            if outage:
                parts.append('production crash cannot login')
            if security:
                parts.append('security vulnerability data breach')
            if legal:
                parts.append('lawyer legal action')
            if refund:
                parts.append('double charged need refund')
            age_h = 80 if breached else 0.5
            ticket = {
                'subject': ' '.join(parts) or 'General question',
                'body': 'Details here',
                'rating': 1 if one_star else 5,
                'createdAt': (now - timedelta(hours=age_h)).isoformat().replace('+00:00', 'Z'),
                'status': 'open',
            }
            res = triage_gate.classify_ticket(ticket, policy, now)
            any_risk = any((outage, security, legal, refund, one_star, breached))
            self.assertEqual(res['requiresHumanApproval'], any_risk)
            self.assertEqual(res['autoReplyAllowed'], not any_risk)
            if outage or security or legal:
                self.assertEqual(res['priority'], 'P0')
            elif refund or one_star:
                self.assertEqual(res['priority'], 'P1')
        self.assertEqual(checked, 64)

    def test_class_b_bfs_reply_guard_tamper_pinning_and_idempotency(self):
        """Class B BFS exploration: no action sequence can send unapproved, tampered, leaky, or duplicate replies."""
        # Seed one escalated ticket
        ingest_feedback.merge_tickets(self.ws, [{
            'ticketId': 'email:t-99',
            'channel': 'email',
            'externalId': 't-99',
            'customer': 'user@example.com',
            'subject': 'Billing dispute refund request',
            'body': 'I was double charged',
            'createdAt': '2026-11-25T10:00:00Z',
            'status': 'open',
        }])
        triage_gate.run_triage(self.ws, now=datetime(2026, 11, 25, 11, 0, tzinfo=timezone.utc), write_report=True)

        # Abstract state: (staged, approved, tampered, has_leak, sent_count)
        start = (False, False, False, False, 0)
        visited = {start}
        q = deque([start])

        while q:
            staged, approved, tampered, has_leak, sent_count = q.popleft()
            # Reify concrete workspace state and verify check_send / record_sent invariants
            with tempfile.TemporaryDirectory() as td:
                tws = Path(td) / 'ws'
                init_workspace.init_workspace(tws)
                ingest_feedback.merge_tickets(tws, [{
                    'ticketId': 'email:t-99', 'channel': 'email', 'externalId': 't-99',
                    'customer': 'u@example.com', 'subject': 'Billing refund', 'body': 'Double charged',
                    'createdAt': '2026-11-25T10:00:00Z', 'status': 'open',
                }])
                triage_gate.run_triage(tws, now=datetime(2026, 11, 25, 11, 0, tzinfo=timezone.utc), write_report=True)
                now = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)

                if staged:
                    clean_body = 'Thank you for reaching out. Our billing team is reviewing your duplicate charge.'
                    fake_path = '/' + 'Users/' + 'alice/secret'
                    fake_key = 'sk' + '-' + '1234567890abcdef1234'
                    bad_body = f'Hi {{{{name}}}}, check {fake_path} {fake_key}'
                    reply_guard.stage_draft(tws, 'email:t-99', bad_body if has_leak else clean_body, draft_id='d1')
                    if approved and not has_leak:
                        reply_guard.approve_draft(tws, 'd1', 'commander')
                    if tampered:
                        qp = tws / 'outbound-queue.json'
                        qd = json.loads(qp.read_text(encoding='utf-8'))
                        qd['drafts']['d1']['body'] += ' We guarantee a full refund.'
                        qp.write_text(json.dumps(qd), encoding='utf-8')
                    if sent_count > 0:
                        with (tws / 'reply-log.jsonl').open('a', encoding='utf-8') as fh:
                            fh.write(json.dumps({
                                'draftId': 'prev', 'ticketId': 'email:t-99',
                                'bodyHash': reply_guard.body_hash(clean_body),
                                'sentAt': '2026-11-25T11:30:00Z',
                            }) + '\n')

                    gate = reply_guard.check_send(tws, 'd1', now=now)
                    should_allow = approved and (not tampered) and (not has_leak) and (sent_count == 0)
                    self.assertEqual(gate['allowed'], should_allow, f'State {(staged, approved, tampered, has_leak, sent_count)} got {gate}')
                    if should_allow:
                        rec = reply_guard.record_sent(tws, 'd1', 'ext-reply-1', now=now)
                        self.assertEqual(rec['externalReplyId'], 'ext-reply-1')
                        # Immediate second send attempt MUST fail (idempotency)
                        with self.assertRaises(ValueError):
                            reply_guard.record_sent(tws, 'd1', 'ext-reply-2', now=now)

            # Explore reachable next states
            next_states = []
            if not staged:
                next_states.append((True, False, False, False, 0))
                next_states.append((True, False, False, True, 0))
            else:
                if not approved and not has_leak:
                    next_states.append((True, True, False, False, sent_count))
                if not tampered:
                    next_states.append((True, approved, True, has_leak, sent_count))
                if approved and not tampered and not has_leak and sent_count == 0:
                    next_states.append((True, True, False, False, 1))
            for ns in next_states:
                if ns not in visited:
                    visited.add(ns)
                    q.append(ns)

        self.assertGreaterEqual(len(visited), 8)

    def test_anti_false_consensus_unique_customers_churn_and_kb_deflection(self):
        """One loud customer sending 4 tickets must NOT trigger a global spike; 3 distinct routine users trigger KB deflection."""
        now = datetime(2026, 11, 25, 16, 0, tzinfo=timezone.utc)
        tickets = [
            # 4 tickets from the EXACT same noisy user -> uniqueCustomers == 1 -> MUST NOT spike
            {'ticketId': f'email:loud-{i}', 'channel': 'email', 'externalId': f'loud-{i}', 'customer': 'loud@example.com', 'subject': 'Dark mode toggle', 'body': 'Please add toggle', 'createdAt': '2026-11-25T10:00:00Z', 'status': 'open', 'rootCauseId': 'single-user-noise'}
            for i in range(4)
        ] + [
            # 3 distinct routine customers asking how to export CSV -> MUST flag KB deflection candidate & real spike
            {'ticketId': f'email:kb-{i}', 'channel': 'email', 'externalId': f'kb-{i}', 'customer': f'cust{i}@example.com', 'subject': 'How to export CSV?', 'body': 'Where is export?', 'createdAt': '2026-11-25T14:00:00Z', 'status': 'open', 'rootCauseId': 'how-to-export-csv'}
            for i in range(3)
        ] + [
            # Paying user churn signal -> MUST escalate to P1
            {'ticketId': 'email:churn-1', 'channel': 'email', 'externalId': 'churn-1', 'customer': 'vip@corp.com', 'subject': 'Switching to competitor', 'body': 'We will cancel my subscription next week.', 'createdAt': '2026-11-25T15:00:00Z', 'status': 'open'}
        ]
        ingest_feedback.merge_tickets(self.ws, tickets)
        rep = triage_gate.run_triage(self.ws, now=now, write_report=True)
        spike_ids = {s['rootCauseId'] for s in rep['spikes']}
        self.assertNotIn('single-user-noise', spike_ids)
        self.assertIn('how-to-export-csv', spike_ids)
        kb_ids = {k['rootCauseId'] for k in rep['kbDeflectionCandidates']}
        self.assertIn('how-to-export-csv', kb_ids)
        churn_esc = [e for e in rep['escalations'] if e['ticketId'] == 'email:churn-1']
        self.assertEqual(len(churn_esc), 1)
        self.assertEqual(churn_esc[0]['priority'], 'P1')
        self.assertIn('churn_signal', churn_esc[0]['reasons'])


if __name__ == '__main__':
    unittest.main()
