Local Google 3D preview
======================

This experiment opens Google's photorealistic 3D map at Toronto Zoo using the
Maps JavaScript API. It supports a Maps Demo Key, with Google's development quotas.
It does not use the separate Map Tiles API or Cesium.

Run it
-------

Save your key in the project's ignored `.env` file:

```dotenv
GOOGLE_MAPS_API_KEY=your_key_here
```

An existing `GOOGLE_MAPS_API_KEY` environment variable takes precedence over the
file. The server reads `.env` on each configuration request, so adding a key only
requires reloading the page. Keep the actual key out of Git and chat messages.

From the project directory, run:

```bash
python3 scripts/serve_google_3d.py
```

Open **http://localhost:8002** in a current browser with WebGL enabled. An internet
connection is required. No GIS dependencies or original datasets are needed.
Stop the server with Ctrl+C. Choose another port with `--port 8003` if needed.
Restart an existing server after updating its Python code. Changes only to the
saved camera settings take effect on page reload.

Use the map's mouse or touch controls, the zoom buttons and the viewpoint presets.
The preview includes an orbit/pause control, reset and optional Google map labels.
Google's attribution remains part of the native map.

Configuration and credentials
------------------------------

The server binds only to loopback and serves an explicit list of preview files.
It does not expose `.env`, the repository or the original GIS directories. The
key is passed to the browser in a non-cached configuration response because the
Maps JavaScript API runs in the browser. It is not embedded in tracked HTML or
JavaScript, printed by the server or saved in browser storage by this preview.

If a standard key has website restrictions, permit the local address you use,
such as `http://localhost:8002/*`, and allow Maps JavaScript API. Demo Keys have
their own feature and quota limits. A rejected key or unsupported browser produces
a visible setup message rather than a blank page.

[config/google-3d-preview.json](../config/google-3d-preview.json) contains camera
settings and the WGS84 bounds transformed from the existing pilot extent. The
server checks those source bounds against `config/study-area.json`, and uses its
entrance and pavilion checkpoints for the presets. Camera target altitudes are
viewing choices, not adjustments to either dataset.

The navigation uses the same approximate 3 × 2.5 km study area as the GIS demo.
Google's native bounds restrict camera position. An additional guard keeps the
camera's focus inside that extent and caps camera range for buttons and native
mouse, keyboard and touch gestures. The saved navigation settings allow ranges
from 120 to 2,400 m, tilt up to 60 degrees and a native altitude ceiling of
2,800 m. The overview is centred on the study area's geographic bounding box and
starts at a 1,700 m range and 45 degree tilt. Reset uses that same view.

These are navigation limits. Google can still render objects beyond the extent
in an oblique view. The API does not expose a geographic clipping option for its
photorealistic scene. This preview does not block Google tile requests or attempt
to extract its meshes.

Quota and scope
----------------

Limiting navigation helps keep exploration focused. It is not a quota saving
guarantee. Google's documented Immersive Maps SKU for this API counts successful
map loads, rather than the area of the study extent. The Demo Key has separate
daily limits, and Google does not publish an area-based quota formula on its
Demo Key page. A smaller camera extent does not make a map load free or remove
those limits. All controls reuse the existing map instance.

Sources: [camera bounds and limits](https://developers.google.com/maps/documentation/javascript/reference/3d-map),
[Immersive Maps usage](https://developers.google.com/maps/billing-and-pricing/sku-details/maps#sku-immersive-maps),
[Demo Key limits](https://developers.google.com/maps/demo-key).

Relationship to the existing demo
----------------------------------

The existing Three.js viewer, its City/OSM data, DTM and cached City image remain
available through their original launch commands. This experiment displays
Google's combined scene instead. It does not provide independent tree/building
layer toggles or transfer Google's geometry into the existing dataset.

The same preview is packaged separately at `google-3d/` by the GitHub Pages
build. The Python configuration endpoint is only used locally. The static build
uses public settings from `scripts/google_3d_config.py` and an explicitly supplied
`GOOGLE_MAPS_API_KEY` build environment variable. It never reads `.env`.

The welcome screen requires an explicit **Open Google 3D** click before loading
Google, and the daily quota notice remains visible in the map panel. A missing
hosted key produces a visitor-friendly availability message and GIS link.
See [publishing instructions](PUBLISHING.md#enable-the-google-evaluation) for the
required key restrictions and Actions secret. A Demo Key is only for evaluation
and testing, with all visitors sharing its daily limits.

Verification
-------------

With the existing Playwright test environment and the server running:

```bash
.venv/bin/python scripts/browser_check_google_3d.py
```

Screenshots and redacted verification output go to `reports/google-3d/`, which
remains ignored. The browser test checks map initialization, camera presets,
zoom, orbit/pause, labels, reset, phone layout and blocked input/credential paths.

The initial preview was verified on November 10, 2026 in Chromium with software
WebGL. The November 11 navigation update passed all 28 browser checks, with no
JavaScript or console errors. These checks exercise wheel zoom, range limits,
camera and focus at each study edge, native dragging, reset and phone controls.
The overview and pavilion screenshots were also inspected.

The prepared Pages version later passed 31 live Google browser checks at the
intended GitHub Pages origin, with the website files supplied locally by the
test browser. This is a prepublication check, not proof of a live deployment.
Thirteen offline browser checks covered the quota welcome, network/access
errors, missing hosted key and phone layout. The combined package also passed
all 26 existing GIS browser checks and nine packaging checks. A clean checkout
built byte-identically without GIS inputs, and a canary `.env` value never
entered the output. The actual browser key is absent from Git-visible source.

During verification, a lower native altitude ceiling caused Google to shorten
the overhead range before the zoom limit was reached. The 2,800 m ceiling leaves
room for the 2,400 m range and local surface elevation. The final browser run
confirmed that zoom stops at the range limit and the zoom-out button disables.

Screenshots and the latest results are saved in `reports/google-3d/`.
Missing-key guidance makes no Google requests. The local server rejects
cross-origin configuration access. The GitHub Pages package includes the
Google view's web files and a browser configuration, but excludes `.env`, the
Python server and local inputs.

References: [Maps Demo Key](https://developers.google.com/maps/demo-key),
[Google 3D Maps setup](https://developers.google.com/maps/documentation/javascript/3d/get-started),
[3D map controls and properties](https://developers.google.com/maps/documentation/javascript/reference/3d-map).
