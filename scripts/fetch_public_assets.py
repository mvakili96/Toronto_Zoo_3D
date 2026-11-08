"""Optional network step; preparation and the app run offline with cached assets.

Use --refresh-imagery only when you want the City's current service image.
It can change vintage. The 2022 university files are never copied to public/.
"""
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,json

ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--config',default='config/study-area.json');ap.add_argument('--refresh-imagery',action='store_true');args=ap.parse_args()
cfg=json.loads((ROOT/args.config).read_text())
def fetch(path,url):
    path.parent.mkdir(parents=True,exist_ok=True)
    with urlopen(Request(url,headers={'User-Agent':'TorontoZooPilot/1.0'}),timeout=90) as r:b=r.read()
    path.write_bytes(b);print(path.relative_to(ROOT),len(b),'bytes',flush=True);return b

vendor=ROOT/'public/vendor'
for name,url in [('three.module.js','https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js'),('OrbitControls.js','https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/controls/OrbitControls.js'),('THREE-LICENSE.txt','https://cdn.jsdelivr.net/npm/three@0.170.0/LICENSE')]:
    if not (vendor/name).exists():fetch(vendor/name,url)
cache=ROOT/'generated/sources';img=cache/'zoo-ortho.jpg'
if args.refresh_imagery or not img.exists():
    url='https://gis.toronto.ca/arcgis/rest/services/basemap/cot_ortho/MapServer/export?'+urlencode({'f':'image','bbox':','.join(map(str,cfg['bounds'])),'bboxSR':cfg['crs'].split(':')[-1],'imageSR':cfg['crs'].split(':')[-1],'size':','.join(map(str,cfg['imagery_pixels'])),'format':'jpg','dpi':96,'transparent':'false'})
    b=fetch(img,url)
    # Decode now so JSON errors or empty service responses cannot masquerade as imagery.
    from PIL import Image
    Image.open(img).verify()
    p=cache/'requests.json';log=json.loads(p.read_text()) if p.exists() else []
    log=[r for r in log if r['file']!='zoo-ortho.jpg'];log.append({'file':'zoo-ortho.jpg','url':url,'bytes':len(b),'retrieved':datetime.now(ZoneInfo('America/Toronto')).isoformat()})
    p.write_text(json.dumps(log,indent=2))
