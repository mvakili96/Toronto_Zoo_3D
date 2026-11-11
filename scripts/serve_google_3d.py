"""Serve a local Google Maps 3D preview. Uses Python's standard library only."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "experiments/google-3d"
FILES = {"/": ("index.html", "text/html"),
         "/index.html": ("index.html", "text/html"),
         "/app.js": ("app.js", "text/javascript"),
         "/style.css": ("style.css", "text/css")}


def read_key():
    value = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not value and (ROOT / ".env").is_file():
        for line in (ROOT / ".env").read_text().splitlines():
            name, sep, candidate = line.strip().removeprefix("export ").partition("=")
            if sep and name.strip() == "GOOGLE_MAPS_API_KEY":
                value = candidate.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                break
    return "" if value in ("your_key_here", "YOUR_API_KEY") else value


def preview_config():
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
        views[view_id] = {"center": {"lat": lat, "lng": lng,
                                     "altitude": preview["checkpoint_altitudes"][name]},
                          "range": 520 if view_id == "entrance" else 420,
                          "tilt": 60, "heading": 60}
    views["top"] = {**preview["overview"], "tilt": 0, "heading": 0,
                    "range": navigation["max_range_m"]}
    for view in views.values():
        if not (navigation["min_range_m"] <= view["range"] <= navigation["max_range_m"]
                and view["tilt"] <= navigation["max_tilt_deg"]
                and preview["bounds"]["south"] <= view["center"]["lat"] <= preview["bounds"]["north"]
                and preview["bounds"]["west"] <= view["center"]["lng"] <= preview["bounds"]["east"]):
            raise ValueError("A camera preset exceeds the study area or navigation limits.")
    key = read_key()
    return {"configured": bool(key), "apiKey": key, "views": views,
            "bounds": preview["bounds"], "navigation": navigation,
            "studyName": study["name"]}


class PreviewHandler(BaseHTTPRequestHandler):
    def log_request(self, code="-", size="-"):
        # Never log request query strings, response bodies or API credentials.
        print(f"{self.command} {urlsplit(self.path).path} {code}", flush=True)

    def send_body(self, status, content, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(content)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        port = self.server.server_port
        allowed_hosts = {f"localhost:{port}", f"127.0.0.1:{port}"}
        if self.headers.get("Host") not in allowed_hosts:
            self.send_body(403, b"Local preview only.", "text/plain")
            return
        path = urlsplit(self.path).path
        if path == "/config.json":
            origin = self.headers.get("Origin")
            if ((origin and origin not in {f"http://{h}" for h in allowed_hosts})
                    or self.headers.get("Sec-Fetch-Site") == "cross-site"):
                self.send_body(403, b"Same-origin requests only.", "text/plain")
                return
            try:
                body = json.dumps(preview_config(), allow_nan=False).encode()
                self.send_body(200, body, "application/json")
            except (ValueError, KeyError, OSError):
                body = json.dumps({"error": "Preview configuration is unavailable. Check the study and preview configuration files."}).encode()
                self.send_body(500, body, "application/json")
            return
        if path not in FILES:
            self.send_body(404, b"Not found.", "text/plain")
            return
        name, mime = FILES[path]
        self.send_body(200, (WEB / name).read_bytes(), mime)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8002)
    args = parser.parse_args()
    try:
        config = preview_config()
        server = ThreadingHTTPServer(("127.0.0.1", args.port), PreviewHandler)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Could not start Google 3D preview: {type(error).__name__}. Check the port and preview configuration.\n")
    print(f"Google 3D Zoo preview: http://localhost:{server.server_port}", flush=True)
    print("Google key configured." if config["configured"] else "Add GOOGLE_MAPS_API_KEY to .env, then reload the page.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
