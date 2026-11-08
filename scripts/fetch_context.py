"""Optional provenance-preserving downloads. Runtime/preparation use cached files offline."""
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import json
root=Path(__file__).resolve().parents[1]
q=(root/'config/context-query.overpass').read_text()
for host in ['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter','https://overpass.private.coffee/api/interpreter']:
 try:
  u=host+'?'+urlencode({'data':q})
  with urlopen(Request(u,headers={'User-Agent':'TorontoZooPilot/1.0 (local GIS review)'}),timeout=35) as r:b=r.read()
  x=json.loads(b); assert 'elements' in x
  (root/'generated/sources/osm-context.json').write_bytes(b)
  (root/'generated/sources/osm-context-request.json').write_text(json.dumps({'url':u,'timestamp':x.get('osm3s',{}).get('timestamp_osm_base')},indent=2))
  print('OSM context:',len(x['elements']),'elements,',len(b),'bytes',flush=True);break
 except Exception as e: print(host,str(e),flush=True)
