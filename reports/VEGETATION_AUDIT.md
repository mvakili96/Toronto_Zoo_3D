The vegetation investigation found a concrete extraction omission, as well as limits in the tree-placement style. The viewer has not been rebuilt during this investigation; its original source snapshot and browser assets remain unchanged.

OSM describes `natural=wood` as tree-covered land. `landuse=forest` overlaps substantially with it, although mapper interpretations of management/land use vary. Their tag guidance does not specify a universal minimum area, tree count, or canopy-density percentage. A small grove can be an area; an individual tree normally uses a `natural=tree` point. Lines of trees can use `natural=tree_row`. `natural=tree_group` and `landcover=trees` are additional schemes used for groups/areas. A woodland tag applied to a single node can also be a placeholder for an entire wood, rather than an individual tree; the individual-tree tag is distinct.

References: [wood](https://wiki.openstreetmap.org/wiki/Tag:natural%3Dwood), [forest](https://wiki.openstreetmap.org/wiki/Tag:landuse%3Dforest), [individual tree](https://wiki.openstreetmap.org/wiki/Tag:natural%3Dtree), [tree row](https://wiki.openstreetmap.org/wiki/Tag:natural%3Dtree_row), [tree group](https://wiki.openstreetmap.org/wiki/Tag:natural%3Dtree_group), [landcover=trees](https://wiki.openstreetmap.org/wiki/Tag:landcover%3Dtrees).

The original `config/context-query.overpass` asks for ways tagged `natural=wood` or `landuse=forest`. A way is a line or closed outline. Complex areas with multiple rings, including holes, can instead be represented as multipolygon relations. The query did not request woodland relations, individual trees, tree rows, tree groups or `landcover=trees`. The preparation code likewise only interprets woodland geometry in its way branch; its relation branch handles building place names only. Both query and parser need to be extended together.

The original download contains 46 simple woodland ways. After clipping, 42 polygon features enter the scene, covering approximately 1.73685 km². None is rejected by a minimum woodland-size threshold. The smallest clipped polygon is approximately 42 m², although a small polygon can still receive no tree candidate.

A broader read-only query was saved separately in `generated/sources/osm-vegetation-audit.json`. It requests nodes, ways and relations for all those vegetation tags. The original snapshot timestamp is 2026-11-07 22:59:20 UTC; the audit snapshot is 2026-11-08 00:47:21 UTC, still November 7 in Toronto. All 46 simple woodland way geometries match between the snapshots.

| Omission | Confirmed result inside the actual study area |
|---|---|
| Woodland relation 1108483 | 0.00677 km² of additional mapped woodland; last edited in 2010 |
| Woodland relation 1108485 | 0.45904 km² of additional mapped woodland, mainly northeast/east of the Zoo; last edited in 2015 |
| Individual tree points | 19 mapped tree points, all outside the current woodland mask |
| Tree rows | Two mapped rows, with about 277.3 m and 65.9 m of line inside the study |
| Other schemes | No additional `tree_group` or `landcover=trees` results in this bounded audit query |

The two missing relations add **0.46581 km², or 46.58 hectares**, beyond the current woodland polygons. Including them would increase represented woodland area to approximately **2.20265 km²** before buffers, rasterization and tree placement. This is mapped woodland area, not a measured canopy-area estimate or a count of real trees. The relation edit dates establish that these are longstanding mapped features, not woodland newly added between the downloads.

See [the comparison overlay](vegetation-query-audit.png): green shows current woodland polygons, magenta shows the mapped woodland omitted by the original query, cyan shows omitted mapped trees/rows, and orange shows current road/building exclusion buffers. Visible crowns outside all these mapped areas are evidence of further coverage differences, but this audit does not quantify or classify those crowns.

Our own renderer further thins vegetation:

- It creates one candidate per approximately 18.5 × 18.5 m before random jitter. This spacing is chosen for display; it does not come from measured woodland density. With the selected crown sizes it creates visibly open gaps within forest areas.
- It rejects candidates within road/path width plus approximately 5 m clearance on each side, and within approximate circles around building centres. Vector buffers intersect about 0.03940 km², or 2.27%, of the current mapped woodland. This number precedes rasterization and other exclusions.
- The woodland mask is rasterized at 5 m. Narrow strips and tiny polygons can disappear or receive no candidate.
- Woodland and grass share a mask. A grass polygon painted later can overwrite woodland in an overlap; this is another renderer limitation, not an OSM definition.
- The current implementation does not use orthophoto pixels to recover missing canopy. OSM mapping also cannot be assumed to enumerate every real tree, especially scattered trees inside Zoo exhibits, lawns, parking areas and landscaped grounds.

The first corrections should be to support woodland multipolygon relations with inner holes, render explicitly mapped tree points and rows separately, and separate grass styling from the tree-eligibility mask. Road/building exclusions should use deliberate clearance rules and actual footprints; explicit mapped roadside trees should not be removed automatically by a broad decorative-tree buffer. Density can then be adjusted with a visible explanation that it is illustrative. Remaining photograph-visible vegetation needs a separate canopy source or a validated image-based interpretation; merely increasing random-tree density cannot fill areas outside the input polygons.

Reproduce the diagnostic without altering the app:

```bash
# Optional online refresh, saved as a separate audit snapshot:
.venv/bin/python scripts/audit_vegetation.py
# Offline comparison and map from the saved snapshots:
.venv/bin/python scripts/summarize_vegetation_audit.py
```

The detailed counts, source timestamps, relation identifiers, areas and buffer calculations are in [vegetation-audit.json](vegetation-audit.json). This investigation does not establish complete tree coverage or tree heights from the aerial image.
