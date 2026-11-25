# Real Feedback Channels & Ingestion

Never invent or simulate customer tickets. Ingest real user reports in strict priority order:

## Priority 1: Ducoro Core Connectors

Check connected support, issue-tracker, and inbox tools first:
```sh
ducoro-cli mcp catalog list --json
ducoro-cli mcp catalog status <slug> --json
ducoro-cli mcp catalog tools <slug> --json
```
Typical Connectors: Intercom, Zendesk, Linear, Jira, GitHub, Gmail, Outlook, Slack, Discord. Normalize fetched items into `customer-support-ticket/1` JSONL and ingest via `scripts/ingest_feedback.py <workspace> --jsonl <file>`.

## Priority 2: Built-in Real Source Fetchers & File Importers (`scripts/ingest_feedback.py`)

Zero third-party packages required:

| Mode | Flag | Real Data Source |
|---|---|---|
| GitHub Issues | `--github-repo <owner/repo>` | Official GitHub REST API (keyless for public repos; uses `GITHUB_TOKEN` env var if set for private repos) |
| Email Archive | `--eml <file_or_dir>` / `--mbox <file>` | Standard RFC 5322 `.eml` / `.mbox` files via Python `email` & `mailbox` stdlib |
| Ticket Export CSV | `--csv <file>` | Standard CSV exports from Zendesk, Intercom, Freshdesk, Shopify, or support spreadsheets |
| Normalized JSONL | `--jsonl <file>` | Connector or external export payloads matching `customer-support-ticket/1` (including App Store Connect / Play Console reviews) |

Every ingested record is deterministically deduplicated by `(channel, externalId)` so repeated runs never duplicate tickets.

## Priority 3: Official Browser Support & App Store Desks

When a channel has no Connector or export (e.g., App Store Connect reviews where legacy keyless RSS feeds no longer return entries, Google Play Console, or domestic web chat desks), use the host browser and pause immediately for human login/2FA/CAPTCHA; never extract cookies or call private undocumented APIs.
