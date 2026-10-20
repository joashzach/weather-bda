# Scroll and 3D: awards-grade motion that still works

Use this for Tier 2 (showcase) work and for the signature moment in Tier 1. Read `motion.md` §1–2 first.
Scroll and 3D are where "extremely cool" and "vibe-coded and broken" are one bad decision apart; the rules
below are what separate them. (Sources: GSAP's official agent skills for core/timeline/ScrollTrigger/React/
performance, the drei and R3F ecosystems, CSS scroll-driven animations, and patterns recurring across
CSS Design Awards / Awwwards winners.)

## Contents
1. Decide first: story, tool, budget
2. CSS scroll-driven animations (no JS)
3. GSAP + ScrollTrigger: rules and recipes
4. Smooth scroll (Lenis) and how to wire it
5. Scroll recipes (12)
6. DOM-synced WebGL (shader images)
7. 3D scenes: R3F and vanilla three
8. CSS 3D (cheap, charming)
9. Performance budgets
10. Accessibility and fallbacks
11. Sandboxed pages (claude.ai artifacts)

---

## 1. Decide first

**Write the scroll story as beats before touching code.** A scroll sequence without a story is a screensaver.

| Beat | Viewport | What the viewer learns / feels | What moves | Scrub or trigger |
|---|---|---|---|---|
| 1 Arrive | 0–100% | The subject, in one look | Headline reveal (once) | trigger |
| 2 Turn | 100–250% | The problem/difference | Object rotates, text swaps | scrub, pinned |
| 3 Proof | 250–400% | Evidence | Numbers count, chart draws | scrub |
| 4 Invite | 400%+ | What to do next | Quiet; CTA is still | none |

Rules for beats: one idea each; motion must **carry meaning** (reveal, compare, build up, zoom into detail);
leave breathing room (a still section between intense ones); end calm.

**Tool choice:**

| You need | Use |
|---|---|
| Fade/translate/reveal on enter; progress bars; simple parallax | CSS `animation-timeline` (§2) |
| Pinned scenes, scrubbed timelines, horizontal rails, text splitting, sequencing, SVG, canvas values, cleanup in React | GSAP + ScrollTrigger (§3) |
| React-only scroll values driving styles/springs | Motion `useScroll` + `useTransform` + `useSpring` |
| A 3D object that responds to scroll | R3F (React) or three.js (vanilla), progress fed by ScrollTrigger (§7) |
| Images that distort/ripple/RGB-split with scroll velocity | DOM-synced WebGL (§6) |

## 2. CSS scroll-driven animations

Chrome/Edge 115+ and Safari 26+ support `animation-timeline`; Firefox stable did not enable it by default at time
of writing, so it is **progressive enhancement**: the page must look correct with the animation stripped.
Re-check support (caniuse/MDN) before relying on it.

```css
/* Reveal as an element crosses into view; scoped so unsupported browsers just show the content */
@supports (animation-timeline: view()) {
  .reveal { animation: reveal linear both; animation-timeline: view(); animation-range: entry 5% cover 28%; }
}
@keyframes reveal { from { opacity: 0; translate: 0 2.5rem; filter: blur(6px); } to { opacity: 1; translate: 0 0; filter: blur(0); } }

/* Reading-progress bar tied to the root scroller */
.progress { position: fixed; inset: 0 0 auto 0; height: 3px; background: var(--accent); transform-origin: 0 50%;
  scale: 0 1; animation: grow linear both; animation-timeline: scroll(root); }
@keyframes grow { to { scale: 1 1; } }

/* Named timeline: a sticky stage whose child reacts to the section's progress */
.chapter { view-timeline: --ch block; }
.chapter .obj { animation: spin linear both; animation-timeline: --ch; animation-range: cover 0% cover 100%; }
@keyframes spin { to { rotate: 180deg; scale: 1.15; } }
```
Use `ease: linear` for scrubbed animations; shape the motion in the keyframes. Wrap in a
`prefers-reduced-motion: no-preference` query.

## 3. GSAP + ScrollTrigger: rules and recipes

GSAP and its formerly-paid plugins (ScrollTrigger, SplitText, ScrollSmoother, Flip, MorphSVG, DrawSVG, etc.) are
free to use since 2025; check the current licence at gsap.com before shipping commercially.

**Rules (distilled from the official GSAP skills):**
1. `gsap.registerPlugin(ScrollTrigger)` once, before use. In React also register `useGSAP`.
2. **Sequence with timelines and the position parameter** (`"<"`, `"+=0.2"`, labels), not chained delays.
3. **Put the `scrollTrigger` on the timeline, not on child tweens** of a timeline.
4. **Scrubbed tweens use `ease: "none"`**; shape feel with `scrub: 0.5–1` (a smoothing lag in seconds) or damping,
   never with an ease inside the scrub (it fights the scrollbar).
5. **Animate transforms and opacity** (`x, y, xPercent, yPercent, scale, rotate, autoAlpha`); use `clipPath` for
   masks. Never animate `top/left/width/height`.
6. **Function-based values + `invalidateOnRefresh: true`** for anything depending on layout (`x: () => -dist()`).
7. **Pin**: `pin: true, anticipatePin: 1`; pinned sections change document height, so create triggers in
   top-to-bottom DOM order (or set `refreshPriority`), and keep pins ≤ ~3 viewport lengths.
8. **Refresh after layout changes**: `document.fonts.ready.then(() => ScrollTrigger.refresh())`, after images
   load (use explicit `aspect-ratio` to avoid shifts), and after route/DOM changes.
9. **Responsive + accessible branches with `gsap.matchMedia()`**, never by hand-rolled resize listeners:
   ```js
   const mm = gsap.matchMedia();
   mm.add({ motion: "(prefers-reduced-motion: no-preference)", wide: "(min-width: 900px)" }, (ctx) => {
     const { motion, wide } = ctx.conditions;
     if (!motion) return;                       // reduced motion: leave the static layout alone
     /* build triggers; if (!wide) build the simpler mobile version */
   });
   ```
   Everything created inside is reverted automatically when the query stops matching.
10. **React:** use `useGSAP(() => {...}, { scope: ref, dependencies: [...] })`; it wraps `gsap.context()` and cleans
    up. Use `contextSafe` for event handlers; select with scoped class names/refs, not global selectors.
    Mark client components (`"use client"`) in Next.js; never run GSAP on the server.
11. **Avoid FOUC without breaking no-JS:** add `html.js` via script in `<head>`, and hide initial states only
    under `.js` (`.js .reveal { opacity: 0 }`); `autoAlpha` handles `visibility`.
12. **Batching and quick setters:** `ScrollTrigger.batch(".item", { onEnter: els => gsap.to(els, {...stagger: .08}) })`
    for lists; `gsap.quickTo(el, "x", { duration: .4, ease: "power3" })` for pointer followers.
13. Mobile address-bar jank: `ScrollTrigger.config({ ignoreMobileResize: true })`; consider
    `ScrollTrigger.normalizeScroll(true)` only if you truly need it (it changes native scroll behaviour).
14. **Don't leak:** kill triggers on unmount (`useGSAP` does), `ScrollTrigger.getAll().forEach(t => t.kill())` for SPAs
    without it, and remove ticker callbacks.

Skeleton (React):
```tsx
"use client";
import { useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
gsap.registerPlugin(useGSAP, ScrollTrigger);

export function Stage() {
  const root = useRef<HTMLElement>(null);
  useGSAP(() => {
    const mm = gsap.matchMedia();
    mm.add("(prefers-reduced-motion: no-preference)", () => {
      gsap.timeline({ defaults: { ease: "none" },
        scrollTrigger: { trigger: ".stage", start: "top top", end: "+=250%", scrub: 0.6, pin: true, anticipatePin: 1 } })
        .from(".obj", { scale: 0.7, rotate: -12 })
        .to(".obj", { rotate: 90 }, "+=0.2")
        .from(".copy-2", { autoAlpha: 0, y: 40 }, "<0.3");
    });
  }, { scope: root });
  return <section ref={root}><div className="stage">…</div></section>;
}
```

## 4. Smooth scroll (Lenis)

Smooth scroll adds inertia and is the signature of most award sites. It is also the easiest way to break
accessibility, anchors, find-in-page and native feel. Use Lenis, keep native scroll semantics (it uses real
scrolling), never hijack wheel to something other than scrolling, and disable it for reduced motion.

```js
import Lenis from "lenis";
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
if (!reduce) {
  const lenis = new Lenis({ lerp: 0.1, smoothWheel: true });
  lenis.on("scroll", ScrollTrigger.update);                 // keep ScrollTrigger in sync
  gsap.ticker.add((t) => lenis.raf(t * 1000));              // drive Lenis from GSAP's ticker
  gsap.ticker.lagSmoothing(0);
  // anchors: lenis.scrollTo("#id", { offset: -80 })
  // velocity for effects: lenis.velocity
}
```
React: `lenis/react` (`<ReactLenis root />`) with `autoRaf: false` and the same ticker hookup.

## 5. Scroll recipes

**R1 Pinned scrubbed scene** → §3 skeleton. Use for "turn" beats: object transforms while copy swaps.

**R2 Horizontal rail**
```js
const track = document.querySelector(".track");
const dist = () => track.scrollWidth - innerWidth;
gsap.to(track, { x: () => -dist(), ease: "none",
  scrollTrigger: { trigger: ".rail", start: "top top", end: () => "+=" + dist(), pin: true, scrub: 1, invalidateOnRefresh: true, anticipatePin: 1 } });
```
Inner triggers use `containerAnimation: tween`. On mobile, consider a native `overflow-x: auto; scroll-snap-type: x mandatory` rail instead.

**R3 Scrubbed word-by-word statement** (large paragraph lights up as you read)
```js
const split = SplitText.create(".statement", { type: "words", aria: "auto" });
gsap.fromTo(split.words, { opacity: 0.15 }, { opacity: 1, stagger: 0.1, ease: "none",
  scrollTrigger: { trigger: ".statement", start: "top 75%", end: "bottom 40%", scrub: true } });
```

**R4 Mask / clip-path image reveal** (frame expands to full-bleed)
```js
gsap.fromTo(".media", { clipPath: "inset(18% 12% 18% 12% round 24px)", scale: 1.15 },
  { clipPath: "inset(0% 0% 0% 0% round 0px)", scale: 1, ease: "none",
    scrollTrigger: { trigger: ".media-wrap", start: "top 85%", end: "top 15%", scrub: true } });
```

**R5 Sticky split stage** (CSS sticky + content that swaps)
```css
.split { display: grid; grid-template-columns: 5fr 7fr; gap: var(--gutter); }
.split .stage { position: sticky; top: 0; height: 100svh; align-self: start; }
.split .step { min-height: 100svh; display: grid; align-content: center; }
```
Use IntersectionObserver or ScrollTrigger on each `.step` to set `data-step` on `.stage`; animate the stage in CSS
from that attribute. Often better than pin: native, robust, and accessible.

**R6 Stacked cards** (sticky, each covers the last; previous card scales/dims)
```css
.stack > .card { position: sticky; top: calc(var(--s-6) + var(--i) * 1rem); }
```
```js
gsap.utils.toArray(".stack > .card").forEach((c, i, all) => i < all.length - 1 && gsap.to(c, { scale: 0.94, filter: "brightness(.85)", ease: "none",
  scrollTrigger: { trigger: all[i + 1], start: "top 90%", end: "top 20%", scrub: true } }));
```

**R7 Depth parallax** (`data-speed` 0.8–1.2; layers with different speeds; transform only)
```js
gsap.utils.toArray("[data-speed]").forEach(el => gsap.to(el, { yPercent: () => (1 - +el.dataset.speed) * 30, ease: "none",
  scrollTrigger: { trigger: el, start: "top bottom", end: "bottom top", scrub: true, invalidateOnRefresh: true } }));
```
Subtle: ±15–30% travel. Parallax on everything is a tell.

**R8 Image-sequence scrub** (canvas frames; the "product turntable" effect)
```js
const N = 120, state = { f: 0 }, imgs = Array.from({ length: N }, (_, i) => Object.assign(new Image(), { src: `/seq/${String(i + 1).padStart(4, "0")}.webp` }));
const ctx = canvas.getContext("2d");
const draw = (img) => { /* cover-fit img into canvas, respecting devicePixelRatio */ };
gsap.to(state, { f: N - 1, snap: "f", ease: "none", onUpdate: () => draw(imgs[state.f]),
  scrollTrigger: { trigger: ".seq", start: "top top", end: "+=400%", scrub: 0.5, pin: true } });
```
≤ ~150 frames at ~1280px, WebP/AVIF, first frame drawn immediately, the rest loaded progressively; fewer frames on mobile.

**R9 Velocity marquee** (text strip speeds up and flips with scroll direction)
```js
const loop = gsap.to(".marquee__inner", { xPercent: -50, repeat: -1, duration: 30, ease: "none" });
ScrollTrigger.create({ onUpdate: s => gsap.to(loop, { timeScale: s.direction * Math.max(1, Math.abs(s.getVelocity() / 300)), overwrite: true, duration: .2 }) });
```
Duplicate the content once so `-50%` loops seamlessly. Pause when offscreen.

**R10 Counting numbers and drawing charts** (scrub or once)
`gsap.fromTo(obj, { v: 0 }, { v: 4821, snap: { v: 1 }, scrollTrigger: {…, once: true}, onUpdate: () => el.textContent = fmt(obj.v) })`;
`tabular-nums`. SVG paths: `DrawSVG` or `stroke-dashoffset`.

**R11 Chapter colour shifts** (background and ink change between sections)
Interpolate CSS variables with ScrollTrigger `onEnter`/`onEnterBack` or CSS `animation-timeline: view()` on a
`::before` layer; keep contrast valid in every state (verify each pair with `color.py`).

**R12 Page-level transitions** → `motion.md` §4.8 (View Transitions) or a GSAP exit/enter timeline on route change.

## 6. DOM-synced WebGL (shader images)

The look: images that bend, ripple or RGB-split with scroll velocity and hover. The structure: **real
`<img>`/text stay in the DOM** (SEO, a11y, no-JS fallback); a fixed full-viewport canvas draws textured planes
aligned to each image's bounding rect, updated every frame from the scroll position.

```js
// one orthographic camera in CSS pixels; one plane per [data-gl] image
const cam = new THREE.OrthographicCamera(-w/2, w/2, h/2, -h/2, -1000, 1000);
function sync(m, el) { const r = el.getBoundingClientRect();
  m.scale.set(r.width, r.height, 1); m.position.set(r.left + r.width/2 - w/2, -(r.top + r.height/2 - h/2), 0); }
// each frame (driven by gsap.ticker): meshes.forEach(sync), uniforms.uVel.value = lenis.velocity, render
```
```glsl
// fragment: RGB split proportional to scroll velocity
uniform sampler2D uTex; uniform float uVel; varying vec2 vUv;
void main(){ vec2 o = vec2(0.0, uVel * 0.02);
  gl_FragColor = vec4(texture2D(uTex, vUv + o).r, texture2D(uTex, vUv).g, texture2D(uTex, vUv - o).b, 1.0); }
```
Hide the DOM image with `opacity: 0` (not `display: none`) once its texture is ready; remove the effect and show
the `<img>` if WebGL fails or reduced motion is on. Lightweight options: OGL, curtains-style plane syncing, or
drei's `<Image>` and `<Scroll>` in R3F. Clamp DPR (`Math.min(devicePixelRatio, 1.75)`) and only render when something
moves.

## 7. 3D scenes

**Rule zero: 3D must carry the story** (product you can inspect, space you move through, data you can explore).
"3D for 3D's sake" is the 2026 equivalent of a spinning logo. If the subject is physical, 3D is earned.

### Architecture that works on real sites
Native page scroll stays in charge. A sticky full-viewport canvas lives inside a tall section; **ScrollTrigger (or
Lenis) writes a progress number into a mutable ref/store; the render loop reads it.** Never push 60fps scroll
values through React state.
```tsx
const progress = useRef(0);                      // 0..1, written by ScrollTrigger onUpdate
useGSAP(() => { ScrollTrigger.create({ trigger: ".journey", start: "top top", end: "bottom bottom", scrub: true,
  onUpdate: (s) => (progress.current = s.progress) }); }, { scope: root });

function Rig({ progress }) {
  const obj = useRef(); 
  useFrame((state, dt) => {
    const p = progress.current;
    easing.damp3(state.camera.position, [Math.sin(p * 3) * 1.2, 0.4 - p * 0.6, 6 - p * 3], 0.25, dt); // from "maath"
    state.camera.lookAt(0, 0, 0);
    obj.current.rotation.y = p * Math.PI * 2;
  });
  return <group ref={obj}><Product /></group>;
}
<div className="journey" style={{ height: "400svh" }}>
  <div style={{ position: "sticky", top: 0, height: "100svh" }}>
    <Canvas dpr={[1, 1.75]} camera={{ position: [0, 0.4, 6], fov: 35 }} frameloop="always">
      <Suspense fallback={null}><Rig progress={progress} /><Environment preset="studio" /></Suspense>
    </Canvas>
  </div>
  {/* DOM copy panels positioned over the canvas, animated by ScrollTrigger */}
</div>
```
`drei`'s `<ScrollControls pages={4} damping={0.2}>` + `useScroll()` (`offset`, `range(from, d)`, `curve(from, d)`,
`visible(from, d)`) + `<Scroll html>` is the fastest prototype, but it replaces native scrolling inside the canvas
(weaker for SEO, anchors and mixed pages). Prefer it for full-screen experiences; prefer the sticky pattern for sites.

### Vanilla three + GSAP camera path
```js
const curve = new THREE.CatmullRomCurve3([new THREE.Vector3(0,0.5,8), new THREE.Vector3(3,1,4), new THREE.Vector3(0,0.2,0)]);
const p = { t: 0 };
gsap.to(p, { t: 1, ease: "none", scrollTrigger: { trigger: ".journey", start: "top top", end: "bottom bottom", scrub: 0.8 },
  onUpdate: () => { camera.position.copy(curve.getPoint(p.t)); camera.lookAt(curve.getPoint(Math.min(p.t + 0.02, 1))); renderer.render(scene, camera); } });
```
Render on demand (in `onUpdate`, plus the ticker only while something animates) to save battery.

### Look: make it art-directed, not default
- **Lighting:** one environment (HDRI/`Environment`) + one key + a rim. Not seven lights.
- **Materials:** vary roughness; add subtle bump/noise; clearcoat or transmission for glass/lacquer; avoid flat
  `MeshStandardMaterial` grey. Use `MeshTransmissionMaterial` sparingly (it is expensive).
- **Palette:** feed your CSS token colours into uniforms/materials so 3D and DOM share one palette.
- **Grain/dither:** a final noise or dither pass prevents gradient banding and gives a filmic finish.
- **Camera language:** pick one (slow dolly, orbit, fly-through) and stay consistent. Damp camera motion
  (`easing.damp3`) so it feels heavy and expensive, never linear-jerky.
- **Pointer response:** ≤ 5° parallax toward the cursor; not a full orbit unless the object is meant to be inspected.
- **Loading is design:** a real progress counter/mask that matches the brand, then a clean handoff to the scene.
- **Text stays DOM.** Use `drei` `<Text>` (SDF) only for text that lives in 3D space.
- **No assets? Go procedural:** `TorusKnot`/`Icosahedron` with a displacement shader, `InstancedMesh` grids
  with wave functions (thousands of cubes for the cost of one draw call), particle `Points` with a custom shader, a
  full-screen raymarched SDF (metaballs, terrain) in a fragment shader. These are cheap, distinctive and asset-free.

### Useful libraries (R3F ecosystem)
`@react-three/fiber`, `@react-three/drei` (Environment, ScrollControls, useGLTF, Float, MeshTransmissionMaterial,
MeshDistortMaterial, ContactShadows, Html, Text, Image, View, AdaptiveDpr, PerformanceMonitor, Instances, Bvh,
Preload), `@react-three/postprocessing` (Bloom, Noise, Vignette, DepthOfField, ChromaticAberration; at most two on
mobile), `maath` (damp/ease helpers), `leva` (debug controls only; remove from prod), `@react-three/rapier`
(physics), `gltfjsx` (GLB → component), `@gltf-transform/cli` (Draco/Meshopt/KTX2 compression), `zustand`
(shared scene state). drei `<View>` lets **one** Canvas render into many DOM slots (multiple 3D thumbnails without
multiple WebGL contexts).

## 8. CSS 3D (cheap, charming)

For cards, device frames, tilt, flips and layered depth: no WebGL needed.
```css
.stage { perspective: 1200px; perspective-origin: 50% 30%; }
.tilt  { transform-style: preserve-3d; transform: rotateX(var(--rx, 0deg)) rotateY(var(--ry, 0deg));
         transition: transform var(--dur-fast) var(--ease-out); will-change: transform; }
.tilt .layer-1 { transform: translateZ(24px); } .tilt .layer-2 { transform: translateZ(56px); }
.tilt .shine { background: radial-gradient(400px circle at var(--mx) var(--my), rgb(255 255 255 / .18), transparent 60%); mix-blend-mode: soft-light; }
@media (hover: none), (prefers-reduced-motion: reduce) { .tilt { transform: none; } }
```
```js
// pointer tilt: ±8° max, smoothed with quickTo, only on fine pointers
const rx = gsap.quickTo(el, "--rx", { duration: .4, ease: "power3" }), ry = gsap.quickTo(el, "--ry", { duration: .4, ease: "power3" });
el.addEventListener("pointermove", e => { const r = el.getBoundingClientRect();
  ry(((e.clientX - r.left) / r.width - .5) * 16 + "deg"); rx(-((e.clientY - r.top) / r.height - .5) * 16 + "deg"); });
el.addEventListener("pointerleave", () => { rx("0deg"); ry("0deg"); });
```
Scroll-linked CSS 3D: bind `rotateX` of a "device" frame to `animation-timeline: view()` for a laptop that opens as
it scrolls into view.

## 9. Performance budgets

| Metric | Target |
|---|---|
| LCP | ≤ 2.5s on mid-range mobile (the hero must not wait for WebGL) |
| CLS | ≤ 0.1 (explicit `aspect-ratio`, font fallbacks, pinned sections measured after fonts load) |
| INP | ≤ 200ms |
| Scroll | 60fps; no long tasks > 50ms during scroll |
| JS (marketing, excl. 3D) | ≲ 170kB gzipped initial |
| 3D chunk | Lazy-loaded after LCP (`import()`/`React.lazy`/`next/dynamic` with `ssr: false`), ≲ 500kB gz |
| Models | ≲ 2–3MB compressed (Draco/Meshopt), textures ≤ 2048px (KTX2), ≲ 100 draw calls, ≲ 300–500k triangles |
| Pixel ratio | `dpr={[1, 1.75]}`; drop with `PerformanceMonitor` / `AdaptiveDpr` |

Tactics: `frameloop="demand"` + `invalidate()` for scenes that only change on scroll; pause the loop when the
canvas is offscreen; instance repeated meshes; bake ambient occlusion/lighting; reuse geometry/materials; dispose
on unmount; device-tier detection before loading the scene; serve a static poster for weak devices.

## 10. Accessibility and fallbacks

- **Content first:** all information is real DOM text/images; canvas is enhancement. Page works with JS off.
- **Reduced motion:** `gsap.matchMedia` / `useReducedMotion` → no pin/scrub/parallax/smooth-scroll; show the static
  end-state composition; keep 3D as a still render.
- **Don't trap scroll:** no pinning > ~3 viewports, no wheel hijacking, anchors/Find/keyboard (Space, PgDn, Tab)
  must work; Lenis stays on real scroll. Focus order follows visual order; focused elements are scrolled into
  view and never stuck behind pins.
- **Photosensitivity:** no flashing > 3 times/second; avoid full-screen strobing shader effects.
- **Text over WebGL/images:** verify contrast against the *worst* frame; add a scrim.
- **WebGL fallback:** feature-detect (`canvas.getContext("webgl2")`), catch context loss, show the poster image.
- **Pause control** for any autoplaying motion or video > 5s; mute by default.

## 11. Sandboxed pages (claude.ai artifacts)

When the output is a self-contained HTML page published from a sandbox: external scripts may only come from an
allow-list (cdnjs, jsDelivr `/npm/`, the Tailwind CDN, jQuery CDN); stylesheets only from Google Fonts; **no remote
images or network requests**; pin exact versions (≥ 2 weeks old); load libraries as UMD `<script>` tags before your inline
script; the file must stay < 16MB. Therefore:
- GSAP + ScrollTrigger from cdnjs (`gsap.min.js`, `ScrollTrigger.min.js`); verify the version path exists, or use jsDelivr `/npm/gsap@<version>/dist/`.
- three.js as a UMD build from cdnjs; **no external GLB/HDRI**, so go procedural (see §7) and embed textures as data URIs
  only when tiny.
- Fonts: choose from the Google Fonts pairings in `foundations.md`.
- Dark/light: tokens on `:root` with `prefers-color-scheme` variants; real second palette.
- `localStorage` access in try/catch; never assume `window.storage` / Claude API exist in a published page.
- Prefer CSS scroll-driven animations + small JS (IntersectionObserver) when the effect is simple, which avoids the library entirely.
