## Domain

Version-accurate lookup of external library, framework, and SDK documentation via live Context7 documentation sources instead of relying on stale model memory.

## Activation & Boundaries

Activate when answering questions that depend on an exact API signature, configuration key, version difference, or migration path for a third-party library, framework, or SDK. Stay inactive for whole-repository architecture exploration of a GitHub repo (leave that to `repo-research`), local git commits or PR drafting (leave that to `git-workflows`), content marketing workflows, and pure conceptual questions that do not depend on versioned library docs.

## Operating Loop

1. Confirm the target library/framework and whether a specific version matters; if ambiguous, ask rather than silently substituting another package.
2. Ensure the `context7` MCP connector (`resolve-library-id`, `query-docs`) is available; read `playbooks/context7-lookup.md` for setup and fallback rules if tools are missing.
3. Resolve the exact library id, run narrow focused doc queries (exact API or option rather than broad dumps), and ground the answer in the returned documentation.
4. Cite the resolved library id, doc topic, and visible version; if the docs contradict prior memory, follow the docs, and state explicitly when the docs do not cover the question.

## Needs a Yes

Obtain explicit human approval before adding a new `context7` MCP definition via `ducoro-cli mcp add` or storing new credentials. Always defer to stricter approval rules in the Bot's own profile.

## Resources & Tools

- `playbooks/context7-lookup.md`: Connector readiness check, `ducoro-cli mcp` setup commands, narrow query workflow, divergence handling, and anti-patterns.
- External connector used when configured: `context7` MCP (`resolve-library-id`, `query-docs`).
