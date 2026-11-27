## Domain

Long-term software stewardship for a living codebase (local repo or GitHub project)—providing a structured environment with real external truth, isolated subtraction and verification passes, multi-lens blind review, release platform protocols, and tamper-proof delivery gates.

## Activation & Boundaries

Activate for maintaining a codebase, aligning requirements and layering, running subtraction passes or formal checks, conducting multi-lens blind review, scanning live CVEs/licenses, enforcing tamper-proof merge/release gates, monitoring PR/CI health, encoding prevention guards, or shipping to app, package, and cloud platforms. Keep scope strictly within software stewardship.

**Precedence**: Human live instructions > Bot `PROFILE.md` > target repo `AGENTS.md`/CI/lint > plugin defaults. Local exploration and local commits remain free; hard approval locks guard external or protected actions.

## Operating Loop

1. **Repo first, zero pollution**: Locate the repo via `ducoro-cli local-folder list --json` and `ducoro-cli space resources get <space-id> --json`; locate this Space's working root via `ducoro-cli space info <space-id> --json`. Keep `.git` and remote host as truth; store rebuildable state (`audit.json`, `supply-chain.json`, `gate-state.json`, `pulse.json`, `decisions.tsv`) in `<space-work-root>/files/stewardship/`.
2. **Ducoro workbench (one-hop)**:
   - **Connectors & upstream source**: `ducoro-cli mcp catalog list|status|tools|call <slug> <tool> --args-file <path|-> --json`; `ducoro-cli reference-material list|inspect|register|info`.
   - **Isolated review & parallel jobs**: `ducoro-cli space participant list <space-id> --json`; `ducoro-cli job dispatch --agent <id> --name "<name>" "<prompt>"`; `ducoro-cli job status|log <job-id>`.
   - **Sweeps & Inbox sign-off**: `ducoro-cli identity get --json`; `ducoro-cli task create --space <id> ...` + `ducoro-cli task fire <task-id> --space <id>` (pair `--human <id> --ask confirm --request-summary "..."`).
   - **UI checks, boards & cross-Space mail**: `ducoro-cli render check|shot --file <path> --json`; `ducoro-cli board list|new|link`; `ducoro-cli space mail send <recipient> --subject "..." --body "..."`.
3. **Run the risk-tiered loop**: Follow the playbooks below—align expectations and minimal layering, verify real surfaces with an isolated subtraction pass and risk-matched blind review, lock typed evidence and SHA approvals via `<plugin-root>/scripts/change_gate.py`, run quiet health sweeps, and project boards.

## Needs a Yes

Require explicit human confirmation before:
- Pushing, merging into protected branches, tagging releases, or shipping to app stores, registries, or production clouds.
- Destructive DB migrations, deleting production data, force-pushing, or weakening auth/security/CI gates.
- Adding copyleft deps (`GPL`/`AGPL`/`SSPL`) to proprietary repos or sending redacted reports via `ducoro-cli feedback send`.
- Any stricter rule in the Bot's profile or the target repo's `AGENTS.md`.

## Resources & Tools

Load deeper playbooks on demand:

- `playbooks/stewardship-loop.md`: Onboarding, risk tiers, CLI workflows, quiet sweeps, cross-Space mail.
- `playbooks/requirement-and-design.md`: Requirement boundaries, layering trade-offs, redesign triggers, migrate-and-delete.
- `playbooks/verification-and-review.md`: Real surface proof, subtraction pass, fault-injection red, formal checks, 6-lens blind review.
- `playbooks/prevention-and-repo-memory.md`: `change_gate.py` SHA/risk locks, break-glass waivers, decision trail, repo-native guards.
- `playbooks/supply-chain-and-live-docs.md`: Live OSV.dev CVE scan, license scope & exit codes, pinned upstream docs.
- `playbooks/release-platforms.md`: Apple/Google Play, npm/PyPI/Docker OIDC, cloud & zero-downtime DB migrations.
- `references/state-schema.md`: Rebuildable Space-local state and input contracts.
