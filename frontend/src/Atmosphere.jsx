import React,{useEffect,useRef} from 'react';
export default function Atmosphere({still=false}){
 const canvas=useRef(null);
 useEffect(()=>{
 const el=canvas.current,ctx=el.getContext('2d',{alpha:true}),hero=el.closest('.signal-hero');if(!ctx)return;
 let width=0,height=0,frame=0,visible=true,time=0,last=0,progress=0;
 const pointer={x:0,y:0},target={x:0,y:0};
 const points=Array.from({length:2600},(_,i)=>{const y=1-2*(i+.5)/2600,a=i*2.39996323,r=Math.sqrt(1-y*y);return{x:Math.cos(a)*r,y,z:Math.sin(a)*r,wx:Math.sin(a*.37)*2.3,wy:y*.8,wz:Math.cos(a*.19),phase:a%6.283};});
 const resize=()=>{const r=el.getBoundingClientRect();width=r.width;height=r.height;const d=Math.min(devicePixelRatio,1.5);el.width=width*d;el.height=height*d;ctx.setTransform(d,0,0,d,0,0);if(still)draw();};
 function draw(){if(!width||!height)return;ctx.clearRect(0,0,width,height);
 const mobile=width<720,base=Math.min(width*(mobile?.64:.32),height*.48),size=base*(1+progress*.8),cx=width*((mobile?.53:.74)-progress*(mobile?.03:.23)),cy=height*(mobile?.69:.52);
 const spin=time*.12+progress*2.5+pointer.x*.2,tilt=.15+progress*.5+pointer.y*.15,cs=Math.cos(spin),ss=Math.sin(spin),ct=Math.cos(tilt),st=Math.sin(tilt),spread=Math.max(0,(progress-.22)/.78),bands=[[],[],[]];
 for(const p of points){const ripple=1+.045*Math.sin(p.phase*3+time*.45),px=(p.x*cs-p.z*ss)*ripple,pz=(p.x*ss+p.z*cs)*ripple;const x=px*(1-spread)+p.wx*spread,y=(p.y*ct-pz*st)*(1-spread)+(p.wy+Math.sin(p.phase+time)*.16)*spread,z=(p.y*st+pz*ct)*(1-spread)+p.wz*spread,scale=2.8/(3.4-z),sx=cx+x*size*scale,sy=cy+y*size*scale,depth=Math.max(0,Math.min(2,Math.floor((z+1)*1.5)));if(sx>=0&&sx<=width&&sy>=0&&sy<=height)bands[depth].push(sx,sy);}
 const colors=['rgba(239,129,56,.38)','rgba(255,177,71,.72)','rgba(255,225,167,.98)'];bands.forEach((band,i)=>{ctx.fillStyle=colors[i];const dot=(i===2?2:1.5)*(mobile?.85:1);for(let k=0;k<band.length;k+=2)ctx.fillRect(band[k],band[k+1],dot,dot);});}
 const loop=now=>{frame=requestAnimationFrame(loop);const dt=Math.min((now-(last||now))/1000,.05);last=now;if(!visible||document.hidden)return;time+=dt;const s=1-Math.exp(-dt*11);progress+=(Number(hero.dataset.progress||0)-progress)*s;pointer.x+=(target.x-pointer.x)*s;pointer.y+=(target.y-pointer.y)*s;draw();};
 const move=e=>{const r=el.getBoundingClientRect();target.x=(e.clientX-r.left)/r.width-.5;target.y=(e.clientY-r.top)/r.height-.5;};
 const observer=new ResizeObserver(resize);observer.observe(el);const inview=new IntersectionObserver(([entry])=>visible=entry.isIntersecting);inview.observe(el);hero.addEventListener('pointermove',move,{passive:true});resize();if(!still)frame=requestAnimationFrame(loop);return()=>{cancelAnimationFrame(frame);observer.disconnect();inview.disconnect();hero.removeEventListener('pointermove',move);};
 },[still]);return <canvas ref={canvas} className="atmosphere-canvas" aria-hidden="true"/>;
}
