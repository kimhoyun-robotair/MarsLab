import * as THREE from './vendor/three.module.js';

export function prepareWheels(model){
 const wheels=[];
 model.traverse(part=>{if(part.isMesh&&part.name.startsWith('Body_Wheel'))wheels.push(part);});
 if(wheels.length!==6)throw new Error('The rover model must contain six wheel meshes.');
 return wheels.map(mesh=>{
  mesh.geometry.computeBoundingBox();
  const box=mesh.geometry.boundingBox,center=box.getCenter(new THREE.Vector3());
  const size=box.getSize(new THREE.Vector3());
  const pivot=new THREE.Group();
  pivot.name=`${mesh.name}_rolling`;
  pivot.position.copy(center);
  mesh.parent.add(pivot);
  pivot.add(mesh);
  mesh.position.sub(center);
  return {pivot,radius:(size.x+size.y)/4};
 });
}

export function travelSamples(frames){
 let distance=0;
 return frames.map((frame,i)=>{
  if(i){
   const previous=frames[i-1].pose;
   const delta=new THREE.Vector3(...frame.pose.slice(0,3)).sub(new THREE.Vector3(...previous.slice(0,3)));
   const forward=new THREE.Vector3(1,0,0).applyQuaternion(new THREE.Quaternion(...previous.slice(3,7)).normalize());
   distance+=delta.length()*Math.sign(delta.dot(forward));
  }
  return {t:frame.t,distance};
 });
}

export function rollWheels(wheels,samples,index,time){
 const a=samples[index],b=samples[Math.min(index+1,samples.length-1)];
 const u=b.t>a.t?THREE.MathUtils.clamp((time-a.t)/(b.t-a.t),0,1):0;
 const distance=THREE.MathUtils.lerp(a.distance,b.distance,u);
 // The original GLB is Y-up: -Z is the rover's +Y wheel axle.
 for(const {pivot,radius} of wheels)pivot.rotation.z=-distance/radius;
}
