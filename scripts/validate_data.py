"""Independent checks of browser assets, terrain alignment and source preservation."""
from pathlib import Path
import json, math
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
assets=ROOT/'public/assets'
s=json.loads((assets/'scene.json').read_text());cfg=s['study'];ox,oy,oz=cfg['origin'];xmin,ymin,xmax,ymax=cfg['bounds']
t=s['terrain'];w,h,step=t['width'],t['height'],t['step']
elev=np.fromfile(assets/'terrain.f32',dtype='<f4').reshape(h,w)
v=np.fromfile(assets/'buildings.f32',dtype='<f4').reshape(-1,3)
c=np.fromfile(assets/'building-colors.f32',dtype='<f4').reshape(-1,3)
checks=[]
def check(name,condition,details=None):
    checks.append({'name':name,'passed':bool(condition),'details':details})
    print(('PASS ' if condition else 'FAIL ')+name,flush=True)

def ground(x,n):
    x=np.asarray(x,dtype='float64');n=np.asarray(n,dtype='float64')
    u=np.clip((x+ox-xmin)/step,0,w-1-1e-6);vv=np.clip((ymax-n-oy)/step,0,h-1-1e-6)
    i=u.astype(int);j=vv.astype(int);a=u-i;b=vv-j
    nw=elev[j,i];ne=elev[j,i+1];sw=elev[j+1,i];se=elev[j+1,i+1]
    return np.where(a+b<=1,nw+a*(ne-nw)+b*(sw-nw),se+(1-a)*(sw-se)+(1-b)*(ne-se))-oz

audit=json.loads((ROOT/'reports/data-audit.json').read_text())
check('Terrain has complete finite coverage',np.isfinite(elev).all() and audit['terrain']['missing_cells']==0)
check('At least one supplied terrain tile covers this scene',len(audit['terrain']['overlapping_tiles'])>0)
check('Building buffers have finite aligned position and colour arrays',len(v)==len(c) and np.isfinite(v).all() and np.isfinite(c).all())
check('All buildings are clipped or contained by study area',bool(np.all((v[:,0]>=xmin-ox-.02)&(v[:,0]<=xmax-ox+.02)&(-v[:,2]>=ymin-oy-.02)&(-v[:,2]<=ymax-oy+.02))))
ranges=s['buildings']['features']
check('Building feature ranges cover mesh without overlap or holes',sum(b['count'] for b in ranges)==len(v) and all(a['first']+a['count']==b['first'] for a,b in zip(ranges,ranges[1:])))
clearance=v[:,1]-ground(v[:,0],-v[:,2]);base=np.abs(clearance+.12)<.025
# Ground bottoms and source roof/eave vertices have separate clearance rules.
buried=(clearance<-.15)
check('No building vertex is buried more than the intended 12 cm footing',not np.any(buried),{'buried_vertices':int(buried.sum()),'minimum_clearance_m':float(clearance.min())})
check('Buildings have grounded bottom vertices',int(base.sum())>len(ranges),{'grounded_vertex_copies':int(base.sum())})
ids=[(r['id'],r['part']) for r in s['routes']]
check('Rendered route ids and part ids are unique',len(ids)==len(set(ids)))
check('Route widths are plausible positive metre values',all(.5<=r['width_m']<=40 for r in s['routes']))
check('Every bridge has a separately estimated deck',all('deck_endpoint_m' in r for r in s['routes'] if r['bridge']))
check('No unlabelled default building heights',all(not b['height_estimated'] or b.get('height_source') is not None for b in ranges))
check('Original input sizes and modification times preserved',all((ROOT/p).stat().st_size==a['bytes'] and (ROOT/p).stat().st_mtime_ns==a['mtime_ns'] for p,a in json.loads((ROOT/'reports/input-inventory-prepare.json').read_text()).items()))
old=ROOT/'reports/input-inventory-before.json'
if old.exists():check('Inputs present before the coverage update remain unchanged',all((ROOT/p).stat().st_size==a['bytes'] and (ROOT/p).stat().st_mtime_ns==a['mtime_ns'] for p,a in json.loads(old.read_text()).items()))
check('University imagery excluded from public assets',not any('2022' in p.name or p.suffix.lower()=='.tif' for p in (ROOT/'public').rglob('*')))
result={'checks':checks,'passed':all(c['passed'] for c in checks),'slope_lifts':[{'id':b['id'],'lift_m':b['slope_clearance_lift_m']} for b in ranges if b.get('slope_clearance_lift_m',0)>0],'footprint_roof_lifts':[{'id':b['id'],'lift_m':b['roof_lift_for_slope_m']} for b in ranges if b.get('roof_lift_for_slope_m',0)>0]}
(ROOT/'reports/data-verification.json').write_text(json.dumps(result,indent=2))
raise SystemExit(0 if result['passed'] else 1)
