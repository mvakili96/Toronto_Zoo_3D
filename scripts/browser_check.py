"""Playwright checks and screenshots against an already running local server.

PLAYWRIGHT_BROWSERS_PATH=/tmp/toronto-zoo-browser python scripts/browser_check.py
"""
from pathlib import Path
import json, time
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'reports';out.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader'])
    page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
    errors=[];responses=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('response',lambda r:responses.append({'url':r.url,'status':r.status}))
    print('Opening local app...',flush=True)
    page.goto('http://127.0.0.1:8000',wait_until='networkidle',timeout=60000)
    page.wait_for_function('window.zoo?.state.ready',timeout=120000)
    page.wait_for_timeout(1600)
    print('READY',page.evaluate('zoo.snapshot()'),flush=True)
    page.screenshot(path=str(out/'overview.png'),timeout=60000)
    print('Saved overview',flush=True)
    report={'overview':page.evaluate('zoo.snapshot()'),'errors':errors,'responses':responses,'checks':[]}
    def check(name,passed,details=None):
        report['checks'].append({'name':name,'passed':bool(passed),'details':details})
        print(('PASS ' if passed else 'FAIL ')+name,flush=True)
        assert passed, (name,details)
    original=page.evaluate('zoo.snapshot()')
    # Exercise real pointer controls on an unobstructed piece of canvas.
    page.mouse.move(1020,560);page.mouse.down();page.mouse.move(1140,590,steps=12);page.mouse.up();page.wait_for_timeout(700)
    orbit=page.evaluate('zoo.snapshot()');check('Mouse drag orbits camera',orbit['camera']!=original['camera'])
    page.mouse.move(1030,560);page.mouse.down(button='right');page.mouse.move(1100,600,steps=10);page.mouse.up(button='right');page.wait_for_timeout(700)
    pan=page.evaluate('zoo.snapshot()');check('Right-drag pans target',pan['target']!=orbit['target'])
    page.mouse.wheel(0,-400);page.wait_for_timeout(900)
    zoom=page.evaluate('zoo.snapshot()');check('Wheel zoom changes camera',zoom['camera']!=pan['camera'])
    page.click('#reset');page.wait_for_function('(expected)=>zoo.snapshot().camera.every((v,i)=>Math.abs(v-expected[i])<.1)',arg=original['camera'],timeout=30000)
    reset=page.evaluate('zoo.snapshot()');check('Reset restores overview',all(abs(a-b)<.1 for a,b in zip(reset['camera'],original['camera'])),reset)
    for layer in ['terrain','buildings','roads','paths','water','parking','woodland','boundary','labels']:
        selector=f'input[data-layer="{layer}"]'
        page.locator(selector).uncheck(force=True);page.wait_for_timeout(80)
        check(layer+' toggle off',not page.evaluate(f'zoo.state.layers.{layer}'))
        page.locator(selector).check(force=True)
    page.click('#open-notes');check('Sources dialog opens',page.locator('#notes').is_visible())
    page.locator('input[data-layer="comparison"]').check();check('City comparison on',page.evaluate('zoo.state.layers.comparison'))
    page.locator('input[data-layer="comparison"]').uncheck();page.click('#close-notes')
    page.click('[data-view="pavilion"]');page.wait_for_timeout(1600)
    page.screenshot(path=str(out/'close-up.png'),timeout=60000)
    report['close_up']=page.evaluate('zoo.snapshot()')
    # Pick a source 3D building using its projected center.
    b=page.evaluate('zoo.data.buildings.features.filter(b=>b.id==="Multipatch_60P/510")[0]')
    x,y=page.evaluate('(b)=>zoo.project(...b.center,b.height_m+2)',b)
    page.mouse.click(x,y);page.wait_for_timeout(150)
    check('Building inspection opens source details',page.locator('#feature').is_visible(),page.locator('#feature-facts').inner_text())
    page.click('#close-feature');page.click('#imagery');page.wait_for_function('zoo.state.imagery');page.wait_for_timeout(600)
    check('Imagery toggle loads the georeferenced aerial',page.evaluate('zoo.state.imagery'))
    page.screenshot(path=str(out/'close-up-imagery.png'),timeout=60000)
    page.click('[data-view="entrance"]');page.wait_for_timeout(1500);page.screenshot(path=str(out/'entrance-imagery.png'),timeout=60000)
    page.click('#neutral');page.wait_for_function('!zoo.state.imagery');check('Neutral terrain restored',not page.evaluate('zoo.state.imagery'))
    page.click('[data-view="top"]');page.wait_for_timeout(1500);check('Top view works',page.evaluate('zoo.snapshot().camera[1]')>3900)
    # Actual HTTP resource sizes, including optional imagery loaded by the test.
    report['resources']=page.evaluate('performance.getEntriesByType("resource").map(r=>({name:r.name,bytes:r.decodedBodySize,transferBytes:r.transferSize,durationMs:r.duration}))')
    report['loaded_resource_bytes']=sum(r['bytes'] for r in report['resources'])
    report['document_bytes']=(ROOT/'public/index.html').stat().st_size
    report['total_body_bytes_with_document']=report['loaded_resource_bytes']+report['document_bytes']
    report['initial_body_bytes']=report['total_body_bytes_with_document']-sum(r['bytes'] for r in report['resources'] if r['name'].endswith('ortho.webp'))
    check('All runtime resources come from the local server',all(r['name'].startswith('http://127.0.0.1:8000/') for r in report['resources']))
    report['errors']=errors
    check('No browser JavaScript errors',not errors,errors)
    report['route_clearance']=page.evaluate('zoo.routeClearanceAudit()')
    check('Road and path triangle centers remain above terrain',report['route_clearance']['buriedSamples']==0,report['route_clearance'])
    # Phone viewport: collapse the layers and use the same camera/layer actions.
    page.set_viewport_size({'width':390,'height':844});page.click('#collapse-layers');page.click('#reset');page.wait_for_timeout(1500)
    page.screenshot(path=str(out/'mobile.png'),timeout=60000)
    check('Phone controls remain reachable',page.locator('#reset').is_visible() and page.locator('[data-view="entrance"]').is_visible())
    (out/'browser-verification.json').write_text(json.dumps(report,indent=2))
    print('Browser verification saved. Bytes:',report['loaded_resource_bytes'],flush=True)
    browser.close()
