"""Compare the saved broader OSM vegetation query with the unchanged pilot.

Writes diagnostic reports/maps only; no changes to source inputs or public/.
"""
from pathlib import Path
from collections import Counter
import json
from shapely.geometry import shape,Point,LineString,Polygon,box
from shapely.ops import unary_union,polygonize
from shapely import make_valid
from pyproj import Transformer
from PIL import Image,ImageDraw

root=Path(__file__).resolve().parents[1]
scene=json.loads((root/'public/assets/scene.json').read_text())
old=json.loads((root/'generated/sources/osm-context.json').read_text())
new=json.loads((root/'generated/sources/osm-vegetation-audit.json').read_text())
cfg=scene['study'];ox,oy,_=cfg['origin'];xmin,ymin,xmax,ymax=cfg['bounds']
aoi=box(xmin-ox,ymin-oy,xmax-ox,ymax-oy)
tr=Transformer.from_crs(4326,cfg['crs'],always_xy=True)
def coords(raw):
    return [(x-ox,y-oy) for x,y in [tr.transform(p['lon'],p['lat']) for p in raw]]
def geometry(e):
    if e['type']=='node':
        x,y=tr.transform(e['lon'],e['lat']);return Point(x-ox,y-oy)
    if e['type']=='way':
        c=coords(e.get('geometry',[]))
        if len(c)<2:return Polygon()
        return make_valid(Polygon(c)) if len(c)>3 and c[0]==c[-1] else LineString(c)
    outer=[];inner=[]
    for m in e.get('members',[]):
        if m['type']!='way' or not m.get('geometry'):continue
        c=coords(m['geometry'])
        if len(c)>1:(inner if m.get('role')=='inner' else outer).append(LineString(c))
    outside=unary_union(list(polygonize(unary_union(outer))))
    holes=unary_union(list(polygonize(unary_union(inner))))
    return make_valid(outside.difference(holes))
current=unary_union([shape(f['geometry']) for f in scene['context'] if f['kind']=='wood'])
relations=[];area_geoms=[];points=[];rows=[];other=[]
counts=Counter();oldids={(e['type'],e['id']) for e in old['elements']}
for e in new['elements']:
    t=e.get('tags',{});tag=t.get('natural') or ('forest' if t.get('landuse')=='forest' else 'landcover=trees')
    counts[(e['type'],tag)]+=1
    g=geometry(e).intersection(aoi)
    if g.is_empty:continue
    if tag in ['wood','forest','landcover=trees'] and g.area:
        area_geoms.append(g)
        if e['type']=='relation':relations.append({'osm_id':e['id'],'tags':t,'last_edit':e.get('timestamp'),'area_in_study_km2':g.area/1e6,'new_area_beyond_current_km2':g.difference(current).area/1e6})
    elif tag=='tree' and e['type']=='node':points.append({'osm_id':e['id'],'geometry':g,'inside_current_woodland':current.covers(g),'tags':t})
    elif tag=='tree_row':rows.append({'osm_id':e['id'],'geometry':g,'length_in_study_m':g.length,'tags':t})
    else:other.append({'osm_id':e['id'],'tag':tag,'geometry_type':g.geom_type})
expanded=unary_union(area_geoms);additional=expanded.difference(current)
routes=unary_union([LineString(r['line']).buffer(r['width_m']/2+5) for r in scene['routes']])
building_avoidance=unary_union([Point(*b['center']).buffer(max(12,b['count']**.5/3)) for b in scene['buildings']['features']])
excluded=current.intersection(unary_union([routes,building_avoidance]))
oldways={e['id']:e for e in old['elements'] if e['type']=='way' and (e.get('tags',{}).get('natural')=='wood' or e.get('tags',{}).get('landuse')=='forest')}
newways={e['id']:e for e in new['elements'] if e['type']=='way' and (e.get('tags',{}).get('natural')=='wood' or e.get('tags',{}).get('landuse')=='forest')}
unchanged=sum(i in newways and oldways[i].get('geometry')==newways[i].get('geometry') for i in oldways)
report={
    'purpose':'Read-only extraction/placement audit. App assets and original source snapshot remain unchanged.',
    'original_osm_timestamp':old.get('osm3s',{}).get('timestamp_osm_base'),
    'comparison_osm_timestamp':new.get('osm3s',{}).get('timestamp_osm_base'),
    'query_feature_counts':[{'element_type':k[0],'tag':k[1],'count':v} for k,v in sorted(counts.items())],
    'old_simple_woodland_ways':len(oldways),'simple_way_geometry_unchanged':unchanged,
    'current_woodland_features':sum(f['kind']=='wood' for f in scene['context']),
    'current_woodland_area_km2':current.area/1e6,
    'omitted_woodland_relations':relations,
    'expanded_woodland_area_km2':expanded.area/1e6,
    'additional_mapped_woodland_area_km2':additional.area/1e6,
    'individual_tree_points_in_study':len(points),
    'individual_tree_points_outside_current_woodland':sum(not p['inside_current_woodland'] for p in points),
    'tree_rows_in_study':[{'osm_id':r['osm_id'],'length_m':r['length_in_study_m']} for r in rows],
    'current_route_building_exclusion_area_km2':excluded.area/1e6,
    'current_route_building_exclusion_fraction':excluded.area/current.area,
    'density_policy':'One candidate per approximately 18.5 x 18.5 m before jitter/exclusions; not measured tree density.',
    'additional_notes':['Only closed way polygons were handled for woodland in the original extractor.','Original query omitted woodland relations and individual trees/tree rows/tree groups/landcover=trees.','5 m raster mask and grass painting order can remove small/narrow or overlapping areas.','Buffer exclusion calculation is vector based, before rasterization, grass override and sparse placement.'],
    'other_features':other,
}
(root/'reports/vegetation-audit.json').write_text(json.dumps(report,indent=2))
image=Image.open(root/'generated/sources/zoo-ortho.jpg').convert('RGBA');overlay=Image.new('RGBA',image.size);draw=ImageDraw.Draw(overlay)
sx=image.width/(xmax-xmin);sy=image.height/(ymax-ymin)
def pixel(p):return ((p[0]+ox-xmin)*sx,(ymax-p[1]-oy)*sy)
def drawgeom(g,fill,outline):
    ps=[g] if g.geom_type=='Polygon' else list(getattr(g,'geoms',[]))
    for p in ps:
        if p.geom_type!='Polygon':continue
        draw.polygon([pixel(c) for c in p.exterior.coords],fill=fill)
        draw.line([pixel(c) for c in p.exterior.coords],fill=outline,width=3)
        for ring in p.interiors:draw.polygon([pixel(c) for c in ring.coords],fill=(0,0,0,0))
drawgeom(current,(90,255,70,45),(95,255,75,240))
drawgeom(additional,(255,60,210,65),(255,80,225,255))
drawgeom(excluded,(255,165,30,120),(255,185,35,230))
for p in points:
    x,y=pixel(p['geometry'].coords[0]);draw.ellipse((x-6,y-6,x+6,y+6),fill=(0,230,255,255),outline='white',width=1)
for r in rows:
    if r['geometry'].geom_type=='LineString':draw.line([pixel(c) for c in r['geometry'].coords],fill=(0,230,255,255),width=5)
image=Image.alpha_composite(image,overlay).convert('RGB');image.thumbnail((1500,1250));canvas=Image.new('RGB',(1500,1330),'#18392d');canvas.paste(image,(0,80));d=ImageDraw.Draw(canvas)
d.text((20,12),'Green = current woodland. Magenta = mapped woodland omitted by the way-only query. Orange = current exclusion buffers.',fill='white')
d.text((20,37),'Cyan = mapped individual trees / tree rows omitted by the original query. This is an audit overlay, not a changed render.',fill='white')
d.text((20,59),f"Current woodland {current.area/1e6:.3f} km2; additional mapped woodland {additional.area/1e6:.3f} km2. North up.",fill='white')
canvas.save(root/'reports/vegetation-query-audit.png')
print(json.dumps(report,indent=2))
