# Pull Request Description Playbook

Give the reviewer a clear map before they enter the diff.

## Structure

1. **Why** (1–3 sentences): the problem or goal this PR exists for. Link the issue or Space when one exists.
2. **What changed**: the semantic changes as short bullets, grouped by subsystem—not a raw file list.
3. **How it was verified**: the exact commands run (tests, typecheck, manual steps) and their outcomes. Explicitly name unverified parts as unverified.
4. **Review guide**: which file to start with, what is mechanical vs. load-bearing, and any subtle change a reviewer might mistake for a bug.
5. **Risk / rollout**: behavior changes, migrations, feature flags, or revert plan—only when applicable; omit empty sections.

## Anti-patterns

- Do not restate the commit list as the PR description; tell the aggregate story.
- Do not claim "tests pass" without naming which suite actually ran.
- Do not hide breaking changes inside a bullet list—lead the Risk section with them.

## Done when

A reviewer who reads only the description can decide where to focus, how much to trust the verification, and what could break.
