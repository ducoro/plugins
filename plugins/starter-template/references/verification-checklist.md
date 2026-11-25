# Starter Template Verification & Scaffolding Checklist

## Verification Check

When asked to verify that `starter-template` is mounted and working:

1. Confirm that the request explicitly targets `starter-template` verification.
2. Reply concisely with:
   - Plugin name: `starter-template`
   - Entry file loaded: `PLUGIN.md`
   - On-demand file read: `references/verification-checklist.md`
   - Example MCP status: `.mcp.json` declares `example-http` with `${EXAMPLE_MCP_TOKEN}`; no external call or secret credential is required for this check.

## Authoring a New Plugin from This Blueprint

1. Verify orthogonality against every existing plugin in `marketplace.json` before creating a new directory.
2. Copy `plugins/starter-template/` to `plugins/<plugin-name>/` and preserve an exact copy of `LICENSE`.
3. Update `plugin.json` (`name`, `version`, `description`, `license: "Apache-2.0"`, and `"mcpServers": "./.mcp.json"` only when `.mcp.json` is kept).
4. Author `PLUGIN.md` (≤ 4,000 UTF-16 chars, no YAML frontmatter) with the five required sections: `Domain`, `Activation & Boundaries`, `Operating Loop`, `Needs a Yes`, and `Resources & Tools`.
5. Place deeper playbooks, schemas, scripts, or assets in level-2/level-3 subdirectories referenced progressively from `PLUGIN.md`.
6. Register the plugin in `marketplace.json`, add links in `README.md` and `README.zh-CN.md`, and run `python3 scripts/validate.py` and `python3 -m unittest discover -s tests -v`.
