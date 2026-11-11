"""Verify the local Google 3D preview without recording its API key."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit
from urllib.request import urlopen
from urllib.error import HTTPError
from playwright.sync_api import sync_playwright
from serve_google_3d import read_key

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8002/")
    args = parser.parse_args()
    out = ROOT / "reports/google-3d"
    out.mkdir(parents=True, exist_ok=True)
    key = read_key()
    # Keep credentials out of test output. Only these public settings are used.
    with urlopen(urljoin(args.url, "config.json"), timeout=10) as response:
        config = json.load(response)
    if "navigation" not in config:
        parser.error("The running preview uses the previous server code. Restart it or select the updated server with --url.")
    views, bounds, limits = config["views"], config["bounds"], config["navigation"]
    del config

    def clean(value):
        value = str(value)
        if key:
            value = value.replace(key, "[redacted]")
        return re.sub(r"AIza[\w-]+", "[redacted]", value)

    checks, errors, console_errors = [], [], []
    responses = Counter()

    def check(name, passed):
        checks.append({"name": name, "passed": bool(passed)})
        print(("PASS " if passed else "FAIL ") + name, flush=True)
        assert passed, name

    # These routes must never expose local credentials or original GIS inputs.
    for path in (".env", ".git/config", "maria/", "elevation/", "buildings/"):
        try:
            with urlopen(urljoin(args.url, path), timeout=10) as response:
                code = response.status
        except HTTPError as error:
            code = error.code
        check("Private/input route blocked: " + path, code == 404)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            "--no-sandbox", "--enable-unsafe-swiftshader", "--use-angle=swiftshader"])
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("pageerror", lambda e: errors.append(clean(e)))
            page.on("console", lambda m: console_errors.append(clean(m.text)) if m.type == "error" else None)
            page.on("response", lambda r: responses.update([(urlsplit(r.url).hostname, r.status)]))
            page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
            phase = None
            for _ in range(18):
                page.wait_for_timeout(10000)
                phase = page.locator("#status").get_attribute("data-state")
                print("Google preview state: " + str(phase), flush=True)
                if phase in ("ready", "error", "missing-key"):
                    break
            if phase != "ready":
                page.screenshot(path=str(out / "local-google-load-state.png"), timeout=60000)
                print(json.dumps({"status": page.locator("#status").inner_text(),
                                  "page_errors": errors, "console_errors": console_errors[-10:]}, indent=2), flush=True)
            check("User's Google key loads the 3D map", phase == "ready")
            page.screenshot(path=str(out / "local-google-overview.png"), timeout=60000)
            check("Google map element exists", page.locator("gmp-map-3d").count() == 1)
            check("Native camera bounds match the GIS study area", page.evaluate("""bounds => {
              const actual = document.querySelector('gmp-map-3d').bounds.toJSON();
              return Object.keys(bounds).every(k => Math.abs(actual[k]-bounds[k]) < 1e-8);
            }""", bounds))
            baseline = page.evaluate("googleZoo.snapshot()")
            page.click("#zoom-in")
            page.wait_for_function("(r)=>googleZoo.snapshot().range < r", arg=baseline["range"], timeout=30000)
            check("Zoom control changes camera range", page.evaluate("googleZoo.snapshot().range") < baseline["range"])
            page.click('[data-view="pavilion"]')
            page.wait_for_function("r => Math.abs(googleZoo.snapshot().range-r)<2", arg=views["pavilion"]["range"], timeout=30000)
            check("Rainforest Pavilion camera preset works", page.evaluate("googleZoo.snapshot().view") == "pavilion")
            page.wait_for_timeout(8000)
            page.screenshot(path=str(out / "local-google-pavilion.png"), timeout=60000)
            page.locator("#labels").check()
            check("Map labels can be enabled", page.evaluate("googleZoo.snapshot().labels"))
            page.locator("#labels").uncheck()
            page.click("#orbit")
            page.wait_for_function("googleZoo.snapshot().orbiting", timeout=30000)
            heading = page.evaluate("googleZoo.snapshot().heading")
            page.wait_for_timeout(2500)
            check("Orbit moves the camera", abs(page.evaluate("googleZoo.snapshot().heading") - heading) > .1)
            page.click("#orbit")
            page.wait_for_function("!googleZoo.snapshot().orbiting", timeout=30000)
            check("Orbit can be paused", not page.evaluate("googleZoo.snapshot().orbiting"))
            page.click("#reset")
            # Google normalizes the camera against the rendered surface/limits.
            # Verify the returned location, distance and orientation together.
            page.wait_for_function("""view => {
              const s = googleZoo.snapshot();
              return (Math.abs(s.range-view.range)<view.range*.05 && Math.abs(s.tilt-view.tilt)<1 &&
                Math.abs(s.heading-view.heading)<1 && Math.abs(s.center.lat-view.center.lat)<.0005 &&
                Math.abs(s.center.lng-view.center.lng)<.0005);
            }""", arg=views["overview"], timeout=30000)
            check("Reset restores the overview", page.evaluate("googleZoo.snapshot().view") == "overview")
            page.click('[data-view="entrance"]')
            page.wait_for_function("r => googleZoo.snapshot().view==='entrance' && Math.abs(googleZoo.snapshot().range-r)<r*.05", arg=views["entrance"]["range"], timeout=30000)
            check("Entrance-area preset works", page.evaluate("googleZoo.snapshot().view") == "entrance")
            page.click('[data-view="top"]')
            page.wait_for_function("r => googleZoo.snapshot().tilt<1 && Math.abs(googleZoo.snapshot().range-r)<r*.05", arg=views["top"]["range"], timeout=30000)
            check("Overhead preset works", page.evaluate("googleZoo.snapshot().view") == "top")
            # Exercise native gestures as well as our buttons. The same map
            # instance is reused throughout, without extra map loads.
            page.mouse.move(1050, 550)
            for _ in range(3):
                page.mouse.wheel(0, 1600)
                page.wait_for_timeout(400)
            page.wait_for_function("r => googleZoo.snapshot().range<=r+1", arg=limits["max_range_m"], timeout=30000)
            check("Mouse wheel cannot zoom out beyond the configured range", page.evaluate("googleZoo.snapshot().range") <= limits["max_range_m"]+1)
            page.evaluate("r => document.querySelector('gmp-map-3d').range=r*4", limits["max_range_m"])
            page.wait_for_function("r => googleZoo.snapshot().range<=r+1", arg=limits["max_range_m"], timeout=30000)
            check("Camera range changes are capped beyond the buttons", page.evaluate("googleZoo.snapshot().range") <= limits["max_range_m"]+1)
            check("Zoom-out button stops at the limit", page.locator("#zoom-out").is_disabled())
            for edge, center in {
                "north": {"lat": bounds["north"]+.02, "lng": views["overview"]["center"]["lng"]},
                "south": {"lat": bounds["south"]-.02, "lng": views["overview"]["center"]["lng"]},
                "east": {"lat": views["overview"]["center"]["lat"], "lng": bounds["east"]+.02},
                "west": {"lat": views["overview"]["center"]["lat"], "lng": bounds["west"]-.02},
            }.items():
                page.evaluate("""center => {
                  const map = document.querySelector('gmp-map-3d');
                  map.range=420;
                  map.tilt=0;
                  map.center={...center, altitude:180};
                }""", center)
                page.wait_for_function("""b => {
                  const s=googleZoo.snapshot(), c=s.center, p=s.cameraPosition;
                  const inside = v => v && v.lat>=b.south-1e-5 && v.lat<=b.north+1e-5 &&
                    v.lng>=b.west-1e-5 && v.lng<=b.east+1e-5;
                  return inside(c) && inside(p);
                }""", arg=bounds, timeout=30000)
                check("Camera and focus stay inside the "+edge+" study edge", True)
            page.evaluate("r => document.querySelector('gmp-map-3d').range=r/4", limits["min_range_m"])
            page.wait_for_function("r => googleZoo.snapshot().range>=r-.5", arg=limits["min_range_m"], timeout=30000)
            check("Close-up zoom has a lower limit", page.evaluate("googleZoo.snapshot().range") >= limits["min_range_m"]-.5)
            page.click('[data-view="pavilion"]')
            page.wait_for_function("""view => {
              const s=googleZoo.snapshot();
              return Math.abs(s.range-view.range)<2 && Math.abs(s.center.lat-view.center.lat)<1e-5 &&
                Math.abs(s.center.lng-view.center.lng)<1e-5 && Math.abs(s.tilt-view.tilt)<.1;
            }""", arg=views["pavilion"], timeout=30000)
            # The preceding limit test also used a 420 m range. Wait for the
            # preset's location and the end of its one-second fly animation
            # before starting a gesture, rather than checking range alone.
            page.wait_for_timeout(1200)
            start = page.evaluate("googleZoo.snapshot().center")
            page.mouse.move(1100, 550)
            page.mouse.down()
            page.mouse.move(1250, 600, steps=15)
            page.mouse.up()
            page.wait_for_timeout(1000)
            end = page.evaluate("googleZoo.snapshot().center")
            check("Native drag still pans within the study area", abs(start["lat"]-end["lat"])+abs(start["lng"]-end["lng"])>1e-6)
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(1000)
            check("Camera controls remain available in phone layout", page.locator("#reset").is_visible() and page.locator("#zoom-in").is_visible())
            check("No JavaScript errors", not errors)
            check("No browser console errors", not console_errors)
            report = {"checks": checks, "passed": all(c["passed"] for c in checks),
                      "study_bounds": bounds, "navigation": limits,
                      "page_errors": errors, "console_errors": console_errors,
                      "responses": [{"host": host, "status": status, "count": count}
                                    for (host, status), count in responses.items()]}
            result = json.dumps(report, indent=2)
            assert not key or key not in result
            (out / "local-verification.json").write_text(result)
        except Exception:
            diagnostic = {"camera": page.evaluate("window.googleZoo?.snapshot() ?? null"),
                          "page_errors": errors, "console_errors": console_errors[-10:]}
            print(clean(json.dumps(diagnostic, indent=2)), flush=True)
            page.screenshot(path=str(out / "local-google-failure.png"), timeout=60000)
            raise
        finally:
            browser.close()


if __name__ == "__main__":
    main()
