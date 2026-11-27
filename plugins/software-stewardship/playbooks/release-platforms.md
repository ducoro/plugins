# External Release & Deployment Platform Protocols

External app stores, package registries, and cloud platforms enforce non-obvious rules that change frequently and fail hard on misconfiguration. Load the matching section before cutting a release.

## 1. Apple macOS & App Store / Electron Desktop

- **Signing & Notarization**: Distributed macOS binaries outside the App Store must be signed with a `Developer ID Application` certificate, Hardened Runtime enabled, and notarized via `xcrun notarytool submit --wait` followed by `xcrun stapler staple`. Verify with `spctl --assess --type execute --verbose=4 <App.app>`.
- **App Store Review Traps**:
  - Include `PrivacyInfo.xcprivacy` declaring required-reason APIs (`NSPrivacyAccessedAPITypes`) and tracking disclosures.
  - Keep `Entitlements` minimal; remove unused sandbox exceptions or debug flags before archiving.
  - Auto-update frameworks (Sparkle / Electron updater) must sign update feeds and verify signatures before applying.
- **Rollback**: Keep the previous signed artifact and update manifest immutable so auto-updaters can pin back without waiting for a new store review.

## 2. Google Play (Android)

- Verify `targetSdkVersion` satisfies the current Google Play enforcement window before building release bundles.
- Ship signed `.aab` (Android App Bundle) via Play App Signing; never commit `.keystore` files or signing passwords.
- Confirm Data Safety form parity with third-party SDK permissions (analytics, crash reporting, ads) and use staged rollout tracks (`internal` -> `closed` -> percentage production rollout) so crashes can be halted before 100% exposure.

## 3. Package & Container Registries (npm / PyPI / Homebrew / Cargo / Docker)

- **Prefer OIDC Trusted Publishing**: Publish from CI using short-lived OIDC identity tokens (npm provenance, PyPI Trusted Publishers, GitHub Attestations) instead of long-lived static upload tokens.
- **Dry-run & artifact inspection**: Inspect the exact published archive (`npm pack --dry-run`, `tar -tzf dist/*.tar.gz`, `unzip -l dist/*.whl`) before uploading to verify no `.env`, local paths, or test fixtures leaked into the package.
- **Immutability**: Most registries forbid overwriting a published version tag and restrict unpublishing after a short window—treat every public version bump as irreversible and require a valid `change_gate.py` approval lock first.

## 4. Cloud & Production Database Changes (Cloudflare / Vercel / Postgres / D1)

- **Zero-downtime migrations (Expand-Contract)**:
  1. **Expand**: Add nullable columns/tables or dual-write while old code still runs cleanly.
  2. **Backfill & verify**: Migrate existing rows idempotently with checksums/counts.
  3. **Switch reads**: Deploy code reading the new shape.
  4. **Contract**: Drop legacy columns/paths only in a later release after rollback window closes.
- **Runtime & Environment Boundaries**: Never assume full Node.js `fs`/native addons on edge runtimes (Cloudflare Workers / Edge middleware); verify secrets live only in platform secret stores, never committed in `wrangler.toml`, `vercel.json`, or client bundles.
- **Live post-deploy readback**: After deploying, verify real public health endpoints, key user paths, and error-tracking rates (Sentry / platform logs) before declaring the release healthy.
