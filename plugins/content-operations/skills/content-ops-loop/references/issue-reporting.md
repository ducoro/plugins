# Plugin Problem Feedback Protocol

When executing any skill or script in `content-operations`, if you hit a **plugin defect or upstream platform change**, proactively offer to submit a sanitized problem report through the built-in feedback channel so maintainers can fix it.

## When to Offer Feedback

**Offer to report** when you encounter:
- A built-in Python script crash, traceback, or unexpected non-zero failure on valid inputs.
- A platform official API change (deprecated version/metric, renamed required field, unexpected `400`/`426` schema error).
- A platform official browser Creator Studio layout change that breaks documented steps.
- A mismatch between `references/specs.json` and the platform's real live limits.
- Missing or contradictory skill instructions that block completing a documented step.

**Do NOT trigger feedback** for:
- Missing, mistyped, or expired user-owned credentials / tokens.
- Local network outages, user-side permissions/tier limits, or content moderation rejections on user copy.

## Mandatory Consent & Redaction

1. **Always ask first.** Never send feedback silently. Show the user the exact redacted message and ask for confirmation before running the send command.
2. **Redact strictly.** Never include raw draft copy, private brand notes, API tokens, cookies, passwords, personal account IDs, or local absolute filesystem paths.

## Standard Tag Format & Delivery

Start every report body with the exact structured prefix so maintainers can triage by plugin, skill, and location:

```text
[plugin:content-operations@<version>] [skill:<skill-name>] [location:<file-or-step>]

Summary: <one-line description of what failed>
Steps / Command: <exact subcommand or browser step, redacted>
Observed: <HTTP status / error code / symptom>
Expected: <what should have happened>
```

After the user confirms, send via the built-in feedback command:
```sh
ducoro-cli feedback send "<redacted report body>"
```
(If a screenshot helps diagnose a browser layout change, obtain explicit user approval before running `ducoro-cli feedback upload <image>`—PNG/JPEG/WebP up to 5 MiB—and attaching up to 4 repeatable `--image <id>` flags.)
