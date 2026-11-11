Google 3D trial at Toronto Zoo
==============================

Tested November 10, 2026. Google's Photorealistic 3D Tiles rendered successfully
at the Zoo in Google's hosted 3D Area Explorer, using Chromium with software WebGL.
This is a successful coverage and appearance trial in the official demo. It is
not yet an integration into this project's viewer.

[Open the official demo at the Zoo](https://js-3d-area-explorer-demo-dev-t6a6o7lkja-uc.a.run.app/#location.coordinates.lat=43.8204&location.coordinates.lng=-79.1824&camera.speed=0.1&camera.orbitType=fixed-orbit&poi.density=10&poi.searchRadius=1500).

What worked
------------

- The Zoo grounds displayed textured terrain, tree canopy, pavilion roofs,
  building walls, paths and parking as one 3D scene.
- The existing entrance-area checkpoint and the City building locations used for
  the African Rainforest Pavilion and Americas Pavilion could be inspected.
  The Rainforest Pavilion's roof was clearly recognizable. The Americas-area
  viewpoint was dominated by canopy, so it does not confirm that building's detail.
- The official zoom button moved the camera. Starting auto-orbit also moved the
  camera, and pausing it stopped the orbit.
- Tile requests succeeded. At a settled pavilion view, the SDK reported the
  tileset ready and loaded, with zero pending requests and zero processing tiles.
- Google's attribution remained visible in the captured views.

Local screenshots:

- [Zoo overview](google-3d/official-demo-zoo-paused.png)
- [Entrance-area view](google-3d/google-zoo-entrance.png)
- [African Rainforest Pavilion detail](google-3d/google-zoo-pavilion-detail.png)
- [Americas-area viewpoint](google-3d/google-zoo-americas-detail.png)

The overview and pavilion views look substantially more realistic than plain
building massing and decorative trees. Close-up vegetation remains a reconstructed
surface, and textures and small details have visible limitations. These samples
do not establish current exhibit layouts, complete Zoo coverage or surveyed accuracy.
The imagery capture date was not determined.

What needed investigation
--------------------------

The first screenshot had a black background while tiles were still loading.
After loading settled, the same Zoo view rendered normally. This was not evidence
of missing coverage. The demo's automatic orbit was paused for inspection.

The public demo uses Cesium 1.105 and initially renders at twice the viewport
resolution. Later views used resolution scale 1 to reduce software-rendering load.
The extra globe surface was hidden for those views, following the standalone
Google 3D Tiles example. The rendered Google mesh remained the scene source.
One opaque console error labelled `JS` appeared during the trial. It did not
prevent the settled views, zoom or orbit from working, but this trial does not
certify the old hosted demo as an error-free production application.

Access and next step
---------------------

No Google Maps API key was configured in the project or environment. The trial
used Google's publicly offered demo at its own origin. Its key was not copied or
reused in this project. No account or billing setup was performed.

Adding this as an optional realistic view in our app would require our own
Map Tiles API access. The Google mesh would supply that view's terrain, buildings
and vegetation together. Our independent geographic layers could supply labels
and overlays, with alignment checked before relying on them. The existing layer
viewer can remain available for separate building, road and woodland controls.

The current app, prepared GIS assets and published website were not changed.
Only this trial note and ignored local screenshots were added. No raw Google
tiles were copied into the project or its deployment snapshot.

References: [official demo and source links](https://developers.google.com/maps/architecture/3d-area-explorer),
[supported URL controls](https://developers.google.com/maps/architecture/3d-area-explorer-customizations),
[3D Tiles setup](https://developers.google.com/maps/documentation/tile/3d-tiles),
[usage policies](https://developers.google.com/maps/documentation/tile/policies).
