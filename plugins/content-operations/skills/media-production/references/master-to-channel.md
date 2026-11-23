# Master Draft to Per-Platform Projection

One topic produces one canonical `master.md` and N native `variants/<platform>.md` files. Facts stay invariant; framing, pacing, and visual packaging change per platform.

## Canonical `master.md` Structure

```markdown
# <Working Title>

- **Topic ID**: top-20260115-01
- **Core Claim**: <one sentence>
- **Canonical URL**: <verified link if applicable>

## Verified Facts & Sources
- Fact A — source: `<ref>`
- Fact B — source: `<ref>`

## Core Argument / Story Arc
1. Problem / Tension
2. Mechanism / Evidence
3. Concrete Takeaway / Action

## Visual Proof Inventory
- `assets/hero-demo.png` — what it proves
```

## Variant File Format (`variants/<platform>.md`)

Every variant starts with a machine-readable ```` ```json ```` metadata fence (parsed by `check_media_specs.py`) followed by publishable body copy. Never use YAML frontmatter.

````markdown
```json
{
  "platform": "xiaohongshu",
  "mode": "image_text",
  "title": "20-char native title",
  "topics": ["tag1", "tag2"],
  "cover": {"path": "assets/cover-optional.jpg"},
  "media": [
    {"type": "image", "path": "assets/xhs-cover-3x4.jpg"},
    {"type": "image", "path": "assets/xhs-card-02.jpg"}
  ],
  "options": {}
}
```

Publishable body copy goes here below the metadata block...
````

### Special Conventions
- **Video covers & duration**: attach video covers under top-level `"cover": {"path": "assets/cover.jpg"}` (never inside `media[]`, which forbids mixing images and video). Include `"durationSec": 45` on video objects in `media[]` so `check_media_specs.py` validates duration limits.
- **Spoken scripts vs. captions**: keep full video voiceover scripts and shot lists in `drafts/<draft-id>/script.md`; keep `variants/<platform>.md` body strictly to the publishable caption/description.
- **Multi-tweet / Threads series**: separate sequential posts with `\n---\n` in the body (or supply `"threads": ["Post 1...", "Post 2..."]` in the JSON header). `check_media_specs.py` validates each post individually against the 280/500 char ceiling (with X t.co 23-char URL weighting and CJK/emoji double weighting).
- **Temporary public HTTPS media relay (for URL-fetch platforms)**: Keep canonical media files locally in `drafts/<draft-id>/assets/` for spec validation and archiving. For APIs that fetch from a public HTTPS URL (**Instagram, Facebook Page, Threads, Pinterest**, and optionally TikTok `PULL_FROM_URL`), obtain a temporary 5-hour HTTPS URL **just before publishing** (never days in advance when scheduling):
  - **In Ducoro**: run `ducoro-cli media upload <local-file> --json` (supports images and videos up to 300 MiB with automatic resumable multipart upload; returns `{ id, publicUrl, filename, contentType, sizeBytes, sha256, createdAt, expiresAt, ttlSeconds: 18000, status }`). The `publicUrl` (`https://media-tmp.ducoro.ai/<token>`) expires automatically after 5 hours—no manual cleanup command is needed; if a publish is retried later, re-upload before calling the platform API. You can inspect prior uploads via `ducoro-cli media list --json`.
  - **On non-Ducoro hosts**: upload the local file to your own HTTPS object storage/CDN (e.g. R2/S3/OSS) with accurate `Content-Type` and `Content-Length` headers, or pause and ask the human for a public URL.

## Projection Matrix (Quick Reference)

| Platform Family | Native Packaging Shift from `master.md` |
| --- | --- |
| **Visual note / carousel** (Xiaohongshu, Instagram, Pinterest) | Distill into 3–9 scannable cards; put the sharpest payoff on card 1 cover; keep body structured with checklists and a save/comment cue |
| **Short vertical video** (Douyin, TikTok, WeChat Channels, Kuaishou) | Convert arc into a 3-second visual/verbal hook, 30–90s spoken script with on-screen caption cues, and a single loop/share payoff |
| **Long / mid-form video** (YouTube, Bilibili) | Expand into chaptered outline (hook 0–15s, proof, walkthrough, pitfalls, CTA), thumbnail contrast brief, and keyword-rich description |
| **Microblog / thread** (X/Twitter, Threads) | Open with a sharp standalone claim + visual proof; break supporting evidence into tight numbered follow-ups |
| **Professional / long-form** (LinkedIn, WeChat Official, Facebook) | Frame around operator lessons, concrete metrics, and scannable subheadings; preserve nuance and citations |

## Anti-Drift Rules
- Never invent a metric, benchmark, or customer quote to make a hook punchier.
- If a platform's character cap forces omitting an important caveat, link to the canonical source or drop the unprovable claim rather than oversimplifying into a falsehood.
