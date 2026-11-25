# Support Triage & SLA Board

Displays deduplicated support tickets, deterministic risk escalations, SLA breaches, and guarded reply draft status.

## Location IDs
- Summary KPIs: `data-card="triage-kpis"` (`kpi-open`, `kpi-escalations`, `kpi-sla`, `kpi-drafts`)
- Ticket rows: `data-card="ticket-<ticketId>"`, `data-mark-item="ticket-<ticketId>"`

## Agent Commands (`ducoro-cli board command`)
- `filterPriority` (`{ "priority": "all|P0|P1|P2|P3" }`)
- `filterEscalated` (`{ "escalatedOnly": true|false }`)
- `focusTicket` (`{ "ticketId": "<ticketId>" }`)
- `resetFilters` (`{}`)
