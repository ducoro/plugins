# Board Installation & SDK Integration

All 5 prebuilt boards in `assets/boards/` are File-Backed Executable Documents (FBED) that run standalone as static HTML and progressively enhance with `window.ducoro` when served inside a Ducoro Space.

## Installing Into a Ducoro Space Board

In Ducoro, keep canonical operational files in your registered global Local Folder (default `~/.ducoro/workspaces/content-ops`, or a user-chosen external directory if requested), while each Board lives under its owning Space's `boards/<board-id>/`. Boards read their own `assets/data.json` projection rather than referencing arbitrary host paths directly.

1. Create the board folder via the host CLI so `board.json` is initialized cleanly:
   ```sh
   ducoro-cli board new --space <space-id> --title "<Board Title>" --json
   ```
2. Assemble the template (`index.html`, `README.md`, `runtime/board-sdk-bridge.js`, and shared `shadcn/ui` stylesheet `runtime/board-ui.css` from `assets/boards/shared/`) and project data from the Local Folder into `assets/data.json` in one command:
   ```sh
   python3 scripts/build_boards.py <local-folder-path> --board <board-name> --board-dir <space-work-root>/boards/<board-id> --overwrite-templates
   ```
   (For example, `<local-folder-path>` is `~/.ducoro/workspaces/content-ops` by default. Subsequent data refreshes omit `--overwrite-templates` so only `assets/data.json` changes and live sessions apply updates in place via `ducoro.board.revalidate` without reloading.)
3. Verify layout, fonts, and capture before sharing the board link:
   ```sh
   ducoro-cli board check --space <space-id> --board boards/<board-id> --json
   ducoro-cli board shot --space <space-id> --board boards/<board-id> --json
   ```

## UI Design System (`shared/board-ui.css` — `shadcn/ui` Paradigm)

All 5 boards share `runtime/board-ui.css` implementing the `shadcn/ui` semantic token and component system with zero external CDN or build dependencies:
- **Semantic tokens**: `--background`, `--foreground`, `--card`, `--primary`, `--secondary`, `--muted`, `--muted-foreground`, `--accent`, `--destructive`, `--border`, `--input`, `--radius` (`0.625rem`), `--chart-1..5` across light (`:root`) and dark (`.dark` / `prefers-color-scheme: dark`).
- **Calm by default**: neutral surfaces and `1px` borders; normal/completed states stay neutral while `warning` and `destructive` tones flag only exceptions, pending approvals, or failures.
- **Uniform control heights**: `32px` toolbar controls (`.ui-select`, `.ui-tabs`, `.ui-btn`, `.ui-check-pill`), quiet `24px–28px` row/card actions, and scan-first `.ui-table` with `11px` uppercase headers and `tabular-nums`.

## Built-In SDK Contract (Implemented by `shared/board-sdk-bridge.js`)

- **No manual SDK `<script>`**: host injects `window.ducoro`; missing SDK degrades silently to standalone mode with Composer buttons hidden.
- **Read-only & non-embedded guards**: write controls, `commands`, and `storage.set` stay disabled in `shot` mode, projection windows (`ducoro.ui.projection`), non-embedded tabs (`embedded === false`), or disconnected links.
- **Addressable content**: stable `data-card`, `data-card-title`, `data-mark-item`, `data-mark-label` on all business items; `data-mark-ignore` on toolbars/filters; zero inline file editing.
- **Safe Composer staging**: all collaboration buttons use `ducoro.composer.draft(...)` with dynamic Lead resolution from `ducoro.space.onCastChange`.
- **View-only `commands`**: every declared command validates arguments synchronously, lists valid values on error, and mutates only transient UI state.
- **Single-owner `revalidate`**: refreshes `assets/data.json` in place, throws on fetch failure so the host offers Retry, and returns `reload-required` if HTML/runtime files or `scope === 'all'` changed.
- **Shot & export frames**: `html[data-ducoro-render='shot']` hides chrome/actions; `prefers-reduced-motion: reduce` paints final state immediately; `[data-ducoro-export-frame]` marks each board's primary export canvas.
