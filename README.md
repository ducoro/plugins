# Ducoro Plugins

Official plugin marketplace for [Ducoro](https://ducoro.ai), also directly usable in **Claude Code** and **OpenAI Codex**.

**English** | [简体中文](README.zh-CN.md)

Each plugin packages portable **Agent Skills** (`SKILL.md`) and optional **MCP server declarations** (`.mcp.json`) in open, cross-host marketplace formats.

## Available plugins

| Plugin | What it helps with | Components |
| --- | --- | --- |
| [Starter Template](plugins/starter-template) | Minimal reference plugin for testing and authoring new plugins | Skill + MCP example |
| [Docs Lookup](plugins/docs-lookup) | Answer library and framework questions using current documentation | Skill (Context7) |
| [Repo Research](plugins/repo-research) | Understand public GitHub repositories through their documentation | Skill (DeepWiki) |
| [Git Workflows](plugins/git-workflows) | Write clear commit messages and pull request descriptions | Skill |
| [Content Operations](plugins/content-operations) | Run a continuous multi-platform content loop across 14 platforms with interactive boards | Skills + Scripts + Boards |

## Use this marketplace

- **Ducoro**: Automatically synced from this repository; mount any plugin onto individual Bots.
- **Claude Code**: Add `ducoro/plugins` as a plugin marketplace (`/plugin marketplace add ducoro/plugins`) using `.claude-plugin/marketplace.json`.
- **OpenAI Codex**: Add `ducoro/plugins` via `.agents/plugins/marketplace.json` (or root `marketplace.json`).

Any MCP server requiring credentials uses environment variable placeholders (for example `${EXAMPLE_MCP_TOKEN}`); supply your own tokens locally in your host tool's credential store.

## Repository layout

```text
.agents/plugins/marketplace.json   # Open Agent Plugins / Codex marketplace index
.claude-plugin/marketplace.json    # Claude Code marketplace index
marketplace.json                   # Root marketplace index (mirror)
plugins/
  <plugin-name>/
    LICENSE
    plugin.json                    # Open Agent Plugins manifest
    .claude-plugin/plugin.json     # Claude Code manifest
    .codex-plugin/plugin.json      # Codex manifest
    .mcp.json                      # Optional MCP server declarations (no secrets)
    skills/
      <skill-name>/
        SKILL.md
        agents/openai.yaml         # Optional discovery metadata
```

## Contribute

- Human contributors: see [CONTRIBUTING.md](CONTRIBUTING.md).
- AI agents: see [AGENTS.md](AGENTS.md) for the exact authoring and validation checklist.
- Security concerns: please use [private vulnerability reporting](https://github.com/ducoro/plugins/security/advisories/new); see [SECURITY.md](SECURITY.md).

## License

[Apache License 2.0](LICENSE). Third-party services and their documentation remain governed by their respective terms.
