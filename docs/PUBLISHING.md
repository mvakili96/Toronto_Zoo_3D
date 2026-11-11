Publishing the interactive Zoo demo
====================================

GIS demo URL: **https://mvakili96.github.io/Toronto_Zoo_3D/**

Google evaluation URL: **https://mvakili96.github.io/Toronto_Zoo_3D/google-3d/**

The main page is the existing Three.js viewer with its saved Zoo data. A visitor
only needs a browser with WebGL2. Aerial imagery is selected initially and woodland is
off. All current camera, appearance and layer controls remain available.
Changing the underlying extent or geographic data still uses the preparation scripts.

First deployment
----------------

1. Commit and push the deployment files to `main` in `mvakili96/Toronto_Zoo_3D`.
2. Open [repository Settings → Pages](https://github.com/mvakili96/Toronto_Zoo_3D/settings/pages).
3. Under **Build and deployment → Source**, select **GitHub Actions**. This enables Pages for this repository. No custom domain or separate token is needed for normal deployments.
4. In [Actions](https://github.com/mvakili96/Toronto_Zoo_3D/actions), select **Publish interactive Zoo demo → Run workflow → main**. Later pushes that change viewer code or the deployment snapshot publish automatically.
5. Wait for the build and deploy jobs to succeed, then open the demo URL above.

The README contains both a direct demo link and a clickable preview image. The
interactive app opens on GitHub Pages, in its own browser page. It is not embedded
inside GitHub's Markdown README.

Enable the Google evaluation
-----------------------------

The same deployment also publishes the standalone Google view at `google-3d/`.
Visitors see the daily quota notice before deciding whether to load Google.
All camera controls reuse one map instance. Visiting the GIS demo does not load
Google, and visiting the Google welcome screen does not load the Google SDK.

1. In [Google Cloud credentials](https://console.cloud.google.com/apis/credentials), choose a dedicated browser key for this evaluation. Under **Application restrictions**, choose **Websites** and allow `https://mvakili96.github.io/*`. Under **API restrictions**, allow **Maps JavaScript API** only. Keep a separate key for localhost, or explicitly add your local development origins if needed.
2. In the repository’s [Actions secrets](https://github.com/mvakili96/Toronto_Zoo_3D/settings/secrets/actions), add a repository secret named **`GOOGLE_MAPS_API_KEY`** with that restricted key as its value. Do not commit `.env` or put the actual value in a workflow, README or chat message.
3. Push the changes to `main`, or run **Publish interactive Zoo demo** manually. If you add or replace the secret after a deployment, run the workflow again so the website receives the updated browser key.
4. Open the Google evaluation URL, check the quota notice, choose **Open Google 3D**, then exercise zoom, the presets and reset. Confirm Google Cloud accepts the deployed origin. Open the GIS fallback link as well.

The workflow injects the secret only into the static build step. The resulting
`google-3d/config.json` must contain the browser key, so visitors can inspect it.
An Actions secret keeps it out of source and normal build logs. It does not hide
it from browsers. Google's website and API restrictions provide the protection.
Use the account's GitHub Pages origin, rather than a repository path, because
browsers normally omit the path from cross-origin referrers. No wildcard for
other GitHub users is needed.

Without an Actions secret, the build succeeds and publishes an explicit
unavailable page with a working link to the GIS demo. It makes no Google requests.
The static build never reads the local `.env` file. Removing the secret and
redeploying removes the key from the current site. Revoke or restrict the key in
Google Cloud as well if it must stop working, since previously served copies may
remain in browser caches or old deployment artifacts.

All visitors share this Demo Key's daily quota. The Google view may pause until
the next daily reset when that limit is reached. Google does not publish a fixed
daily allowance on the Demo Key page. The README, welcome screen and map panel
state this limitation. This is an evaluation and testing demo, not a production
Google Maps deployment. A production deployment needs a suitable billing-enabled
key and updated usage messaging. Narrowing the camera bounds is not a guarantee
of reduced quota use.

References: [key restrictions](https://developers.google.com/maps/api-security-best-practices),
[Demo Key limits](https://developers.google.com/maps/demo-key),
[Demo Project terms](https://cloud.google.com/terms/maps-platform/demo-project-terms),
[GitHub Actions secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).

What gets published
--------------------

The workflow builds `dist/` using `python scripts/build_site.py`, then uploads
**only `dist/`** to GitHub Pages. No GIS packages are installed on the runner.
The script combines the current `public/index.html`, `app.js` and `style.css`
with the versioned [deployment data snapshot](../deployment/README.md).
It also copies the three `experiments/google-3d/` web files and generates a small
Google configuration from the saved study area, camera settings and build
environment. It never publishes the Python server or any `.env` file.

The initial website is about **13.59 MB** uncompressed, including the aerial
image and local viewer libraries. The original multi-GB `maria/`, `buildings/`
and `elevation/` folders, raw downloads, intermediate rasters and local reports
are excluded. A manifest records the published file hashes and byte counts, and
the build refuses missing/changed snapshot files and mismatched study extents.

The snapshot contains the same City open-service imagery used locally. The
university-licensed TIFFs are excluded. Existing source attribution and licence
links remain in the viewer and library licence text is included. Google streams
its scene directly to the visitor. No Google meshes or imagery tiles are stored
in the repository or deployment snapshot, and native Google attribution remains
visible in its map.

Updating it
------------

For appearance or controls, edit `public/`, commit and push to `main`. The next
deployment uses that source with the existing exact data snapshot.
Changes to `experiments/google-3d/`, `scripts/google_3d_config.py` and
`config/google-3d-preview.json` also trigger a deployment.

For geographic data changes, prepare and validate locally first:

```bash
.venv/bin/python scripts/prepare.py
.venv/bin/python scripts/validate_data.py
python3 scripts/build_site.py --refresh-data
git add deployment public config/study-area.json
```

Review the changed data/manifest, then commit and push. See the snapshot README
for source attribution and its explicit size limit. Do not add original inputs.

Local verification
--------------------

```bash
python3 scripts/build_site.py
python3 -m http.server 8001 --bind 127.0.0.1 --directory dist
```

With the browser test environment installed, run in another terminal:

```bash
.venv/bin/python scripts/browser_check.py --url http://127.0.0.1:8001/ --output-dir reports/pages
```

The same check accepts the live GitHub Pages URL. It checks the initial defaults,
camera controls, every main layer toggle, inspection, image switching, source
dialog, phone layout, request paths and road/terrain clearance. The local
publishing check also uses `/Toronto_Zoo_3D/` as a URL prefix so relative assets
are tested under the repository path.

Check the Google welcome, missing-key, access-error and phone states without
making live Google requests:

```bash
.venv/bin/python scripts/browser_check_google_sharing.py --url http://127.0.0.1:8001/google-3d/
```

For a configured view, `scripts/browser_check_google_3d.py --url <google-view-url>`
also exercises the live map and camera controls. This consumes Google usage.
The tested origin must be allowed by that browser key. Do not loosen the public
key's restrictions just to run a localhost test.

For prepublication verification of an already configured static package, add
`--site-dir /absolute/path/to/the/package/google-3d` and use the intended Pages
URL with `--url`. Playwright supplies the page files locally at that origin and
lets Google load normally. This tests the package before upload without adding
localhost to a public key. It does not upload the package or verify that a real
deployment has completed.
