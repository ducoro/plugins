# Four-Tier Comment Triage & Platform Compliance

Every incoming comment stored in `engagement/inbox.json` gets one `tier` and one clear action path.

| Tier | Signal Examples | Default Action | Approval Gate | Feed Back to Topics? |
| --- | --- | --- | --- | --- |
| `high_intent` | Pricing, links, compatibility, booking, purchase or collaboration questions | Draft a direct, platform-compliant answer | **Human approval required** | Yes if asked 2+ times |
| `feedback` | Bug reports, factual corrections, strong counter-arguments | Verify the underlying fact first; draft a calm, clear reply | **Human approval required** | **Always** (`topicCandidate: true`) |
| `general` | Appreciation, brief reactions, emojis | Natural, varied acknowledgement matching the creator's voice | Autonomous only if enabled in `brand-profile.md` | Optional |
| `spam` | Bot ads, scams, pure abuse | Set `status: "ignored"`; do not argue in public | Delete/hide requires approval unless standing spam rule exists | No |

## Platform Compliance Red Lines in Comments
- **CN off-platform diversion (`引流红线`)**: Xiaohongshu, Douyin, Kuaishou, Bilibili, and WeChat Channels actively throttle or mute comments containing raw WeChat IDs, phone numbers, QR codes, external links, or homophone workarounds ("加V", "绿泡泡", "主页微"). Use official platform contact cards, pinned shop/service links, or compliant DM flows instead.
- **Cross-platform originality order**: When syndicating one piece across CN platforms (WeChat Official, Xiaohongshu, Bilibili, Douyin), publish and declare **Original (`原创`)** on the lead platform first—especially WeChat Official Account before third-party aggregators crawl it—to avoid false copyright strikes.
- **No fabricated commitments or copy-paste bursts**: Never promise unshipped features, discounts, or SLAs without human confirmation, and never blast identical replies (triggers spam classifiers). Always run `scripts/engagement_guard.py` before acting.
