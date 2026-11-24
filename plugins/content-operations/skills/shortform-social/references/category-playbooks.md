# Xiaohongshu & Social Carousel Category Reference

Neutral domain reference showing how different niches behave on visual-first platforms (especially Xiaohongshu / RedNote and WeChat `newspic`), what asset mix each niche typically needs, and starter blueprint ideas. Always respect the user's own style preference or custom layout over any default below.

## 1. Visual-Structure-Driven Niches (HTML Cards Shine End-to-End)

| Niche | Audience Mindset | Common Winning Formats | Starter Style / Blueprint Ideas |
|---|---|---|---|
| **Tools / AI / Benchmarks** | Seeking faster workflows, real comparisons, verifiable proof | Cover hook + metric breakdown + before/after + UI screenshots | `grid-spec` (`cover-split`, `metric-hero`, `compare-two`, `shot-stage`) |
| **Workplace / Study / SOP** | Saving actionable templates, career advice, exam/interview notes | Step-by-step checklists, big-type cover, summary takeaway card | `grid-spec` or bold-type custom layout (`cover-split`, `step-flow`, `checklist`) |
| **Travel / City Walk / Routes** | Practical non-backtracking itineraries + authentic atmosphere | Photo cover + route map + time stops + real tips | `paper-studio` (`cover-bleed`, `map-route`, `step-flow`, `quote-note`) |
| **Books / Essays / Perspectives** | Resonance, shareable quotes, structured takeaways | Pull quotes, single thesis cards, side-by-side mental models | `paper-studio` (`thesis`, `quote-note`, `compare-two`) |
| **Buying Guides / Comparisons** | Avoiding bad purchases, clear specs & price tiers | Spec comparison tables, pros/cons, honest caveats | `grid-spec` or `paper-studio` (`compare-two`, `metric-hero`, `checklist`) |

## 2. Photography- & Footage-Led Niches (Real User Media Drives Conversion)

These niches thrive on visual platforms, and **real user photos or clips carry most of the persuasive weight**. HTML cards still work great here as lightweight framing, photo-led covers, ingredient/gear checklists, or Live Photo puzzles—just confirm media sources with the user upfront rather than substituting generic stock:

- **OOTD / Fashion / Styling**: real lookbook shots (minimal or zero text on cover; optional detail/item tags or capsule pairing cards on slides 2–N).
- **Food & Recipes**: real dish photos/clips for appetite appeal + structured ingredient ratios, timing steps, and common-mistake cards.
- **Home / Desk Setup / Decor**: real room photos or `grid-4` Live Photo puzzles + layout breakdown, dimensions, and gear list slides.
- **Beauty / Skincare / Fitness**: real swatches, demo clips, or form guides paired with routine step cards and skin-type/level caveats.
- **Gaming / Film / Hardware**: real key art, in-game screenshots, or hardware shots paired with `darkroom-frame` layouts or `stack-3` Live Photo comparisons.
- **Plog / Emotional / Collage / Decorative Aesthetics**: if the user wants collage, stickers, film borders, or expressive high-saturation posters rather than minimalist presets, write custom HTML/CSS directly inside the Board instead of forcing minimalist starter templates.

## 3. Finished Reference Decks (`assets/examples/`)

Inspect `assets/examples/index.html` to see 4 completed starter examples (not rigid rules—adapt or create fresh designs freely):
- `assets/examples/xhs-tool-teardown/index.html` — `grid-spec / cobalt-grid` 5-slide benchmark & screenshot deck
- `assets/examples/xhs-travel-route/index.html` — `paper-studio / warm-linen` 4-slide full-bleed cover + `map-route` itinerary
- `assets/examples/wechat-cover-pair/index.html` — `darkroom-frame / obsidian-gold` paired `900×383` + `1080×1080` covers + `16:9` thumbnail
- `assets/examples/xhs-live-photo/index.html` — Live Photo transparent overlay starter & `stack-3` / `grid-4` geometry specs
