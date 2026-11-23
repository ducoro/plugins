# Four-Tier Comment Triage

Every incoming comment stored in `engagement/inbox.json` gets one `tier` and one clear action path.

| Tier | Signal Examples | Default Action | Approval Gate | Feed Back to Topics? |
| --- | --- | --- | --- | --- |
| `high_intent` | "Where is the link?", "How much?", "Does it support X?", "Can I try this?" | Draft a direct, platform-compliant answer (avoid banned off-platform phrasing on CN platforms) | **Human approval required** | Yes if asked 2+ times |
| `feedback` | "This broke on step 3", "Your benchmark is misleading", "Why not use Y instead?" | Verify the underlying fact first; draft a calm, evidence-backed reply without defensiveness | **Human approval required** | **Always** (`topicCandidate: true`) |
| `general` | "Great breakdown!", "Saved!", emoji reactions | Short, varied, human-sounding acknowledgement (never identical copy-paste) | Autonomous only if enabled in `brand-profile.md` | Optional |
| `spam` | Bot ads, scam links, pure trolling | Set `status: "ignored"`; do not argue in public | Delete/hide requires approval unless standing spam rule exists | No |

## Reply Quality Rules
- Match the commenter's language and the platform's tone.
- Answer the actual question in sentence one; keep replies under 2–3 sentences unless a technical walkthrough is needed.
- Never promise unshipped features, discounts, or SLAs without explicit human confirmation.
- Never reply to multiple comments with identical templates (triggers spam classifiers).
