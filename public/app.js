import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';

const $ = (s) => document.querySelector(s);
const canvas = $('#scene');
const loadMessage = $('#load-message');
const state = { ready: false, imagery: false, layers: {}, selection: null };
let renderer, scene, camera, controls, data, heights, terrain, texture, selectedOutline;
let flight = null, redraw = true, lastFrame = 0;
const groups = {}, pickable = [], labelEntries = [], routeRanges = {};
const clock = new THREE.Clock();
const pointer = new THREE.Vector2(), raycaster = new THREE.Raycaster();
const vector = new THREE.Vector3();
let baseColors, orthoPromise;

async function request(url, binary = false) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return binary ? new Float32Array(await r.arrayBuffer()) : r.json();
}
function group(name) {
  const g = new THREE.Group(); g.name = name; scene.add(g); groups[name] = g; state.layers[name] = true; return g;
}
function ground(x, n) {
  const { width: w, height: h, step } = data.terrain, [ox, oy, oz] = data.study.origin;
  const [xmin, , , ymax] = data.study.bounds;
  const u = THREE.MathUtils.clamp((x + ox - xmin) / step, 0, w - 1.000001);
  const v = THREE.MathUtils.clamp((ymax - n - oy) / step, 0, h - 1.000001);
  const i = Math.floor(u), j = Math.floor(v), a = u - i, b = v - j;
  const nw = heights[j*w+i], ne = heights[j*w+i+1], sw = heights[(j+1)*w+i], se = heights[(j+1)*w+i+1];
  return (a+b<=1 ? nw+a*(ne-nw)+b*(sw-nw) : se+(1-a)*(sw-se)+(1-b)*(ne-se)) - oz;
}
function coordinates(g) {
  if (g.type === 'Polygon') return [g.coordinates];
  if (g.type === 'MultiPolygon') return g.coordinates;
  if (g.type === 'GeometryCollection') return g.geometries.flatMap(coordinates);
  return [];
}
function lineCoordinates(g) {
  if (g.type === 'LineString') return [g.coordinates];
  if (g.type === 'MultiLineString') return g.coordinates;
  if (g.type === 'GeometryCollection') return g.geometries.flatMap(lineCoordinates);
  return [];
}
function bufferGeometry(vertices) {
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3)); g.computeVertexNormals(); return g;
}
function mesh(vertices, color, parent, options = {}) {
  const g = bufferGeometry(vertices);
  const m = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ color, roughness: 1, side: THREE.DoubleSide, ...options }));
  parent.add(m); return m;
}
function polygonMesh(rings, output, lift = .15) {
  const contour = rings[0].map(p => new THREE.Vector2(...p));
  const holes = rings.slice(1).map(r => r.map(p => new THREE.Vector2(...p)));
  function triangle(a,b,c,depth=0) {
    const d = Math.max(a.distanceToSquared(b), b.distanceToSquared(c), c.distanceToSquared(a));
    if (d > 144 && depth < 10) {
      const ab=a.clone().add(b).multiplyScalar(.5), bc=b.clone().add(c).multiplyScalar(.5), ca=c.clone().add(a).multiplyScalar(.5);
      triangle(a,ab,ca,depth+1); triangle(ab,b,bc,depth+1); triangle(ca,bc,c,depth+1); triangle(ab,bc,ca,depth+1); return;
    }
    // Match the terrain between polygon vertices as well as at their corners.
    // This keeps water and parking fills from flickering through sloping ground.
    surfaceTriangle(...[a,b,c].map(p=>[p.x,ground(p.x,p.y)+lift,-p.y]),output,lift);
  }
  const faces=THREE.ShapeUtils.triangulateShape(contour,holes);
  const points = [...contour, ...holes.flat()];
  faces.forEach(face => triangle(...face.map(i=>points[i])));
}
function makeMask() {
  const c=document.createElement('canvas'); c.width=data.terrain.width; c.height=data.terrain.height;
  const ctx=c.getContext('2d', {willReadFrequently:true});
  const [xmin,, ,ymax]=data.study.bounds, [ox,oy]=data.study.origin;
  const project = ([x,n]) => [(x+ox-xmin)/data.terrain.step,(ymax-n-oy)/data.terrain.step];
  for (const f of data.context) {
    if (!['wood','grass'].includes(f.kind)) continue;
    ctx.fillStyle=f.kind==='wood'?'#00ff00':'#ffff00';
    for (const rings of coordinates(f.geometry)) {
      ctx.beginPath();
      for (const r of rings) r.forEach((p,i)=>{const q=project(p);i?ctx.lineTo(...q):ctx.moveTo(...q);});
      ctx.fill('evenodd');
    }
  }
  return ctx.getImageData(0,0,c.width,c.height).data;
}
function makeTerrain() {
  const {width:w,height:h,step}=data.terrain, [ox,oy,oz]=data.study.origin, [xmin,, ,ymax]=data.study.bounds;
  const pos=new Float32Array(w*h*3), uv=new Float32Array(w*h*2), colors=new Float32Array(w*h*3), indices=new Uint32Array((w-1)*(h-1)*6);
  const mask=makeMask();
  const low=new THREE.Color('#a2b487'), high=new THREE.Color('#c8cea3'), woods=new THREE.Color('#819a72'), grass=new THREE.Color('#bbca8e');
  let ix=0;
  for(let j=0;j<h;j++) for(let i=0;i<w;i++) {
    const k=j*w+i, elevation=heights[k];
    pos.set([xmin+i*step-ox,elevation-oz,-(ymax-j*step-oy)],k*3);
    uv.set([i/(w-1),1-j/(h-1)],k*2);
    const color=low.clone().lerp(high,THREE.MathUtils.clamp((elevation-100)/65,0,1));
    if(mask[k*4+1]>100) color.lerp(mask[k*4]>100?grass:woods,.75);
    const shade=1+Math.sin(i*.11)*Math.cos(j*.083)*.018;
    color.multiplyScalar(shade);colors.set([color.r,color.g,color.b],k*3);
    if(i<w-1&&j<h-1) {indices.set([k,k+w,k+1,k+1,k+w,k+w+1],ix);ix+=6;}
  }
  baseColors=colors;
  const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.BufferAttribute(pos,3));geo.setAttribute('uv',new THREE.BufferAttribute(uv,2));geo.setAttribute('color',new THREE.BufferAttribute(colors,3));geo.setIndex(new THREE.BufferAttribute(indices,1));geo.computeVertexNormals();
  terrain=new THREE.Mesh(geo,new THREE.MeshStandardMaterial({vertexColors:true,roughness:1,side:THREE.DoubleSide}));group('terrain').add(terrain);
  // The cut edge makes the study extent explicit, with real terrain along its rim.
  const rim=[];for(let i=0;i<w;i++)rim.push(i);for(let j=1;j<h;j++)rim.push(j*w+w-1);for(let i=w-2;i>=0;i--)rim.push((h-1)*w+i);for(let j=h-2;j>0;j--)rim.push(j*w);
  const sides=[];
  rim.forEach((k,i)=>{const l=rim[(i+1)%rim.length],a=[pos[k*3],pos[k*3+1],pos[k*3+2]],b=[pos[l*3],pos[l*3+1],pos[l*3+2]],aa=[a[0],-30,a[2]],bb=[b[0],-30,b[2]];sides.push(...a,...b,...aa,...aa,...b,...bb);});
  mesh(sides,'#7d8e6f',groups.terrain);
  const base=new THREE.Mesh(new THREE.PlaneGeometry(14000,14000),new THREE.MeshBasicMaterial({color:'#dce5d9'}));base.rotation.x=-Math.PI/2;base.position.y=-32;scene.add(base);
  return mask;
}
function surfaceTriangle(a,b,c,output,lift,depth=0) {
  const mid=(p,q)=>{const x=(p[0]+q[0])/2,z=(p[2]+q[2])/2;return[x,ground(x,-z)+lift,z]};
  const ab=mid(a,b),bc=mid(b,c),ca=mid(c,a);
  const cx=(a[0]+b[0]+c[0])/3,cz=(a[2]+b[2]+c[2])/3;
  const error=Math.max(Math.abs((a[1]+b[1]+c[1])/3-ground(cx,-cz)-lift),Math.abs((a[1]+b[1])/2-ab[1]),Math.abs((b[1]+c[1])/2-bc[1]),Math.abs((c[1]+a[1])/2-ca[1]));
  if(error>.08&&depth<4){surfaceTriangle(a,ab,ca,output,lift,depth+1);surfaceTriangle(ab,b,bc,output,lift,depth+1);surfaceTriangle(ca,bc,c,output,lift,depth+1);surfaceTriangle(ab,bc,ca,output,lift,depth+1);}
  else output.push(...a,...b,...c);
}
function ribbon(line,width,output,lift=.22,deck=null) {
  let total=0;const lengths=[0];for(let i=1;i<line.length;i++){total+=Math.hypot(line[i][0]-line[i-1][0],line[i][1]-line[i-1][1]);lengths.push(total);}
  if(!total)return;
  for(let s=0;s<line.length-1;s++) {
    const a=line[s],b=line[s+1],dx=b[0]-a[0],dn=b[1]-a[1],len=Math.hypot(dx,dn);if(len<.001)continue;
    const along=Math.max(1,Math.ceil(len/2.5)),across=Math.max(1,Math.ceil(width/2.5));
    const vertex=(t,u)=>{const x=a[0]+dx*t-dn/len*width*(u-.5),n=a[1]+dn*t+dx/len*width*(u-.5);const z=deck?THREE.MathUtils.lerp(deck[0],deck[1],(lengths[s]+len*t)/total)-data.study.origin[2]:ground(x,n);return [x,z+lift,-n];};
    for(let i=0;i<along;i++)for(let j=0;j<across;j++){
      const p=vertex(i/along,j/across),q=vertex((i+1)/along,j/across),r=vertex(i/along,(j+1)/across),ss=vertex((i+1)/along,(j+1)/across);
      if(deck)output.push(...p,...q,...r,...r,...q,...ss);
      else{surfaceTriangle(p,q,r,output,lift);surfaceTriangle(r,q,ss,output,lift);}
    }
  }
}
function makeRoutes() {
  const road=group('roads'),path=group('paths'),comparison=group('comparison');comparison.visible=false;state.layers.comparison=false;
  const rpos=[],ppos=[],roadRails=[],pathRails=[],markings=[],comp=[];routeRanges.roads=[];routeRanges.paths=[];
  for(const r of data.routes) {
    if(r.tunnel) continue;
    const out=r.kind==='road'?rpos:ppos,name=r.kind==='road'?'roads':'paths',start=out.length/3;
    ribbon(r.line,r.width_m,out,r.kind==='road'?.26:.32,r.deck_endpoint_m);
    routeRanges[name].push({first:start,count:out.length/3-start,route:r});
    if(r.bridge) {
      // Source-supported raised crossings have separate solid decks and rails.
      for(let side of [-1,1])for(let i=1;i<r.line.length;i++) {
        const a=r.line[i-1],b=r.line[i],dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy);if(!len)continue;
        const x=(a[0]+b[0])/2,n=(a[1]+b[1])/2;
        const h=(r.deck_endpoint_m[0]+r.deck_endpoint_m[1])/2-data.study.origin[2];
        (r.kind==='road'?roadRails:pathRails).push(x-dy/len*r.width_m*.48*side,h+1.15,-(n+dx/len*r.width_m*.48*side),b[0]-dy/len*r.width_m*.48*side,h+1.15,-(b[1]+dx/len*r.width_m*.48*side));
      }
    }
    if(r.kind==='road' && Number(r.lanes)>=2 && r.width_m>6 && !r.bridge) {
      let accumulated=0;
      for(let i=1;i<r.line.length;i++){
        const a=r.line[i-1],b=r.line[i],d=Math.hypot(b[0]-a[0],b[1]-a[1]);
        for(let t=0;t<d;t+=8){const s=t/d,e=Math.min(t+3,d)/d;const x=a[0]+(b[0]-a[0])*s,n=a[1]+(b[1]-a[1])*s,xx=a[0]+(b[0]-a[0])*e,nn=a[1]+(b[1]-a[1])*e;markings.push(x,ground(x,n)+.33,-n,xx,ground(xx,nn)+.33,-nn);}accumulated+=d;
      }
    }
  }
  // Slightly cool grays keep asphalt and paved paths legible under the warm landscape lighting.
  const roads=mesh(rpos,'#41454b',road),paths=mesh(ppos,'#7d858c',path);roads.userData.kind='roads';paths.userData.kind='paths';pickable.push(roads,paths);
  for(const [vertices,parent]of [[roadRails,road],[pathRails,path]])if(vertices.length)parent.add(new THREE.LineSegments(bufferGeometry(vertices),new THREE.LineBasicMaterial({color:'#92989e'})));
  road.add(new THREE.LineSegments(bufferGeometry(markings),new THREE.LineBasicMaterial({color:'#e0e1e3',transparent:true,opacity:.7})));
  for(const r of data.cityComparison) ribbon(r.line,1.1,comp,.55);
  mesh(comp,'#d95dab',comparison,{transparent:true,opacity:.8});
}
function makeBuildings(pos,colors) {
  const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(pos,3));g.setAttribute('color',new THREE.BufferAttribute(colors,3));g.computeVertexNormals();
  const buildings=new THREE.Mesh(g,new THREE.MeshStandardMaterial({vertexColors:true,side:THREE.DoubleSide,roughness:.92}));buildings.userData.kind='buildings';group('buildings').add(buildings);pickable.push(buildings);
  const edges=new THREE.LineSegments(new THREE.EdgesGeometry(g,36),new THREE.LineBasicMaterial({color:'#4a6055',transparent:true,opacity:.20}));groups.buildings.add(edges);
}
function makeContext() {
  const waterLayer=group('water'),parkingLayer=group('parking'),water=[],parking=[];
  for(const f of data.context) {
    if(f.kind==='water'||f.kind==='parking')for(const rings of coordinates(f.geometry))polygonMesh(rings,f.kind==='water'?water:parking,f.kind==='water'?.13:.11);
    if(f.kind==='stream'&&!f.tunnel)for(const line of lineCoordinates(f.geometry))ribbon(line,f.name==='Rouge River'?7:2.2,water,.17);
  }
  mesh(water,'#3e7fa3',waterLayer,{roughness:.45,metalness:.08});
  mesh(parking,'#9b8874',parkingLayer);
  const boundary=group('boundary'),verts=[];
  if(data.zooBoundary)for(const rings of coordinates(data.zooBoundary))for(const ring of rings)for(let i=1;i<ring.length;i++){
    const a=ring[i-1],b=ring[i],d=Math.hypot(b[0]-a[0],b[1]-a[1]);
    for(let t=0;t<d;t+=6){const s=t/d,e=Math.min(t+3,d)/d;for(const u of [s,e]){const x=a[0]+(b[0]-a[0])*u,n=a[1]+(b[1]-a[1])*u;verts.push(x,ground(x,n)+.6,-n);}}
  }
  boundary.add(new THREE.LineSegments(bufferGeometry(verts),new THREE.LineBasicMaterial({color:'#b28c4d',transparent:true,opacity:.85})));
}
function makeWoodland(mask) {
  const g=group('woodland'),{width:w,height:h,step}=data.terrain,[ox,oy]=data.study.origin,[xmin,,,ymax]=data.study.bounds;
  // Spatial masks let decorative trees avoid routes and buildings without a
  // per-frame spatial query. Positions are not an individual tree inventory.
  const avoid=document.createElement('canvas');avoid.width=w;avoid.height=h;const ctx=avoid.getContext('2d',{willReadFrequently:true});ctx.strokeStyle='white';ctx.fillStyle='white';
  for(const r of data.routes){ctx.lineWidth=(r.width_m+10)/step;ctx.beginPath();r.line.forEach(([x,n],i)=>{const a=(x+ox-xmin)/step,b=(ymax-n-oy)/step;i?ctx.lineTo(a,b):ctx.moveTo(a,b)});ctx.stroke();}
  for(const b of data.buildings.features){ctx.beginPath();ctx.arc((b.center[0]+ox-xmin)/step,(ymax-b.center[1]-oy)/step,Math.max(12,Math.sqrt(b.count)/3)/step,0,Math.PI*2);ctx.fill();}
  const amask=ctx.getImageData(0,0,w,h).data,trees=[];let seed=487;
  const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)|0;return(seed>>>0)/4294967296;};
  for(let j=2;j<h-2;j+=3.7)for(let i=2;i<w-2;i+=3.7){const u=Math.round(i+(random()-.5)*2.8),v=Math.round(j+(random()-.5)*2.8),k=v*w+u;if(mask[k*4+1]<100||mask[k*4]>100||amask[k*4]>0)continue;const x=xmin+u*step-ox,n=ymax-v*step-oy;trees.push([x,ground(x,n),-n,5+random()*5,3+random()*2.7,random()]);}
  const crown=new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1,0),new THREE.MeshStandardMaterial({color:'#668358',roughness:1,flatShading:true}),trees.length);
  const trunk=new THREE.InstancedMesh(new THREE.CylinderGeometry(.5,.65,1,4),new THREE.MeshStandardMaterial({color:'#7b8061',roughness:1}),trees.length);
  const dummy=new THREE.Object3D(),color=new THREE.Color();
  trees.forEach(([x,y,z,height,r,t],i)=>{dummy.position.set(x,y+height*.65,z);dummy.scale.set(r,height*.6,r);dummy.rotation.y=t*Math.PI;dummy.updateMatrix();crown.setMatrixAt(i,dummy.matrix);color.setHSL(.25+t*.035,.16,.34+t*.09);crown.setColorAt(i,color);dummy.position.y=y+height*.25;dummy.scale.set(.8,height*.5,.8);dummy.updateMatrix();trunk.setMatrixAt(i,dummy.matrix);});
  g.add(trunk,crown);state.treeCount=trees.length;
}
function addLabel(name,x,n,secondary=false) {
  const el=document.createElement('button');el.className='map-label'+(secondary?' secondary':'');el.textContent=name;el.setAttribute('aria-label',`Fly to ${name}`);$('#labels').appendChild(el);
  const entry={el,x,n,secondary,width:el.offsetWidth,height:el.offsetHeight};labelEntries.push(entry);
  el.addEventListener('click',()=>{flyTo([x,ground(x,n),-n],[300,300,370]);showDetails(name,'Place name and location from OpenStreetMap. This is an exploratory visualization.',[['Coordinates','OSM mapped'],['Ground',`${(ground(x,n)+data.study.origin[2]).toFixed(1)} m`]]);});
}
function makeLabels() {
  const c=data.checkpoints[0];addLabel('Main entrance',...c.local);
  const names=['African Rainforest Pavillion','Indo-Malaya Pavillion','Australasia Pavilion','Americas Pavilion'];
  for(const name of names){const p=data.places.find(p=>p.name===name);if(p)addLabel(name.replace('Pavillion','Pavilion'),...p.center);}
  addLabel('Visitor parking',595,280,true);addLabel('Rouge Valley',-420,-380,true);addLabel('Meadowvale Road',870,-570,true);
}
function showDetails(title,description,facts) {
  $('#feature-title').textContent=title;$('#feature-description').textContent=description;
  const dl=$('#feature-facts');dl.replaceChildren();for(const [a,b]of facts){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=a;dd.textContent=b;dl.append(dt,dd);}$('#feature').hidden=false;
}
function inspect(event) {
  pointer.set(event.clientX/innerWidth*2-1,-event.clientY/innerHeight*2+1);raycaster.setFromCamera(pointer,camera);
  const hits=raycaster.intersectObjects(pickable.filter(m=>m.visible&&m.parent.visible));if(!hits.length)return;
  const hit=hits[0],kind=hit.object.userData.kind,vertex=hit.faceIndex*3;
  state.selection=null;
  if(kind==='buildings') {
    const b=data.buildings.features.find(b=>vertex>=b.first&&vertex<b.first+b.count);if(!b)return;
    const nearest=data.places.map(p=>({...p,d:Math.hypot(p.center[0]-b.center[0],p.center[1]-b.center[1])})).sort((a,b)=>a.d-b.d)[0];
    const name=nearest&&nearest.d<35?nearest.name.replace('Pavillion','Pavilion'):'Building massing';
    showDetails(name,`${b.source}. Colours are visualization styling.`,[['Source height',`${b.height_m.toFixed(1)} m${b.height_estimated?' · estimated':''}`],['Ground anchor',`${b.base_m.toFixed(1)} m`],['Geometry',b.source.includes('Multipatch')?'Source 3D faces':'Footprint extrusion'],['Height source',b.height_source||'Source 3D geometry'],['Slope clearance lift',`${(b.slope_clearance_lift_m||b.roof_lift_for_slope_m||0).toFixed(2)} m · placement`],['Identifier',b.id]]);
    if(selectedOutline){scene.remove(selectedOutline);selectedOutline.geometry.dispose();}
    const source=hit.object.geometry.attributes.position.array.subarray(b.first*3,(b.first+b.count)*3),g=bufferGeometry(source);
    selectedOutline=new THREE.LineSegments(new THREE.EdgesGeometry(g,25),new THREE.LineBasicMaterial({color:'#ddaf56',depthTest:false,transparent:true,opacity:.85}));scene.add(selectedOutline);g.dispose();state.selection=b.id;
  } else {
    const r=routeRanges[kind]?.find(r=>vertex>=r.first&&vertex<r.first+r.count)?.route;if(!r)return;
    showDetails(r.name|| (r.kind==='road'?'Road / service route':'Walking path'),`OpenStreetMap via Maria’s ${r.source.includes('Zoo')?'dedicated Zoo':'Toronto-wide'} package.`,[['Width',`${r.width_m} m · estimated`],['Width method',r.width_method],['Surface',r.surface||'Unspecified'],['Crossing',r.bridge?'Raised deck · estimated':r.tunnel?'Tunnel':'Follows terrain'],['Access',r.access||'Unspecified'],['OSM identifier',r.id]]);state.selection=r.id;
  }
  redraw=true;
}
function flyTo(target,offset,duration=1000) {
  // Flush remaining drag inertia before an explicit camera destination.
  // Otherwise a reset can drift away from its saved view after the flight.
  controls.enableDamping=false;controls.update();controls.enableDamping=true;
  flight={start:performance.now(),duration,from:camera.position.clone(),fromTarget:controls.target.clone(),target:new THREE.Vector3(...target),to:new THREE.Vector3(...target).add(new THREE.Vector3(...offset))};redraw=true;
}
function setView(name,instant=false) {
  const entrance=data.checkpoints[0].local,pavilion=data.checkpoints[2].local;
  const views={overview:[[100,35,-30],[2200,2200,2700]],entrance:[[entrance[0]+60,ground(...entrance),-entrance[1]],[330,290,390]],pavilion:[[pavilion[0]+40,ground(...pavilion),-pavilion[1]],[280,240,310]],top:[[0,30,0],[0,4000,1]]};
  const [target,offset]=views[name];flyTo(target,offset,instant?0:1100);
  document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===name));
}
async function setImagery(enabled) {
  if(!data.imagery)return;
  if(enabled&&!texture){
    orthoPromise ??= new THREE.TextureLoader().loadAsync(data.imagery.url);
    texture=await orthoPromise;texture.colorSpace=THREE.SRGBColorSpace;texture.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());
  }
  terrain.material.map=enabled?texture:null;terrain.material.vertexColors=!enabled;terrain.material.color.set(enabled?0xffffff:0xffffff);terrain.material.needsUpdate=true;state.imagery=enabled;
  $('#neutral').classList.toggle('active',!enabled);$('#neutral').setAttribute('aria-pressed',String(!enabled));$('#imagery').classList.toggle('active',enabled);$('#imagery').setAttribute('aria-pressed',String(enabled));
  $('#image-note').textContent=enabled?'City aerial · capture year unverified':'A quiet palette. Real ground elevations.';
  // Forest decoration has a separate toggle; leave its state under user control.
  redraw=true;
}
function setLayer(name,visible) {
  if(name==='labels')$('#labels').hidden=!visible;
  else if(groups[name])groups[name].visible=visible;
  state.layers[name]=visible;document.querySelectorAll(`[data-layer="${name}"]`).forEach(c=>c.checked=visible);redraw=true;
}
function zoom(multiplier) {
  const diff=camera.position.clone().sub(controls.target).multiplyScalar(multiplier);flyTo(controls.target.toArray(),diff.toArray(),250);
}
function bindControls() {
  document.querySelectorAll('[data-layer]').forEach(c=>c.addEventListener('change',()=>setLayer(c.dataset.layer,c.checked)));
  document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>setView(b.dataset.view)));
  $('#neutral').onclick=()=>setImagery(false);$('#imagery').onclick=()=>setImagery(true).catch(fail);
  $('#zoom-in').onclick=()=>zoom(.75);$('#zoom-out').onclick=()=>zoom(1.33);$('#reset').onclick=()=>setView('overview');
  $('#close-feature').onclick=()=>{$('#feature').hidden=true;if(selectedOutline)selectedOutline.visible=false;redraw=true;};
  $('#open-notes').onclick=()=>$('#notes').showModal();$('#close-notes').onclick=()=>$('#notes').close();$('#help').onclick=()=>$('#controls-help').showModal();$('#close-help').onclick=()=>$('#controls-help').close();
  for(const d of document.querySelectorAll('dialog'))d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close();}});
  $('#collapse-layers').onclick=()=>{const hidden=!$('#layer-body').hidden;$('#layer-body').hidden=hidden;$('#collapse-layers').textContent=hidden?'+':'−';$('#collapse-layers').setAttribute('aria-expanded',String(!hidden));};
  addEventListener('keydown',e=>{if(e.key.toLowerCase()==='r'&&!document.querySelector('dialog[open]'))setView('overview');});
  let start;canvas.addEventListener('pointerdown',e=>{start=[e.clientX,e.clientY,e.button];});canvas.addEventListener('pointerup',e=>{if(start&&start[2]===0&&Math.hypot(e.clientX-start[0],e.clientY-start[1])<4)inspect(e);});
  controls.addEventListener('start',()=>{flight=null;redraw=true;});controls.addEventListener('change',()=>{redraw=true;});
  canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();loadMessage.textContent='Graphics context lost. Reload to restore the landscape.';$('#loading').classList.remove('done');});
  addEventListener('resize',()=>{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight);redraw=true;});
}
function animate(time) {
  requestAnimationFrame(animate);
  if(flight){const t=flight.duration?Math.min(1,(time-flight.start)/flight.duration):1,e=t*t*(3-2*t);camera.position.lerpVectors(flight.from,flight.to,e);controls.target.lerpVectors(flight.fromTarget,flight.target,e);if(t>=1)flight=null;redraw=true;}
  controls.update();
  const [ox,oy]=data.study.origin,[xmin,ymin,xmax,ymax]=data.study.bounds;
  if(camera.position.x+ox>xmin&&camera.position.x+ox<xmax&&-camera.position.z+oy>ymin&&-camera.position.z+oy<ymax){const floor=ground(camera.position.x,-camera.position.z)+4;if(camera.position.y<floor){camera.position.y=floor;redraw=true;}}
  if(!redraw)return;
  renderer.render(scene,camera);redraw=false;lastFrame=time;
  const distance=camera.position.distanceTo(controls.target),projected=new THREE.Vector3();
  const labelBoxes=[];
  for(const l of labelEntries){
    projected.set(l.x,ground(l.x,l.n)+20,-l.n).project(camera);
    const x=(projected.x*.5+.5)*innerWidth,y=(-projected.y*.5+.5)*innerHeight;
    const b={left:x-l.width/2-5,right:x+l.width/2+5,top:y-l.height-4,bottom:y+4};
    let visible=projected.z<1&&projected.z>-1&&Math.abs(projected.x)<1.1&&Math.abs(projected.y)<1.1&&(!l.secondary||distance>1100);
    if(labelBoxes.some(a=>b.left<a.right&&b.right>a.left&&b.top<a.bottom&&b.bottom>a.top))visible=false;
    if(visible){labelBoxes.push(b);l.el.style.left=`${x}px`;l.el.style.top=`${y}px`;}
    l.el.hidden=!visible;
  }
  const angle=Math.atan2(camera.position.x-controls.target.x,camera.position.z-controls.target.z);$('#compass-needle').style.transform=`rotate(${-angle*180/Math.PI}deg)`;
  const mpp=2*distance*Math.tan(THREE.MathUtils.degToRad(camera.fov/2))/innerHeight;$('#scale-label').textContent=`≈ ${Math.round(95*mpp/10)*10} m`;
}
function fail(error) {
  console.error(error);$('#loading').classList.remove('done');loadMessage.textContent=`Could not open the landscape: ${error.message}. Run scripts/prepare.py, then serve public/ with Python.`;$('.loading-bar').hidden=true;
}
async function init() {
  try {
    renderer=new THREE.WebGLRenderer({canvas,antialias:true,powerPreference:'high-performance'});
    renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.setSize(innerWidth,innerHeight);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.12;
    scene=new THREE.Scene();scene.background=new THREE.Color('#dce5d9');scene.fog=new THREE.Fog('#dce5d9',4300,11000);
    camera=new THREE.PerspectiveCamera(40,innerWidth/innerHeight,1,18000);camera.position.set(1800,1800,2200);
    controls=new OrbitControls(camera,canvas);controls.enableDamping=true;controls.dampingFactor=.085;controls.minDistance=65;controls.maxDistance=6800;controls.maxPolarAngle=Math.PI*.465;controls.minPolarAngle=.015;controls.screenSpacePanning=true;controls.panSpeed=.75;controls.zoomSpeed=.75;controls.rotateSpeed=.55;controls.listenToKeyEvents(canvas);
    scene.add(new THREE.HemisphereLight('#f4fae7','#627557',2.2));const sun=new THREE.DirectionalLight('#fff5d9',2.3);sun.position.set(-1100,2400,1200);scene.add(sun);
    data=await request('assets/scene.json');loadMessage.textContent='Lifting the terrain…';
    const [elev,bpos,bcol]=await Promise.all([request(data.terrain.url,true),request(data.buildings.url,true),request(data.buildings.colors,true)]);heights=elev;
    const mask=makeTerrain();makeBuildings(bpos,bcol);loadMessage.textContent='Connecting roads and paths…';
    await new Promise(resolve=>setTimeout(resolve,20));makeRoutes();makeContext();makeWoodland(mask);makeLabels();
    state.layers.labels=true;bindControls();
    $('#area-label').textContent=`${data.summary.study_area_km2} km² study area`;$('#height-range').textContent=`${Math.round(data.terrain.range[0])}—${Math.round(data.terrain.range[1])} m`;
    $('#terrain-note').textContent=`Ontario GTA 2023 lidar terrain from ${data.summary.terrain_tiles} local tiles. CGVD2013 heights in metres; ${data.terrain.step} m display grid, no vertical exaggeration.`;
    $('#building-note').textContent=`${data.summary.multipatches.toLocaleString()} City 2025 Multipatch buildings and ${data.summary.extrusions} footprint extrusions. ${data.summary.estimated_heights} default height estimates. Colours are visualization styling. Click a building for its source.`;
    if(!data.imagery){$('#imagery').disabled=true;$('#imagery').title='A licensed georeferenced image crop is needed for this extent.';}
    setView('overview',true);animate(performance.now());state.ready=true;$('#loading').classList.add('done');setTimeout(()=>$('#loading').hidden=true,650);
    // Small, read-only QA interface plus the same actions exposed in the UI.
    function routeClearanceAudit(){const report={samples:0,minimumM:Infinity,maximumM:-Infinity,buriedSamples:0};for(const obj of pickable){const kind=obj.userData.kind;if(!['roads','paths'].includes(kind))continue;const pos=obj.geometry.attributes.position.array;for(const range of routeRanges[kind]){if(range.route.bridge)continue;for(let v=range.first;v<range.first+range.count;v+=3){const a=v*3,b=(v+1)*3,c=(v+2)*3,x=(pos[a]+pos[b]+pos[c])/3,z=(pos[a+2]+pos[b+2]+pos[c+2])/3,y=(pos[a+1]+pos[b+1]+pos[c+1])/3,clearance=y-ground(x,-z);report.samples++;report.minimumM=Math.min(report.minimumM,clearance);report.maximumM=Math.max(report.maximumM,clearance);if(clearance<-.01)report.buriedSamples++;}}}return report;}
    window.zoo={state,data,ground,view:setView,setLayer,setImagery,routeClearanceAudit,inspectAt:(x,y)=>inspect({clientX:x,clientY:y}),snapshot:()=>({camera:camera.position.toArray(),target:controls.target.toArray(),layers:{...state.layers},imagery:state.imagery,selection:state.selection,triangles:renderer.info.render.triangles,calls:renderer.info.render.calls,trees:state.treeCount}),project:(x,n,z=20)=>{const p=new THREE.Vector3(x,ground(x,n)+z,-n).project(camera);return[(p.x*.5+.5)*innerWidth,(-p.y*.5+.5)*innerHeight]},render:()=>{redraw=true;}};
  }catch(error){fail(error);}
}
init();
