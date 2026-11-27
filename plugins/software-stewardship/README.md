# Software Stewardship

Long-term software repository stewardship for Ducoro—creating a structured engineering environment where requirements stay grounded, designs converge, implementations face real execution, formal checks, and multi-lens blind review, and releases pass deterministic tamper-proof gates.

## What It Solves

- **Zero-pollution repo-first workflow**: Operates directly on the human's existing local repository or GitHub project. No global workspace bootstrap is required; ephemeral pulse snapshots, approval locks, decision trails, and interactive boards stay inside the owning Space's `files/` directory.
- **Requirement alignment & multi-shape design (`playbooks/requirement-and-design.md`)**: Independent requirement expectations before coding, multi-shape architecture comparison, prototype-backed decisions, and convergence checks.
- **Verification, formal proof & 6-lens blind review (`playbooks/verification-and-review.md`)**: Evidence ladder, six-surface proof-obligation matrix, mandatory fault-injection red checks, Class A/B formal verification with user-facing statecharts, and risk-tiered blind review with adversarial re-verification.
- **Live external truth (`scripts/supply_chain_check.py`)**: Parses real project lockfiles (`package-lock.json`, `pnpm-lock.yaml`, `requirements.txt`, `pyproject.toml`, `Cargo.lock`, `go.mod`), queries the keyless public OSV.dev batch API for live CVEs, and flags copyleft license risks.
- **Deterministic git audits & tamper-proof gates (`scripts/repo_audit.py`, `scripts/change_gate.py`)**: Computes real diff blast radius, sensitive path touches, 30-day churn hotspots, stale worktrees, typed execution evidence (`verification`, `fault-injection-red`, `formal-check`, `independent-review`), objective diff blockers, and risk-aware `head_sha + diff_hash` approval locks.
- **Quiet pulse monitoring & shadcn/ui Boards (`scripts/repo_monitor.py`, `scripts/build_boards.py`)**: Tracks PRs, CI status, and revert signals with honest `no_material_change` quiet runs, projecting one-way into `delivery-board` and `health-board`.
- **External release platform protocols (`playbooks/release-platforms.md`)**: Concrete shipping and rollback guardrails for macOS notarization, App Store, Google Play, npm/PyPI/Homebrew/Docker OIDC publishing, and zero-downtime cloud/DB migrations.

## Layout

- `PLUGIN.md` — Domain role contract, Ducoro CLI one-hop workbench shortcuts, approval boundaries, and level-1 resource map.
- `playbooks/` — Stewardship loop & risk tiers, requirement/design alignment, verification/formal proof/blind review, deterministic brakes & repo-native memory, live docs & supply-chain checks, and external release platform rules.
- `references/state-schema.md` — Rebuildable Space-local state contracts.
- `scripts/` — Zero-dependency Python 3 stdlib scripts (`repo_audit.py`, `supply_chain_check.py`, `change_gate.py`, `repo_monitor.py`, `build_boards.py`).
- `assets/boards/` — Standalone + Ducoro Board SDK interactive dashboards (`delivery-board`, `health-board`).

## License

Apache License 2.0. See [LICENSE](LICENSE).
