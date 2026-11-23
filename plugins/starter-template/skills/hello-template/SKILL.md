---
name: hello-template
description: Verify that the starter-template plugin is loaded and demonstrate the minimal structure of a Ducoro Agent Skill.
---

# Hello Template

Use this skill when verifying plugin installation, indexing, or sync behavior, or when using `starter-template` as a blueprint for a new plugin.

## Workflow

1. Confirm the request asks to verify the `starter-template` plugin or inspect the reference skill structure.
2. Reply with a short confirmation that includes:
   - Plugin name: `starter-template`
   - Skill name: `hello-template`
   - Whether any optional MCP configuration in `.mcp.json` is needed for the current task (none is required for this verification check).
3. If the user is authoring a new plugin, direct them to copy `plugins/starter-template/` and replace `plugin.json`, skill files, and optional `.mcp.json`.

## Completion criteria

- The response is concise, accurate, and directly confirms the skill was read.
- No external network call or secret credential is required to complete this check.
