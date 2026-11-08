Publishing the interactive Zoo demo
====================================

Demo URL: **https://mvakili96.github.io/Toronto_Zoo_3D/**

The site is the existing Three.js viewer with its saved Zoo data. A visitor only
needs a browser with WebGL2. Aerial imagery is selected initially; woodland is
off. All current camera, appearance and layer controls remain available.
Changing the underlying extent or geographic data still uses the preparation scripts.

First deployment
----------------

1. Commit and push the deployment files to `main` in `mvakili96/Toronto_Zoo_3D`.
2. Open [repository Settings → Pages](https://github.com/mvakili96/Toronto_Zoo_3D/settings/pages).
3. Under **Build and deployment → Source**, select **GitHub Actions**. This enables Pages for this repository; no custom domain or separate token is needed for normal deployments.
4. In [Actions](https://github.com/mvakili96/Toronto_Zoo_3D/actions), select **Publish interactive Zoo demo → Run workflow → main**. Later pushes that change viewer code or the deployment snapshot publish automatically.
5. Wait for the build and deploy jobs to succeed, then open the demo URL above.

The README contains both a direct demo link and a clickable preview image. The
interactive app opens on GitHub Pages, in its own browser page. It is not embedded
inside GitHub's Markdown README.

What gets published
--------------------

The workflow builds `dist/` using `python scripts/build_site.py`, then uploads
**only `dist/`** to GitHub Pages. No GIS packages are installed on the runner.
The script combines the current `public/index.html`, `app.js` and `style.css`
with the versioned [deployment data snapshot](../deployment/README.md).

The initial website is about **13.59 MB** uncompressed, including the aerial
image and local viewer libraries. The original multi-GB `maria/`, `buildings/`
and `elevation/` folders, raw downloads, intermediate rasters and local reports
are excluded. A manifest records the published file hashes and byte counts;
the build refuses missing/changed snapshot files and mismatched study extents.

The snapshot contains the same City open-service imagery used locally. The
university-licensed TIFFs are excluded. Existing source attribution and licence
links remain in the viewer; library licence text is included.

Updating it
------------

For appearance or controls, edit `public/`, commit and push to `main`. The next
deployment uses that source with the existing exact data snapshot.

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
