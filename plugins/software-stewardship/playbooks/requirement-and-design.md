# Requirement Alignment & Layering Boundaries

## Why This Environment Exists

Strong models rarely fail on syntax; they fail when an unchecked assumption shifts the starting line by five degrees and code plus tests stay locally self-consistent around the wrong goal, or when stacked workarounds erode architecture. This environment sets soft boundaries before code locks in—without dictating how you must think or format notes.

## 1. Requirement-First Boundaries

Current requirements and confirmed human decisions are the specification; existing code, existing tests, fixtures, and snapshots are **current-state evidence** only.

- **Independent expectation**: Before trusting existing code or tests, pin down who acts, from what state, through which real entry point, what observable outcome/persisted state must hold, and what side effects or authority boundaries are forbidden—along with what objective artifact proves the problem is solved.
- **Engineering experiments vs. human decisions**:
  - Choices an experiment can settle (latency, layout, parser behavior, local ergonomics) belong to engineering—test with a quick throwaway prototype or `ducoro-cli render shot` rather than debating in the abstract.
  - Ambiguous, missing, or conflicting product semantics and trade-offs belong to the human—stop and present the concrete options instead of guessing silently.
- **Conflict resolution**:
  - Code contradicts the confirmed requirement -> reproduce the failure against the requirement first, then fix.
  - Code matches the requirement but an old test/fixture is stale -> update the test against the requirement and verify it can fail via fault injection.
  - Requirement itself is unclear or contradictory -> mark undecided and ask the human.

## 2. Minimal Layering & Design Convergence

Good layering eliminates glue code before implementation begins. You are free to choose the concrete structure, subject to four soft boundaries:

- **Reuse before adding**: Inspect existing repo helpers, types, and modules before introducing new abstractions.
- **Favor single state ownership & minimal necessary code**: Given equal requirement satisfaction, plain readability (never cryptic compression), and zero unnecessary third-party dependencies, prefer the layering with single state ownership, one canonical path, and less code.
- **Multi-candidate convergence for high-stakes or contested designs**: When a design is expensive to reverse, dispatch independent candidates with identical requirements into isolated scratch paths or git worktrees (`ducoro-cli job dispatch`) and synthesize the cleanest base. If independent attempts converge, boundaries are solid; if they wildly diverge, the requirement itself is under-specified—tighten the requirement rather than averaging incompatible shapes.

## 3. Structural Pain Triggers vs. Scope Discipline

When `<plugin-root>/scripts/repo_audit.py` flags repeated cross-module shotgun commits (`architectureSignals.shotgunCommits`), oversized files (`largeFiles`), or high-churn hotspots—or when git history / `decisions.tsv` shows a 2nd–3rd workaround around the same boundary—apply one clear referee rule so structural cleanup never silently becomes scope creep:

- **Pain is outside the current task's boundary**: Log it transparently as pre-existing debt and keep the current change narrowly scoped.
- **Pain sits directly on the boundary you are changing**: Pause patching and present the human with two concrete options—(a) minimal scoped fix + logged debt, or (b) approved scope expansion to fix the boundary first. Never silently expand a small feature into a repo-wide refactor.
- **Migrate-and-delete when a boundary is replaced**: Enumerate all callers, migrate them to the new path, and physically delete the old path, adapter glue, and obsolete guards in the same batch (using `--allow-assertion-pruning` with explicit human sign-off if dead test assertions are removed).
