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
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / 'plugins/customer-support-ops'
SCRIPTS = PLUGIN_ROOT / 'scripts'


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

    def test_init_workspace_clean_schema_without_board_pollution(self):
        """init_workspace creates only data directories (no boards/) and seeds spikeMinUniqueCustomers."""
        self.assertFalse((self.ws / 'boards').exists())
        policy = json.loads((self.ws / 'sla-policy.json').read_text(encoding='utf-8'))
        self.assertEqual(policy['spikeMinUniqueCustomers'], 2)
        self.assertEqual(policy['replyCooldownHours'], 24)
        self.assertFalse(policy['requireApprovalForRoutine'])

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

        gh_meta: dict = {}
        gh_t = ingest_feedback.fetch_github_issues(
            'acme/app',
            state='open',
            limit=2,
            api_url=f'http://127.0.0.1:{port}/gh',
            meta=gh_meta,
        )
        self.assertEqual(len(gh_t), 1)
        self.assertTrue(gh_meta['truncated'])

        # Connector/JSONL normalized review preserving vip & rating
        jsonl_path = Path(self.tmp.name) / 'connector.jsonl'
        jsonl_path.write_text(json.dumps({
            'channel': 'appstore_ios', 'externalId': 'rev-1', 'customer': 'bob',
            'subject': 'Double charged', 'body': 'Please refund immediately',
            'rating': 1, 'vip': True, 'createdAt': '2026-11-25T05:00:00Z',
        }) + '\n', encoding='utf-8')
        conn_t = ingest_feedback.parse_jsonl_file(jsonl_path)
        self.assertEqual(len(conn_t), 1)
        self.assertTrue(conn_t[0]['vip'])

        # Real .eml + .mbox + .csv files (CSV with rating & root_cause_id)
        eml_path = Path(self.tmp.name) / 'msg1.eml'
        eml_path.write_text('From: carol@example.com\nSubject: How to export CSV?\nDate: Tue, 24 Nov 2026 12:00:00 +0000\nMessage-ID: <m1@example.com>\n\nCould you show me where export is?\n', encoding='utf-8')
        mbox_path = Path(self.tmp.name) / 'archive.mbox'
        mb = mailbox.mbox(str(mbox_path))
        mb.add('From: dave@example.com\nSubject: Sync fails on macOS\nDate: Tue, 24 Nov 2026 13:00:00 +0000\nMessage-ID: <m2@example.com>\n\nSync hangs on startup.\n')
        mb.flush()
        mb.close()
        csv_path = Path(self.tmp.name) / 'zendesk.csv'
        csv_path.write_text(
            'id,subject,description,requester,created_at,rating,root_cause_id\n'
            'Z-1,Sync fails on macOS,Stuck at 0%,eve@example.com,2026-11-24T14:00:00Z,4,macos-sync-hang\n'
            'Z-2,Sync fails again,Freezes after update,frank@example.com,2026-11-24T15:00:00Z,3,macos-sync-hang\n',
            encoding='utf-8',
        )
        csv_t = ingest_feedback.parse_csv_file(csv_path)
        self.assertEqual(csv_t[0]['rating'], 4)
        self.assertEqual(csv_t[0]['rootCauseId'], 'macos-sync-hang')

        all_in = gh_t + conn_t + ingest_feedback.parse_eml_path(eml_path) + ingest_feedback.parse_mbox_file(mbox_path) + csv_t
        res1 = ingest_feedback.merge_tickets(self.ws, all_in)
        self.assertEqual(res1['added'], 6)
        # Re-ingesting exact same batch must add 0 new tickets
        res2 = ingest_feedback.merge_tickets(self.ws, all_in)
        self.assertEqual(res2['added'], 0)

        # Assign rootCauseId to the mbox ticket so 3 distinct customers hit macos-sync-hang
        t_path = self.ws / 'tickets/tickets.json'
        store = json.loads(t_path.read_text(encoding='utf-8'))
        store['tickets']['email:m2@example.com']['rootCauseId'] = 'macos-sync-hang'
        t_path.write_text(json.dumps(store), encoding='utf-8')

        now = datetime(2026, 11, 25, 16, 0, tzinfo=timezone.utc)
        report = triage_gate.run_triage(self.ws, now=now, write_report=True)
        self.assertEqual(report['openCountsByPriority']['P0'], 1)
        self.assertEqual(report['openCountsByPriority']['P1'], 1)
        self.assertGreaterEqual(report['slaBreachCount'], 2)
        self.assertEqual(report['spikeCount'], 1)
        self.assertEqual(report['spikes'][0]['rootCauseId'], 'macos-sync-hang')
        self.assertIn('macos-sync-hang', report['clusterMetrics'])

        boards_out = Path(self.tmp.name) / 'space-boards'
        b1 = build_boards.project_board(self.ws, 'triage-sla-board', boards_out / 'triage-sla-board')
        b2 = build_boards.project_board(self.ws, 'root-cause-board', boards_out / 'root-cause-board')
        self.assertEqual(json.loads(b1.read_text())['summary']['escalationCount'], report['escalationCount'])
        self.assertEqual(json.loads(b2.read_text())['summary']['spikeCount'], 1)

    def test_monotonic_triage_preservation_and_missing_policy_fallback(self):
        """Re-running triage never downgrades human/model P0/P1 or clears requiresHumanApproval, and works without sla-policy.json."""
        (self.ws / 'sla-policy.json').unlink()
        now = datetime(2026, 11, 25, 16, 0, tzinfo=timezone.utc)
        ingest_feedback.merge_tickets(self.ws, [
            {
                # Subtle wording with zero keyword matches, already marked P0 by human/model
                'ticketId': 'connector:subtle-p0',
                'channel': 'connector',
                'externalId': 'subtle-p0',
                'customer': 'enterprise@corp.com',
                'subject': 'Checkout summary mismatch for EU region',
                'body': '300 accounts saw empty receipts after morning deploy.',
                'createdAt': '2026-11-25T15:40:00Z',
                'status': 'open',
                'priority': 'P0',
                'requiresHumanApproval': True,
                'escalationReasons': ['model_assessed_revenue_loss'],
            },
            {
                # Already P0 with a P1 keyword match -> must stay P0 and merge both reasons
                'ticketId': 'connector:p0-plus-refund',
                'channel': 'connector',
                'externalId': 'p0-plus-refund',
                'customer': 'cto@corp.com',
                'subject': 'Please refund this invoice',
                'body': 'Following up on our incident call.',
                'createdAt': '2026-11-25T15:45:00Z',
                'status': 'open',
                'priority': 'P0',
                'requiresHumanApproval': True,
                'escalationReasons': ['executive_escalation'],
            },
            {
                # Explicit riskFlags + vip without keywords
                'ticketId': 'connector:explicit-flag',
                'channel': 'connector',
                'externalId': 'explicit-flag',
                'customer': 'vip@corp.com',
                'subject': 'Account question',
                'body': 'Need clarification on audit trail.',
                'createdAt': '2026-11-25T15:50:00Z',
                'status': 'open',
                'vip': True,
                'riskFlags': ['security_privacy'],
            },
        ])

        report = triage_gate.run_triage(self.ws, now=now, write_report=True)
        store = json.loads((self.ws / 'tickets/tickets.json').read_text(encoding='utf-8'))['tickets']

        t1 = store['connector:subtle-p0']
        self.assertEqual(t1['priority'], 'P0')
        self.assertTrue(t1['requiresHumanApproval'])
        self.assertIn('model_assessed_revenue_loss', t1['escalationReasons'])
        self.assertEqual(t1['heuristicSignals'], [])

        t2 = store['connector:p0-plus-refund']
        self.assertEqual(t2['priority'], 'P0')
        self.assertIn('executive_escalation', t2['escalationReasons'])
        self.assertIn('billing_refund', t2['escalationReasons'])
        self.assertIn('billing_refund', t2['heuristicSignals'])

        t3 = store['connector:explicit-flag']
        self.assertEqual(t3['priority'], 'P0')
        self.assertIn('security_privacy', t3['escalationReasons'])
        self.assertIn('vip_customer', t3['escalationReasons'])
        self.assertEqual(report['openCountsByPriority']['P0'], 3)

    def test_real_cluster_metrics_for_steady_clusters_and_latest_draft_selection(self):
        """Non-spiking clusters report real 7d/prior-7d trends (never fabricated from totalTickets); boards pick latest draft by stagedAt."""
        now = datetime(2026, 11, 25, 16, 0, tzinfo=timezone.utc)
        tickets = [
            # 2 recent7d + 3 prior7d + 2 older (total 7) -> steady, NOT spiking (ratio 2/3 = 0.67)
            {'ticketId': 'email:s-r1', 'channel': 'email', 'externalId': 's-r1', 'customer': 'c1@x.com', 'subject': 'Theme tweak', 'body': 'Color', 'createdAt': '2026-11-24T10:00:00Z', 'status': 'open', 'rootCauseId': 'steady-theme'},
            {'ticketId': 'email:s-r2', 'channel': 'email', 'externalId': 's-r2', 'customer': 'c2@x.com', 'subject': 'Theme tweak 2', 'body': 'Font', 'createdAt': '2026-11-23T10:00:00Z', 'status': 'open', 'rootCauseId': 'steady-theme'},
            {'ticketId': 'email:s-p1', 'channel': 'email', 'externalId': 's-p1', 'customer': 'c3@x.com', 'subject': 'Old theme 1', 'body': 'Font', 'createdAt': '2026-11-15T10:00:00Z', 'status': 'resolved', 'rootCauseId': 'steady-theme'},
            {'ticketId': 'email:s-p2', 'channel': 'email', 'externalId': 's-p2', 'customer': 'c4@x.com', 'subject': 'Old theme 2', 'body': 'Font', 'createdAt': '2026-11-14T10:00:00Z', 'status': 'resolved', 'rootCauseId': 'steady-theme'},
            {'ticketId': 'email:s-p3', 'channel': 'email', 'externalId': 's-p3', 'customer': 'c5@x.com', 'subject': 'Old theme 3', 'body': 'Font', 'createdAt': '2026-11-13T10:00:00Z', 'status': 'resolved', 'rootCauseId': 'steady-theme'},
            {'ticketId': 'email:s-a1', 'channel': 'email', 'externalId': 's-a1', 'customer': 'c6@x.com', 'subject': 'Ancient 1', 'body': 'Font', 'createdAt': '2026-11-01T10:00:00Z', 'status': 'resolved', 'rootCauseId': 'steady-theme'},
            {'ticketId': 'email:s-a2', 'channel': 'email', 'externalId': 's-a2', 'customer': 'c7@x.com', 'subject': 'Ancient 2', 'body': 'Font', 'createdAt': '2026-10-28T10:00:00Z', 'status': 'resolved', 'rootCauseId': 'steady-theme'},
        ]
        ingest_feedback.merge_tickets(self.ws, tickets)
        report = triage_gate.run_triage(self.ws, now=now, write_report=True)

        cm = report['clusterMetrics']['steady-theme']
        self.assertFalse(cm['isSpiking'])
        self.assertEqual(cm['totalTickets'], 7)
        self.assertEqual(cm['recent7dCount'], 2)
        self.assertEqual(cm['prior7dCount'], 3)
        self.assertEqual(cm['spikeRatio'], 0.67)

        rc_payload = build_boards.build_root_cause_payload(self.ws)
        steady_card = next(i for i in rc_payload['issues'] if i['rootCauseId'] == 'steady-theme')
        self.assertEqual(steady_card['recent7dCount'], 2)
        self.assertEqual(steady_card['prior7dCount'], 3)
        self.assertEqual(steady_card['spikeRatio'], 0.67)
        self.assertFalse(steady_card['isSpiking'])

        # Multi-draft selection: board must pick latest draft by stagedAt descending regardless of dict insertion order
        queue_path = self.ws / 'outbound-queue.json'
        queue_path.write_text(json.dumps({
            'schemaVersion': 'customer-support-outbound/1',
            'drafts': {
                'd-newer': {'draftId': 'd-newer', 'ticketId': 'email:s-r1', 'status': 'approved', 'stagedAt': '2026-11-25T15:00:00Z'},
                'd-older': {'draftId': 'd-older', 'ticketId': 'email:s-r1', 'status': 'blocked', 'stagedAt': '2026-11-25T10:00:00Z'},
            },
        }), encoding='utf-8')
        triage_payload = build_boards.build_triage_payload(self.ws)
        row = next(t for t in triage_payload['tickets'] if t['ticketId'] == 'email:s-r1')
        self.assertEqual(row['draftStatus'], 'approved')

    def test_single_writer_routine_ready_and_followup_cooldown_unlock(self):
        """record_sent never writes tickets.json; routine tickets stage ready_to_send; follow-ups unlock on new inbound or post-send approval."""
        t0 = datetime(2026, 11, 25, 10, 0, tzinfo=timezone.utc)
        ingest_feedback.merge_tickets(self.ws, [{
            'ticketId': 'email:routine-1',
            'channel': 'email',
            'externalId': 'routine-1',
            'customer': 'user@example.com',
            'subject': 'Where is CSV export?',
            'body': 'Can you point me to the export button?',
            'createdAt': '2026-11-25T09:30:00Z',
            'status': 'open',
        }])
        triage_gate.run_triage(self.ws, now=t0, write_report=True)

        # Routine P3 ticket stages as ready_to_send and passes check_send without human approval
        d1 = reply_guard.stage_draft(self.ws, 'email:routine-1', 'Open Settings -> Data -> Export CSV to download.', draft_id='d1')
        self.assertEqual(d1['status'], 'ready_to_send')
        self.assertFalse(d1['requiresHumanApproval'])

        tickets_before = (self.ws / 'tickets/tickets.json').read_bytes()
        gate1 = reply_guard.check_send(self.ws, 'd1', now=t0)
        self.assertTrue(gate1['allowed'])
        reply_guard.record_sent(self.ws, 'd1', 'ext-1', now=t0)
        tickets_after = (self.ws / 'tickets/tickets.json').read_bytes()
        # Single-writer invariant: tickets/tickets.json is untouched by reply_guard.record_sent
        self.assertEqual(tickets_before, tickets_after)

        # Boards & triage derive 'replied' status directly from reply-log.jsonl
        board_after_send = build_boards.build_triage_payload(self.ws)
        self.assertEqual(board_after_send['summary']['openCount'], 0)
        self.assertEqual(board_after_send['tickets'][0]['status'], 'replied')
        rep_after_send = triage_gate.run_triage(self.ws, now=t0 + timedelta(hours=100), write_report=False)
        self.assertEqual(rep_after_send['openCountsByPriority']['P3'], 0)
        self.assertEqual(rep_after_send['slaBreachCount'], 0)

        # Unapproved new message within 24h without new inbound -> blocked by cooldown
        t1 = t0 + timedelta(hours=2)
        reply_guard.stage_draft(self.ws, 'email:routine-1', 'Also note exports use UTF-8 encoding.', draft_id='d2')
        gate_blocked = reply_guard.check_send(self.ws, 'd2', now=t1)
        self.assertFalse(gate_blocked['allowed'])
        self.assertIn('ticket_in_reply_cooldown', gate_blocked['reasons'])

        # Duplicate exact body hash -> ALWAYS blocked even with human approval or new inbound
        reply_guard.stage_draft(self.ws, 'email:routine-1', 'Open Settings -> Data -> Export CSV to download.', draft_id='d-dup')
        reply_guard.approve_draft(self.ws, 'd-dup', 'commander', now=t1)
        gate_dup = reply_guard.check_send(self.ws, 'd-dup', now=t1, force_followup=True)
        self.assertFalse(gate_dup['allowed'])
        self.assertIn('duplicate_reply_hash', gate_dup['reasons'])

        # Unlock path 1: explicit human approval after last send unlocks cooldown for new follow-up text
        reply_guard.approve_draft(self.ws, 'd2', 'commander', now=t1)
        gate_approved_followup = reply_guard.check_send(self.ws, 'd2', now=t1)
        self.assertTrue(gate_approved_followup['allowed'])
        reply_guard.record_sent(self.ws, 'd2', 'ext-2', now=t1)

        # Unlock path 2: customer sends newer inbound message (lastInboundAt > lastSentAt)
        t2 = t1 + timedelta(hours=1)
        store = json.loads((self.ws / 'tickets/tickets.json').read_text(encoding='utf-8'))
        store['tickets']['email:routine-1']['lastInboundAt'] = (t1 + timedelta(minutes=30)).isoformat().replace('+00:00', 'Z')
        (self.ws / 'tickets/tickets.json').write_text(json.dumps(store), encoding='utf-8')
        reply_guard.stage_draft(self.ws, 'email:routine-1', 'Yes, date columns are formatted as ISO-8601 UTC.', draft_id='d3')
        gate_inbound_followup = reply_guard.check_send(self.ws, 'd3', now=t2)
        self.assertTrue(gate_inbound_followup['allowed'])

        # Structured JSON error on stderr + non-zero exit code for CLI failures
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / 'reply_guard.py'), str(self.ws), 'approve', '--draft-id', 'no-such-draft', '--approved-by', 'commander'],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        err_obj = json.loads(proc.stderr)
        self.assertIn('error', err_obj)

    def test_class_a_exhaustive_risk_escalation_invariants(self):
        """Class A exhaustive proof: every combination of 6 risk flags obeys escalation & autoReplyAllowed=False."""
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
        # Abstract state: (staged, approved, tampered, has_leak, sent_count)
        start = (False, False, False, False, 0)
        visited = {start}
        q = deque([start])

        while q:
            staged, approved, tampered, has_leak, sent_count = q.popleft()
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
                        reply_guard.approve_draft(tws, 'd1', 'commander', now=datetime(2026, 11, 25, 11, 15, tzinfo=timezone.utc))
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
                        with self.assertRaises(ValueError):
                            reply_guard.record_sent(tws, 'd1', 'ext-reply-2', now=now)

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
            {'ticketId': f'email:loud-{i}', 'channel': 'email', 'externalId': f'loud-{i}', 'customer': 'loud@example.com', 'subject': 'Dark mode toggle', 'body': 'Please add toggle', 'createdAt': '2026-11-25T10:00:00Z', 'status': 'open', 'rootCauseId': 'single-user-noise'}
            for i in range(4)
        ] + [
            {'ticketId': f'email:kb-{i}', 'channel': 'email', 'externalId': f'kb-{i}', 'customer': f'cust{i}@example.com', 'subject': 'How to export CSV?', 'body': 'Where is export?', 'createdAt': '2026-11-25T14:00:00Z', 'status': 'open', 'rootCauseId': 'how-to-export-csv'}
            for i in range(3)
        ] + [
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

    def test_board_sdk_contracts_and_strict_boolean_parsing(self):
        """Board shared bridge wires onDisplayChange, runtimeTouched includes shared assets, and boolean command parser rejects invalid strings."""
        bridge_js = (PLUGIN_ROOT / 'assets/boards/shared/board-sdk-bridge.js').read_text(encoding='utf-8')
        css_text = (PLUGIN_ROOT / 'assets/boards/shared/board-ui.css').read_text(encoding='utf-8')
        triage_html = (PLUGIN_ROOT / 'assets/boards/triage-sla-board/index.html').read_text(encoding='utf-8')
        rc_html = (PLUGIN_ROOT / 'assets/boards/root-cause-board/index.html').read_text(encoding='utf-8')

        self.assertIn('customer-support-ops', bridge_js)
        self.assertIn('customer-support-ops', css_text)
        self.assertIn('onDisplayChange', bridge_js)
        self.assertIn('assets/board-sdk-bridge.js', bridge_js)
        self.assertIn('assets/board-ui.css', bridge_js)
        self.assertIn('parseBooleanParam', triage_html)
        self.assertIn('parseBooleanParam', rc_html)
        self.assertIn('Draft Triage Prompt', triage_html)
        self.assertIn('Draft Engineering Escalation', rc_html)
        self.assertIn('data-mark-ignore', triage_html)
        self.assertIn('data-mark-ignore', rc_html)


if __name__ == '__main__':
    unittest.main()
