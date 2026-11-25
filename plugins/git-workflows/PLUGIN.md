## Domain

Change-history and code-review communication for Git repositories—turning real diffs into clear conventional commit messages and actionable pull-request descriptions.

## Activation & Boundaries

Activate when asked to draft or refine a Git commit message, split mixed staged changes into coherent commits, or write/update a pull-request description for a branch or diff. Stay inactive for researching external GitHub repositories (leave that to `repo-research`), querying third-party library documentation (leave that to `docs-lookup`), content marketing workflows, and unrelated coding tasks where no commit or PR communication is requested.

## Operating Loop

1. Always inspect the actual diff first (`git diff --staged`, `git diff`, or `git log`)—never author commit or PR text from memory or a task summary alone.
2. Read the matching level-2 playbook (`playbooks/conventional-commit.md` or `playbooks/pr-description.md`) before drafting.
3. Keep each commit semantically cohesive (split mixed concerns instead of inventing compound types) and keep PR descriptions grounded in actually executed verification commands and real risks.
4. Deliver reviewable text that lets a future engineer or reviewer understand intent, verification, and blast radius before opening every line of the diff.

## Needs a Yes

Obtain explicit human approval before executing destructive Git history rewrites, pushing to a remote, or opening/editing a remote pull request. Always defer to stricter confirmation rules in the Bot's own profile.

## Resources & Tools

- `playbooks/conventional-commit.md`: Rules for `type(scope): subject`, body depth, footers, and anti-patterns.
- `playbooks/pr-description.md`: Five-part PR description structure (Why, What changed, Verification, Review guide, Risk/rollout) and anti-patterns.
