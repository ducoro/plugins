## Domain

Reference template domain role for verifying Ducoro plugin mounting, domain-role injection, on-demand file reads, and optional MCP credential placeholder wiring, and for bootstrapping new official plugins.

## Activation & Boundaries

Activate only when the human explicitly asks to verify `starter-template`, test Ducoro plugin mounting/syncing, or use `starter-template` as a blueprint to author a new plugin. Stay inactive for all ordinary engineering, research, git, or content operations tasks.

## Operating Loop

1. Confirm whether the request is a plugin-wiring verification check or a new-plugin authoring request.
2. Read `references/verification-checklist.md` on demand when detailed steps or scaffolding instructions are needed.
3. For verification checks, confirm that `starter-template` is mounted and report whether the example MCP server is needed (none is required for basic verification).
4. For authoring requests, guide copying `templates/starter-template/` to `plugins/<plugin-name>/`, updating `plugin.json` and `PLUGIN.md`, keeping `.mcp.json` only if needed, and running repository validation.

## Needs a Yes

Ask for explicit human confirmation before configuring credentials for any real MCP server, registering new marketplaces, or modifying repository files outside the agreed target directory. Always defer to stricter confirmation rules in the Bot's own profile.

## Resources & Tools

- `references/verification-checklist.md`: Detailed verification response items and new-plugin scaffolding checklist.
- `.mcp.json` (`example-http`): Placeholder HTTP MCP server declaration using `${EXAMPLE_MCP_TOKEN}` to demonstrate secret-free credential binding; never required for basic verification.
