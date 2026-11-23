# Ducoro Plugins

Official plugin marketplace for [Ducoro](https://ducoro.ai).

**English** | [简体中文](README.zh-CN.md)

Each plugin packages **Agent Skills** (`SKILL.md`), scripts, boards, and optional **MCP server declarations** (`.mcp.json`) built around Ducoro Spaces, Boards, Connectors, and `ducoro-cli`.

## Available plugins

| Plugin | What it helps with | Components |
| --- | --- | --- |
| [Starter Template](plugins/starter-template) | Minimal reference plugin for testing and authoring new plugins | Skill + MCP example |
| [Docs Lookup](plugins/docs-lookup) | Answer library and framework questions using current documentation | Skill (Context7) |
| [Repo Research](plugins/repo-research) | Understand public GitHub repositories through their documentation | Skill (DeepWiki) |
| [Git Workflows](plugins/git-workflows) | Write clear commit messages and pull request descriptions | Skill |
| [Content Operations](plugins/content-operations) | Run a continuous multi-platform content loop across 14 platforms with interactive boards | Skills + Scripts + Boards |

## Use this marketplace

- **Ducoro**: Automatically synced from this repository via `marketplace.json`; mount any plugin onto individual Bots.

Any MCP server requiring credentials uses environment variable placeholders (for example `${EXAMPLE_MCP_TOKEN}`); supply your own tokens locally in Ducoro's credential store.

## Repository layout

```text
marketplace.json                   # Marketplace index
plugins/
  <plugin-name>/
    LICENSE
    plugin.json                    # Plugin manifest
    .mcp.json                      # Optional MCP server declarations (no secrets)
    skills/
      <skill-name>/
        SKILL.md
```

## Contribute

- Human contributors: see [CONTRIBUTING.md](CONTRIBUTING.md).
- AI agents: see [AGENTS.md](AGENTS.md) for the exact authoring and validation checklist.
- Security concerns: please use [private vulnerability reporting](https://github.com/ducoro/plugins/security/advisories/new); see [SECURITY.md](SECURITY.md).

## License

[Apache License 2.0](LICENSE). Third-party services and their documentation remain governed by their respective terms.
