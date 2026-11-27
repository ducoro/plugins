# Real Feedback Channels & Ingestion

Never invent or simulate customer tickets. Ingest real user reports in strict priority order:

## Priority 1: Ducoro Core Connectors

Check connected support, issue-tracker, and inbox tools first:
```sh
ducoro-cli mcp catalog list --json
ducoro-cli mcp catalog status <slug> --json
ducoro-cli mcp catalog tools <slug> --json
```
Typical Connectors: Intercom, Zendesk, Linear, Jira, GitHub, Gmail, Outlook, Slack, Discord. Normalize fetched items into `customer-support-ticket/1` JSONL (preserving `vip`, `labels`, `rating`, `rootCauseId`, `riskFlags`, and `lastInboundAt` whenever available) and ingest via:
```sh
python3 scripts/ingest_feedback.py <data-dir> --jsonl <file>
```

## Priority 2: Built-in Real Source Fetchers & File Importers (`scripts/ingest_feedback.py`)

Zero third-party packages required:

| Mode | Flags | Real Data Source & Fields |
|---|---|---|
| GitHub Issues | `--github-repo <owner/repo> [--state open\|closed\|all] [--limit 1..100]` | Official GitHub REST API (keyless for public repos; uses `GITHUB_TOKEN` env var if set for private repos). Emits a `warnings` entry if raw results hit `--limit` so you know pagination/Connector fetch is needed. |
| Email Archive | `--eml <file_or_dir>` / `--mbox <file>` | Standard RFC 5322 `.eml` / `.mbox` files via Python `email` & `mailbox` stdlib. |
| Ticket Export CSV | `--csv <file>` | Standard CSV exports from Zendesk, Intercom, Freshdesk, Shopify, or spreadsheets. Parses `rating`/`stars`/`score`, `root_cause_id`/`rootCauseId`, `vip`, `labels`/`tags`, and `last_inbound_at` when present. |
| Normalized JSONL | `--jsonl <file>` | Connector or external export payloads matching `customer-support-ticket/1` (preserves `vip`, `rating`, `labels`, `rootCauseId`, `riskFlags`, `priority`, `requiresHumanApproval`, `escalationReasons`, and `lastInboundAt`). |

Every ingested record is deterministically deduplicated by `(channel, externalId)`. Re-ingestion monotonically preserves existing `rootCauseId`, `priority`, `requiresHumanApproval`, `escalationReasons`, `riskFlags`, and `vip` metadata.

## Priority 3: Official Browser Support & App Store Desks

When a channel has no Connector or export (e.g., App Store Connect reviews where legacy keyless RSS feeds no longer return entries, Google Play Console, or domestic web chat desks), use the host browser and pause immediately for human login/2FA/CAPTCHA; never extract cookies or call private undocumented APIs.
