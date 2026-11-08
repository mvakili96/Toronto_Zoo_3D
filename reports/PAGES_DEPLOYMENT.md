GitHub Pages deployment verification
====================================

Prepared November 8, 2026. The local implementation and verification are complete.
Publication still requires authenticated GitHub access and first-time Pages
activation; this session had neither GitHub credentials nor a connected GitHub
integration. The public repository API confirmed `has_pages: false`.

Intended URL: **https://mvakili96.github.io/Toronto_Zoo_3D/**

The package is the same existing viewer and scene, with aerial imagery initially
on and woodland off. No building, route, terrain, imagery or vegetation data was
recomputed. The deployment snapshot copies all eight required prepared data/library
files byte for byte and records their hashes. It contains 13,540,864 bytes.
The complete static website is 13,593,198 bytes, including its generated manifest.

Verification completed:

- A separate checkout containing source files and `deployment/`, with no original
  inputs, no ignored `public/assets/` and no GIS dependencies, built successfully
  using system Python. Its output was byte-identical to the local package.
- A deliberately corrupted snapshot buffer caused the build to fail. An unrelated
  file added to `public/` stayed outside the package.
- The workflow YAML parsed successfully. It uploads only `dist/` and uses the
  required Pages deployment permissions.
- All **26 browser checks passed** in software-WebGL Chromium at
  `http://127.0.0.1:8001/Toronto_Zoo_3D/`. Camera controls, reset, all main layer
  toggles, default appearance, source dialog, building inspection, imagery
  switching, top view, phone controls and road/terrain clearance passed.
- Every runtime request stayed under the project URL and succeeded, with no
  JavaScript or shader errors. The browser loaded 13,589,071 response-body bytes
  initially, including aerial imagery. Library licence and deployment-manifest
  files are published but are not automatically requested by the viewer.

An initial browser check used a fixed 1.5-second wait for the top-view animation
and checked it too early. Waiting for the camera to reach its target resolved
the test; no viewer camera code changed.

Local evidence: [overview](pages/overview.png), [building close-up](pages/close-up.png),
[phone layout](pages/mobile.png), [complete browser report](pages/browser-verification.json).
These generated evidence files remain ignored. The [README preview](../docs/demo-preview.webp)
is a tracked, compressed copy of the verified initial overview.

The workflow has not yet run on GitHub and the hosted URL has not been browser-tested.
Follow [the publishing instructions](../docs/PUBLISHING.md), or connect authenticated
GitHub access to complete that final deployment and verification.
