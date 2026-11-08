"""Build a small offline scene. Source inputs are always opened read-only.

python scripts/prepare.py --config config/study-area.json
All geometry calculations use the configured projected metre CRS. Browser axes
are East, Up, South relative to the saved origin. No Web Mercator scale factor
is applied to the source height values (which are already in metres).
"""
import argparse
from pathlib import Path
import json, math, re, shutil, hashlib
from collections import Counter
import fiona
import rasterio
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.transform import from_origin
import numpy as np
from scipy.ndimage import map_coordinates
from shapely.geometry import shape, box, Polygon, LineString, Point, mapping
from shapely.ops import transform, unary_union
from shapely import make_valid, force_2d
from shapely.strtree import STRtree
from pyproj import Transformer, CRS
import mapbox_earcut as earcut
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]

def dump(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, allow_nan=False))

def polygons(g):
    if g.geom_type == 'Polygon': return [g]
    return [p for a in getattr(g, 'geoms', []) for p in polygons(a)]

def lines(g):
    if g.geom_type == 'LineString': return [g]
    return [p for a in getattr(g, 'geoms', []) for p in lines(a)]

def triangulate(rings):
    rs = [np.asarray(r, dtype='float64') for r in rings if len(r) >= 3]
    if not rs: return np.empty((0, 3))
    rs = [r[:-1] if np.allclose(r[0],r[-1]) else r for r in rs]
    vertices = np.concatenate(rs)
    # Project a 3D face into its dominant plane, including vertical walls.
    v = rs[0]
    normal = np.sum(np.cross(v, np.roll(v,-1,axis=0)), axis=0)
    if np.linalg.norm(normal) < 1e-8: return np.empty((0,3))
    plane = np.delete(vertices, np.argmax(np.abs(normal)), axis=1)
    idx = earcut.triangulate_float64(np.ascontiguousarray(plane), np.cumsum([len(r) for r in rs],dtype=np.uint32))
    return vertices[idx]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',default='config/study-area.json');args=ap.parse_args()
    cfg=json.loads((ROOT/args.config).read_text());crs=cfg['crs'];bounds=cfg['bounds'];xmin,ymin,xmax,ymax=bounds
    if any(a.unit_name not in ['metre','meter'] for a in CRS.from_user_input(crs).axis_info[:2]):
        raise ValueError('Choose a projected CRS whose horizontal units are metres.')
    if (xmax-xmin)%cfg['terrain_grid_m'] or (ymax-ymin)%cfg['terrain_grid_m']:
        raise ValueError('Study width and height must be multiples of terrain_grid_m.')
    ox,oy,oz=cfg['origin'];aoi=box(*bounds)
    out=ROOT/'public/assets';out.mkdir(parents=True,exist_ok=True)
    gen=ROOT/'generated';gen.mkdir(exist_ok=True)
    audit={'study_area':cfg,'crs':{},'warnings':[], 'adjustments':[]}
    ll=transform(Transformer.from_crs(crs,4326,always_xy=True).transform,aoi)
    dump(ROOT/'config/study-extent.geojson',{'type':'Feature','properties':{'name':cfg['name'],'status':cfg['boundary_status'],'edit':'config/study-area.json is the source of truth'},'geometry':mapping(ll)})
    # Inventory makes accidental source modifications reviewable, including newly added tiles.
    inventory={str(p.relative_to(ROOT)):{'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for d in ['maria','buildings','elevation'] for p in (ROOT/d).rglob('*') if p.is_file()}
    dump(ROOT/'reports/input-inventory-prepare.json',inventory)
    print('Inspecting terrain coverage...',flush=True)
    tiles=[];covered=[]
    for p in sorted((ROOT/'elevation').rglob('*.tif')):
        with rasterio.open(p) as s:
            tr=Transformer.from_crs(s.crs,crs,always_xy=True)
            b=transform_bounds(s.crs,crs,*s.bounds)
            overlap=box(*b).intersects(aoi)
            rec={'file':str(p.relative_to(ROOT)),'crs':str(s.crs),'resolution':list(s.res),'bounds':list(s.bounds),'overlaps':overlap}
            if overlap:
                g=transform(tr.transform,box(*s.bounds));covered.append(g)
            tiles.append(rec)
    active=[t for t in tiles if t['overlaps']]
    cov=unary_union(covered).intersection(aoi).area/aoi.area
    # 2 m working DTM, using actual local tiles only. Do not use the earlier web crop.
    res=2;w=math.ceil((xmax-xmin)/res);h=math.ceil((ymax-ymin)/res)
    affine=from_origin(xmin,ymax,res,res);dtm=np.full((h,w),np.nan,dtype='float32')
    for t in active:
        with rasterio.open(ROOT/t['file']) as s:
            reproject(rasterio.band(s,1),dtm,src_nodata=s.nodata,dst_transform=affine,dst_crs=crs,dst_nodata=np.nan,init_dest_nodata=False,resampling=Resampling.bilinear)
    missing=int((~np.isfinite(dtm)).sum())
    audit['terrain']={'files_checked':len(tiles),'overlapping_tiles':active,'polygon_coverage_fraction':cov,'working_resolution_m':res,'valid_cells':int(np.isfinite(dtm).sum()),'missing_cells':missing,'vertical_datum':'CGVD2013, metres (Ontario DTM User Guide, Table 4, GTA 2023)','range_m':[float(np.nanmin(dtm)),float(np.nanmax(dtm))]}
    dump(ROOT/'reports/terrain-tile-index.json',tiles)
    if missing: raise RuntimeError(f'{missing} missing terrain cells: change extent or provide covering tiles; refusing invented terrain.')
    with rasterio.open(gen/'zoo-dtm-2m.tif','w',driver='GTiff',width=w,height=h,count=1,dtype='float32',crs=crs,transform=affine,nodata=np.nan,compress='deflate') as d:d.write(dtm,1)
    def ground(x,y):
        return map_coordinates(dtm,[np.atleast_1d((ymax-np.asarray(y))/res-.5),np.atleast_1d((np.asarray(x)-xmin)/res-.5)],order=1,mode='nearest').reshape(np.shape(x))
    step=cfg['terrain_grid_m'];nx=round((xmax-xmin)/step)+1;ny=round((ymax-ymin)/step)+1
    gx,gy=np.meshgrid(np.linspace(xmin,xmax,nx),np.linspace(ymax,ymin,ny))
    heights=ground(gx.ravel(),gy.ravel()).reshape((ny,nx))
    heights.astype('<f4').tofile(out/'terrain.f32')
    def surface(x,y):
        # Same triangles as the rendered grid: NW, SW, NE and NE, SW, SE.
        u=np.clip((np.asarray(x)-xmin)/step,0,nx-1-1e-7);v=np.clip((ymax-np.asarray(y))/step,0,ny-1-1e-7)
        i=np.floor(u).astype(int);j=np.floor(v).astype(int);a=u-i;b=v-j
        nw=heights[j,i];ne=heights[j,i+1];sw=heights[j+1,i];se=heights[j+1,i+1]
        return np.where(a+b<=1,nw+a*(ne-nw)+b*(sw-nw),se+(1-a)*(sw-se)+(1-b)*(ne-se))
    def xyz(coords):
        v=np.asarray(coords,dtype='float64').copy();v[:,0]-=ox;v[:,1]-=oy
        return np.column_stack((v[:,0],v[:,2]-oz,-v[:,1])).astype('float32')
    def local2(g):
        return transform(lambda x,y,z=None:(np.asarray(x)-ox,np.asarray(y)-oy),g)
    manifest={'study':cfg,'terrain':{'width':nx,'height':ny,'step':step,'range':audit['terrain']['range_m'],'url':'assets/terrain.f32'},'imagery':None}
    # Open City current-year service crop; private university GeoTIFFs are inspection-only.
    cache=ROOT/'generated/sources/zoo-ortho.jpg';requests=ROOT/'generated/sources/requests.json'
    if cache.exists() and requests.exists():
        req=next((r for r in json.loads(requests.read_text()) if r['file']=='zoo-ortho.jpg'),None)
        from urllib.parse import urlparse,parse_qs
        params=parse_qs(urlparse(req['url']).query) if req else {}
        cached_bounds=[float(v) for v in params.get('bbox',[''])[0].split(',') if v]
        if cached_bounds==bounds:
            im=Image.open(cache);im.save(out/'ortho.webp',quality=88)
            manifest['imagery']={'url':'assets/ortho.webp','source':'City of Toronto current ortho service','vintage':'Service says current year; capture year unverified','retrieved':req.get('retrieved','2026-11-07'),'bounds':bounds,'crs':crs,'pixels':list(im.size),'licence':'Open Government Licence – Toronto','request':req['url']}
    image_info=[]
    for p in sorted((ROOT/'maria').rglob('*.tif')):
        with rasterio.open(p) as s:image_info.append({'file':str(p.relative_to(ROOT)),'crs':str(s.crs),'bounds':list(s.bounds),'pixel_m':list(s.res),'bands':s.count,'tags':s.tags()})
    audit['imagery']={'supplied':image_info,'decision':'2022 Scholars GeoPortal files used only for inspection; no redistributed texture. Open City service crop used in viewer.','rendered':manifest['imagery']}
    if not manifest['imagery']:audit['warnings'].append('Imagery unavailable for this extent. Fetch an Open Government Licence Toronto georeferenced ortho crop in EPSG:2952 covering study bounds.')
    print('Reading buildings and route layers...',flush=True)
    # Footprint heights and positions, plus source-to-terrain elevation differences.
    shp=next((ROOT/'buildings').glob('*Shapefile*/*.shp'));foot=[]
    with fiona.open(shp) as s:
        audit['crs']['footprints']=s.crs.to_wkt();tr=Transformer.from_crs(s.crs,crs,always_xy=True)
        for f in s.filter(bbox=Transformer.from_crs(crs,s.crs,always_xy=True).transform_bounds(*bounds)):
            g=force_2d(transform(tr.transform,shape(f['geometry'])));g=make_valid(g)
            if not g.intersects(aoi):continue
            for pg in polygons(g.intersection(aoi)):
                if pg.area<2:continue
                p=dict(f['properties']);c=pg.representative_point();gnd=float(ground(c.x,c.y))
                foot.append({'id':f.id,'g':pg,'p':p,'ground':gnd,'delta':p['SURF_ELEV']-gnd if p.get('SURF_ELEV') is not None else None})
    tree=STRtree([f['g'] for f in foot]);mp=[];mp_coverage=[];mpidx=[];pos=[];cols=[];failed=[];vertical=[]
    gdb=next((ROOT/'buildings').glob('*Multipatch*/*.gdb'))
    with fiona.open(gdb,layer='Context_Tiles') as s:
        tr=Transformer.from_crs(s.crs,crs,always_xy=True)
        context=[{'name':f['properties']['Tile_Name'],'g':transform(tr.transform,shape(f['geometry']))} for f in s]
    for layer in fiona.listlayers(gdb):
        if not layer.startswith('Multipatch_'):continue
        with fiona.open(gdb,layer=layer) as s:
            b=transform_bounds(s.crs,crs,*s.bounds);overlap=box(*b).intersects(aoi)
            rec={'layer':layer,'total_features':len(s),'bounds_study_crs':list(b),'overlaps':overlap,'selected':0}
            if overlap:
                tr=Transformer.from_crs(s.crs,crs,always_xy=True);bb=Transformer.from_crs(crs,s.crs,always_xy=True).transform_bounds(*bounds)
                for f in s.filter(bbox=bb):
                    faces=[];plan=[]
                    for face in f['geometry']['coordinates']:
                        rr=[]
                        for ring in face:
                            v=np.asarray(ring,dtype=float);x,y=tr.transform(v[:,0],v[:,1]);rr.append(np.column_stack([x,y,v[:,2]]))
                        faces.append(rr)
                        pg=Polygon(rr[0][:,:2], [r[:,:2] for r in rr[1:]])
                        if pg.area>.01:plan.extend(polygons(make_valid(pg)))
                    if not plan:failed.append({'layer':layer,'id':f.id,'reason':'no usable planar faces'});continue
                    g=unary_union(plan)
                    # Keep complete buildings only if their footprint lies within the study.
                    if not aoi.covers(g):
                        if g.intersects(aoi):failed.append({'layer':layer,'id':f.id,'reason':'crosses study edge; clipped footprint fallback'})
                        continue
                    rec['selected']+=1
                    z=np.concatenate([r for face in faces for r in face])[:,2];zmin=float(z.min());zmax=float(z.max())
                    relative=abs(zmin)<.1
                    vertices=np.concatenate([p.exterior.coords for p in polygons(g)])
                    samples=surface(vertices[:,0],vertices[:,1]);anchor=float(np.median(samples))
                    # Some pavilions span steep banks. Preserve the roof shape,
                    # raising its common anchor only when roof/eave vertices
                    # would otherwise be below the terrain. Extend walls down.
                    allv=np.concatenate([r for face in faces for r in face])
                    nonbase=allv[:,2]-zmin>.05
                    clearance=anchor+allv[nonbase,2]-zmin-surface(allv[nonbase,0],allv[nonbase,1])
                    original_anchor=anchor
                    slope_lift=max(0.,.25-float(clearance.min())) if len(clearance) else 0.
                    anchor+=slope_lift
                    start=len(pos);feature_bad=0
                    for face in faces:
                        tri=triangulate(face)
                        if not len(tri):feature_bad+=1;continue
                        if np.max(tri[:,2])-zmin<.05:continue # omit ground face
                        rawz=tri[:,2].copy()
                        # Ground-relative source Z=0 is not mean-sea-level elevation.
                        tri[:,2]=anchor+rawz-zmin
                        base=rawz-zmin<.05
                        tri[base,2]=surface(tri[base,0],tri[base,1])-.12
                        roof=(np.max(rawz)-np.min(rawz))<.4
                        color=[.78,.80,.72] if roof else [.47,.56,.50]
                        pos.extend(xyz(tri).tolist());cols.extend([color]*len(tri))
                    if len(pos)==start:failed.append({'layer':layer,'id':f.id,'reason':'triangulation empty'});continue
                    ids=tree.query(g);match=max(ids,key=lambda i:foot[i]['g'].intersection(g).area,default=None)
                    props=foot[match]['p'] if match is not None else {}
                    c=g.centroid
                    mp.append({'id':f'{layer}/{f.id}','source':'City 2025 Multipatch','first':start,'count':len(pos)-start,'center':[c.x-ox,c.y-oy],'height_m':round(zmax-zmin,2),'height_estimated':False,'base_m':round(anchor,2),'native_z':[zmin,zmax],'placement':'median terrain plus minimum roof clearance lift; wall bottoms draped to terrain','slope_clearance_lift_m':round(slope_lift,3),'original_terrain_anchor_m':round(original_anchor,3),'minimum_original_eave_clearance_m':round(float(clearance.min()),3) if len(clearance) else None,'footprint_id':foot[match]['id'] if match is not None else None,'ground_relief_m':round(float(np.ptp(samples)),2),'untriangulated_faces':feature_bad})
                    mp_coverage.append(g);vertical.append({'id':mp[-1]['id'],'zmin':zmin,'zmax':zmax,'relative_zero':relative,'terrain_anchor_m':anchor,'relief_m':float(np.ptp(samples))})
            mpidx.append(rec)
    mptree=STRtree(mp_coverage);extrusions=[];duplicates=[]
    for f in foot:
        g=f['g'];hits=mptree.query(g);ratio=unary_union([mp_coverage[i].intersection(g) for i in hits]).area/g.area if len(hits) else 0
        if ratio>=.5:duplicates.append(f['id']);continue
        p=f['p'];height=p.get('AVG_HEIGHT');estimated=not height or not math.isfinite(height) or height<=0
        if estimated:height=p.get('MAX_HEIGHT') if p.get('MAX_HEIGHT',0)>0 else 3.0
        vertices=np.asarray(g.exterior.coords);base=float(np.median(surface(vertices[:,0],vertices[:,1])))
        roof=max(base+height,float(np.max(surface(vertices[:,0],vertices[:,1])))+.25)
        start=len(pos)
        rings=[np.column_stack([np.asarray(r.coords),np.full(len(r.coords),roof)]) for r in [g.exterior,*g.interiors]]
        tri=triangulate(rings);pos.extend(xyz(tri).tolist());cols.extend([[.71,.75,.68]]*len(tri))
        for ring in [g.exterior,*g.interiors]:
            v=np.asarray(ring.coords)
            for a,b in zip(v[:-1],v[1:]):
                za=float(surface(*a))-.12;zb=float(surface(*b))-.12
                tri=np.array([[*a,za],[*b,zb],[*a,roof],[*a,roof],[*b,zb],[*b,roof]])
                pos.extend(xyz(tri).tolist());cols.extend([[.53,.61,.55]]*6)
        c=g.centroid;extrusions.append({'id':'footprint/'+f['id'],'source':'City 2025 footprint extrusion','first':start,'count':len(pos)-start,'center':[c.x-ox,c.y-oy],'height_m':round(float(height),2),'height_estimated':estimated,'height_source':p.get('HEIGHT_SRC'),'base_m':round(base,2),'source_surface_elevation_m':p.get('SURF_ELEV'),'ground_relief_m':round(float(np.ptp(surface(vertices[:,0],vertices[:,1]))),2),'roof_lift_for_slope_m':round(roof-(base+height),2)})
    np.asarray(pos,dtype='<f4').tofile(out/'buildings.f32');np.asarray(cols,dtype='<f4').tofile(out/'building-colors.f32')
    building_meta=mp+extrusions
    manifest['buildings']={'url':'assets/buildings.f32','colors':'assets/building-colors.f32','features':building_meta}
    deltas=[f['delta'] for f in foot if f['delta'] is not None]
    audit['buildings']={'footprints_in_extent':len(foot),'multipatch_features':len(mp),'extrusions':len(extrusions),'estimated_height_extrusions':sum(f['height_estimated'] for f in extrusions),'suppressed_covered_footprints':len(duplicates),'omitted_multipatches':failed,'native_zmin_range':[min(v['zmin'] for v in vertical),max(v['zmin'] for v in vertical)],'source_surface_minus_dtm_m':{'p10':float(np.percentile(deltas,10)),'median':float(np.median(deltas)),'p90':float(np.percentile(deltas,90))},'high_relief_buildings':[b for b in building_meta if b['ground_relief_m']>3]}
    dump(ROOT/'reports/multipatch-coverage.json',mpidx);dump(ROOT/'reports/building-grounding.json',building_meta)
    audit['adjustments'].append('Multipatch local Z rebased to median terrain around each building; lower wall vertices meet terrain. Where eaves would be buried, apply minimum common lift for 0.25 m vertex clearance, recorded per building. Relative roof geometry preserved. No global vertical or horizontal shift applied. City SURF_ELEV vertical datum unspecified; not treated as CGVD2013.')
    # Vector source policy: dedicated Zoo OSM > citywide OSM by stable way id.
    # City vectors are a comparison overlay, since their generalized centrelines
    # do not represent both sides of roads and add duplicates inside the Zoo.
    maria=ROOT/'maria/Stream1_Roads_Paths_Imagery.gdb';routes=[];city=[];seen=set();route_layers={};rejected=[]
    layers=[('TorontoZooRoadsTurbo','road'),('TorontoZooPedestriansTurbo','path'),('TorontoWideRoadTurbo','road'),('TorontoWidePedestriansTurbo','path'),('TorontoWideRoadOpenData','city'),('TorontoWidePedestrianOpenData','city')]
    for layer,kind in layers:
        count=0
        with fiona.open(maria,layer=layer) as s:
            audit['crs'][layer]=s.crs.to_wkt();tr=Transformer.from_crs(s.crs,crs,always_xy=True);bb=Transformer.from_crs(crs,s.crs,always_xy=True).transform_bounds(*bounds)
            for f in s.filter(bbox=bb):
                p=dict(f['properties']);g=transform(tr.transform,shape(f['geometry'])).intersection(aoi)
                if g.is_empty:continue
                count+=1;fid=p.get('F_id') or f'{layer}/{f.id}'
                if kind!='city' and fid in seen:rejected.append({'id':fid,'layer':layer,'reason':'same OSM way id as preferred source'});continue
                if kind!='city':seen.add(fid)
                # Zero Z values in Maria's vectors are placeholders, not surveyed elevations.
                width=None;method='default';raw=p.get('width')
                if raw:
                    m=re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(m|metres|meters)?\s*',raw)
                    if m and .5<=float(m[1])<=40:width=float(m[1]);method='valid width tag'
                if width is None and kind=='road':
                    n=p.get('lanes')
                    if n and re.fullmatch(r'[1-8]',n):width=3.1*int(n)+.6;method='lanes × 3.1 m + 0.6 m total edge allowance'
                if width is None:
                    typ=p.get('highway','');width=({'motorway':14,'primary':10,'secondary':8,'tertiary':7,'residential':6,'unclassified':6,'service':4.5,'track':3.2}.get(typ,5.5) if kind=='road' else {'footway':2.8,'path':2.2,'pedestrian':5,'steps':2}.get(typ,2.8))
                bridge=p.get('bridge') not in [None,'no','false','0'];tunnel=p.get('tunnel') not in [None,'no','false','0']
                for j,line in enumerate(lines(g)):
                    if line.length<1:continue
                    v=np.asarray(line.coords)[:,:2]
                    rec={'id':str(fid),'part':j,'source':layer,'kind':kind,'name':p.get('name') or p.get('LINEAR_NAME_FULL') or '', 'highway':p.get('highway') or p.get('FEATURE_CODE_DESC') or p.get('ROAD_TYPE'),'width_m':round(width,2),'width_method':method,'lanes':p.get('lanes'),'width_tag':raw,'bridge':bridge,'bridge_tag':p.get('bridge'),'layer':p.get('layer'),'tunnel':tunnel,'tunnel_tag':p.get('tunnel'),'access':p.get('access'),'surface':p.get('surface'),'line':np.round(v-[ox,oy],3).tolist()}
                    (city if kind=='city' else routes).append(rec)
        route_layers[layer]=count
    # Document near-coincident different IDs; retain them, since parallel routes are real.
    rtree=STRtree([LineString(r['line']) for r in routes]);near=[]
    for i,r in enumerate(routes):
        g=LineString(r['line'])
        for j in rtree.query(g.buffer(.5)):
            if j<=i or r['kind']!=routes[j]['kind'] or r['bridge']!=routes[j]['bridge']:continue
            other=LineString(routes[j]['line'])
            ratio=g.intersection(other.buffer(.5)).length/g.length
            if ratio>.95 and abs(g.length-other.length)<2:near.append({'a':i,'b':int(j),'ids':[r['id'],routes[j]['id']]})
    # Only suppress geometrically coincident, same-level copies, never nearby parallels.
    suppress={p['b'] for p in near};routes=[r for i,r in enumerate(routes) if i not in suppress]
    manifest['routes']=routes;manifest['cityComparison']=city
    audit['routes']={'source_counts':route_layers,'rendered_parts':len(routes),'width_methods':dict(Counter(r['width_method'] for r in routes)),'duplicates_by_id':len(rejected),'coincident_copies':near,'policy':'Zoo OSM preferred, citywide OSM fills surrounding extent; only identical ids or coincident same-level geometry removed. City routes offered as comparison only.','bridge_parts':sum(r['bridge'] for r in routes),'tunnel_parts':sum(r['tunnel'] for r in routes),'imagery_width_measurements':0,'width_note':'No valid width tags in selected sources. Lane-derived road widths and documented class defaults used; image edges are checked for plausibility, not claimed as measurements.'}
    dump(ROOT/'reports/route-widths.json',routes);dump(ROOT/'reports/route-source-comparison.json',{'counts':route_layers,'id_duplicates':rejected,'city':city})
    # OSM context: saved independently so this task can be reproduced offline.
    context=[];places=[];boundary=None
    cp=ROOT/'generated/sources/osm-context.json'
    if cp.exists():
        tr=Transformer.from_crs(4326,crs,always_xy=True)
        for e in json.loads(cp.read_text())['elements']:
            t=e.get('tags',{})
            if e['type']=='way' and e.get('geometry'):
                c=[tr.transform(p['lon'],p['lat']) for p in e['geometry']]
                closed=len(c)>3 and c[0]==c[-1]
                if t.get('name')=='Toronto Zoo' and closed:
                    boundary=Polygon(c);dump(ROOT/'config/zoo-osm-boundary.geojson',{'type':'Feature','properties':{'source':f"https://www.openstreetmap.org/way/{e['id']}",'status':'OSM mapped Zoo extent; not cadastral','retrieved':'2026-11-07'},'geometry':mapping(transform(Transformer.from_crs(crs,4326,always_xy=True).transform,boundary))})
                typ='parking' if t.get('amenity')=='parking' else 'water' if t.get('natural')=='water' else 'wood' if t.get('natural')=='wood' or t.get('landuse')=='forest' else 'grass' if t.get('landuse') in ['grass','meadow'] else 'stream' if t.get('waterway') else None
                if typ:
                    g=(make_valid(Polygon(c)) if closed else LineString(c)).intersection(aoi)
                    if not g.is_empty:context.append({'id':str(e['id']),'kind':typ,'name':t.get('name',''),'geometry':mapping(local2(g)),'tunnel':t.get('tunnel')})
                if t.get('building') and t.get('name'):
                    c=Polygon(c).centroid if closed else LineString(c).centroid
                    if aoi.covers(c):places.append({'name':t['name'],'center':[c.x-ox,c.y-oy],'osm':f"way/{e['id']}"})
            elif e['type']=='relation' and t.get('building') and t.get('name'):
                b=e.get('bounds',{});
                if b:
                    x,y=tr.transform((b['minlon']+b['maxlon'])/2,(b['minlat']+b['maxlat'])/2);places.append({'name':t['name'],'center':[x-ox,y-oy],'osm':f"relation/{e['id']}"})
    manifest['context']=context;manifest['places']=places
    manifest['zooBoundary']=mapping(local2(boundary.intersection(aoi))) if boundary else None
    audit['boundary']={'study':'Approximate editable rectangle, includes access and parking','zoo_outline':'OSM way 229069541; volunteered mapped boundary, not official property boundary' if boundary else 'No usable Zoo polygon','fully_inside_study':aoi.covers(boundary) if boundary else None}
    # Planar comparisons to City generalized lines, sampled in metre coordinates.
    roadunion=unary_union([LineString(r['line']) for r in routes if r['kind']=='road'])
    distances=[]
    for r in city:
        if 'RoadOpenData' not in r['source']:continue
        g=LineString(r['line']);distances.extend(roadunion.distance(g.interpolate(t)) for t in np.linspace(0,g.length,max(2,int(g.length/20))))
    audit['routes']['city_road_to_osm_distance_m']={'median':float(np.median(distances)),'p90':float(np.percentile(distances,90))}
    # Ground clearance audit for all source-supported bridges. A deck is an
    # endpoint interpolation lifted only enough to clear the common terrain.
    crossings=[]
    for r in routes:
        g=LineString(r['line']);pts=np.array([g.interpolate(t).coords[0] for t in np.linspace(0,g.length,max(2,math.ceil(g.length/2)+1))]);z=surface(pts[:,0]+ox,pts[:,1]+oy)
        if r['bridge']:
            ramp=np.linspace(z[0],z[-1],len(z));lift=max(.5,float(np.max(z-ramp))+.35);r['deck_endpoint_m']=[float(z[0]+lift),float(z[-1]+lift)];r['deck_lift_m']=round(lift,2)
            crossings.append({'id':r['id'],'length_m':round(g.length,2),'bridge_tag':r['bridge_tag'],'terrain_endpoints_m':[float(z[0]),float(z[-1])],'estimated_deck_lift_m':round(lift,2),'note':'Deck profile estimated from terrain and bridge tag; no surveyed deck height.'})
        r['max_centerline_slope_percent']=round(float(np.max(np.abs(np.diff(z)))/(g.length/(len(z)-1))*100),1)
    audit['crossings']=crossings
    audit['routes']['steep_parts']=[{'id':r['id'],'grade_percent':r['max_centerline_slope_percent']} for r in routes if r['max_centerline_slope_percent']>25 and not r['bridge']]
    # Three reviewable plan/height checkpoints. Main entrance is the plaza west
    # of visitor parking, not every OSM entrance=main building door.
    tr=Transformer.from_crs(4326,crs,always_xy=True)
    checkpoints=[(c['name'],*c['lonlat']) for c in cfg.get('checkpoints',[])]
    checks=[]
    for name,lon,lat in checkpoints:
        x,y=tr.transform(lon,lat);pt=Point(x,y)
        if not aoi.covers(pt):continue
        nearest=min(foot,key=lambda f:f['g'].distance(pt));rr=min(routes,key=lambda r:LineString(r['line']).distance(Point(x-ox,y-oy)))
        checks.append({'name':name,'lonlat':[lon,lat],'projected_m':[x,y],'local':[x-ox,y-oy],'terrain_m':round(float(ground(x,y)),3),'rendered_surface_m':round(float(surface(x,y)),3),'nearest_footprint_id':nearest['id'],'city_surface_m':nearest['p'].get('SURF_ELEV'),'surface_delta_m':round(nearest['delta'],3) if nearest['delta'] is not None else None,'nearest_route':rr['id'],'visual_status':'Inspect alignment sheet; human visual conclusions in reports/alignment-review.json. Not surveyed control.'})
    manifest['checkpoints']=checks;audit['checkpoints']=checks
    # Contact sheets over the open City image. Blue=MP, green=footprints,
    # amber=OSM and magenta=City generalized geometry.
    if manifest['imagery']:
        img=Image.open(cache).convert('RGB');sheet=Image.new('RGB',(1500,600),'#132a25');sd=ImageDraw.Draw(sheet)
        for k,c in enumerate(checks):
            x,y=c['projected_m'];radius=150;panel=img.crop((x-xmin-radius,ymax-y-radius,x-xmin+radius,ymax-y+radius)).resize((500,500))
            d=ImageDraw.Draw(panel)
            def screen(v):return [(float((a-x+radius)*500/(2*radius)),float((y+radius-b)*500/(2*radius))) for a,b,*_ in v]
            region=box(x-radius,y-radius,x+radius,y+radius)
            for f in foot:
                if f['g'].intersects(region):d.line(screen(f['g'].exterior.coords),fill='#65ff94',width=2)
            for g in mp_coverage:
                if g.intersects(region):
                    for p in polygons(g):d.line(screen(p.exterior.coords),fill='#42dfff',width=1)
            for r in routes+city:
                g=LineString(np.array(r['line'])+[ox,oy]).intersection(region)
                for l in lines(g):d.line(screen(l.coords),fill='#ff6fdf' if r['kind']=='city' else '#ffd16c',width=2)
            d.ellipse((245,245,255,255),outline='white',width=2)
            sheet.paste(panel,(k*500,60));sd.text((k*500+15,12),c['name'],fill='white');sd.text((k*500+15,34),f"DTM {c['terrain_m']:.2f} m / CGVD2013",fill='#b4d4c4')
        sd.text((15,575),'300 m square per panel | Green footprints / cyan Multipatch / amber OSM / magenta City | North up',fill='white')
        sheet.save(ROOT/'reports/alignment-checkpoints.png')
    audit['styling']='Building colours and terrain palette are styling. No source materials, textures or facade colours present in inspected City fields. No invented windows.'
    audit['warnings']+=['Imagery capture year not confirmed by the current service metadata.','City building vertical datum unspecified; local terrain grounding is a visualization placement, not a datum transformation.','Tunnel interiors omitted; bridge deck heights estimated, with source bridge tags preserved.','Five metre display terrain smooths narrow cuts and steep banks; full 0.5 m source retained.']
    dump(ROOT/'reports/data-audit.json',audit)
    manifest['summary']={'multipatches':len(mp),'extrusions':len(extrusions),'routes':len(routes),'terrain_tiles':len(active),'terrain_coverage_percent':round(cov*100,3),'estimated_heights':sum(b['height_estimated'] for b in extrusions),'study_area_km2':aoi.area/1e6}
    manifest['warnings']=audit['warnings'];dump(out/'scene.json',manifest)
    assets=[{'file':str(p.relative_to(ROOT/'public')),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(out.iterdir()) if p.is_file()]
    dump(ROOT/'reports/asset-manifest.json',{'files':assets,'total_bytes':sum(f['bytes'] for f in assets)})
    # Recheck original input metadata after preparation.
    changed=[p for p,v in inventory.items() if (ROOT/p).stat().st_size!=v['bytes'] or (ROOT/p).stat().st_mtime_ns!=v['mtime_ns']]
    if changed:raise RuntimeError(f'Input changed during preparation: {changed}')
    print(json.dumps({'summary':manifest['summary'],'terrain_missing_cells':missing,'asset_bytes':sum(f['bytes'] for f in assets),'inputs_unchanged':True},indent=2),flush=True)

if __name__=='__main__':main()
