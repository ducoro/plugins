# Ducoro Plugins

Official plugin marketplace for [Ducoro](https://ducoro.ai).

**English** | [简体中文](README.zh-CN.md)

Each plugin packages a **Domain Role** (`PLUGIN.md`), progressively disclosed on-demand files (playbooks, references, scripts, boards), and optional **MCP server declarations** (`.mcp.json`) built around Ducoro Spaces, Boards, Connectors, and `ducoro-cli`.

## Available plugins

| Plugin | Domain role | Contents |
| --- | --- | --- |
| [Content Operations](plugins/content-operations) | Run a continuous multi-platform content loop across 14 platforms with interactive boards | `PLUGIN.md` + Playbooks + 14 Platforms + Scripts + Boards |
| [Market Intel](plugins/market-intel) | Track competitor, company, and sector changes with objective snapshot diffs and grounded evidence gates | `PLUGIN.md` + Playbooks + Public Source Fetchers + Diff/Evidence Scripts + Boards |
| [Customer Support Ops](plugins/customer-support-ops) | Triage tickets and reviews, enforce P0/SLA escalations, detect issue spikes, and lock outbound replies | `PLUGIN.md` + Playbooks + Channel Importers + Triage/Reply Guards + Boards |
| [Business Finance Ops](plugins/business-finance-ops) | Reconcile real statements with exact Decimal math, ECB FX rates, anomaly detection, and runway boards | `PLUGIN.md` + Playbooks + Statement Parsers + Decimal Ledger/Audit Scripts + Boards |
| [Software Stewardship](plugins/software-stewardship) | Keep a living codebase healthy with real Git audits, live OSV CVE/license checks, SHA approval locks, release protocols, and quiet boards | `PLUGIN.md` + Playbooks + Git/OSV/Gate/Pulse Scripts + Boards |

## Use this marketplace

- **Ducoro**: Automatically synced from this repository via `marketplace.json`; mount any plugin onto individual Bots to add its domain role to `<you><domain_roles>`.

Any MCP server requiring credentials uses environment variable placeholders (for example `${EXAMPLE_MCP_TOKEN}`); supply your own tokens locally in Ducoro's credential store.

## Repository layout

```text
marketplace.json                   # Marketplace index
templates/
  starter-template/                # Reference authoring blueprint (not published to marketplace)
plugins/
  <plugin-name>/
    LICENSE
    plugin.json                    # Plugin manifest
    PLUGIN.md                      # Level-1 domain role & resource map (≤ 4,000 chars)
    .mcp.json                      # Optional MCP server declarations (no secrets)
    ...                            # Level-2/level-3 on-demand playbooks, references, scripts, boards
```

## Contribute

- Human contributors: see [CONTRIBUTING.md](CONTRIBUTING.md).
- AI agents: see [AGENTS.md](AGENTS.md) for the exact authoring, orthogonality, and validation checklist.
- Security concerns: please use [private vulnerability reporting](https://github.com/ducoro/plugins/security/advisories/new); see [SECURITY.md](SECURITY.md).

## License

[Apache License 2.0](LICENSE). Third-party services and their documentation remain governed by their respective terms.
