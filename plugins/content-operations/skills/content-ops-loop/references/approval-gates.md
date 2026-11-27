# Approval Gates & Authority Boundaries

Every action in the content operations loop falls into one of three authority tiers.

## Authority Matrix

| Action | Default Tier | Condition to Auto-Execute |
| --- | --- | --- |
| Collect raw signals into `inbox/`, deduplicate, score topics | **Autonomous** | Always allowed within read-only / non-destructive bounds |
| Commit production effort to a topic (brief → full assets) | **Gate 1 (Human Approval)** | Only if a standing rule in `brand-profile.md` pre-authorizes that recurring series |
| Draft `master.md`, adapt per-platform variants, run image/spec checks | **Autonomous** | Allowed for approved topics; keep inside `drafts/` |
| Save local drafts or browser-side unpublished platform drafts | **Autonomous** | Never click final Publish; verify draft is saved privately |
| Publish content publicly or schedule public release | **Gate 2 (Human Approval)** | Explicit per-slot approval OR written standing-column rule in `brand-profile.md` (exact account, window, approved-draft-only rule, pause switch) |
| Pull comments and analytics snapshots | **Autonomous** | Respect platform API/browser rate limits |
| Reply to `general` praise/thanks comments | **Conditional Autonomous** | Only when enabled in `brand-profile.md` and strictly within rate limits |
| Reply to `high_intent` (pricing/links/sales) or `feedback` (bugs/disputes/claims) | **Human Approval** | Stage draft reply in `engagement/inbox.json` and surface on the Engagement Board |
| Delete/hide comments or edit/delete published works | **Human Approval** | Always require explicit confirmation except obvious spam per written policy |

## Gate 1: Topic Commitment

Before spending media or deep writing effort, present shortlisted topics directly in conversation—or trigger an immediate Inbox sign-off by looking up `<human-id>` and firing a manual Task:
```sh
ducoro-cli identity get --json
ducoro-cli task create --space <space-id> --manual --title "Gate 1 topic sign-off" \
  --human <human-id> --ask confirm --request-summary "Approve shortlisted topics for production" \
  --instruction "Review shortlisted topics in topics/topics.json and confirm which slots to produce." --json
ducoro-cli task fire <task-id> --space <space-id> --json
```
Include in every Gate 1 summary:
1. Target audience and single core claim.
2. Verified evidence vs. open fact gaps.
3. Target platforms and planned format per platform.
4. Four-dimension score and cooldown check result.

## Gate 2: Publish Authorization

Before any public publish (Connector, browser Studio, or optional API), verify all five checks and surface the confirmation directly to the human (never leave an approval silently buried in a local JSON file; use the same `--manual` + `ducoro-cli task fire <task-id> --space <space-id> --json` Inbox route when human attention is needed right away):
1. **Fact freshness & isolated review**: claims, versions, prices, and links are still true right now. For high-risk external releases or final long-form pieces, never self-certify `assessment.json` in the drafting context—inspect peers via `ducoro-cli space participant list <space-id> --json`, dispatch isolated fresh read-only reviewers via `ducoro-cli job dispatch` across orthogonal lenses (fact/provenance tracing, platform red lines/compliance, reader subtraction), and collect conclusions with `ducoro-cli job status <job-id> --json` and `ducoro-cli job log <job-id>`.
2. **Spec pass**: `check_media_specs.py` passed with zero blocking issues for that platform.
3. **Account match**: target `accountId` matches the intended brand/personal identity.
4. **Explicit authorization**: recorded `approvalRef` (human message/decision or standing column rule) plus tamper-proof `approvedVariantHash` verified by `validate_workspace.py --verify-slot <slotId>`.
5. **Post-publish readback plan**: confirm how `publicUrl` and `workId` will be verified and appended to `publish-log.jsonl`.

## Stale Approval & Scheduled Task Halt

If facts go stale (`needs_update`), copy changes after approval, or a scheduled release must be paused/cancelled, immediately inspect and halt the corresponding Ducoro task rather than letting an outdated wake-up fire:
```sh
ducoro-cli task list --space <space-id> --json
ducoro-cli task disable <task-id> --space <space-id>
# Or remove an obsolete one-shot task permanently:
ducoro-cli task rm <task-id> --space <space-id>
```

## Unknown Outcome Rule

If a publish or engagement request times out or loses network after submission, **do not blindly retry** (avoid duplicate posts or spam). Check the live account/work list first, reconcile `publish-log.jsonl` or `action-log.jsonl`, and ask the human if live state cannot be confirmed.
