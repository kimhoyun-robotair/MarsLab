import * as THREE from './vendor/three.module.js';
import {OrbitControls} from './vendor/OrbitControls.js';
import {GLTFLoader} from './vendor/GLTFLoader.js';
import {prepareWheels,travelSamples,rollWheels} from './wheel-motion.js';
const $=id=>document.getElementById(id);
if(new URLSearchParams(location.search).has('embed'))document.body.classList.add('embedded');
const state={mode:'explore',scene:'crater',time:0,playing:false,run:null,terrain:null,algorithm:'mola',token:0,frame:-1,map:-1,dirty:true};
const names={crater:'Main Crater',canyon:'Grand Canyon'};
let renderer,world,camera,controls,terrainMesh,rover,mapCloud,estimatedLine,gtLine,routeLine,axes,texture;
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
let lastFollow=null,abort;
const v=(a)=>new THREE.Vector3(...a.slice(0,3));
const q=(a)=>new THREE.Quaternion(...a.slice(3,7)).normalize();
function nearestBefore(items,t){let lo=0,hi=items.length-1;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(items[mid].t<=t)lo=mid;else hi=mid-1;}return lo;}
function poseAt(items,t){const i=nearestBefore(items,t),a=items[i],b=items[Math.min(i+1,items.length-1)];const u=b.t>a.t?THREE.MathUtils.clamp((t-a.t)/(b.t-a.t),0,1):0;return {position:v(a.pose).lerp(v(b.pose),u),quaternion:q(a.pose).slerp(q(b.pose),u)};}
function dispose(object){if(!object)return;world.remove(object);object.traverse?.(o=>{o.geometry?.dispose();if(Array.isArray(o.material))o.material.forEach(m=>m.dispose());else o.material?.dispose();});}
function line(color){return new THREE.Line(new THREE.BufferGeometry(),new THREE.LineBasicMaterial({color,depthTest:false,transparent:true,opacity:.95}));}
function setLine(object,positions){object.geometry.dispose();object.geometry=new THREE.BufferGeometry().setFromPoints(positions);object.renderOrder=5;}
let roverAsset,wheels=[],travel=[];
function loadRover(){
 if(!roverAsset)roverAsset=new GLTFLoader().loadAsync('data/rover.glb').then(gltf=>{
  const model=gltf.scene;
  wheels=prepareWheels(model);
  model.rotation.x=Math.PI/2;
  model.position.z=.7;
  model.name='Original MarsLab Perseverance';
  rover.add(model);
  state.dirty=true;
 }).catch(error=>{roverAsset=null;throw error;});
 return roverAsset;
}
function init3D(){THREE.Object3D.DEFAULT_UP.set(0,0,1);renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:'low-power'});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.outputColorSpace=THREE.SRGBColorSpace;$('viewport').append(renderer.domElement);world=new THREE.Scene();world.background=new THREE.Color(0xe9ddcf);camera=new THREE.PerspectiveCamera(48,1,.1,20000);camera.up.set(0,0,1);controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=!reduced;controls.dampingFactor=.12;controls.maxPolarAngle=Math.PI*.495;controls.minDistance=3;controls.maxDistance=12000;controls.listenToKeyEvents($('viewport'));controls.addEventListener('change',()=>state.dirty=true);controls.addEventListener('start',()=>{$('follow').checked=false;lastFollow=null;});world.add(new THREE.HemisphereLight(0xfff3df,0x6e513a,2));const light=new THREE.DirectionalLight(0xffffff,2.2);light.position.set(-300,-600,1000);world.add(light);rover=new THREE.Group();world.add(rover);axes=new THREE.AxesHelper(3);axes.material.depthTest=false;axes.renderOrder=10;world.add(axes);mapCloud=new THREE.Points(new THREE.BufferGeometry(),new THREE.PointsMaterial({color:0xc88f57,size:.3,sizeAttenuation:true}));world.add(mapCloud);estimatedLine=line(0x409cff);gtLine=line(0x49b86d);routeLine=line(0x943c20);world.add(estimatedLine,gtLine,routeLine);new ResizeObserver(resize).observe($('viewport'));resize();}
function resize(){if(!renderer)return;const {clientWidth:w,clientHeight:h}=$('viewport');renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();state.dirty=true;}
function buildTerrain(data,image){dispose(terrainMesh);texture?.dispose();const n=data.n,positions=new Float32Array(n*n*3),uv=new Float32Array(n*n*2),indices=[];for(let i=0;i<n;i++)for(let j=0;j<n;j++){const k=i*n+j;positions.set([(j/(n-1)-.5)*data.width,(.5-i/(n-1))*data.height,data.heights[k]],k*3);uv.set([j/(n-1),1-i/(n-1)],k*2);if(i<n-1&&j<n-1){const a=k,b=k+1,c=k+n,d=c+1;indices.push(a,c,b,b,c,d);}}const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.BufferAttribute(positions,3));geo.setAttribute('uv',new THREE.BufferAttribute(uv,2));geo.setIndex(indices);geo.computeVertexNormals();texture=new THREE.Texture(image);texture.colorSpace=THREE.SRGBColorSpace;texture.needsUpdate=true;texture.anisotropy=Math.min(4,renderer.capabilities.getMaxAnisotropy());terrainMesh=new THREE.Mesh(geo,new THREE.MeshLambertMaterial({map:texture,side:THREE.DoubleSide}));world.add(terrainMesh);}
async function json(url,signal){const r=await fetch(url,{signal});if(!r.ok)throw new Error(`Could not load ${url} (${r.status})`);return r.json();}
function image(url){return new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(new Error(`Could not load image ${url}`));im.src=url;});}
function setBusy(b){$('loading').hidden=!b;for(const id of ['play','restart','timeline'])$(id).disabled=b;}
async function loadScene(name){const token=++state.token;abort?.abort();abort=new AbortController();state.playing=false;$('play').textContent='Play traverse';state.time=0;state.run=null;state.scene=name;state.frame=-1;state.map=-1;setBusy(true);$('loading').textContent=`Loading ${names[name]} terrain and recorded data…`;try{const base=`data/${name}/`;const [terrain,run,terrainImage,rgb,depth]=await Promise.all([json(base+'terrain.json',abort.signal),json(base+'run.json',abort.signal),image(base+'terrain.jpg'),image(base+'rgb.jpg'),image(base+'depth.jpg'),loadRover()]);if(token!==state.token)return;if(!run.frames?.length||!run.maps?.mola?.length||!run.maps?.rtab?.length)throw new Error('This sample is missing required observations.');state.run=run;travel=travelSamples(run.frames);state.terrain=terrain;state.rgb=rgb;state.depth=depth;buildTerrain(terrain,terrainImage);$('timeline').max=run.duration;$('timeline').value=0;$('run-info').textContent=`${names[name]} · actual ROS 2 recording · τ = 0.5 · ${run.frames.length} sensor frames`;$('follow').checked=false;setBusy(false);updateMode(false);renderTime(true);preset(state.mode==='explore'?'overview':'focus');}catch(e){if(token!==state.token||e.name==='AbortError')return;state.run=null;setBusy(true);const button=document.createElement('button');button.textContent='Retry loading';button.onclick=()=>loadScene(name);$('loading').replaceChildren(document.createTextNode(e.message+' '),button);console.error(e);}}
function alignment(){const est=state.run.estimates[state.algorithm],i=nearestBefore(est,0),e=est[i],g=state.run.frames[0];const rotation=q(e.pose).multiply(q(g.pose).invert());return {rotation,origin:v(g.pose),target:v(e.pose)};}
function localGT(pose){const a=alignment();return v(pose).sub(a.origin).applyQuaternion(a.rotation).add(a.target);}
function currentPose(){if(state.mode==='slam')return poseAt(state.run.estimates[state.algorithm],state.time);return poseAt(state.run.frames,state.time);}
function preset(kind){if(!state.run)return;const p=currentPose().position;let target=p.clone(),offset;
 if(kind==='overview'&&state.mode!=='slam'){const d=state.terrain;target.set(0,0,(Math.min(...d.heights)+Math.max(...d.heights))/2);const size=Math.max(d.width,d.height);offset=new THREE.Vector3(size*.55,-size*.65,size*.6);}
 else if(kind==='overview'&&state.mode==='slam'){const points=mapCloud.geometry.attributes.position;if(points?.count){mapCloud.geometry.computeBoundingSphere();target.copy(mapCloud.geometry.boundingSphere.center);const r=Math.max(15,mapCloud.geometry.boundingSphere.radius);offset=new THREE.Vector3(r,-r,r);}else offset=new THREE.Vector3(30,-35,30);}
 else if(kind==='top')offset=new THREE.Vector3(0,-.01,state.mode==='slam'?80:90);
 else offset=state.mode==='slam'?new THREE.Vector3(20,-25,25):new THREE.Vector3(-10,-14,10);
 if(kind==='overview'){const radius=state.mode==='slam'?Math.max(15,mapCloud.geometry.boundingSphere?.radius||30):Math.hypot(state.terrain.width,state.terrain.height)/2;const vertical=THREE.MathUtils.degToRad(camera.fov),horizontal=2*Math.atan(Math.tan(vertical/2)*camera.aspect);offset.normalize().multiplyScalar(radius/Math.sin(Math.min(vertical,horizontal)/2)*1.05);}
 controls.target.copy(target);camera.position.copy(target).add(offset);controls.update();controls.saveState();lastFollow=p.clone();state.dirty=true;}
function updateMode(reset=true){if(!world)return;const slam=state.mode==='slam';$('sensor-panel').hidden=slam;$('slam-panel').hidden=!slam;terrainMesh&&(terrainMesh.visible=!slam);rover.visible=!slam;axes.visible=slam;mapCloud.visible=slam;estimatedLine.visible=slam;gtLine.visible=slam&&$('show-gt').checked;routeLine.visible=!slam;world.background.set(slam?0x111920:0xe9ddcf);$('mode-description').textContent={explore:'Drag to orbit the terrain. Zoom in, pan, or jump to the rover.',slam:'Replay actual map snapshots and compare the estimated path with ground truth.'}[state.mode];$('view-label').textContent=slam?'Recorded map · X red / Y green / Z blue':'HiRISE-derived terrain · original Perseverance model';document.querySelectorAll('[data-mode]').forEach(b=>{const selected=b.dataset.mode===state.mode;b.setAttribute('aria-selected',String(selected));b.tabIndex=selected?0:-1;});$('workspace').setAttribute('aria-labelledby',`tab-${state.mode}`);state.map=-1;state.frame=-1;lastFollow=null;if(state.run){renderTime(true);if(reset)preset(slam?'overview':'overview');}}
function drawAtlas(id,im,index){const {width:w,height:h,columns:c}=state.run.atlas;$(id).getContext('2d').drawImage(im,index%c*w,Math.floor(index/c)*h,w,h,0,0,256,192);}
function drawLidar(points){const canvas=$('lidar'),ctx=canvas.getContext('2d');ctx.fillStyle='#0c1014';ctx.fillRect(0,0,canvas.width,canvas.height);const scale=2.2;for(let i=0;i<points.length;i+=3){const [x,y,z]=points.slice(i,i+3);const sx=260+(x-y)*.72*scale,sy=180-(x+y)*.22*scale-z*scale;ctx.fillStyle=`hsl(${190-Math.min(80,Math.max(-20,z)*3)},65%,62%)`;ctx.fillRect(sx,sy,1.5,1.5);}ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(260,180,3,0,Math.PI*2);ctx.fill();$('lidar-count').textContent=`${points.length/3} displayed points`;}
function renderTime(force=false){if(!state.run)return;const t=state.time,run=state.run,idx=nearestBefore(run.frames,t),frame=run.frames[idx],p=currentPose();rollWheels(wheels,travel,idx,t);rover.position.copy(p.position);rover.quaternion.copy(p.quaternion);axes.position.copy(p.position);axes.quaternion.copy(p.quaternion);
 if($('follow').checked){if(lastFollow){const delta=p.position.clone().sub(lastFollow);camera.position.add(delta);controls.target.add(delta);}lastFollow=p.position.clone();}else lastFollow=null;
 if(force||idx!==state.frame){drawAtlas('rgb',state.rgb,idx);drawAtlas('depth',state.depth,idx);drawLidar(frame.lidar);$('rgb-stamp').textContent=`${frame.t.toFixed(2)} s`;setLine(routeLine,run.frames.slice(0,idx+1).map(f=>v(f.pose).add(new THREE.Vector3(0,0,.7))));state.frame=idx;}
 if(state.mode==='slam'){const snapshots=run.maps[state.algorithm],mi=nearestBefore(snapshots,t),map=snapshots[mi];if(force||mi!==state.map){mapCloud.geometry.dispose();mapCloud.geometry=new THREE.BufferGeometry();mapCloud.geometry.setAttribute('position',new THREE.Float32BufferAttribute(map.points,3));$('map-count').textContent=map.total.toLocaleString();$('map-time').textContent=map.t<0?'Initial':`${map.t.toFixed(1)} s`;state.map=mi;}const est=run.estimates[state.algorithm].filter(e=>e.t<=t);setLine(estimatedLine,est.map(e=>v(e.pose)));setLine(gtLine,run.frames.filter(f=>f.t<=t).map(f=>localGT(f.pose)));$('pose-count').textContent=est.length;}
 $('timeline').value=t;$('time').textContent=`${t.toFixed(1)} / ${run.duration.toFixed(1)} s`;state.dirty=true;}
$('scene').addEventListener('change',e=>loadScene(e.target.value));
document.querySelectorAll('[data-mode]').forEach(b=>{b.onclick=()=>{state.mode=b.dataset.mode;updateMode();};b.onkeydown=e=>{const tabs=[...document.querySelectorAll('[data-mode]')];let i=tabs.indexOf(b);if(e.key==='ArrowRight')i=(i+1)%tabs.length;else if(e.key==='ArrowLeft')i=(i+tabs.length-1)%tabs.length;else if(e.key==='Home')i=0;else if(e.key==='End')i=tabs.length-1;else return;e.preventDefault();tabs[i].focus();tabs[i].click();};});
$('algorithm').onchange=e=>{state.algorithm=e.target.value;state.map=-1;renderTime(true);preset('overview');};
$('show-gt').onchange=()=>{gtLine.visible=$('show-gt').checked&&state.mode==='slam';state.dirty=true;};
for(const [id,kind] of [['overview','overview'],['focus','focus'],['top','top'],['reset-camera','overview']])$(id).onclick=()=>preset(kind);
$('follow').onchange=()=>{lastFollow=null;if($('follow').checked)preset('focus');};
$('play').onclick=()=>{if(!state.run)return;if(state.time>=state.run.duration)state.time=0;state.playing=!state.playing;$('play').textContent=state.playing?'Pause':'Play traverse';};
$('restart').onclick=()=>{state.playing=false;state.time=0;$('play').textContent='Play traverse';renderTime(true);};
$('timeline').oninput=e=>{state.playing=false;$('play').textContent='Play traverse';state.time=Number(e.target.value);renderTime();};
document.addEventListener('visibilitychange',()=>{if(document.hidden){state.playing=false;$('play').textContent='Play traverse';}});
let last=performance.now();function loop(now){requestAnimationFrame(loop);const dt=Math.min((now-last)/1000,.1);last=now;if(document.hidden||!renderer)return;if(state.playing&&state.run){state.time=Math.min(state.run.duration,state.time+dt*Number($('speed').value));renderTime();if(state.time>=state.run.duration){state.playing=false;$('play').textContent='Play traverse';}}controls.update();if(state.dirty){renderer.render(world,camera);state.dirty=false;}}
try{init3D();loadScene('crater');requestAnimationFrame(loop);}catch(e){$('loading').textContent='This device could not start the 3D view. Enable WebGL or try another browser. The project page and downloadable data remain available.';console.error(e);}

if(window.parent!==window){
 const reportHeight=()=>window.parent.postMessage({type:'marslab-demo-height',height:Math.ceil(document.querySelector('.lab').getBoundingClientRect().height)+2},location.origin);
 new ResizeObserver(reportHeight).observe(document.querySelector('.lab'));
 reportHeight();
}
