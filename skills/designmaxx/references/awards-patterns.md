# Awards-grade patterns (CSS Design Awards, Awwwards, FWA)

What the sites that win these shows have in common, and how to reproduce the *quality bar* without copying
anyone's work. Study the techniques, never the layouts: cloning a winning site is itself a slop pattern.

## Contents
1. How the juries judge
2. What winners share
3. Pattern catalog (with how to build)
4. Craft bar: the details juries notice
5. Awards-grade checklist
6. Where to study (and how)

---

## 1. How the juries judge

- **CSS Design Awards** weights **UI design 40%, UX 30%, innovation 30%**. It rewards clean, original
  front-end craft over raw spectacle, and is broader than Awwwards/FWA (more brand, SaaS and commerce sites).
- **Awwwards** scores design, usability, creativity and content; a Site of the Day needs an average around 8.0+.
  Developer score covers semantic markup, performance and responsiveness.
- **FWA** leans experimental and interactive (WebGL, installations).

Implication: spectacle alone does not win. **Usability and performance are scored.** A beautiful site that
janks, blocks keyboard users, or hides its content loses points, and your user's trust.

## 2. What winners share

1. **A concept, not a template.** One idea expressed everywhere (a metaphor, a material, a rule system).
2. **Typography as the hero.** Oversized or kinetic type, confident scale contrast, a distinctive face, set with
   care (tight display tracking, real quotes, balanced wraps).
3. **A restrained palette** with one or two decisive colours; large flat fields; rare gradients.
4. **Scroll-driven narrative** with pacing: intense beats and still beats; a clear ending.
5. **One signature interaction** you remember: a cursor behaviour, a transition, a shader, a physical object.
6. **Motion with authored easing.** Consistent curves and durations (tokens), orchestrated entrances, no randomness.
7. **Grid discipline *and* deliberate rule-breaking.** A strict grid so the broken moment reads as intent.
8. **Craft in the small stuff:** hover states, focus rings, loaders, 404, footer, form microcopy, cursor, selection colour.
9. **Real content and imagery** art-directed to the concept; not stock.
10. **Performance and accessibility as design constraints** (fast LCP, reduced-motion path, mobile parity).
11. **Mobile is designed, not shrunk:** different interactions where desktop ones don't translate.

## 3. Pattern catalog

| Pattern | What it is | Build with | Watch out |
|---|---|---|---|
| **Kinetic hero type** | Headline reveals by word/line (mask slide-up), optional variable-font weight/width shift on hover/scroll | SplitText + `expo.out`; `font-variation-settings` | Once only; keep text accessible |
| **Pinned scene + scrubbed object** | Section pins; object transforms; copy swaps | ScrollTrigger timeline, `scrub: .6` | ≤ 3 viewports; reduced-motion static |
| **Horizontal rail** | Section scrolls sideways | `scroll-and-3d.md` R2 | Native snap rail on mobile |
| **Mask/clip expand** | Image frame grows to full-bleed | R4 | Provide aspect-ratio to avoid CLS |
| **Word-by-word reading reveal** | Statement lights up as it scrolls | R3 | Keep contrast ≥ 4.5:1 at the lowest opacity that carries meaning (don't use 0.15 for essential text, or provide a static state) |
| **Index/ledger hover preview** | Rows of project names; hovering shows a floating image following the cursor | `gsap.quickTo` for x/y, `hover: hover` gate | Keyboard focus must trigger the same preview |
| **Custom cursor** | Dot/ring that scales over links, shows labels ("View", "Drag") | Pointer events + `quickTo`; hide on coarse pointers | Never remove the real cursor for text inputs; contrast; no lag |
| **Shader image distortion** | Images bend/RGB-split with velocity or hover | `scroll-and-3d.md` §6 | WebGL fallback to plain `<img>` |
| **Scroll-scrubbed image sequence** | Product turntable / process frames on canvas | R8 | Frame budget; mobile fewer frames |
| **3D product/space** | Object or environment moves with scroll | `scroll-and-3d.md` §7 | Lazy load; poster; story-justified |
| **Marquee with velocity** | Text strip reacts to scroll speed | R9 | Pause offscreen; static for reduced-motion |
| **Page transition** | Route change morphs shared elements or wipes | View Transitions / GSAP | Must not delay the page; skip for reduced-motion |
| **Preloader with meaning** | Counter or mask that reveals the hero | CSS/GSAP; real progress | Keep ≤ ~1.5s perceived; never block content for fast loads |
| **Sticky split stage** | One side sticky, other scrolls | R5 | Native sticky beats pin |
| **Menu as an experience** | Full-screen index overlay with staggered links | Dialog/popover + stagger | Focus trap, Esc to close, `aria-expanded` |
| **Type-and-image collisions** | Display type overlapping imagery with `mix-blend-mode` | CSS blend modes | Check legibility across the image |
| **Texture and grain** | SVG noise or canvas grain over flat colour | `feTurbulence` / small PNG tile | Keep opacity ≤ 6–8%; costly on large layers, pre-render |

## 4. Craft bar: the details juries notice

- **Authored easing everywhere** (no browser default `ease`); a consistent token set for duration and curve.
- **Hover/focus/active/disabled/loading/empty/error** for every interactive element, consistent across the site.
- **Selection colour**, scrollbar styling (subtle), caret colour, `accent-color` on form controls.
- **Optical details** from `surfaces-and-feel.md`: concentric radii, optical alignment, tabular numbers, image outlines.
- **Microcopy with a voice**, specific and short (`Download the 2026 tide table (PDF, 2 MB)`, not `Learn more →`).
- **A designed 404, empty states, and footer.** They are free points and free personality.
- **Cursor and pointer behaviour** that respects touch (`pointer: coarse`) and keyboard users.
- **Smooth, stable layout:** no CLS from fonts/images/pins; text does not jump when numbers change.
- **A deliberate loading sequence** and a graceful no-JS/no-WebGL experience.
- **Sound:** off by default; never autoplay.
- **Consistent grid and baseline;** the "break" is one thing, on purpose.

## 5. Awards-grade checklist

- [ ] One-sentence concept that explains the type, colour, motion and imagery choices
- [ ] Palette from the subject; tinted neutrals; contrast verified (`color.py palette`)
- [ ] Distinctive type pairing set with care; fails the "default font" test
- [ ] First screen is characteristic of the subject (not the hero template)
- [ ] Scroll storyboard with beats, rests and an ending; each motion carries meaning
- [ ] Exactly one signature interaction; everything else is quiet
- [ ] Motion tokens used everywhere; no `ease`, no bounce, no `transition: all`
- [ ] Every interactive state designed; focus-visible clear; hit areas ≥ 40px
- [ ] Mobile designed separately (interactions adapted, not just stacked)
- [ ] Reduced-motion and no-JS/no-WebGL paths verified
- [ ] LCP ≤ 2.5s, CLS ≤ 0.1, INP ≤ 200ms; 3D lazy-loaded
- [ ] `python3 scripts/slop_scan.py` exits 0; swap test fails (could only be this subject)
- [ ] Real content; fake logos/testimonials/metrics absent

## 6. Where to study (and how)

Browse CSS Design Awards, Awwwards (Sites/Elements of the Day, by technology: GSAP, WebGL, 3D, React), FWA,
Godly, Siteinspire, Land-book, and agency work from studios known for scroll and WebGL craft. For each
reference, write down only **technique and intent**: what the motion communicates, how it is paced, which
property is animated, how it degrades on mobile. Then design your own composition from your subject's world. Use
DevTools (Performance, Layers, Animations panels) and the sources of GSAP/three sites to learn how effects are
actually constructed.
