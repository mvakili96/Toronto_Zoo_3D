Toronto Zoo Landscape Explorer
=============================

A local Three.js app with real terrain, City building massing, OSM roads and paths, optional aerial imagery, camera presets and feature inspection. This working directory has a prepared pilot in `public/assets/`; no network access, Node.js, map API key or GIS software is needed to view it with the existing local assets.

Git tracks the application source, editable configuration, preparation/download scripts, dependency lists and hand-written documentation. Original datasets, downloads, vendored libraries, generated assets, generated reports and the Python environment are ignored and stay on disk. The exported GeoJSON outlines are also ignored; `config/study-area.json` and `config/context-query.overpass` are tracked. The hand-written vegetation investigation in `reports/VEGETATION_AUDIT.md` is tracked, while its generated evidence remains local.

From this directory, launch with:

```bash
python3 scripts/serve.py
```

Open **http://127.0.0.1:8000** in a browser with WebGL2. Stop the server with Ctrl+C. It serves only `public/`, so the browser cannot request the source collection.

To rebuild from your original inputs, use Python 3.12 or 3.13:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/prepare.py --config config/study-area.json
.venv/bin/python scripts/validate_data.py
.venv/bin/python scripts/serve.py
```

Preparation is offline with the supplied files and the existing `generated/sources/` cache. It scans coverage before loading pixels, selects only overlapping terrain tiles and City Multipatch layers, writes a 2 m working DTM, and produces a 5 m display grid and clipped browser assets. It refuses missing terrain cells. Original inputs are opened read-only.

A checkout containing only Git-tracked files needs the original datasets restored separately under `maria/`, `buildings/` and `elevation/`. After creating the environment and installing `requirements.txt`, run the following to restore the pinned Three.js libraries, download the current imagery/context and generate the browser assets:

```bash
.venv/bin/python scripts/fetch_public_assets.py
.venv/bin/python scripts/fetch_context.py
.venv/bin/python scripts/prepare.py
```

Those download steps need internet access. Copy the existing ignored `generated/sources/` cache separately to preserve the exact imagery/context snapshot instead of obtaining newer service data. Generated screenshots and reports linked below are local evidence files, not part of the Git baseline.

Edit [config/study-area.json](config/study-area.json) to change the study bounds, origin, display resolution or alignment checkpoints. Bounds use NAD83(CSRS) / MTM zone 10, EPSG:2952, in metres. Width and height must be multiples of the display-grid spacing. [config/study-extent.geojson](config/study-extent.geojson) is a WGS84 export for inspection; edit the JSON configuration as the source of truth. [config/zoo-osm-boundary.geojson](config/zoo-osm-boundary.geojson) is the separate mapped OSM Zoo outline.

If the imagery extent changes, the old crop is disabled automatically. To fetch a replacement from the open City service, or restore vendored Three.js files:

```bash
.venv/bin/python scripts/fetch_public_assets.py --refresh-imagery
.venv/bin/python scripts/prepare.py
```

That optional step needs internet access and records the request. It does not download a new terrain package. `scripts/fetch_context.py` refreshes the optional OSM context using the query in `config/context-query.overpass`. Change that query when expanding the study area. Keep `generated/sources/` if you want to reproduce this exact image/context snapshot; the current services can change.

Browser verification can be repeated against the running server:

```bash
.venv/bin/pip install -r requirements-test.txt
.venv/bin/playwright install chromium
.venv/bin/python scripts/browser_check.py
```

This session used Chromium with software WebGL. On this Ubuntu 20 host the browser installer needed `PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu22.04-x64` and `PLAYWRIGHT_BROWSERS_PATH=/tmp/toronto-zoo-browser`; these are environment workarounds, not app requirements.

Read [HANDOFF.md](HANDOFF.md) for source choices, problems encountered, evidence and remaining limitations. Useful evidence files:

- Current water/parking categories and palette: [overview](reports/water-parking-overview.png), [entrance close-up](reports/water-parking-close-up.png), [aerial view](reports/water-parking-imagery.png). Road/path palette close-ups: [landscape](reports/roads-paths-close-up.png), [aerial](reports/roads-paths-imagery.png). Initial capture: [phone layout](reports/mobile.png).
- [Three alignment checkpoints](reports/alignment-checkpoints.png) and [visual review](reports/alignment-review.json).
- [Data audit](reports/data-audit.json), [terrain tile index](reports/terrain-tile-index.json), [Multipatch coverage](reports/multipatch-coverage.json), [building grounding](reports/building-grounding.json), [route widths](reports/route-widths.json).
- [Data checks](reports/data-verification.json), [browser checks and loaded bytes](reports/browser-verification.json), [asset sizes and hashes](reports/asset-manifest.json).

The preparation pipeline can support another extent; the viewer’s Zoo labels and camera presets are specific to this pilot. A Toronto-wide release needs streamed spatial tiles and levels of detail, more terrain coverage, a confirmed building vertical reference, and a larger validation sample before serving the full city.
