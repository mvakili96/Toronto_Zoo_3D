GitHub Pages data snapshot
==========================

This directory intentionally tracks only the small, prepared Zoo browser data
and pinned Three.js libraries. It lets GitHub Actions publish the same scene
without the original GIS packages, Python GIS dependencies or online map services.
It is an explicit exception to the rule that generated outputs stay out of Git.

The app's current HTML, JavaScript and CSS still come from `public/` at build time.
`manifest.json` records the scene, source descriptions, byte sizes and SHA-256
checksums. Every build verifies them and packages only an explicit file list.
The snapshot has a 50 MB limit; the initial Zoo snapshot is about 13.54 MB.

To build an ordinary checkout, with Python 3.12 or newer and no extra packages:

```bash
python3 scripts/build_site.py
```

To refresh the snapshot **after** preparing intentional data changes locally:

```bash
.venv/bin/python scripts/prepare.py
.venv/bin/python scripts/validate_data.py
python3 scripts/build_site.py --refresh-data
git add deployment
```

Review the manifest/data diff, commit and push. A normal source change does not
need a data refresh. Changes to study-area configuration require a matching
prepared snapshot; the build refuses inconsistent extents. `dist/` remains ignored.

Sources and attribution:

- Ontario GTA 2023 DTM: [Ontario Open Government Licence](https://www.ontario.ca/page/open-government-licence-ontario).
- City 2025 building massing and cached City ortho imagery: [Open Government Licence – Toronto](https://open.toronto.ca/open-data-licence/).
- Roads, paths and OSM context: [© OpenStreetMap contributors, ODbL](https://www.openstreetmap.org/copyright).
- Three.js 0.170.0: MIT; see [the included licence](vendor/THREE-LICENSE.txt).

The aerial is the existing City open-service crop retrieved November 7, 2026;
its capture year is unverified. Maria's university-licensed 2022 imagery is not
included. Original inputs, intermediate datasets and reports are not deployed.
Data assumptions and remaining limitations are described in [HANDOFF.md](../HANDOFF.md).
