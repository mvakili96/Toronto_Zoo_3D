"""Package the GIS viewer and Google evaluation using only the standard library.

Normal builds use the committed deployment snapshot, not local GIS inputs or
ignored public assets. --refresh-data explicitly replaces that small snapshot
from an already prepared public/ directory.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
from google_3d_config import view_settings

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "deployment"
APP_FILES = ("index.html", "app.js", "style.css")
GOOGLE_FILES = tuple("google-3d/" + name for name in (*APP_FILES, "config.json"))
DATA_FILES = (
    "assets/scene.json",
    "assets/terrain.f32",
    "assets/buildings.f32",
    "assets/building-colors.f32",
    "assets/ortho.webp",
    "vendor/three.module.js",
    "vendor/OrbitControls.js",
    "vendor/THREE-LICENSE.txt",
)
MAX_DATA_BYTES = 50_000_000


def fingerprint(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Required ordinary file is missing: {path}")
    content = path.read_bytes()
    if not content:
        raise ValueError(f"Required file is empty: {path}")
    return {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def read_json(path):
    return json.loads(path.read_text())


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def validate_scene(folder):
    scene = read_json(folder / "assets/scene.json")
    if scene["study"] != read_json(ROOT / "config/study-area.json"):
        raise ValueError("Scene extent/configuration differs from config/study-area.json. "
                         "Prepare the intended area, then refresh the deployment snapshot.")
    references = (
        scene["terrain"]["url"], scene["buildings"]["url"],
        scene["buildings"]["colors"], (scene.get("imagery") or {}).get("url"),
    )
    if any(url is not None and url not in DATA_FILES for url in references):
        raise ValueError("Scene refers to an asset outside the deployment allowlist.")
    terrain = scene["terrain"]
    if (folder / terrain["url"]).stat().st_size != terrain["width"] * terrain["height"] * 4:
        raise ValueError("Terrain dimensions do not match the prepared buffer.")
    vertices = sum(b["count"] for b in scene["buildings"]["features"])
    for key in ("url", "colors"):
        if (folder / scene["buildings"][key]).stat().st_size != vertices * 3 * 4:
            raise ValueError("Building ranges do not match the prepared buffers.")
    return scene


def refresh_snapshot():
    public = ROOT / "public"
    files = {name: fingerprint(public / name) for name in DATA_FILES}
    if sum(item["bytes"] for item in files.values()) > MAX_DATA_BYTES:
        raise ValueError("The Zoo deployment snapshot exceeds its 50 MB size limit.")
    scene = validate_scene(public)
    for name in DATA_FILES:
        target = SNAPSHOT / name
        if target.is_symlink() or target.parent.is_symlink():
            raise ValueError(f"Snapshot paths must not be symlinks: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(public / name, target)
    write_json(SNAPSHOT / "manifest.json", {
        "format_version": 1,
        "snapshot_utc": datetime.now(timezone.utc).isoformat(),
        "study": scene["study"],
        "imagery": scene.get("imagery"),
        "summary": scene["summary"],
        "sources": {
            "terrain": "Ontario GTA 2023 DTM, CGVD2013; prepared 5 m display grid",
            "buildings": "City of Toronto 2025 3D Massing",
            "routes_and_context": "OpenStreetMap snapshots; Maria's Zoo/City OSM layers",
            "imagery": "City of Toronto open ortho service; university imagery excluded",
            "viewer_library": "Three.js 0.170.0, MIT; licence included",
        },
        "files": files,
        "total_bytes": sum(item["bytes"] for item in files.values()),
    })
    print("Refreshed the deployment snapshot from the prepared public assets.")


def verify_snapshot():
    manifest = read_json(SNAPSHOT / "manifest.json")
    if manifest["format_version"] != 1 or set(manifest["files"]) != set(DATA_FILES):
        raise ValueError("Deployment manifest has an unsupported format or file list.")
    for name in DATA_FILES:
        if fingerprint(SNAPSHOT / name) != manifest["files"][name]:
            raise ValueError(f"Deployment snapshot checksum/size mismatch: {name}")
    total = sum(item["bytes"] for item in manifest["files"].values())
    if total != manifest["total_bytes"] or total > MAX_DATA_BYTES:
        raise ValueError("Deployment snapshot size is invalid or exceeds 50 MB.")
    scene = validate_scene(SNAPSHOT)
    if scene["study"] != manifest["study"]:
        raise ValueError("Snapshot manifest does not describe its scene.")
    for folder in ("assets", "vendor"):
        actual = {str(p.relative_to(SNAPSHOT)) for p in (SNAPSHOT / folder).rglob("*") if p.is_file()}
        expected = {name for name in DATA_FILES if name.startswith(folder + "/")}
        if actual != expected:
            raise ValueError(f"Unexpected or missing files in deployment/{folder}.")
    return manifest


def build_site(output):
    manifest = verify_snapshot()
    output = output.resolve()
    # Do not overwrite a source/input directory or an ancestor of this checkout.
    protected = ("public", "deployment", "maria", "buildings", "elevation", "config", "scripts", "experiments", ".git")
    if ROOT.is_relative_to(output) or any(output.is_relative_to(ROOT / p) for p in protected):
        raise ValueError("Choose dist/ or a separate empty directory for the build.")
    expected = set(APP_FILES) | set(DATA_FILES) | set(GOOGLE_FILES) | {".nojekyll", "deployment-manifest.json"}
    if output.exists():
        if output.is_symlink():
            raise ValueError("Output must be an ordinary directory.")
        extra = {str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()} - expected
        if extra:
            raise ValueError(f"Output contains unrelated files; choose an empty directory: {sorted(extra)}")
    for name in APP_FILES:
        fingerprint(ROOT / "public" / name)
        fingerprint(ROOT / "experiments/google-3d" / name)
    # Static hosting needs a browser-visible key. Read only the explicitly
    # supplied build environment, never the developer's ignored .env file.
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if key and (len(key) < 20 or any(c.isspace() for c in key)):
        raise ValueError("GOOGLE_MAPS_API_KEY is not a valid browser key. The value has not been logged.")
    google_config = {**view_settings(), "configured": bool(key), "apiKey": key,
                     "hosted": True, "gisUrl": "../"}
    output.mkdir(parents=True, exist_ok=True)
    for name, source in [(n, ROOT / "public" / n) for n in APP_FILES] + [(n, SNAPSHOT / n) for n in DATA_FILES]:
        target = output / name
        if target.is_symlink() or target.parent.is_symlink():
            raise ValueError(f"Output paths must not be symlinks: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    for name in APP_FILES:
        target = output / "google-3d" / name
        if target.is_symlink() or target.parent.is_symlink():
            raise ValueError("Google view output paths must not be symlinks.")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "experiments/google-3d" / name, target)
    config_path = output / "google-3d/config.json"
    if config_path.is_symlink():
        raise ValueError("Google view configuration must not be a symlink.")
    write_json(config_path, google_config)
    (output / ".nojekyll").write_text("")
    files = {name: fingerprint(output / name) for name in (*APP_FILES, *DATA_FILES, *GOOGLE_FILES)}
    write_json(output / "deployment-manifest.json", {
        "snapshot_utc": manifest["snapshot_utc"], "study": manifest["study"],
        "sources": manifest["sources"], "files": files,
        "google_view": {"path": "google-3d/", "configured": bool(key),
                        "source": "Google Maps JavaScript API, streamed on visitor request",
                        "purpose": "Evaluation only, shared daily Demo Key quota"},
        "total_bytes": sum(item["bytes"] for item in files.values()),
    })
    print(f"Built {output}: {len(expected)} files, "
          f"{sum(p.stat().st_size for p in output.rglob('*') if p.is_file()):,} bytes.")
    print("Google 3D evaluation: " + ("browser key supplied." if key else "no key supplied, availability page only."))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-data", action="store_true", help="Refresh the tracked deployment data from prepared public assets.")
    parser.add_argument("--output", type=Path, default=ROOT / "dist", help="Static output directory (default: dist/).")
    args = parser.parse_args()
    try:
        if args.refresh_data:
            refresh_snapshot()
        build_site(args.output)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Site build failed: {error}\n")


if __name__ == "__main__":
    main()
