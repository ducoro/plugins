# Customer Support Boundaries, VoC Synthesis & KB Deflection

Closing tickets one by one is a treadmill. High-leverage support operations enforce clear trust boundaries on every reply while compounding verified insights that prevent future tickets and guide product priorities.

## 1. Outbound Reply Boundaries (Leaving Tone to the Bot Profile)

Leave tone, phrasing, and bedside manner to the mounted Bot's `PROFILE.md` and human instructions. Regardless of style, every customer reply must stay inside four objective boundaries:

- **Factual grounding only**: Cite only verified symptoms, account facts, and confirmed workarounds—never invent root causes or unverified fix timelines.
- **No unauthorized commitments**: Never admit legal liability or promise refunds, credits, ship dates, or uptime guarantees without explicit human approval pinned by `scripts/reply_guard.py`.
- **Direct question coverage**: Address every concrete question in the customer's latest message, or state plainly what is still under investigation and when the next verified update will arrive.
- **Escalation handoff**: Whenever `triage_gate.py` marks `requiresHumanApproval: true`, stage the draft, run the isolated read-only review (`playbooks/reply-safety-and-boards.md`), and present clear decision options to the human before sending.

## 2. Six-Element Engineering Escalation Package

When handing a confirmed defect to an engineering Space via `ducoro-cli space mail send`, never forward raw vague complaints. Include six verifiable elements:

1. **Impact scope**: Priority, affected `uniqueCustomers` count, and whether revenue or onboarding is blocked.
2. **Minimal reproduction steps**: Exact sequence, inputs, and expected vs actual behavior.
3. **Environment**: App version, OS/browser, account tier (stripped of PII and secrets).
4. **Troubleshooting already completed**: Rules out duplicates or user-config issues.
5. **Source citations**: Exact `ticketId`s and upstream URLs for auditability.
6. **Decision requested**: Clear ask (hotfix now, workaround guidance, or backlog triage).

## 3. Isolated Read-Only Verification for Escalations & VoC Clusters

Before sending a high-impact engineering escalation or weekly VoC spike summary via `ducoro-cli space mail send`, dispatch an independent read-only audit job so clustering bias and unverified claims are caught before crossing Space boundaries:

```sh
ducoro-cli space participant list <space-id> --json
ducoro-cli job dispatch --space <space-id> --agent <reviewer-agent-id> \
  --name "audit-voc-escalation" \
  "Read-only audit of proposed escalation/VoC brief against <data-dir>/tickets/tickets.json and sla-report.json. Do NOT edit files. Verify two orthogonal dimensions: (1) Anti-false-consensus clustering—confirm uniqueCustomers counts reflect distinct customers experiencing the same root mechanism, not one loud user or unrelated symptoms merged together; (2) Escalation package grounding—confirm all 6 elements are present, PII/secrets are redacted, every ticketId/URL exists verbatim, and no root cause is speculated without evidence."
ducoro-cli job status <job-id> --json
ducoro-cli job log <job-id>
```

## 4. Anti-False-Consensus Voice of Customer (VoC) Layering

Raw ticket counts routinely mislead product decisions when one loud user sends five follow-ups or asks for a specific button instead of naming the real bottleneck. Classify every root-cause cluster across four tiers:

| VoC Tier | Definition | Decision Weight |
|---|---|---|
| `blocker_bug` | Core workflow broken or data corrupted | Immediate engineering fix |
| `churn_signal` | Paying customer threatening cancellation, migration, or non-renewal | Urgent human retention review |
| `workflow_friction` | Repeated confusion or manual workarounds across distinct customers | High-ROI UX fix or KB deflection |
| `feature_wish` | Single-customer enhancement request | Log cleanly; do not derail roadmap |

### Hard Anti-False-Consensus Invariants (Enforced by `scripts/triage_gate.py`)
- **Count `uniqueCustomers`, not just raw tickets**: One customer sending 5 messages equals `uniqueCustomers = 1` and cannot trigger a product-wide spike alert (`spikeMinUniqueCustomers >= 2`).
- **Real window trends for every cluster**: `sla-report.json` records `clusterMetrics` (`recent7dCount`, `prior7dCount`, `uniqueCustomers`, `spikeRatio`) across all clusters—never fabricate 7-day trends from all-time totals.
- **Separate verbatim request from underlying job**: Retain the customer's exact quote alongside the root problem so the principal can verify interpretation.

## 5. Knowledge Base Deflection Loop

Every routine question asked by `>= 3` distinct customers in the recent 7-day window is flagged automatically as a **`kbDeflectionCandidate`**:
1. Draft or update a concise help-center article or in-product microcopy fix under `kb/`.
2. Link the KB article in replies for that cluster.
3. Measure whether tickets for that `rootCauseId` drop in the next 14-day window—the true metric of support leverage is prevented tickets, not faster manual typing.
