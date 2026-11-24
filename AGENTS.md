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

## Design Principles

- **Neutral domain & platform expert**: Every plugin and skill is a neutral advisor oriented toward a domain, workflow, or official platform—not one user's personal aesthetic. Present official constraints, real audience patterns, and starter examples, while leaving style choice and creative freedom to the user and the model.
- **Plugin is mounted by an agent; style & decisions live in the agent's user context**: Plugins are read-only, neutral capability packs (domain strategies, structured schemas/board templates, deterministic pipelines, and objective guardrails) mounted onto an agent/bot. User-specific style, goals, concrete targets (such as benchmark accounts to watch), and decision criteria live in the mounted agent's own context (its persona/profile, memory, private overrides, conversation/workspace state) and belong to the human—never hardcoded into or overridden by a public plugin.
- **Text teaches domain specifics; code enforces objective invariants**: Keep `SKILL.md` and `references/` focused on specialized knowledge the model does not inherently know (platform mechanics, audience psychology, starter blueprints) rather than micromanaging generic taste or structure. Use deterministic scripts for repeatable production pipelines and objective hard checks (dimensions, byte/char limits, file existence, provenance URLs, tamper-proof hashes, readable contrast floors)—never turn subjective style preferences into hard blocking errors.

## Interactive Board UI Standard (shadcn/ui)

Whenever a plugin ships or instructs an agent to build an interactive **Board** (dashboards, kanban pipelines, calendars, ledgers, inboxes, retrospective views, or monitoring panels), the Board MUST follow the **`shadcn/ui` design paradigm and semantic token system**—never ad-hoc per-page CSS or rainbow status pills:

- **Single shared stylesheet per plugin**: Place shared tokens and component primitives in `assets/boards/shared/board-ui.css` (assembled into each board's `runtime/board-ui.css`) so every board stays zero-dependency, offline-runnable, and visually coherent.
- **Canonical shadcn/ui semantic tokens** (both light `:root` and dark `.dark` / `prefers-color-scheme: dark`):
  - Surfaces & text: `--background`, `--foreground`, `--card`, `--card-foreground`, `--popover`, `--popover-foreground`, `--muted`, `--muted-foreground`
  - Actions & chrome: `--primary`, `--primary-foreground`, `--secondary`, `--secondary-foreground`, `--accent`, `--accent-foreground`, `--destructive`, `--destructive-foreground`, `--border`, `--input`, `--ring`, `--radius` (`0.625rem`)
  - Charts: `--chart-1` through `--chart-5`
- **Calm by default, semantic color only for exceptions**:
  - Neutral white/near-black canvas with `1px solid var(--border)` hairline framing; avoid nested double-bordered cards or decorative shadows/gradients.
  - Normal/rest states (`active`, `published`, `healthy`, `general`) stay neutral (`--foreground` / `--muted-foreground` / `--secondary`). Reserve `warning` (amber) and `destructive` (red) strictly for items requiring human attention, approval, or error recovery, and `--primary` for the primary action or active state.
- **Uniform control heights (one tier per chrome row)**:
  - Toolbar controls (`select`, segmented `tabs`, toolbar `button`, toggle chips) share a single **`32px`** height (`2rem`) with aligned radius (`calc(var(--radius) - 2px)`).
  - Card-level and table-row actions use quiet `ghost` or `outline` buttons at `28px` / `24px` height so repeated rows never form a loud wall of solid buttons.
- **Scan-first tables & numeric alignment**:
  - Tables live inside a clean `1px` bordered card wrapper with `11px` uppercase muted column headers (`letter-spacing: 0.04em`), subtle row dividers, row hover tint, and `font-variant-numeric: tabular-nums` for counts, dates, and KPIs.
- **Scope boundary**: This standard governs interactive application Boards. External social-media visual export canvases (carousel slides, covers, posters) remain free to use expressive editorial or brand-specific art direction.

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
