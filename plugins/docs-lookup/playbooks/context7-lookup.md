# Context7 Library Documentation Lookup Playbook

Answer library-specific questions from live documentation, not memory.

## Prerequisite

This workflow uses the `context7` MCP connector (`resolve-library-id`, `query-docs`). If those tools are unavailable, check `ducoro-cli mcp list --json` for an existing definition. With the human's authorization, add a missing definition and verify connectivity:

```sh
ducoro-cli mcp add --slug context7 --transport http --url https://mcp.context7.com/mcp
ducoro-cli mcp probe context7
```

If a definition already exists, probe it first and explain any connection failure. Follow the service's current authentication instructions if required; keep credentials in Ducoro's credential storage. Continue once the tools are available, and report missing access instead of inventing results.

## Workflow

1. **Resolve.** Call `resolve-library-id` with the library name the user used. If several candidates return, pick by ecosystem match (language, framework) and state which one you chose.
2. **Query narrow.** Call `query-docs` with the resolved id and a focused query—the exact API, option, or task (for example `"app router middleware auth"`, not `"next.js docs"`).
3. **Answer against the source.** State the answer, quote the relevant signature or config snippet, and name the library version the docs describe when visible.
4. **Resolve divergence.** When the docs contradict memory, base the answer on the docs. Describe a version change only when versioned documentation or a changelog establishes it.

## Anti-patterns

- Do not answer version-sensitive questions purely from memory when the connector is available.
- Do not dump whole doc pages; extract the lines the question needs.
- Do not silently substitute a different library when resolution is ambiguous—ask.

## Done when

The answer cites which library id and doc topic it came from, or explicitly states that the documentation did not cover it.
