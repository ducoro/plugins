# Short-Form Packaging, Variant Contract & Exact-Pixel Card Pipeline

## 1. Variant File Contract (`variants/<platform>.md`)

Every variant starts with a ```` ```json ```` metadata fence parsed by `../content-ops-loop/scripts/check_media_specs.py` (never YAML frontmatter):

````markdown
```json
{
  "platform": "xiaohongshu",
  "mode": "image_text",
  "title": "Sharp native title",
  "topics": ["tag1", "tag2"],
  "media": [
    {"type": "image", "path": "assets/card-01.png"},
    {"type": "image", "path": "assets/card-02.png"}
  ],
  "options": {}
}
```

Publishable body copy goes here...
````

- **Threads (X/Twitter, Threads)**: separate sequential posts with `\n---\n` in the body (or `"threads": [...]` in JSON). `check_media_specs.py` enforces per-post character limits (including X 23-char `t.co` URL weighting and CJK/emoji double weighting).
- **Anti-drift rule**: never fabricate metrics, quotes, or personal experiences to make a hook punchier; if a character limit forces dropping a critical caveat, link to the source or narrow the claim.

## 2. Built-In AI Visuals (`image_generate` in Ducoro)

- Call built-in `image_generate` directly with `prompt`, `aspectRatio` (`3:4`, `4:5`, `16:9`, `1:1`, `2:3`), optional `size`, `quality`, `outputFormat`, `background`, `n`, and up to 16 current-Space relative `referencePaths`.
- Avoid asking AI image generators to render dense Chinese/UI typography—use `image_generate` for illustration/art, then place it inside HTML cards exported via `ducoro-cli board shot`.
- Start with `n: 1` and confirm with the user before multi-image batches; copy approved outputs into `drafts/<draft-id>/assets/`.

## 3. Exact-Pixel Card & Carousel Rendering (`ducoro-cli board shot`)

Use `assets/card-deck-template/index.html` (`card-01` & `card-02` at `1080x1440`, `thumb-16x9` at `1280x720`, `wechat-cover` at `900x383`):
1. `ducoro-cli board new --space <space-id> --title "<Card Deck Title>" --json`
2. Copy `assets/card-deck-template/index.html` into that Board folder, customize copy/palette/assets, and delete unused frames.
3. `ducoro-cli board check --space <space-id> --board boards/<board-id> --json` — fix any overflow or missing assets.
4. `ducoro-cli board shot --space <space-id> --board boards/<board-id> --query frame=card-01 --json` (or `--query pack=all --json` for ZIP of all `[data-ducoro-export-frame]` slides). If `renderer-installable` is returned, ask the human before running `ducoro-cli board install-renderer`.
5. Visually inspect exported PNGs and copy them into `drafts/<draft-id>/assets/`.

## 4. Temporary Public HTTPS Media Relay (URL-Fetch APIs)

For official APIs that fetch media from a public HTTPS URL (**Instagram, Facebook Page, Threads, Pinterest**), keep canonical files locally in `drafts/<draft-id>/assets/` and upload **right before publish** via `ducoro-cli media upload <local-file> --json` (resumable upload up to 300 MiB, automatic 5-hour TTL, inspectable via `ducoro-cli media list --json`), or use user-owned HTTPS object storage/CDN if preferred.
