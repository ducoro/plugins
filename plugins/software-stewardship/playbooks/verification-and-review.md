# Verification, Subtraction, Formal Proof & Multi-Lens Blind Review

## Why This Environment Exists

When the same context writes both the implementation and the checks, "it compiles" and "tests are green" can still hide shared blind spots, silent bloat, or broken edge interleavings. Rather than lecturing you on generic testing habits, this environment puts the change through **four independent falsification environments** scaled to risk.

## 1. Real Surface Verification & Isolated Subtraction Pass

1. **Verify on the real changed surface**: Run the real CLI/binary, exercise the real UI path (`ducoro-cli render check|shot --file <path> --json`), or read back persisted storage bytes and external-producer inputs rather than relying on verbal reasoning or same-code roundtrips alone. If claiming a performance win, name the concrete bottleneck and compare alternating production-tuned runs; otherwise report `inconclusive`.
2. **Separate building from cutting (Isolated Subtraction Pass)**: Making tests green invites defensive branches, one-off wrappers, and duplicated helpers; once green, sunk-cost bias makes cutting hard. Switch environments after tests pass:
   - Read `<plugin-root>/scripts/repo_audit.py` objective physical signals first (`blastRadius.netLines`, `blastRadius.newFiles`, `blastRadius.dependencyManifestTouches`, `largeFiles`, `architectureSignals.shotgunCommits`). These are a **thermometer, not a hard gate**—scripts cannot judge semantic duplication or distinguish clear code from bloat.
   - Under green-test protection (for large diffs, dispatch a fresh seated agent via `ducoro-cli job dispatch` with zero sunk-cost attachment), trim only the diff: swap duplicated helpers for existing repo primitives, fold speculative one-off wrappers and dead branches, run the repo's native dead-code checks where available (`knip`, `vulture`, compiler `dead_code`), and re-run verification to prove identical behavior and plain readability without adding unnecessary dependencies.

## 2. Proof Obligations & Fault-Injection Red Check

Anchor tests on independently falsifiable **proof obligations** (which real bug turns this check red?) across the surfaces your change touches—especially cross-producer external inputs, authority/state transitions, retries/concurrency (using controllable clocks/signals, not blind sleeps), persistence recovery, real downstream consumers, and error recoverability.

- **Prove new or edited guards can fail red**: Before trusting a new guard on medium/high-risk changes:
  1. Back up the target production file into `<state-dir>/tmp/` (never inside the target repo, and never use `git checkout --` to discard uncommitted edits);
  2. Deliberately break or revert the guarded production line and run the check to confirm a **non-zero exit**;
  3. **Restore the backed-up file first** (so `diffHash` matches the clean working tree, not the broken variant) and delete the temporary backup from `<state-dir>/tmp/`;
  4. Record the audit trail entry using the full command in `playbooks/prevention-and-repo-memory.md` (`--kind fault-injection-red`, which passes **only** on non-zero `--exit-code` and serves as audit evidence—it does not substitute for passing `--kind verification`).

## 3. Formal Verification & Human-Readable Statecharts

When correctness depends on **state transitions, concurrent interleavings, retries, idempotency, authority revocation, or accounting/data invariants**, example tests miss the exact interleaving that fails in production:

- **Class A (finite exhaustive enumeration)**: Execute the real implementation across every combination of a bounded equivalence domain against an independent reference oracle.
- **Class B (bounded state-machine / model checking)**: Explore reachable states (BFS harness or TLA+/TLC) where each atomic action maps 1-to-1 to an indivisible implementation step.

Non-negotiable standards:
1. Map modeled states/actions to real files and functions, and record covered paths plus the **last verified commit SHA** so refactors flag drift.
2. Prove the invariant fails on a deliberately broken variant; never weaken a property to force green.
3. Replay every model counterexample against the real entry point before filing a product defect, and state bounds/assumptions honestly.
4. Translate key invariants and shortest counterexamples into plain domain language with Mermaid statecharts so non-specialists can review behavior directly.

## 4. Risk-Tiered Multi-Lens Blind Review & Adversarial Re-Check

Physically separate **writing** from **reviewing** (`playbooks/stewardship-loop.md`). Keep all **six orthogonal lenses**, and scale reviewer count to scope:

- **Low risk**: Exempt from blind review; record the rationale and deterministic verification evidence.
- **Medium risk or localized high risk**: Dispatch **one fresh, read-only reviewer** covering all six lenses in order; the lead verifies every finding directly against code.
- **Broad multi-subsystem high risk**: Dispatch **parallel fresh, read-only reviewers** across the six lenses, then send findings to an **independent adversarial verifier** whose default stance is *"false until proven by real code or a failing command"* (seeing only the finding and repo snapshot—never the original reviewer's reasoning).

### Dispatch & Collection Contract
1. Inspect seated Agents via `ducoro-cli space participant list <space-id> --json`. Because `ducoro-cli job dispatch` always runs in a **fresh native session** with zero conversation history, **single-Bot Spaces can dispatch blind review directly to the seated Lead Agent** (if multiple Agents or distinct models are seated, prefer a different Agent for perspective diversity).
2. Dispatch a fresh session (`job dispatch` starts immediately—no separate start step):
   ```sh
   ducoro-cli job dispatch --space <space-id> --agent <reviewer-agent-id> --name "blind-review" "<brief>"
   ```
   Pass only the original human requirement, confirmed scope, and repo path / commit or diff reference (write large diffs to `<state-dir>/review.diff` instead of stuffing shell args, and delete `<state-dir>/review.diff` once review finishes)—never pass the author's excuses or self-check conclusions. Explicitly instruct the reviewer to stay **strictly read-only** (no file edits, no commits).
3. Collect completion and report via `ducoro-cli job status <job-id> --json` and `ducoro-cli job log <job-id>`.

### Six Orthogonal Lenses
1. **Rollback Falsifiability**: Revert each modified block mentally—which test fails? None implies unguarded logic or dead code.
2. **Same-Symptom & Side Effects**: What sibling states/timings cause the same symptom? Did the change hide a previously visible fact or break an existing action?
3. **Exhaustive Peer Sweep (Horizontal)**: Were all sibling write sites, consumers, fixtures, and docs checked? State the search method used.
4. **Contract & Projection Sync (Vertical)**: Are APIs, CLIs, schemas, events, UI projections, and docs synchronized?
5. **Ownership, Necessity & Minimalism**: Why is each changed file needed? Did scope creep, logic land in the wrong layer, or redundant helpers/wrappers remain that can be safely deleted?
6. **Test Portfolio Sync**: Derive expected behavior independently from the original requirement first, then compare against both code and tests to catch shared drift; check minimal proof set and dead-guard cleanup.

### Two-Bucket Disposition & Clearance
Separate verified findings into **Introduced in this change** (blocks shipping—must reach **zero**) and **Pre-existing debt** (logged transparently—never hijacks the current change). Unproven style nitpicks are dropped with reasons noted. Once **Introduced** reaches zero, record clearance via `change_gate.py record-evidence --kind independent-review` (full syntax in `playbooks/prevention-and-repo-memory.md`).
