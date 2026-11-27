#!/usr/bin/env python3
"""Deterministic triage, monotonic escalation preservation, SLA breach detection, and root-cause spike detector."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re

DEFAULT_SLA_POLICY = {
    'schemaVersion': 'customer-support-sla/1',
    'firstResponseHours': {'P0': 1, 'P1': 4, 'P2': 24, 'P3': 72},
    'replyCooldownHours': 24,
    'spikeMinRecentCount': 3,
    'spikeMinUniqueCustomers': 2,
    'spikeRatioThreshold': 2.0,
    'requireApprovalForRoutine': False,
}

PRIORITY_RANK = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}

EXPLICIT_RISK_SEVERITY = {
    'p0_outage': 'P0',
    'security_privacy': 'P0',
    'legal_regulatory': 'P0',
    'label_p0': 'P0',
    'billing_refund': 'P1',
    'churn_signal': 'P1',
    'one_star_review': 'P1',
    'vip_customer': 'P1',
}

# Monotonic heuristic safety nets: only elevate priority or add escalation signals, never downgrade existing assessments.
HEURISTIC_RISK_RULES: list[tuple[str, str, re.Pattern[str]]] = [
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


def load_policy(data_dir: Path) -> dict:
    policy_path = data_dir / 'sla-policy.json'
    if not policy_path.is_file():
        return dict(DEFAULT_SLA_POLICY)
    try:
        loaded = json.loads(policy_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_SLA_POLICY)
    if not isinstance(loaded, dict):
        return dict(DEFAULT_SLA_POLICY)
    merged = dict(DEFAULT_SLA_POLICY)
    merged.update(loaded)
    return merged


def load_latest_sent_by_ticket(data_dir: Path) -> dict[str, datetime]:
    """Derive latest outbound reply timestamp per ticket from append-only reply-log.jsonl."""
    log_path = data_dir / 'reply-log.jsonl'
    if not log_path.is_file():
        return {}
    latest: dict[str, datetime] = {}
    for line in log_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        tid = row.get('ticketId')
        sent_raw = row.get('sentAt')
        if not tid or not sent_raw:
            continue
        try:
            sent_dt = parse_ts(str(sent_raw))
        except ValueError:
            continue
        if tid not in latest or sent_dt > latest[tid]:
            latest[tid] = sent_dt
    return latest


def derive_effective_status(ticket: dict, latest_sent: datetime | None) -> str:
    base_status = str(ticket.get('status') or 'open')
    if base_status in {'resolved', 'closed'}:
        return base_status
    if latest_sent is not None:
        inbound_raw = ticket.get('lastInboundAt') or ticket.get('createdAt')
        if inbound_raw:
            try:
                inbound_dt = parse_ts(str(inbound_raw))
                if latest_sent >= inbound_dt:
                    return 'replied'
            except ValueError:
                return 'replied'
        else:
            return 'replied'
    return base_status


def classify_ticket(
    ticket: dict,
    policy: dict,
    now: datetime,
    *,
    latest_sent: datetime | None = None,
) -> dict:
    # Monotonic baseline: preserve any human/model-assigned priority, escalation reasons, and approval requirement.
    existing_priority = ticket.get('priority')
    priority = existing_priority if existing_priority in PRIORITY_RANK else 'P3'
    existing_requires_human = ticket.get('requiresHumanApproval') is True

    # Preserve existing non-transient escalation reasons; recompute transient sla_breached freshly below.
    reasons: set[str] = {
        str(r).strip()
        for r in (ticket.get('escalationReasons') or [])
        if str(r).strip() and str(r).strip() != 'sla_breached'
    }

    def raise_priority(target: str) -> None:
        nonlocal priority
        if target in PRIORITY_RANK and PRIORITY_RANK[target] < PRIORITY_RANK[priority]:
            priority = target

    # 1. Explicit riskFlags & preserved escalationReasons (authoritative objective/model signals)
    explicit_flags = [str(f).strip() for f in (ticket.get('riskFlags') or []) if str(f).strip()]
    for flag in explicit_flags:
        reasons.add(flag)
    for code in list(reasons):
        sev = EXPLICIT_RISK_SEVERITY.get(code)
        if sev:
            raise_priority(sev)

    # 2. Objective structured metadata: labels, rating, vip
    labels = {str(x).strip().lower() for x in (ticket.get('labels') or []) if str(x).strip()}
    if {'security', 'p0', 'outage', 'incident', 'legal'} & labels:
        reasons.add('label_p0')
        if 'security' in labels:
            reasons.add('security_privacy')
        if 'legal' in labels:
            reasons.add('legal_regulatory')
        raise_priority('P0')
    if {'bug', 'billing', 'refund', 'p1'} & labels:
        if 'billing' in labels or 'refund' in labels:
            reasons.add('billing_refund')
        raise_priority('P1')

    rating = ticket.get('rating')
    if isinstance(rating, int) and not isinstance(rating, bool):
        if rating <= 1:
            reasons.add('one_star_review')
            raise_priority('P1')
        elif rating == 2:
            raise_priority('P2')

    if ticket.get('vip') is True:
        reasons.add('vip_customer')
        raise_priority('P1')

    # 3. Monotonic heuristic signals (safety-net alerts only; never downgrade existing priority/reasons)
    text = f"{ticket.get('subject', '')}\n{ticket.get('body', '')}"
    heuristic_signals: list[str] = []
    for code, sev, pat in HEURISTIC_RISK_RULES:
        if pat.search(text):
            heuristic_signals.append(code)
            reasons.add(code)
            raise_priority(sev)

    # 4. Deterministic SLA timing based on effective reply state
    sla_hours_map = policy.get('firstResponseHours') or DEFAULT_SLA_POLICY['firstResponseHours']
    sla_limit = float(sla_hours_map.get(priority, 72))
    created_dt = parse_ts(ticket.get('createdAt') or now.isoformat())
    age_hours = max(0.0, round((now - created_dt).total_seconds() / 3600.0, 2))
    effective_status = derive_effective_status(ticket, latest_sent)
    is_open = effective_status in {'open', 'pending_human'}
    sla_breached = is_open and age_hours > sla_limit

    if sla_breached:
        reasons.add('sla_breached')

    require_for_routine = bool(policy.get('requireApprovalForRoutine', False))
    requires_human = (
        existing_requires_human
        or bool(reasons)
        or priority in {'P0', 'P1'}
        or require_for_routine
    )
    return {
        'priority': priority,
        'escalationReasons': sorted(reasons),
        'heuristicSignals': sorted(set(heuristic_signals)),
        'requiresHumanApproval': requires_human,
        'autoReplyAllowed': not requires_human,
        'effectiveStatus': effective_status,
        'ageHours': age_hours,
        'slaLimitHours': sla_limit,
        'slaBreached': sla_breached,
    }


def run_triage(data_dir: Path, *, now: datetime | None = None, write_report: bool = True) -> dict:
    data_dir = data_dir.expanduser().resolve()
    now_dt = now or utc_now()
    policy = load_policy(data_dir)
    store_path = data_dir / 'tickets/tickets.json'
    store = (
        json.loads(store_path.read_text(encoding='utf-8'))
        if store_path.is_file()
        else {'schemaVersion': 'customer-support-tickets/1', 'tickets': {}}
    )
    tickets_map = store.get('tickets', {})
    latest_sent_map = load_latest_sent_by_ticket(data_dir)

    escalations = []
    sla_breaches = []
    priority_counts = {'P0': 0, 'P1': 0, 'P2': 0, 'P3': 0}

    recent_cutoff = now_dt - timedelta(days=7)
    prior_cutoff = now_dt - timedelta(days=14)
    cluster_all: dict[str, list[dict]] = {}
    cluster_recent: dict[str, list[dict]] = {}
    cluster_prior: dict[str, int] = {}

    for tid, ticket in tickets_map.items():
        res = classify_ticket(ticket, policy, now_dt, latest_sent=latest_sent_map.get(tid))
        ticket.update(res)
        if res['effectiveStatus'] in {'open', 'pending_human'}:
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
            entry = {
                'ticketId': tid,
                'customer': str(ticket.get('customer') or tid).strip().lower(),
                'priority': res['priority'],
                'subject': ticket.get('subject', ''),
                'url': ticket.get('url', ''),
                'createdAt': ticket.get('createdAt', ''),
            }
            cluster_all.setdefault(rc, []).append(entry)
            ts = parse_ts(ticket.get('createdAt') or now_dt.isoformat())
            if ts >= recent_cutoff:
                cluster_recent.setdefault(rc, []).append(entry)
            elif ts >= prior_cutoff:
                cluster_prior[rc] = cluster_prior.get(rc, 0) + 1

    min_recent = int(policy.get('spikeMinRecentCount', 3))
    min_unique = int(policy.get('spikeMinUniqueCustomers', 2))
    ratio_thresh = float(policy.get('spikeRatioThreshold', 2.0))
    spikes = []
    kb_deflection_candidates = []
    cluster_metrics: dict[str, dict] = {}

    for rc in sorted(cluster_all.keys()):
        all_items = cluster_all[rc]
        recent_items = cluster_recent.get(rc, [])
        recent_n = len(recent_items)
        recent_unique = len({it['customer'] for it in recent_items})
        total_unique = len({it['customer'] for it in all_items})
        prior_n = cluster_prior.get(rc, 0)
        if recent_n == 0:
            ratio = 0.0
        elif prior_n == 0:
            ratio = float(recent_n)
        else:
            ratio = round(recent_n / prior_n, 2)
        # Anti-false-consensus invariant: one loud user sending repeated tickets cannot trigger a global spike.
        is_spike = recent_n >= min_recent and recent_unique >= min_unique and (prior_n == 0 or ratio >= ratio_thresh)
        cluster_metrics[rc] = {
            'rootCauseId': rc,
            'totalTickets': len(all_items),
            'uniqueCustomers': recent_unique if recent_n > 0 else total_unique,
            'recent7dUniqueCustomers': recent_unique,
            'totalUniqueCustomers': total_unique,
            'recent7dCount': recent_n,
            'prior7dCount': prior_n,
            'spikeRatio': ratio,
            'isSpiking': is_spike,
        }
        if is_spike:
            spikes.append({
                'rootCauseId': rc,
                'recent7dCount': recent_n,
                'uniqueCustomers': recent_unique,
                'prior7dCount': prior_n,
                'spikeRatio': ratio,
                'evidenceTickets': recent_items[:10],
            })
        routine_items = [it for it in recent_items if it['priority'] in {'P2', 'P3'}]
        routine_unique = len({it['customer'] for it in routine_items})
        if routine_unique >= 3:
            kb_deflection_candidates.append({
                'rootCauseId': rc,
                'uniqueCustomers': routine_unique,
                'ticketCount': len(routine_items),
                'sampleSubjects': [it['subject'] for it in routine_items[:5]],
            })

    escalations.sort(key=lambda e: (PRIORITY_RANK[e['priority']], -e['ageHours']))
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
        'clusterMetrics': cluster_metrics,
        'kbDeflectionCandidates': kb_deflection_candidates,
    }

    if write_report:
        store['updatedAt'] = report['generatedAt']
        store_path.parent.mkdir(parents=True, exist_ok=True)
        store_path.write_text(json.dumps(store, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        (data_dir / 'sla-report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Run deterministic triage, SLA, and spike detection.')
    parser.add_argument('data_dir', help='Path to customer-support-ops data directory')
    parser.add_argument('--write-report', action='store_true')
    args = parser.parse_args()
    report = run_triage(Path(args.data_dir), write_report=args.write_report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
