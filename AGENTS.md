# Contributing Guide for AI Agents

This repository (`ducoro/plugins`) is the official public plugin marketplace for **Ducoro**, distributing **Agent Skills** (`SKILL.md`), supporting scripts/boards/references, and optional **MCP server declarations** (`.mcp.json`) built for Ducoro's runtime capabilities.

Follow every rule below when adding, editing, or removing a plugin.

## Scope & Hard Boundaries

- **Allowed components**: `skills/` (`SKILL.md` plus optional `scripts/`, `references/`, `assets/`) and optional `.mcp.json`.
- **Forbidden components**: Do **not** add unsupported or external-host entries such as `.agents/`, `.claude-plugin/`, `.codex-plugin/`, `skills/*/agents/`, `hooks/`, `commands/`, `agents/`, or `.app.json`.
- **No secrets, ever**: Never commit real API keys, bearer tokens, passwords, private URLs, or machine-specific paths. In `.mcp.json`, always use environment variable placeholders such as `${SERVICE_API_TOKEN}`.
- **No symlinks**: Every file in the repository must be a regular file.
- **Public repository hygiene**: Never include internal product architecture, private repository paths, or internal operational details in plugin instructions, docs, or commit messages.
- **Exact Ducoro CLI binary name**: When plugin instructions invoke the Ducoro CLI, always use `ducoro-cli` (for example, `ducoro-cli board ...`, `ducoro-cli feedback send ...`, `ducoro-cli media upload ...`)—never bare `ducoro <subcommand>`.

## Required Files for Every Plugin

Use `plugins/starter-template/` as the reference blueprint. Every plugin directory `plugins/<plugin-name>/` must contain:

```text
plugins/<plugin-name>/
├── LICENSE                        # Exact byte-for-byte copy of root LICENSE (Apache-2.0)
├── plugin.json                    # Plugin manifest (single source of truth)
├── skills/
│   └── <skill-name>/
│       └── SKILL.md               # Required YAML frontmatter + English instructions
└── .mcp.json                      # Optional MCP server declarations (placeholders only)
```

### Manifest Rules

1. `<plugin-name>` and `<skill-name>` must be lowercase kebab-case (`a-z0-9-`).
2. `plugin.json` must declare `name`, `version` (`major.minor.patch`), non-empty `description`, `license` (`Apache-2.0`), and `"skills": "./skills/"`.
3. If `.mcp.json` is present, `plugin.json` must set `"mcpServers": "./.mcp.json"`. If `.mcp.json` is absent, omit `mcpServers`.
4. Each `SKILL.md` frontmatter must define:
   - `name`: exact match with `<skill-name>` directory name
   - `description`: single line, non-empty, at most 300 UTF-16 code units

## Step-by-Step: Add a New Plugin

1. Copy `plugins/starter-template/` to `plugins/<plugin-name>/`.
2. Update `plugin.json`.
3. Replace `skills/hello-template/` with one or more `skills/<skill-name>/` folders. Write clear, actionable English instructions covering prerequisites, workflow, completion criteria, and failure handling.
4. Keep `.mcp.json` only if the plugin declares MCP servers; otherwise delete `.mcp.json` and remove `"mcpServers"` from `plugin.json`.
5. Register the plugin in `marketplace.json` (`source: { "source": "local", "path": "./plugins/<plugin-name>" }`).
6. Add a row linking to `(plugins/<plugin-name>)` in both `README.md` and `README.zh-CN.md`.
7. Run local validation and unit tests (must both pass with zero errors):

```sh
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
```

## Updating an Existing Plugin

- Bump `version` (semver) in `plugin.json` whenever distributed skill instructions or `.mcp.json` change.
- Never rename an existing plugin directory without coordinating migration, because consumers reference plugins by `name`.
- Run both validation commands before committing or opening a pull request.

## Workspace Indexes

If `.rules/README.md`, `.plans/README.md`, or `.docs/README.md` exist in the local workspace, check them for additional context:

- `.rules/README.md`: repository workflow and maintenance rules
- `.plans/README.md`: active plans and working notes
- `.docs/README.md`: design and architecture references

Keep these index files updated when adding, renaming, or removing files in their directories, and do not stage git-ignored files inside them.
