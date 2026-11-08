"""Read-only OSM query audit; does not replace the app's existing source snapshot."""
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode
import json

root=Path(__file__).resolve().parents[1]
query='''[out:json][timeout:50];
(
 nwr["natural"~"^(wood|tree|tree_row|tree_group)$"](43.807,-79.207,43.833,-79.166);
 nwr["landuse"="forest"](43.807,-79.207,43.833,-79.166);
 nwr["landcover"="trees"](43.807,-79.207,43.833,-79.166);
);
out meta geom;
'''
sources=root/'generated/sources'
(sources/'osm-vegetation-audit.overpass').write_text(query)
for host in ['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter','https://overpass.private.coffee/api/interpreter']:
    try:
        url=host+'?'+urlencode({'data':query})
        with urlopen(Request(url,headers={'User-Agent':'TorontoZooPilot/1.0 (vegetation coverage audit)'}),timeout=60) as r:body=r.read()
        data=json.loads(body)
        assert 'elements' in data
        (sources/'osm-vegetation-audit.json').write_bytes(body)
        (sources/'osm-vegetation-audit-request.json').write_text(json.dumps({'url':url,'osm_timestamp':data.get('osm3s',{}).get('timestamp_osm_base')},indent=2))
        print('Saved vegetation audit:',len(data['elements']),'elements,',len(body),'bytes',flush=True)
        break
    except Exception as error:print(host,str(error),flush=True)
else:raise SystemExit('Vegetation audit download failed; existing app data untouched.')
