# Contributing

Thank you for helping improve the official Ducoro plugin marketplace.

If you are an AI agent working on this repository, start with [AGENTS.md](AGENTS.md) for the exact step-by-step checklist.

## Propose a change

Open an issue for a new plugin or a substantial behavior change. Explain the task it supports, when an agent should use it, any required MCP servers or tools, and how you will verify the result. Small corrections can go directly to a pull request.

## Plugin contract

Use [`plugins/starter-template`](plugins/starter-template) as a ready-to-copy blueprint.

1. Create `plugins/<name>/` with a single `plugin.json` manifest declaring lowercase kebab-case `name`, semantic `version`, non-empty `description`, `license: "Apache-2.0"`, and `skills: "./skills/"`.
2. Put each skill in `skills/<skill-name>/SKILL.md`. Its YAML frontmatter declares `name` (matching the folder name) and a single-line `description` of at most 300 UTF-16 code units. Write clear English instructions covering prerequisites, workflow, observable completion, and failure handling.
3. Optional `.mcp.json`: if a plugin bundles MCP server declarations, place them in `.mcp.json` and set `"mcpServers": "./.mcp.json"` in `plugin.json`. Never commit real credentials or machine-specific paths—use environment variable placeholders such as `${SERVICE_API_TOKEN}`.
4. Do not include unsupported or external-host entries (`.agents/`, `.claude-plugin/`, `.codex-plugin/`, `skills/*/agents/`, `hooks/`, `commands/`, `agents/`, `.app.json`) or symlinks.
5. Register the plugin in `marketplace.json`.
6. Update both [README.md](README.md) and [README.zh-CN.md](README.zh-CN.md) when adding, removing, or materially changing a plugin.
7. Include an unchanged copy of the root `LICENSE` inside `plugins/<name>/LICENSE`.

Only contribute material you have the right to distribute under Apache-2.0. Keep third-party attributions and license notices with any permitted third-party material.

## Validate locally

Python 3.11 or newer is sufficient; the checks use only the standard library.

```sh
python3 scripts/validate.py
python3 scripts/check_hygiene.py --tracked
python3 -m unittest discover -s tests -v
```

To explicitly run opt-in live network smoke tests locally against public endpoints (skipped in CI):

```sh
RUN_LIVE_TESTS=1 python3 -m unittest tests/test_live_public_sources.py -v
```

To enable the repository Git hooks locally (`pre-commit`, `commit-msg`, and `pre-push`):

```sh
git config core.hooksPath .githooks
```

Validation checks `marketplace.json`, plugin manifests, `.mcp.json` schema and secret hygiene, forbidden unsupported entries, skill frontmatter, `ducoro-cli` invocations, and README coverage.

## Publish updates

Open a pull request against `main`. Keep changes focused and bump the plugin `version` whenever distributed content changes. Once merged to `main`, clients pick up updates automatically on their next sync without requiring an application release.
