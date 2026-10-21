import React,{useLayoutEffect,useRef} from 'react';
import {createRoot} from 'react-dom/client';
import {flushSync} from 'react-dom';
import gsap from 'gsap';
import {ScrollTrigger} from 'gsap/ScrollTrigger';
import CountUp from './reactbits/CountUp';
import Magnet from './reactbits/Magnet';
import Atmosphere from './Atmosphere';

gsap.registerPlugin(ScrollTrigger);
const media=matchMedia('(prefers-reduced-motion: reduce)');
const disabled=()=>media.matches;
let roots=[],dashboardRoots=[],context=null,dashboardContext=null,previousCounts=[],lastNav=null,lastPeriod=null;
const visited=new Set();
function mount(el,component,global=false){if(!el)return;const root=createRoot(el);(global?roots:dashboardRoots).push(root);flushSync(()=>root.render(component));}
export function cleanupDashboardMotion(){dashboardContext?.revert();dashboardContext=null;dashboardRoots.forEach(root=>root.unmount());dashboardRoots=[];}
export function cleanupMotion(){journey?.kill();cleanupDashboardMotion();context?.revert();context=null;roots.forEach(root=>root.unmount());roots=[];}

let journey=null;
function travelIntro(){
 const target=document.querySelector('.section-label');if(!target)return;
 if(disabled()){target.scrollIntoView({behavior:'instant',block:'start'});return;}
 journey?.kill();const state={y:scrollY},end=target.getBoundingClientRect().top+scrollY-110;
 const cancel=()=>journey?.kill(),release=()=>{window.removeEventListener('wheel',cancel);window.removeEventListener('touchstart',cancel);window.removeEventListener('keydown',cancel);};window.addEventListener('wheel',cancel,{once:true,passive:true});window.addEventListener('touchstart',cancel,{once:true,passive:true});window.addEventListener('keydown',cancel,{once:true});
 journey=gsap.to(state,{y:end,duration:2.8,ease:'power2.inOut',onUpdate:()=>window.scrollTo(0,state.y),onComplete:release,onInterrupt:release});
}
function Hero(){return <><Atmosphere still={disabled()}/><div className="hero-vignette"/><div className="hero-copy"><h1 aria-label="A world in motion."><span className="hero-line">A world</span><span className="hero-line hero-italic">in motion.</span></h1><p className="hero-description">Weather is everywhere.<br/>Understanding starts here.</p><Magnet disabled={disabled()} padding={24} maxOffset={10} magnetStrength={4} spring={{stiffness:180,damping:28}}><button className="hero-jump" onClick={travelIntro}><span>Enter the observatory</span><svg viewBox="0 0 24 24" className="ui-icon" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M5 12h14m-5-5 5 5-5 5"/></svg></button></Magnet></div><div className="hero-second" aria-hidden="true"><span>Make sense</span><em>of the signal.</em><p>From scattered reports<br/>to a clearer picture.</p></div><div className="hero-bottom-line"><span>Weather intelligence / India</span><span>Scroll to discover <svg className="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M12 3v18m-5-5 5 5 5-5"/></svg></span><button className="skip-intro" onClick={travelIntro}>Skip introduction</button></div><div className="hero-scroll-index" aria-hidden="true"><span className="hero-scroll-fill"/></div></>}
function NativeControl({node}){const ref=useRef(null);useLayoutEffect(()=>{ref.current.appendChild(node);},[node]);return <span ref={ref} className="native-control"/>;}
function magneticControls(){if(disabled()||!matchMedia('(hover:hover) and (pointer:fine)').matches)return;const scope=document.querySelector('#dashboard-region')||document.querySelector('main');scope.querySelectorAll('#export,#prev,#next,#utc,#zoom-in,#zoom-out,.primary,.location-clear,.map-footer .text-button').forEach(node=>{const host=document.createElement('span');host.className='magnet-control';node.replaceWith(host);mount(host,<Magnet padding={14} magnetStrength={6} maxOffset={6} spring={{stiffness:220,damping:32}}><NativeControl node={node}/></Magnet>);});}
function slidingIndicator(parent,target,className,previous){if(!parent||!target)return null;const rect=target.getBoundingClientRect(),box=parent.getBoundingClientRect(),next={x:rect.left-box.left,width:rect.width};const marker=document.createElement('span');marker.className=className;marker.setAttribute('aria-hidden','true');marker.style.width=next.width+'px';parent.appendChild(marker);parent.dataset.animated='true';gsap.fromTo(marker,{x:previous?.x??next.x,scaleX:previous?previous.width/next.width:1},{x:next.x,scaleX:1,duration:.5,ease:'power4.out',transformOrigin:'left center'});return next;}
function sceneTone(){const hero=document.querySelector('.signal-hero');document.documentElement.dataset.scene=hero&&hero.getBoundingClientRect().bottom>90?'dark':'light';const progress=document.querySelector('.scroll-progress');if(progress){const span=document.documentElement.scrollHeight-innerHeight;progress.style.transform=`scaleX(${span>0?Math.min(1,scrollY/span):0})`;}}

export function enhanceMotion(page,{dashboardOnly=false}={}){
  const first=!visited.has(page);if(!dashboardOnly)visited.add(page);
  document.documentElement.dataset.motion=disabled()?'off':'on';
  document.documentElement.style.setProperty('--viewport-width',document.documentElement.clientWidth+'px');
  const hero=document.querySelector('#signal-hero');
  if(!dashboardOnly){
    if(hero)mount(hero,<Hero/>,true);
    sceneTone();
    if(!disabled())context=gsap.context(()=>{
      lastNav=slidingIndicator(document.querySelector('.sidebar'),document.querySelector('.nav-button.active'),'section-tab-indicator',lastNav);
      if(hero){
        gsap.set('.hero-second',{autoAlpha:1,y:90,clipPath:'inset(0 0 100% 0)'});
        const story=gsap.timeline({defaults:{ease:'none'},scrollTrigger:{id:'atmosphere-intro',trigger:hero,start:'top top',end:()=>`+=${innerHeight*(innerWidth<720?1:1.45)}`,pin:true,anticipatePin:1,scrub:.65,invalidateOnRefresh:true}});
        const field={progress:0};story.to(field,{progress:1,duration:1,onUpdate:()=>hero.dataset.progress=field.progress},0);
        story.to('.hero-copy',{y:-90,clipPath:'inset(0 0 100% 0)',duration:.26},.08).to('.hero-second',{y:0,clipPath:'inset(0 0 0% 0)',duration:.24},.36).to('.hero-second',{y:-50,clipPath:'inset(0 0 100% 0)',duration:.16},.84).to('.hero-scroll-fill',{scaleY:1,duration:1},0);
        if(first)gsap.fromTo('.hero-line',{yPercent:90,opacity:0,rotate:3},{yPercent:0,opacity:1,rotate:0,duration:1.1,stagger:.12,ease:'power4.out'});
      }else gsap.fromTo('.page-heading h1',{clipPath:'inset(0 0 100% 0)',y:25},{clipPath:'inset(0 0 0% 0)',y:0,duration:.8,ease:'power4.out'});
    });
  }
  document.querySelectorAll('.metrics article>strong').forEach((el,i)=>{const value=Number(el.firstChild?.textContent?.replaceAll(',',''));if(!Number.isFinite(value))return;const host=document.createElement('span');host.className='metric-counter';el.firstChild.replaceWith(host);mount(host,disabled()?<span>{value}</span>:<CountUp to={value} from={previousCounts[i]??0} duration={.55} separator="," easing="expo" trigger="load"/>);previousCounts[i]=value;});
  magneticControls();
  if(!disabled())dashboardContext=gsap.context(()=>{
    lastPeriod=slidingIndicator(document.querySelector('.period'),document.querySelector('.period .selected'),'period-tab-indicator',lastPeriod);
    const map=document.querySelector('.map-panel');
    if(!dashboardOnly){
      document.querySelectorAll('.metrics article').forEach((item,i)=>gsap.fromTo(item,{clipPath:'inset(0 0 100% 0)',y:36},{clipPath:'inset(0 0 0% 0)',y:0,duration:.7,delay:i*.09,ease:'power4.out',scrollTrigger:{trigger:'.metrics',start:'top 88%',once:true}}));
      document.querySelectorAll('.event-bars button').forEach((item,i)=>gsap.fromTo(item,{x:48,opacity:0},{x:0,opacity:1,duration:.55,delay:i*.065,scrollTrigger:{trigger:'.distribution',start:'top 78%',once:true}}));
      document.querySelectorAll('.bar-column>div').forEach((bar,i)=>gsap.fromTo(bar,{scaleY:0,transformOrigin:'bottom'},{scaleY:1,duration:.75,delay:i*.04,ease:'power3.out',scrollTrigger:{trigger:'.trend',start:'top 85%',once:true}}));
      document.querySelectorAll('.reports>.panel-head h2').forEach(el=>gsap.fromTo(el,{clipPath:'inset(0 100% 0 0)'},{clipPath:'inset(0 0% 0 0)',duration:.9,ease:'power4.out',scrollTrigger:{trigger:el,start:'top 90%',once:true}}));
    }
    if(map&&!dashboardOnly)gsap.fromTo(map.querySelector('.map-stage'),{scale:.94,rotationX:7,y:12,transformPerspective:1100,transformOrigin:'50% 50%'},{scale:1,rotationX:0,y:0,ease:'none',scrollTrigger:{trigger:map,start:'top 98%',end:'top 42%',scrub:.5}});
    if(!dashboardOnly){
      document.querySelectorAll('.marker').forEach((el,i)=>gsap.fromTo(el,{opacity:.4},{opacity:1,duration:.3,delay:i*.035,scrollTrigger:{trigger:map,start:'top 80%',once:true}}));
      document.querySelectorAll('.reports tbody tr').forEach((row,i)=>gsap.fromTo(row,{y:22,opacity:.25},{y:0,opacity:1,duration:.65,delay:i*.045,ease:'power3.out',scrollTrigger:{trigger:row,start:'top 97%',once:true}}));
      if(document.querySelector('.distribution'))gsap.fromTo('.donut',{scale:.78,rotation:0,clipPath:'circle(0% at 50% 50%)'},{scale:1,rotation:0,clipPath:'circle(75% at 50% 50%)',duration:1.1,ease:'power4.out',scrollTrigger:{trigger:'.distribution',start:'top 85%',once:true}});
    }else if(document.querySelector('.reports tbody'))gsap.fromTo('.reports tbody',{opacity:.65},{opacity:1,duration:.2});
  });
  if(!dashboardOnly)ScrollTrigger.refresh();sceneTone();
}
media.addEventListener('change',()=>window.dispatchEvent(new Event('monsoon-motion-change')));
window.addEventListener('scroll',sceneTone,{passive:true});
window.addEventListener('resize',()=>{
  document.documentElement.style.setProperty('--viewport-width',document.documentElement.clientWidth+'px');
  requestAnimationFrame(()=>{
    const reposition=(parent,target,selector)=>{if(!parent||!target)return null;const marker=parent.querySelector(selector);if(!marker)return null;const r=target.getBoundingClientRect(),p=parent.getBoundingClientRect(),box={x:r.left-p.left,width:r.width};marker.style.width=box.width+'px';gsap.killTweensOf(marker);gsap.set(marker,{x:box.x,scaleX:1});return box;};
    lastNav=reposition(document.querySelector('.sidebar'),document.querySelector('.nav-button.active'),'.section-tab-indicator')||lastNav;
    lastPeriod=reposition(document.querySelector('.period'),document.querySelector('.period .selected'),'.period-tab-indicator')||lastPeriod;
  });
});

 document.addEventListener('pointermove',e=>{const b=e.target.closest('button');if(!b)return;const r=b.getBoundingClientRect();b.style.setProperty('--pointer-x',(e.clientX-r.left)+'px');b.style.setProperty('--pointer-y',(e.clientY-r.top)+'px');},{passive:true});
