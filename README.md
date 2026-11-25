# Ducoro Plugins

Official plugin marketplace for [Ducoro](https://ducoro.ai).

**English** | [简体中文](README.zh-CN.md)

Each plugin packages a **Domain Role** (`PLUGIN.md`), progressively disclosed on-demand files (playbooks, references, scripts, boards), and optional **MCP server declarations** (`.mcp.json`) built around Ducoro Spaces, Boards, Connectors, and `ducoro-cli`.

## Available plugins

| Plugin | Domain role | Contents |
| --- | --- | --- |
| [Starter Template](plugins/starter-template) | Minimal reference plugin for testing and authoring new domain roles | `PLUGIN.md` + References + MCP example |
| [Docs Lookup](plugins/docs-lookup) | Answer library and framework questions using current documentation | `PLUGIN.md` + Playbook (Context7) |
| [Repo Research](plugins/repo-research) | Understand public GitHub repositories through their AI wiki | `PLUGIN.md` + Playbook (DeepWiki) |
| [Git Workflows](plugins/git-workflows) | Author conventional commits and reviewable pull request descriptions | `PLUGIN.md` + Playbooks |
| [Content Operations](plugins/content-operations) | Run a continuous multi-platform content loop across 14 platforms with interactive boards | `PLUGIN.md` + Playbooks + 14 Platforms + Scripts + Boards |

## Use this marketplace

- **Ducoro**: Automatically synced from this repository via `marketplace.json`; mount any plugin onto individual Bots to add its domain role to `<you><domain_roles>`.

Any MCP server requiring credentials uses environment variable placeholders (for example `${EXAMPLE_MCP_TOKEN}`); supply your own tokens locally in Ducoro's credential store.

## Repository layout

```text
marketplace.json                   # Marketplace index
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
