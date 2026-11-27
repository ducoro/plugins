# Customer Support, VoC Synthesis & KB Deflection Methodology

Closing tickets one by one is a treadmill. High-leverage support operations protect trust on every reply while compounding insights that shrink future ticket volume and guide product priorities.

## 1. Five-Step De-escalation Reply Framework (Warm Without Over-Promising)

Never emit hollow corporate boilerplate ("We apologize for the inconvenience and have forwarded your feedback"). Structure replies for frustrated, urgent, or billing-sensitive customers in five clear parts:

1. **Specific acknowledgment**: Mirror the exact symptom in plain words so the customer knows a human-grade check occurred.
2. **Empathy without unauthorized liability**: Acknowledge impact calmly without admitting legal fault or promising unapproved refunds/credits.
3. **Verified facts or immediate workaround**: State what is already confirmed and give a concrete workaround if one exists.
4. **Honest next step & realistic checkpoint**: Commit only to a verifiable follow-up window (never invent ship dates or 100% uptime guarantees).
5. **Clear human escalation handoff**: When `triage_gate.py` flags `requiresHumanApproval`, route to the human with recommended options before sending.

## 2. Six-Element Engineering Escalation Package

When handing a confirmed defect to an engineering Space via `ducoro-cli space mail send`, never forward raw vague complaints. Package six concrete elements:

1. **Impact scope**: Priority, affected `uniqueCustomers` count, and whether revenue/onboarding is blocked.
2. **Minimal reproduction steps**: Exact sequence, inputs, and expected vs actual behavior.
3. **Environment**: App version, OS/browser, account tier (redacted of PII/secrets).
4. **Troubleshooting already completed**: Rules out duplicates or user-config issues.
5. **Source citations**: Exact `ticketId`s and upstream URLs for auditability.
6. **Decision requested**: Clear ask (hotfix now, workaround guidance, or backlog triage).

## 3. Anti-False-Consensus Voice of Customer (VoC) Layering

Raw ticket counts routinely mislead product decisions when one loud user sends five follow-ups or asks for a specific button instead of naming the real bottleneck. Classify every root-cause cluster across four tiers:

| VoC Tier | Definition | Decision Weight |
|---|---|---|
| `blocker_bug` | Core workflow broken or data corrupted | Immediate engineering fix |
| `churn_signal` | Paying customer threatening cancellation, migration, or non-renewal | Urgent human retention review |
| `workflow_friction` | Repeated confusion or manual workarounds across distinct customers | High-ROI UX fix or KB deflection |
| `feature_wish` | Single-customer enhancement request | Log cleanly; do not derail roadmap |

### Hard Anti-False-Consensus Rules (Enforced by `scripts/triage_gate.py`)
- **Count `uniqueCustomers`, not just raw tickets**: One customer sending 5 messages equals `uniqueCustomers = 1` and cannot trigger a product-wide spike alert (`spikeMinUniqueCustomers >= 2`).
- **Separate verbatim request from underlying job**: Always retain the customer's exact quote alongside the root problem so the principal can verify interpretation.

## 4. Knowledge Base Deflection Loop

Every routine question asked by `>= 3` distinct customers with a known answer is flagged automatically as a **`kbDeflectionCandidate`**:
1. Draft or update a concise help-center article / in-product microcopy fix under `kb/`.
2. Link the KB article in approved replies for that cluster.
3. Measure whether tickets for that `rootCauseId` drop in the next 14-day window—the true metric of support leverage is prevented tickets, not faster manual typing.
