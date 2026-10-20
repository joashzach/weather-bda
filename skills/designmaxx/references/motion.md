# Motion: UI transitions and micro-interactions

For scroll-driven storytelling and 3D, read `scroll-and-3d.md`. This file is about interface motion: the
transitions that make menus, modals, numbers, text, panels and pages feel inevitable. It folds in the pattern
library idea from transitions.dev (namespaced `t-*` selectors, semantic duration/easing tokens, documented HTML
hooks, a reduced-motion guard on every snippet, and "prefer the lower-overhead transition").

## Contents
1. Principles
2. Motion tiers (how much motion this project gets)
3. Tokens and easing
4. Recipes (12 transitions)
5. Orchestration: stagger, lead/follow, shared elements
6. Libraries: CSS vs Motion vs GSAP vs View Transitions
7. Reduced motion and performance

---

## 1. Principles

1. **Motion answers or narrates.** It shows *what changed* in response to an action (open, expand, confirm,
   reorder), or it tells a story (a scroll sequence). Motion that does neither is decoration; cut it.
2. **Frequency inverts intensity.** The more often a user triggers something, the less it animates. Keyboard
   shortcuts and command palettes: near-instant. A modal that appears once per session: a bit more.
3. **Origin matters.** A dropdown grows from its trigger (`transform-origin` at the trigger edge), a modal from the
   centre, a toast from where it will rest. Motion should respect the spatial model.
4. **Enter slow, exit fast.** Exits ≈ 60–70% of the enter duration and visually smaller.
5. **Ease out for things arriving, ease in-out for things travelling across the screen, ease in rarely.**
6. **Never bounce.** No elastic, back, or overshoot easing in UI. Springs use `bounce: 0`. Overshoot reads as a toy.
7. **Interruptible.** UI that can be retriggered uses transitions/springs that retarget mid-flight, never keyframes.
8. **Blur as a softener.** A 4–6px blur on opacity cross-fades hides the "two things overlapping" artefact and
   makes text swaps and panel changes feel like one object morphing. Use briefly (≤ 300ms).
9. **Duration scales with distance and size.** Small = 120–200ms, medium = 240–320ms, large/full-screen =
   400–500ms. Over 500ms on an input-driven UI feels laggy. Reserve 800ms+ for a single orchestrated entrance.
10. **One hero motion per view.** Everything else supports it or stays still.

## 2. Motion tiers

Declare the tier in your plan. It sets budgets and prevents over-animation.

| Tier | Context | Allowed | Not allowed |
|---|---|---|---|
| **0: Quiet** | Tools, dashboards, forms, docs | Micro-interactions ≤ 240ms; dropdown/modal/toast/tab transitions; number and text swaps; skeleton → content | Entrance choreography, scroll effects, ambient motion |
| **1: Branded** | Marketing sites, product pages | Tier 0 + one signature moment (hero reveal *or* one scroll sequence) + view transitions | Scroll-jacking, many independent reveals, 3D for its own sake |
| **2: Showcase** | Awards-style, campaign, portfolio | Tier 1 + scroll narrative (pin/scrub/horizontal), DOM-synced WebGL, 3D scenes, kinetic type; performance budget enforced | Anything that blocks content, keyboard nav, or reduced-motion |

## 3. Tokens and easing

Tokens live in `assets/tokens.css` (`--dur-*`, `--ease-*`, `--stagger`, `--press-scale`). Semantic use:

| Token | Value | Use |
|---|---|---|
| `--dur-instant` | 90ms | press feedback, toggle thumb |
| `--dur-fast` | 160ms | hover/focus colour, tooltips, small exits |
| `--dur-base` | 240ms | menus, popovers, small reveals |
| `--dur-slow` | 420ms | modals, side panels, card resize |
| `--dur-cinema` | 800ms | hero entrance only |
| `--ease-out` | `cubic-bezier(.25,1,.5,1)` | default for entering/state change |
| `--ease-out-x` | `cubic-bezier(.16,1,.3,1)` | big, confident entrances (expo) |
| `--ease-in-out` | `cubic-bezier(.65,0,.35,1)` | travelling across the screen |
| `--ease-ui` | `cubic-bezier(.2,0,0,1)` | cross-fades, icon swaps |

GSAP equivalents: `power2.out` ≈ quad, `power3.out` ≈ cubic, `power4.out` ≈ quart, `expo.out`, `power2.inOut`.
Set `gsap.defaults({ ease: "power3.out", duration: 0.6 })`. Never use `elastic.*`, `bounce.*`, `back.*`.

## 4. Recipes

All use `t-` namespaced classes and tokens; each is wrapped by the reduced-motion rule in `tokens.css`.
Choose the lowest-overhead recipe that fits (card resize before panel reveal; dropdown before modal; inline
check before a celebration).

### 4.1 Card resize (animate to `height: auto`)
```css
.t-resize { display: grid; grid-template-rows: 0fr; transition: grid-template-rows var(--dur-slow) var(--ease-out); }
.t-resize[data-open="true"] { grid-template-rows: 1fr; }
.t-resize > * { overflow: hidden; min-height: 0; }
/* Alternative where supported: :root { interpolate-size: allow-keywords; }  .panel { height: 0; transition: height .4s; }  .panel[open] { height: auto; } */
```

### 4.2 Number pop-in (digits re-enter on change)
```js
function popNumber(el, text) {
  el.setAttribute("aria-label", text);
  el.innerHTML = [...text].map(c => `<span class="t-digit" aria-hidden="true">${c}</span>`).join("");
  el.querySelectorAll(".t-digit").forEach((d, i) => d.animate(
    [{ transform: "translateY(0.4em)", filter: "blur(4px)", opacity: 0 }, { transform: "none", filter: "blur(0)", opacity: 1 }],
    { duration: 320, delay: i * 28, easing: "cubic-bezier(.25,1,.5,1)", fill: "both" }));
}
```
```css
.t-digit { display: inline-block; font-variant-numeric: tabular-nums; }
```

### 4.3 Notification badge
```css
.t-badge { position: absolute; inset: -4px -4px auto auto; scale: 1; opacity: 1;
  transition: scale var(--dur-base) var(--ease-out), opacity var(--dur-fast) var(--ease-out); }
@starting-style { .t-badge { scale: 0.4; opacity: 0; } }
.t-badge[hidden] { display: none; }
```

### 4.4 Text states swap (e.g. "Save" → "Saved")
Stack both labels in one grid cell; toggle `data-state`.
```css
.t-swap { display: inline-grid; } .t-swap > * { grid-area: 1 / 1; transition: opacity var(--dur-fast) var(--ease-ui), translate var(--dur-fast) var(--ease-ui), filter var(--dur-fast) var(--ease-ui); }
.t-swap > [data-s="b"] { opacity: 0; translate: 0 0.35em; filter: blur(4px); }
.t-swap[data-state="b"] > [data-s="a"] { opacity: 0; translate: 0 -0.35em; filter: blur(4px); }
.t-swap[data-state="b"] > [data-s="b"] { opacity: 1; translate: 0 0; filter: blur(0); }
```
Mark the visible state with `aria-live="polite"` on the container if the change carries meaning.

### 4.5 Menu dropdown (origin-aware)
```css
.t-menu { transform-origin: var(--origin, top left); opacity: 0; scale: 0.96; translate: 0 -4px;
  transition: opacity var(--dur-fast) var(--ease-out), scale var(--dur-fast) var(--ease-out), translate var(--dur-fast) var(--ease-out),
              display var(--dur-fast) allow-discrete, overlay var(--dur-fast) allow-discrete; }
.t-menu:popover-open { opacity: 1; scale: 1; translate: 0 0; }
@starting-style { .t-menu:popover-open { opacity: 0; scale: 0.96; translate: 0 -4px; } }
```
Set `--origin` from the trigger side (`top right` for a right-aligned trigger). Use the Popover API
(`popover`, `popovertarget`) for light-dismiss and focus handling for free.

### 4.6 Modal open / close (scale-up in, softer scale-down out)
```css
dialog.t-modal { opacity: 0; scale: 0.96; translate: 0 8px;
  transition: opacity var(--dur-fast) var(--ease-out), scale var(--dur-fast) var(--ease-out), translate var(--dur-fast) var(--ease-out),
              display var(--dur-fast) allow-discrete, overlay var(--dur-fast) allow-discrete; }  /* exit: fast */
dialog.t-modal[open] { opacity: 1; scale: 1; translate: 0 0;
  transition-duration: var(--dur-base), var(--dur-base), var(--dur-base), var(--dur-base), var(--dur-base); } /* enter: base */
@starting-style { dialog.t-modal[open] { opacity: 0; scale: 0.96; translate: 0 8px; } }
dialog.t-modal::backdrop { background: color-mix(in oklab, var(--ink) 42%, transparent); opacity: 0;
  transition: opacity var(--dur-base) var(--ease-out), display var(--dur-base) allow-discrete, overlay var(--dur-base) allow-discrete; }
dialog.t-modal[open]::backdrop { opacity: 1; }
@starting-style { dialog.t-modal[open]::backdrop { opacity: 0; } }
```
Use native `<dialog>.showModal()` for focus trap, Esc, and inert background.

### 4.7 Panel reveal with cross-blur (side panel / step change)
```css
.t-panel-in  { animation: t-panel-in  var(--dur-slow) var(--ease-out-x) both; }
.t-panel-out { animation: t-panel-out var(--dur-base) var(--ease-ui)    both; }
@keyframes t-panel-in  { from { opacity: 0; translate: 24px 0; filter: blur(6px); } }
@keyframes t-panel-out { to   { opacity: 0; translate: -12px 0; filter: blur(4px); } }
```
(Keyframes are fine here: it's a one-shot staged transition. For anything retriggerable use transitions.)

### 4.8 Page slide (cross-document or same-document)
```css
@view-transition { navigation: auto; }                       /* cross-document, progressive enhancement */
::view-transition-old(root) { animation: t-out var(--dur-base) var(--ease-ui) both; }
::view-transition-new(root) { animation: t-in  var(--dur-slow) var(--ease-out-x) both; }
@keyframes t-out { to   { opacity: 0; translate: -3% 0; filter: blur(4px); } }
@keyframes t-in  { from { opacity: 0; translate:  4% 0; filter: blur(6px); } }
```
Same-document: `document.startViewTransition?.(() => update()) ?? update();`. Give shared elements a
`view-transition-name` (unique per element) to morph a thumbnail into a hero.

### 4.9 Success check (inline confirmation)
```css
.t-check path { stroke: currentColor; stroke-width: 2; fill: none; stroke-linecap: round; stroke-linejoin: round;
  stroke-dasharray: 24; stroke-dashoffset: 24; transition: stroke-dashoffset var(--dur-slow) var(--ease-out) var(--dur-fast); }
.t-check[data-done="true"] path { stroke-dashoffset: 0; }
```
Pair with a label swap (4.4) and a `role="status"` live region. Skip confetti unless the moment is genuinely a
celebration.

### 4.10 Error shake
```css
.t-shake { animation: t-shake 280ms var(--ease-out); }
@keyframes t-shake { 20% { translate: -6px 0; } 40% { translate: 5px 0; } 60% { translate: -3px 0; } 80% { translate: 2px 0; } }
@media (prefers-reduced-motion: reduce) { .t-shake { animation: none; outline: 2px solid currentColor; } }
```
Always accompany with text that says what went wrong and how to fix it (`aria-describedby`/`role="alert"`).
Motion alone is not an error message.

### 4.11 Avatar group hover (spacing opens)
```css
.t-stack { display: flex; } .t-stack > * { margin-inline-start: -10px; transition: margin var(--dur-base) var(--ease-out); }
.t-stack > *:first-child { margin-inline-start: 0; }
@media (hover: hover) { .t-stack:hover > * + * { margin-inline-start: 2px; } }
```

### 4.12 Words reveal (once, in the hero)
```js
// split with SplitText (GSAP, free) or: text.split(" ").map(w => `<span class="w"><span>${w}</span></span>`).join(" ")
gsap.from(".w > span", { yPercent: 110, duration: 0.9, ease: "expo.out", stagger: 0.04 });
```
```css
.w { display: inline-block; overflow: clip; vertical-align: top; padding-bottom: .08em; }
```
Do this for the hero only. Splitting every heading is the fade-up-everywhere tell again. Keep the original text
accessible (`aria-label` on the heading, `aria-hidden` on pieces; SplitText's `aria: "auto"` does this).

## 5. Orchestration

- **Lead and follow.** One element leads (heading), others follow 60–100ms behind in reading order. Cap total ≈ 600ms.
- **Group by meaning.** Stagger *chunks* (heading, body, actions), not every `<li>` unless it is a real list.
- **Shared element transitions** (`layoutId` in Motion, `Flip` in GSAP, `view-transition-name` in the browser):
  the strongest "this is the same thing" cue. Use them for list→detail, thumbnail→hero, tab indicator.
- **Direction is meaning.** Forward navigation moves content left/up; back reverses. Don't mix.
- **Don't animate load for what's already there** (see `surfaces-and-feel.md` #15).

## 6. Choosing a tool

| Need | Use |
|---|---|
| hover, focus, press, toggles, menus, dialogs, accordions, simple reveals | **CSS** (transitions, `@starting-style`, Popover/dialog, `grid-template-rows`) |
| React enter/exit, layout and shared-element animation, gestures, springs, `useScroll` | **Motion** (`motion/react`, formerly Framer Motion), `LazyMotion` + `m.*` + `domAnimation` for a ~5kB core |
| timelines, sequencing, SplitText, ScrollTrigger, Flip, SVG, canvas/WebGL values | **GSAP** (+ `@gsap/react` `useGSAP`) |
| route/page-level morphs, thumbnail → detail | **View Transitions API** |
| scroll-linked effects with no JS | **CSS scroll-driven animations** (`animation-timeline`), see `scroll-and-3d.md` |

Pick **one** JS animation library per concern. Motion + GSAP in the same component tree is usually a smell;
if both are needed, give each its own subtree (e.g. Motion for UI, GSAP for the hero scroll scene).

React specifics (Motion):
```tsx
import { MotionConfig, AnimatePresence, LazyMotion, domAnimation, m } from "motion/react";
<LazyMotion features={domAnimation} strict>
  <MotionConfig reducedMotion="user" transition={{ type: "spring", duration: 0.3, bounce: 0 }}>
    <AnimatePresence initial={false} mode="popLayout">
      {open && <m.div key="menu" initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.98, transition: { duration: 0.12 } }} style={{ transformOrigin: "top left" }} />}
    </AnimatePresence>
  </MotionConfig>
</LazyMotion>
```
`MotionConfig reducedMotion="user"` disables transform/layout animation for users who ask, keeping opacity.

## 7. Reduced motion and performance

- Respect `prefers-reduced-motion: reduce` globally (`tokens.css`) **and** for JS (`gsap.matchMedia`,
  `useReducedMotion`). The reduced experience still *works*: replace movement with opacity or an instant state
  change; replace scrubbed scroll scenes with their final static state.
- Animate `transform`, `opacity`, `filter`, `clip-path` only. Measure with the Performance panel; target 60fps
  and INP < 200ms. Avoid animating `box-shadow` (animate the opacity of a pseudo-element holding the shadow).
- Keep `will-change` temporary. Avoid large blurred layers (`filter: blur(40px)` on big areas is expensive).
- Pause offscreen/looping motion (`IntersectionObserver`), and never auto-play more than ~5 seconds of motion without a pause control.
