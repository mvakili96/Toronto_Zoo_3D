Google 3D sharing preparation
==============================

Prepared and verified November 11, 2026. The Google view is packaged at
`google-3d/` alongside the GIS viewer. Deployment requires a restricted browser
key in the repository's Actions secret and a push to the configured Pages
workflow. See [the publishing guide](../docs/PUBLISHING.md).

Decisions and evidence
-----------------------

- The local preview depended on a Python configuration endpoint. GitHub Pages
  only serves static files, so a shared settings module now supplies both the
  local server and the static build. The prepared Google page passed 31 live
  browser checks at its intended HTTPS origin, with files supplied locally by
  Playwright. This did not publish the website.
- A static browser map needs a browser-visible API key. The workflow reads it
  from an Actions secret during the build, while the build never reads `.env`.
  Nine package checks passed, including a clean-checkout build, exclusion of a
  canary `.env` value, no key in build logs and key placement only in the intended
  browser configuration. Google Cloud website and API restrictions remain
  necessary. An Actions secret cannot hide a key from visitors' browsers.
- All visitors share the Demo Key's daily quota. The README, welcome screen and
  map panel now say the view may pause until the next daily reset. Google loads
  only after an explicit click, and camera controls reuse one map instance.
  Thirteen offline browser checks verified the welcome, access/network errors,
  missing-key state, fallback links and phone layout without live Google usage.
  Quota exhaustion itself was not deliberately triggered.
- The GIS demo remains the main independent viewer and fallback. All 26 of its
  browser checks passed in the combined package, with no Google requests. The
  site has 17 explicitly allowed files and is about 13.61 MB before Google
  streams its own scene. No original GIS inputs or Google mesh tiles are added.

The overview and pavilion screenshots were inspected. Redacted reports and
screenshots are under `reports/google-sharing/` and are not committed.
