# Conventional Commit Playbook

Turn a diff into durable history: `type(scope): subject` plus enough description for a future engineer or agent to understand the coherent change.

## Workflow

1. **Read the actual change.** Run `git diff --staged` (or inspect the named files)—never write a message from the task description alone.
2. **Pick one type.** `feat` / `fix` / `refactor` / `docs` / `test` / `chore` / `perf`. Mixed changes mean splitting the commit, not mixing types.
3. **Subject line.** Give the staged change a concise, distinguishable name: `fix(mcp): skip sse entries when importing codex config`. Accuracy and recognizability matter more than a rigid sentence template.
4. **Body.** Add a description when the subject alone does not carry enough context. Summarize the outcome and intent of the change, plus constraints, verification, migration, or risk when they matter.
5. **Footer.** Include only real metadata: `BREAKING CHANGE:`, issue refs, or co-authors.

## Anti-patterns

- Do not write generic subjects like `fix: fix bug` or `chore: update code`.
- Do not list every touched file in the body; name the semantic change once.
- Do not bundle unrelated changes into one commit just to avoid writing two messages.

## Done when

Someone reading `git log --oneline` a year later can identify the coherent change, and the full message carries enough context to understand why it happened.
