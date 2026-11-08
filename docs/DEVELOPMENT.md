Developer guide
===============

The [project README](../README.md) introduces the visualization and its data sources.
This guide covers local setup, data preparation and verification. For GitHub Pages,
see [publishing and updating the demo](PUBLISHING.md).

Run the prepared demo locally
-----------------------------

A normal checkout contains a prepared Zoo snapshot. Python 3.12 or newer can build
and serve it without GIS dependencies or the original datasets:

```bash
python3 scripts/build_site.py
python3 -m http.server 8000 --bind 127.0.0.1 --directory dist
```

Open **http://127.0.0.1:8000** in a browser with WebGL2. Stop the server with Ctrl+C.

If you already have prepared assets in `public/`, you can instead use:

```bash
python3 scripts/serve.py
```

This serves only `public/`. It does not expose the source dataset folders.

Rebuild from the original geographic data
-----------------------------------------

Restore the original inputs separately under `maria/`, `buildings/` and `elevation/`.
Use Python 3.12 or 3.13:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/prepare.py --config config/study-area.json
.venv/bin/python scripts/validate_data.py
.venv/bin/python scripts/serve.py
```

Preparation runs offline when the supplied inputs and `generated/sources/` cache
are present. It checks coverage, selects overlapping terrain tiles and building
layers, creates a 2 m working DTM and prepares a 5 m display grid. It refuses missing
terrain cells and opens original inputs read-only.

If the source cache and local viewer libraries are absent, run these steps before
preparation. They need internet access:

```bash
.venv/bin/python scripts/fetch_public_assets.py
.venv/bin/python scripts/fetch_context.py
.venv/bin/python scripts/prepare.py
```

Copy an existing `generated/sources/` cache to reproduce its exact imagery and OSM
snapshot. A new download can contain newer service data.

Study area and source refreshes
-------------------------------

Edit [config/study-area.json](../config/study-area.json) to change the extent,
origin, display resolution or alignment checkpoints. Bounds use EPSG:2952 in metres.
Extent dimensions must be multiples of the display-grid spacing. Exported GeoJSON
outlines are inspection outputs rather than the configuration source of truth.

If the imagery extent changes, preparation disables the old crop. Fetch a new City
image with:

```bash
.venv/bin/python scripts/fetch_public_assets.py --refresh-imagery
.venv/bin/python scripts/prepare.py
```

This does not fetch additional terrain. Update
[config/context-query.overpass](../config/context-query.overpass) when expanding
the OSM query, then run `scripts/fetch_context.py`. After preparing intentional
data changes, follow the [deployment snapshot instructions](../deployment/README.md)
to update the hosted version.

Browser verification
---------------------

Against a running local viewer:

```bash
.venv/bin/pip install -r requirements-test.txt
.venv/bin/playwright install chromium
.venv/bin/python scripts/browser_check.py --url http://127.0.0.1:8000/
```

The check also accepts the live GitHub Pages URL or a local package served under
`/Toronto_Zoo_3D/`. Use `--output-dir` to choose where screenshots and the report go.

On the development Ubuntu 20 host, Chromium required
`PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu22.04-x64` and
`PLAYWRIGHT_BROWSERS_PATH=/tmp/toronto-zoo-browser`. These are environment workarounds,
not app requirements.

Repository and evidence
------------------------

Source code, configuration, scripts and documentation are tracked. The small
`deployment/` snapshot is also tracked so the website can be built without GIS inputs.
Original datasets, cached downloads, local `public/assets/` and `public/vendor/`,
generated reports and the Python environment remain ignored.

The [technical handoff](../HANDOFF.md) records coverage, grounding, route widths,
imagery choices and remaining limitations. The
[vegetation investigation](../reports/VEGETATION_AUDIT.md) describes known omissions
in the current woodland extraction. Generated screenshots and JSON reports linked
from those documents are local evidence files and are not included in a normal checkout.

The preparation pipeline supports other extents. A Toronto-wide viewer would need
streamed spatial tiles, multiple levels of detail, additional terrain coverage and
broader alignment checks. Zoo-specific camera presets and labels would also need
to become data-driven.
