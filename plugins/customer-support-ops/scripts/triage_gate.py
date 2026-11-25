#!/usr/bin/env python3
"""Deterministic triage, P0/security/refund/legal escalation, SLA breach detection, and root-cause spike detector."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re

RISK_RULES: list[tuple[str, str, re.Pattern[str]]] = [
    ('p0_outage', 'P0', re.compile(r'\b(outage|service\s+down|complete\s+down|data\s+loss|cannot\s+login|all\s+users\s+blocked|500\s+error|production\s+crash)\b|无法登录|服务宕机|数据丢失|全员报错', re.I)),
    ('security_privacy', 'P0', re.compile(r'\b(security\s+vulnerability|data\s+breach|unauthorized\s+access|leaked\s+data|gdpr\s+deletion|cve-|xss|sql\s+injection)\b|数据泄露|安全漏洞|隐私违规', re.I)),
    ('legal_regulatory', 'P0', re.compile(r'\b(lawsuit|attorney|lawyer|legal\s+action|subpoena|regulator|ftc|attorney\s+general)\b|律师函|起诉|监管投诉|消协', re.I)),
    ('billing_refund', 'P1', re.compile(r'\b(refund|chargeback|double\s+charged|unauthorized\s+charge|billing\s+dispute|cancel\s+and\s+refund)\b|退款|重复扣费|误扣费|拒付', re.I)),
    ('churn_signal', 'P1', re.compile(r'\b(cancel\s+my\s+subscription|canceling\s+our\s+plan|switching\s+to|migrating\s+away|will\s+not\s+renew)\b|不续费|注销账号|换别家|迁移走', re.I)),
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_ts(raw: str) -> datetime:
    dt = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def classify_ticket(ticket: dict, policy: dict, now: datetime) -> dict:
    text = f"{ticket.get('subject', '')}\n{ticket.get('body', '')}"
    labels = {str(x).lower() for x in (ticket.get('labels') or [])}
    reasons: list[str] = []
    priority = 'P3'

    rank = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}

    def raise_priority(target: str) -> None:
        nonlocal priority
        if rank[target] < rank[priority]:
            priority = target

    for code, sev, pat in RISK_RULES:
        if pat.search(text):
            reasons.append(code)
            raise_priority(sev)

    if {'security', 'p0', 'outage', 'incident'} & labels:
        if 'label_p0' not in reasons:
            reasons.append('label_p0')
        raise_priority('P0')
    elif {'bug', 'billing', 'refund', 'p1'} & labels:
        if 'billing' in labels or 'refund' in labels:
            reasons.append('billing_refund')
        raise_priority('P1')

    rating = ticket.get('rating')
    if isinstance(rating, int) and rating <= 1:
        reasons.append('one_star_review')
        raise_priority('P1')
    elif isinstance(rating, int) and rating == 2:
        raise_priority('P2')

    if ticket.get('vip') is True:
        reasons.append('vip_customer')
        raise_priority('P1')

    sla_hours_map = policy.get('firstResponseHours') or {'P0': 1, 'P1': 4, 'P2': 24, 'P3': 72}
    sla_limit = float(sla_hours_map.get(priority, 72))
    created_dt = parse_ts(ticket.get('createdAt') or now.isoformat())
    age_hours = max(0.0, round((now - created_dt).total_seconds() / 3600.0, 2))
    is_open = ticket.get('status') in {'open', 'pending_human'}
    sla_breached = is_open and age_hours > sla_limit

    if sla_breached:
        reasons.append('sla_breached')

    requires_human = bool(reasons) or priority in {'P0', 'P1'}
    return {
        'priority': priority,
        'escalationReasons': sorted(set(reasons)),
        'requiresHumanApproval': requires_human,
        'autoReplyAllowed': not requires_human,
        'ageHours': age_hours,
        'slaLimitHours': sla_limit,
        'slaBreached': sla_breached,
    }


def run_triage(workspace: Path, *, now: datetime | None = None, write_report: bool = True) -> dict:
    workspace = workspace.expanduser().resolve()
    now_dt = now or utc_now()
    policy = json.loads((workspace / 'sla-policy.json').read_text(encoding='utf-8'))
    store_path = workspace / 'tickets/tickets.json'
    store = json.loads(store_path.read_text(encoding='utf-8'))
    tickets_map = store.get('tickets', {})

    escalations = []
    sla_breaches = []
    priority_counts = {'P0': 0, 'P1': 0, 'P2': 0, 'P3': 0}

    recent_cutoff = now_dt - timedelta(days=7)
    prior_cutoff = now_dt - timedelta(days=14)
    cluster_recent: dict[str, list[dict]] = {}
    cluster_prior: dict[str, int] = {}

    for tid, ticket in tickets_map.items():
        res = classify_ticket(ticket, policy, now_dt)
        ticket.update(res)
        if ticket.get('status') in {'open', 'pending_human'}:
            priority_counts[res['priority']] += 1
            if res['requiresHumanApproval']:
                escalations.append({
                    'ticketId': tid,
                    'priority': res['priority'],
                    'reasons': res['escalationReasons'],
                    'subject': ticket.get('subject', ''),
                    'customer': ticket.get('customer', ''),
                    'ageHours': res['ageHours'],
                    'slaBreached': res['slaBreached'],
                })
            if res['slaBreached']:
                sla_breaches.append(tid)

        rc = ticket.get('rootCauseId')
        if rc:
            ts = parse_ts(ticket.get('createdAt') or now_dt.isoformat())
            if ts >= recent_cutoff:
                cluster_recent.setdefault(rc, []).append({
                    'ticketId': tid,
                    'customer': str(ticket.get('customer') or tid).strip().lower(),
                    'priority': res['priority'],
                    'subject': ticket.get('subject', ''),
                    'url': ticket.get('url', ''),
                    'createdAt': ticket.get('createdAt', ''),
                })
            elif ts >= prior_cutoff:
                cluster_prior[rc] = cluster_prior.get(rc, 0) + 1

    min_recent = int(policy.get('spikeMinRecentCount', 3))
    min_unique = int(policy.get('spikeMinUniqueCustomers', 2))
    ratio_thresh = float(policy.get('spikeRatioThreshold', 2.0))
    spikes = []
    kb_deflection_candidates = []
    for rc, items in sorted(cluster_recent.items()):
        recent_n = len(items)
        unique_custs = len({it['customer'] for it in items})
        prior_n = cluster_prior.get(rc, 0)
        ratio = float(recent_n) if prior_n == 0 else round(recent_n / prior_n, 2)
        # Anti-false-consensus invariant: one loud user sending repeated tickets cannot trigger a global spike.
        is_spike = recent_n >= min_recent and unique_custs >= min_unique and (prior_n == 0 or ratio >= ratio_thresh)
        if is_spike:
            spikes.append({
                'rootCauseId': rc,
                'recent7dCount': recent_n,
                'uniqueCustomers': unique_custs,
                'prior7dCount': prior_n,
                'spikeRatio': ratio,
                'evidenceTickets': items[:10],
            })
        routine_items = [it for it in items if it['priority'] in {'P2', 'P3'}]
        routine_unique = len({it['customer'] for it in routine_items})
        if routine_unique >= 3:
            kb_deflection_candidates.append({
                'rootCauseId': rc,
                'uniqueCustomers': routine_unique,
                'ticketCount': len(routine_items),
                'sampleSubjects': [it['subject'] for it in routine_items[:5]],
            })

    escalations.sort(key=lambda e: ({'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}[e['priority']], -e['ageHours']))
    report = {
        'schemaVersion': 'customer-support-triage/1',
        'generatedAt': now_dt.isoformat().replace('+00:00', 'Z'),
        'openCountsByPriority': priority_counts,
        'escalationCount': len(escalations),
        'slaBreachCount': len(sla_breaches),
        'spikeCount': len(spikes),
        'kbDeflectionCandidateCount': len(kb_deflection_candidates),
        'escalations': escalations,
        'slaBreaches': sorted(sla_breaches),
        'spikes': spikes,
        'kbDeflectionCandidates': kb_deflection_candidates,
    }

    if write_report:
        store['updatedAt'] = report['generatedAt']
        store_path.write_text(json.dumps(store, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        (workspace / 'sla-report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Run deterministic triage, SLA, and spike detection.')
    parser.add_argument('workspace', help='Path to customer-support-ops workspace')
    parser.add_argument('--write-report', action='store_true')
    args = parser.parse_args()
    report = run_triage(Path(args.workspace), write_report=args.write_report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
