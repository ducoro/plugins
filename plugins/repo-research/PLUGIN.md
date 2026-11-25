## Domain

Architecture and codebase research for public GitHub repositories via DeepWiki—mapping wiki structure first, reading relevant topics, and answering targeted questions with verifiable topic citations.

## Activation & Boundaries

Activate when understanding an unfamiliar public GitHub repository's architecture, locating where a feature lives in a public repo, or investigating how an external open-source project solves a problem. Stay inactive for versioned SDK/library API signature lookups (leave that to `docs-lookup`), local git commit or PR authoring (leave that to `git-workflows`), local workspace code editing, and content operations tasks.

## Operating Loop

1. Confirm the exact `owner/repo` slug with the human if ambiguous—never guess repository ownership.
2. Ensure the `deepwiki` MCP connector (`read_wiki_structure`, `read_wiki_contents`, `ask_wiki_question`) is available; read `playbooks/deepwiki-research.md` if setup or troubleshooting is needed.
3. Map structure first via `read_wiki_structure`, select only the 1–3 relevant topics, and choose targeted `ask_wiki_question` or focused `read_wiki_contents` extraction rather than cloning or dumping whole wikis.
4. Synthesize a concise, sourced answer where every load-bearing claim cites the wiki topic read and explicitly flags unanswerable gaps.

## Needs a Yes

Obtain explicit human approval before adding a new `deepwiki` MCP definition via `ducoro-cli mcp add` or storing credentials. Always defer to stricter confirmation rules in the Bot's own profile.

## Resources & Tools

- `playbooks/deepwiki-research.md`: Connector setup via `ducoro-cli mcp`, structure-first query workflow, citation requirements, and anti-patterns.
- External connector used when configured: `deepwiki` MCP (`read_wiki_structure`, `read_wiki_contents`, `ask_wiki_question`).
