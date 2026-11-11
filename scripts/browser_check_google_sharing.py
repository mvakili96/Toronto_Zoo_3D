"""Check static Google sharing states without making any live Google requests."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8004/Toronto_Zoo_3D/google-3d/")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/google-sharing")
    args = parser.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    with urlopen(urljoin(args.url, "config.json"), timeout=10) as response:
        actual = json.load(response)
    # Only test data reaches these mocked pages. Never save the real config/key.
    base = {k: v for k, v in actual.items() if k not in ("apiKey", "configured")}
    del actual
    configured = {**base, "configured": True, "apiKey": "test-browser-key-for-offline-checks"}
    checks = []

    def check(name, passed):
        checks.append({"name": name, "passed": bool(passed)})
        print(("PASS " if passed else "FAIL ") + name, flush=True)
        assert passed, name

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            google_calls = []

            def new_page(configuration, sdk=None, viewport=None):
                page = browser.new_page(viewport=viewport or {"width": 1440, "height": 1000})
                page.route("**/config.json", lambda r: r.fulfill(json=configuration))

                def google_request(route):
                    google_calls.append(urlsplit(route.request.url).hostname)
                    if sdk is None:
                        route.abort()
                    else:
                        route.fulfill(content_type="text/javascript", body=sdk)

                # Catch all potential Google traffic, not just the SDK URL.
                page.route(re.compile(r"^https://(?:[^/]+\.)?(?:googleapis\.com|gstatic\.com|google\.com)/"), google_request)
                page.goto(args.url, wait_until="domcontentloaded")
                page.wait_for_function("['awaiting-click','missing-key','error'].includes(document.querySelector('#status').dataset.state)")
                return page

            page = new_page(configured)
            check("Quota notice precedes map loading", page.locator("#launch").is_visible() and "daily" in page.locator("#launch").inner_text().lower())
            check("Welcome screen makes no Google request", not google_calls)
            expected_gis = urljoin(args.url, base["gisUrl"])
            check("GIS links resolve correctly under the repository path", all(h == expected_gis for h in page.locator('.gis-link').evaluate_all('(links)=>links.map(l=>l.href)')))
            with urlopen(expected_gis, timeout=10) as response:
                check("GIS fallback page is served", response.status == 200)
            page.screenshot(path=str(out / "welcome.png"))
            page.click("#load-google")
            page.wait_for_function("document.querySelector('#status').dataset.state==='error'")
            check("Network failure offers a useful message and GIS link", "internet connection" in page.locator('#message-text').inner_text() and page.locator('#message .gis-link').is_visible())
            check("Map loading has no automatic retry loop", len(google_calls) == 1)
            page.close()

            google_calls.clear()
            page = new_page({**base, "configured": False, "apiKey": ""})
            check("Missing hosted key shows availability instead of local setup instructions", page.locator('#status').get_attribute('data-state') == 'missing-key' and '.env' not in page.locator('#message-text').inner_text())
            check("Missing key makes no Google request", not google_calls)
            page.screenshot(path=str(out / "unconfigured.png"))
            page.close()

            google_calls.clear()
            page = new_page(configured, sdk="window.gm_authFailure(); window.google3DReady();")
            page.click("#load-google")
            page.wait_for_function("document.querySelector('#status').dataset.state==='error'")
            check("Authorization failure explains possible shared quota and offers fallback", 'quota' in page.locator('#message-text').inner_text() and page.locator('#message .gis-link').is_visible())
            check("Authorization failure does not initialize a map", page.locator('gmp-map-3d').count() == 0)
            page.screenshot(path=str(out / "access-unavailable.png"))
            page.close()

            google_calls.clear()
            page = new_page(configured, viewport={"width": 390, "height": 844})
            box = page.locator('#load-google').bounding_box()
            check("Phone welcome button is visible within the viewport", box and box['x'] >= 0 and box['x']+box['width'] <= 390 and box['y']+box['height'] <= 844)
            check("Phone welcome exposes quota notice and GIS alternative", 'daily' in page.locator('#launch').inner_text().lower() and page.locator('#launch .gis-link').is_visible())
            check("Phone welcome makes no Google request", not google_calls)
            page.screenshot(path=str(out / "phone-welcome.png"))
            page.close()
            (out / "sharing-verification.json").write_text(json.dumps({"passed": True, "checks": checks, "live_google_requests": 0}, indent=2)+"\n")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
