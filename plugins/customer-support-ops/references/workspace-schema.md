# Customer Support Ops Data Schema

This directory layout works inside the human's existing support folder, a single Space's `files/` directory, or an optional cross-Space Local Folder.

```text
customer-support-ops/
├── sla-policy.json            # SLA hours by priority (P0/P1/P2/P3), cooldownHours, spike threshold
├── tickets/
│   └── tickets.json           # Deduplicated ticket store keyed by ticketId (channel:externalId)
├── issues/
│   └── root-causes.json       # Root-cause cluster catalog linked to source ticketIds
├── outbound-queue.json        # Staged & human-approved reply drafts with sha256 approval hash
├── reply-log.jsonl            # Append-only sent reply audit ledger (for idempotency & cooldown)
├── sla-report.json            # Latest deterministic output from triage_gate.py
└── kb/                        # Verified support macros & troubleshooting articles
```

## Ticket Schema (`customer-support-ticket/1`)

- `ticketId`: deterministic ID (`<channel>:<externalId>`)
- `channel`: `"github_issues"` | `"appstore_ios"` | `"email"` | `"csv"` | `"connector"` | `"web"`
- `externalId`: upstream ticket/issue/review/message ID
- `customer`: sender/author identifier
- `subject`: short title
- `body`: raw feedback text
- `url`: optional source URL (`http(s)://`)
- `rating`: optional integer 1–5 (for app store reviews)
- `createdAt`: ISO-8601 UTC timestamp
- `status`: `"open"` | `"pending_human"` | `"replied"` | `"resolved"`
- `rootCauseId`: optional root-cause cluster slug
