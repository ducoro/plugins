# Deterministic Brakes, Decision Trail & Repo-Native Memory

## Why This Environment Exists

Probabilistic execution still carries a non-zero risk of last-minute drift—a forgotten test run, a sneaky edit after sign-off, or repeating last month's incident. Code enforces the final tamper-proof brake, an append-only trail preserves accountability on long runs, and hard lessons are encoded permanently back into the target repository.

## 1. Deterministic Evidence & Tamper-Proof Locks (`scripts/change_gate.py`)

Never claim tests passed, a review cleared, or a release lock holds from memory:

1. **Objective diff guard**: Scan the net diff from `git merge-base <base> HEAD` to the current working tree for objective blockers—leaked secrets/tokens, hardcoded local home paths, newly added test skips (`.skip`, `xit`, `@unittest.skip`) or lint/type bypasses (`@ts-ignore`, `eslint-disable`, `# noqa`) in code files, and net-deleted test assertions:
   ```sh
   python3 <plugin-root>/scripts/change_gate.py --repo <repo-path> --state-dir <state-dir> check-diff --base <base-ref>
   ```
   - **Intentional dead-guard pruning**: Net assertion deletion is blocked by default. When legitimately pruning dead guards or compressing redundant cases into a stronger model, pass `--allow-assertion-pruning` on `check-diff`, `approve`, **and** `verify-release`, and document the superseding proof in `--summary` and `decisions.tsv` (secrets, local paths, skips, and lint bypasses remain unconditionally blocked).
2. **Record typed execution evidence**: Pin commands, exit codes, kind, and `headSha`/`diffHash` in `<state-dir>/gate-state.json`:
   ```sh
   # Normal test/build verification (or --kind formal-check for exhaustive/model checks; passes on exit code 0):
   python3 <plugin-root>/scripts/change_gate.py --repo <repo-path> --state-dir <state-dir> record-evidence \
     --kind verification --command "<test-cmd>" --run --base <base-ref>

   # Fault-injection red audit (run AFTER restoring the backed-up file; passes ONLY on non-zero --exit-code):
   python3 <plugin-root>/scripts/change_gate.py --repo <repo-path> --state-dir <state-dir> record-evidence \
     --kind fault-injection-red --command "<guard-cmd>" --exit-code 1 --summary "reverted branch X; test failed red" --base <base-ref>

   # Blind review cleared (zero introduced findings):
   python3 <plugin-root>/scripts/change_gate.py --repo <repo-path> --state-dir <state-dir> record-evidence \
     --kind independent-review --command "blind-review:6-lenses" --exit-code 0 --summary "0 introduced; 1 pre-existing debt" --base <base-ref>
   ```
3. **Tamper-proof merge/release approval lock** (`--action` accepts `merge | release | migrate`):
   ```sh
   # After explicit human confirmation on a reviewed commit/diff:
   python3 <plugin-root>/scripts/change_gate.py --repo <repo-path> --state-dir <state-dir> approve \
     --action release --risk high --approved-by "<human>" --summary "<scope/notes>" --base <base-ref>

   # Immediately before pushing, merging, or tagging:
   python3 <plugin-root>/scripts/change_gate.py --repo <repo-path> --state-dir <state-dir> verify-release \
     --action release --risk high --base <base-ref>
   ```
   - **Exact machine-enforced checks in `verify-release`**: (1) fresh `check-diff` has zero blockers; (2) an active `approve` record matches the exact current `headSha + diffHash` (changing even 1 byte fails with `tampered_after_approval`); (3) at least one passing `verification` or `formal-check` entry matches the exact same `headSha + diffHash` (`fault-injection-red` is audited separately and cannot substitute for passing verification); (4) when effective risk (`max(approved_risk, requested_risk)`—never downgraded) is `medium` or `high`, either a matching passing `independent-review` entry OR an audited human review waiver is present (`missing_independent_review` otherwise).
   - **Audited break-glass waiver (urgent human override)**: If the human explicitly instructs skipping blind review for an urgent hotfix, never fabricate an `independent-review` or downgrade `--risk`. Record the human's explicit waiver honestly by passing `--waive-review "<reason>"` to **both** `approve` and `verify-release` (and logging the waiver in `decisions.tsv`). Waivers never bypass secrets, local paths, skips, passing verification evidence, or tamper checks.
   - **Post-approval tiny typo**: If an unrelated 1-character doc typo is noticed after approval, either revert the typo to ship the exact approved hash and land the typo as a follow-up low-risk patch, or re-run verification, review (if medium/high), and human confirmation on the new hash.

## 2. Append-Only Decision Trail (Long or Multi-Phase Runs)

For multi-phase or unattended work, maintain `<state-dir>/decisions.tsv` (`ts\tphase\tdecision\twhy\tevidence\tresult`, never committed to the target repo unless requested). Log decision forks, verified milestones, pivots/reverts, blockers, and waivers using plain reasons and concrete pointers (`commit SHA`, `file:line`, output/screenshot paths). Never edit or delete earlier rows—supersede mistakes with a new row, and spot-check claims against real git history before handing back.

## 3. Encode Lessons Back Into the Target Repository

When a bug, incident, or repeated human correction reveals a structural gap, encode the guard permanently into the **target repository itself** (never hidden in plugin state). Prefer stronger structural guards (architecture boundaries, types, CI/lint checks, regression tests) over prose; add to the repo's `AGENTS.md` only for durable repo-specific invariants that code cannot enforce, and prune stale rules regularly.
