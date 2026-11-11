"""Public Zoo camera settings shared by the local server and static build.

This module never reads credentials or .env files.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def view_settings():
    study = json.loads((ROOT / "config/study-area.json").read_text())
    preview = json.loads((ROOT / "config/google-3d-preview.json").read_text())
    if study["crs"] != preview["source_crs"] or study["bounds"] != preview["source_bounds"]:
        raise ValueError("Update the Google preview bounds to match the configured study area.")
    navigation = preview["navigation"]
    if not (0 < navigation["min_range_m"] < navigation["max_range_m"]
            and 0 < navigation["max_tilt_deg"] < 90
            and navigation["max_altitude_m"] > 0):
        raise ValueError("Invalid Google preview navigation limits.")
    views = {"overview": preview["overview"]}
    checkpoints = {p["name"]: p["lonlat"] for p in study["checkpoints"]}
    for view_id, name in [("entrance", "Main entrance plaza"),
                          ("pavilion", "African Rainforest Pavilion")]:
        lng, lat = checkpoints[name]
        views[view_id] = {
            "center": {"lat": lat, "lng": lng,
                       "altitude": preview["checkpoint_altitudes"][name]},
            "range": 520 if view_id == "entrance" else 420,
            "tilt": 60, "heading": 60,
        }
    views["top"] = {**preview["overview"], "tilt": 0, "heading": 0,
                    "range": navigation["max_range_m"]}
    for view in views.values():
        if not (navigation["min_range_m"] <= view["range"] <= navigation["max_range_m"]
                and view["tilt"] <= navigation["max_tilt_deg"]
                and preview["bounds"]["south"] <= view["center"]["lat"] <= preview["bounds"]["north"]
                and preview["bounds"]["west"] <= view["center"]["lng"] <= preview["bounds"]["east"]):
            raise ValueError("A camera preset exceeds the study area or navigation limits.")
    return {"views": views, "bounds": preview["bounds"],
            "navigation": navigation, "studyName": study["name"]}
