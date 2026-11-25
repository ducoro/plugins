# Contributing Guide for AI Agents

This repository (`ducoro/plugins`) is the official public plugin marketplace for **Ducoro**, distributing **Domain Role Plugins** (`PLUGIN.md` + on-demand tree resources + optional `.mcp.json`) built for Ducoro's Spaces, Boards, Connectors, and `ducoro-cli`.

Follow every rule below when adding, editing, or removing a plugin.

## Scope & Hard Boundaries

- **Canonical Ducoro format only**: Every plugin consists of `LICENSE`, `plugin.json`, required `PLUGIN.md`, optional `.mcp.json`, and freely organized on-demand tree folders (`playbooks/`, `references/`, `platforms/`, `scripts/`, `assets/`, `skills/`, etc.).
- **Forbidden components**: Do **not** add external-host or unsupported entries such as `.agents/`, `.claude-plugin/`, `.codex-plugin/`, `hooks/`, `commands/`, `agents/`, `.app.json`, or a legacy `"skills"` field in `plugin.json`.
- **No secrets, ever**: Never commit real API keys, bearer tokens, passwords, private URLs, or machine-specific paths. In `.mcp.json`, always use environment variable placeholders such as `${SERVICE_API_TOKEN}`.
- **No symlinks**: Every file in the repository must be a regular file.
- **Public repository hygiene**: Never include internal product architecture, private repository paths, or internal operational details in plugin instructions, docs, or commit messages.
- **Exact Ducoro CLI binary name**: When plugin instructions invoke the Ducoro CLI, always use `ducoro-cli` (for example, `ducoro-cli board ...`, `ducoro-cli feedback send ...`, `ducoro-cli media upload ...`)—never bare `ducoro <subcommand>`.

## Design Principles

- **Domain role overlay, not flat skill dumps**: Each plugin contributes one coherent domain role (`PLUGIN.md`) mounted into `<you><domain_roles>` alongside the Bot's own `PROFILE.md`. A Bot's `PROFILE.md` and the human's live instructions always take precedence over every mounted plugin.
- **Progressive tree disclosure**: Treat `PLUGIN.md` like a repository's root `README.md`—it holds the domain goal, activation boundaries, operating loop, approval gates, and **level-1 resource map** (at most **4,000 UTF-16 code units**). Deeper level-2/level-3 playbooks, platform guides, schemas, boards, and scripts are indexed by their parent documents and read on demand.
- **Neutral domain & platform expert**: Every plugin is a neutral advisor oriented toward a domain, workflow, or official platform—not one user's personal persona or strategy. User-specific voice, taste, concrete targets, and business policies live in the mounted Bot's own `PROFILE.md`, private Skills (procedural memory), and Memory (episodic memory).
- **Strict orthogonality across all plugins**: Every plugin in this marketplace must coexist peacefully when all plugins are mounted onto the same Bot simultaneously:
  - Clear positive activation triggers and explicit negative boundaries (`## Activation & Boundaries`).
  - Zero persona/tone/global-reply overrides in `PLUGIN.md`.
  - Zero colliding MCP server slugs across different plugins.
- **Text teaches domain specifics; code enforces objective invariants**: Keep prose focused on specialized domain knowledge and use deterministic scripts for repeatable production pipelines and objective hard checks—never turn subjective style preferences into hard blocking errors.

## `PLUGIN.md` Contract (Required 5-Section Skeleton)

Every plugin root MUST contain a regular `PLUGIN.md` file in English, **without** YAML frontmatter (metadata lives solely in `plugin.json`), with trimmed UTF-16 length **≤ 4,000**, containing these five `##` sections in exact order:

1. `## Domain` — What long-term domain outcome this role owns (2–3 sentences).
2. `## Activation & Boundaries` — Explicit positive triggers AND explicit negative boundaries stating when to stay inactive so co-mounted plugins never collide.
3. `## Operating Loop` — End-to-end durable loop, file-backed truth, and completion criteria (no bloated platform tables or script flags).
4. `## Needs a Yes` — Domain-specific irreversible or external actions that require explicit human confirmation (always deferring to stricter rules in the Bot's own profile).
5. `## Resources & Tools` — Level-1 directory map of on-demand files inside the plugin root (all referenced relative paths must exist) and when to use any bundled `.mcp.json` tools.

Never put persona/voice rules, global response-formatting mandates, user-specific business strategies, or long reference tables inside `PLUGIN.md`.

## Interactive Board UI Standard (shadcn/ui)

Whenever a plugin ships or instructs an agent to build an interactive **Board** (dashboards, kanban pipelines, calendars, ledgers, inboxes, retrospective views, or monitoring panels), the Board MUST follow the **`shadcn/ui` design paradigm and semantic token system**—never ad-hoc per-page CSS or rainbow status pills:

- **Single shared stylesheet per plugin**: Place shared tokens and component primitives in a shared `board-ui.css` (assembled into each board's `runtime/board-ui.css`) so every board stays zero-dependency, offline-runnable, and visually coherent.
- **Canonical shadcn/ui semantic tokens** (both light `:root` and dark `.dark` / `prefers-color-scheme: dark`):
  - Surfaces & text: `--background`, `--foreground`, `--card`, `--card-foreground`, `--popover`, `--popover-foreground`, `--muted`, `--muted-foreground`
  - Actions & chrome: `--primary`, `--primary-foreground`, `--secondary`, `--secondary-foreground`, `--accent`, `--accent-foreground`, `--destructive`, `--destructive-foreground`, `--border`, `--input`, `--ring`, `--radius` (`0.625rem`)
  - Charts: `--chart-1` through `--chart-5`
- **Calm by default, semantic color only for exceptions**:
  - Neutral white/near-black canvas with `1px solid var(--border)` hairline framing; avoid nested double-bordered cards or decorative shadows/gradients.
  - Normal/rest states stay neutral (`--foreground` / `--muted-foreground` / `--secondary`). Reserve `warning` (amber) and `destructive` (red) strictly for items requiring human attention, approval, or error recovery, and `--primary` for the primary action or active state.
- **Uniform control heights & scan-first tables**:
  - Toolbar controls share a single `32px` (`2rem`) height; row actions use quiet `ghost` or `outline` buttons at `28px` / `24px`.
  - Tables live inside a clean `1px` bordered card wrapper with `11px` uppercase muted column headers and `font-variant-numeric: tabular-nums`.
- **Scope boundary**: External social-media visual export canvases (carousel slides, covers, posters) remain free to use expressive editorial or brand-specific art direction.

## Required Files for Every Plugin

Use `plugins/starter-template/` as the reference blueprint. Every plugin directory `plugins/<plugin-name>/` must contain:

```text
plugins/<plugin-name>/
├── LICENSE            # Exact byte-for-byte copy of root LICENSE (Apache-2.0)
├── plugin.json        # Plugin manifest (single metadata source of truth)
├── PLUGIN.md          # Required level-1 domain role & resource map (≤ 4,000 UTF-16 chars)
├── .mcp.json          # Optional MCP server declarations (placeholders only)
└── ...                # Optional level-2/level-3 on-demand folders (references/, playbooks/, scripts/, assets/, etc.)
```

### Manifest Rules

1. `<plugin-name>` and MCP server slugs must be lowercase kebab-case (`a-z0-9-`).
2. `plugin.json` must declare `name`, `version` (`major.minor.patch`), non-empty `description`, and `license` (`Apache-2.0`). Omit `skills` and `apps`.
3. If `.mcp.json` is present, `plugin.json` must set `"mcpServers": "./.mcp.json"`. If `.mcp.json` is absent, omit `mcpServers`.

## Step-by-Step: Add a New Plugin

1. Verify orthogonality against all existing plugins in `marketplace.json` (never create a second plugin for an already-covered domain).
2. Copy `plugins/starter-template/` to `plugins/<plugin-name>/`.
3. Update `plugin.json` and author `PLUGIN.md` following the 5-section skeleton and 4,000-char budget, placing deeper material in level-2/level-3 subdirectories.
4. Keep `.mcp.json` only if the plugin declares MCP servers; otherwise delete `.mcp.json` and remove `"mcpServers"` from `plugin.json`.
5. Register the plugin in `marketplace.json` (`source: { "source": "local", "path": "./plugins/<plugin-name>" }`).
6. Add a row linking to `(plugins/<plugin-name>)` in both `README.md` and `README.zh-CN.md`.
7. Run local validation, hygiene, formal verification, and full unit test suites (must all pass with zero errors):

```sh
python3 scripts/validate.py
python3 scripts/check_hygiene.py --tracked
python3 -m unittest discover -s tests -p "test_*_formal_verification.py" -v
python3 -m unittest discover -s tests -v
```

## Updating an Existing Plugin

- Bump `version` (semver) in `plugin.json` whenever distributed instructions, resources, or `.mcp.json` change.
- Never rename an existing plugin directory without coordinating migration, because consumers reference plugins by `name`.
- Run all validation and test commands before committing or opening a pull request.

## Workspace Indexes

If `.rules/README.md`, `.plans/README.md`, or `.docs/README.md` exist in the local workspace, check them for additional context:

- `.rules/README.md`: repository workflow and maintenance rules
- `.plans/README.md`: active plans and working notes
- `.docs/README.md`: design and architecture references

Keep these index files updated when adding, renaming, or removing files in their directories, and do not stage git-ignored files inside them.
