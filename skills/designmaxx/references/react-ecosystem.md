# React ecosystem: what to use, what to steal, what to avoid

Libraries give you behaviour, accessibility and technique. They must never give you your **visual identity**:
an unmodified component library is the single biggest source of cloned-looking sites. Rule: *take the
mechanism, replace the skin.*

## Contents
1. Stack by concern
2. Learn from the animated component libraries (adopt / adapt / avoid)
3. Theming shadcn/Tailwind v4 to your tokens
4. Integration patterns (Next.js, client boundaries, one-library-per-concern)
5. Starter structure
6. Dependency hygiene

---

## 1. Stack by concern

| Concern | Pick | Notes |
|---|---|---|
| Accessible primitives | **Radix UI**, **Base UI**, **React Aria** (or shadcn/ui built on them) | Dialog, Popover, Menu, Tabs, Tooltip, Select, Slider. Don't hand-roll focus traps and ARIA |
| Styling | **Tailwind v4** (CSS-first `@theme`) or CSS Modules/vanilla-extract; tokens from `assets/tokens.css` | Utilities fine; avoid arbitrary-value soup and untouched default palette |
| Components | **shadcn/ui** (copy-in source) | A starting point to restyle, never the final look |
| UI motion | **Motion** (`motion/react`) | Enter/exit, layout, shared element, gestures, `useScroll`. `LazyMotion` + `domAnimation` + `m.*` for ~5kB core |
| Timelines / scroll / text / Flip | **GSAP** + `@gsap/react` (`useGSAP`) + ScrollTrigger, SplitText, Flip | Official skills: core, timeline, scrolltrigger, plugins, utils, react, performance, frameworks |
| Smooth scroll | **Lenis** (`lenis/react`) | Synced to GSAP ticker; disabled for reduced motion |
| 3D | **@react-three/fiber** + **drei** (+ `postprocessing`, `maath`, `rapier`, `zustand`) | Lazy-load; `dynamic(..., { ssr: false })` in Next |
| Choreographed sequences/design-tool timelines | **Theatre.js** (R3F integration) | For art-directed 3D animation authored in a timeline editor |
| Physics-feel springs | Motion springs, `@react-spring/web` / `/three` | Prefer `bounce: 0` unless the object is physical |
| Carousels/sliders | **Embla** | Headless, accessible with plugins; style yourself |
| Drawers, toasts, command menu | **Vaul**, **Sonner**, **cmdk** | Great mechanics; restyle |
| Charts | **visx**, **Recharts**, **D3** (math/scales) | Custom-style; direct labels; own palette |
| Forms | React Hook Form + Zod | Design all states (focus, error, disabled, loading) |
| Icons | One set at one stroke weight (e.g. Phosphor, Lucide, Tabler) or custom SVG | Match stroke to type weight; delete icon tiles |

## 2. Learn from the animated component libraries

React Bits, Magic UI, Aceternity UI, Motion Primitives, Cult UI and similar registries ship copy-paste components
(usually via the shadcn CLI, so you own the source). They are excellent **technique references** and dangerous
**defaults**. React Bits tends to be lighter on dependencies (GSAP/Canvas/OGL-based for many pieces), while
Aceternity and Magic UI lean on Motion and ship dramatic, marketing-shaped effects. Check each component
for reduced-motion support before using it; not all handle it.

| Technique (found across these libraries) | Verdict | How to use it well |
|---|---|---|
| **Blur/split text reveal** | Adopt (once) | Hero headline only; keep accessible text |
| **Count-up / number ticker** | Adopt | Real figures only; `tabular-nums`; trigger once in view |
| **Velocity marquee / scroll velocity text** | Adopt | Recipe R9; pause offscreen; reduced-motion = static row |
| **Scroll-stack / sticky stacked cards** | Adopt | Recipe R6 with real, varied content |
| **Magnetic buttons / cursor-follow** | Adapt | One primary CTA, ≤ 8px pull, fine pointers only |
| **Spotlight card (cursor-lit border)** | Adapt | One dense grid, not every card; subtle; gate on `hover: hover` |
| **Tilt card (3D parallax)** | Adapt | `scroll-and-3d.md` §8; ±8°; once per page |
| **Dock magnification** | Adapt | Only for an actual dock/tool palette |
| **Animated tabs/pill indicator (`layoutId`)** | Adopt | Shared-element indicator; interruptible |
| **Bento grid with animated beams** | Avoid | Tile content must justify tile size; no decorative beams |
| **Aurora / gradient-mesh / "grid + spotlight" backgrounds** | Avoid | Peak AI tell; use imagery, texture or flat colour |
| **Meteors, sparkles, border-beam, shimmer text, typewriter headline** | Avoid | Ambient decoration with no meaning |
| **Rotating dotted globe** | Avoid unless geographic | Use a map that shows real data |
| **Infinite logo carousel of invented brands** | Avoid | Real customers or nothing |
| **Particles / WebGL backgrounds** | Adapt carefully | Must express the subject; budgeted; static fallback |
| **Lanyard/3D hanging badge, card-swap, infinite menu** | Adapt | Fun showcase moments; Tier 2 only, one per page |

**Process for using a registry component:** (1) install it as source, (2) delete effects you don't need, (3)
replace colours/radii/easing/durations with your tokens, (4) add reduced-motion and keyboard behaviour, (5)
run `slop_scan.py`, (6) check the bundle impact. If, after restyling, it still looks like the library's demo,
rebuild it.

## 3. Theming shadcn / Tailwind v4 to your tokens

Never ship the default zinc/slate theme. Map shadcn variables to your palette roles once:

```css
@import "tailwindcss";
@import "./tokens.css";                          /* assets/tokens.css */

:root {                                           /* shadcn variable names → your roles */
  --background: var(--bg);        --foreground: var(--ink);
  --card: var(--surface);         --card-foreground: var(--ink);
  --popover: var(--surface);      --popover-foreground: var(--ink);
  --primary: var(--accent);       --primary-foreground: var(--on-accent);
  --secondary: var(--accent-wash);--secondary-foreground: var(--ink);
  --muted: var(--accent-wash);    --muted-foreground: var(--muted);
  --accent: var(--accent-wash);   /* shadcn's "accent" is a hover wash, not a brand colour */
  --border: var(--line);          --input: var(--line);   --ring: var(--accent);
  --radius: var(--r-md);
}

@theme inline {                                   /* expose tokens as Tailwind utilities */
  --color-bg: var(--bg);  --color-surface: var(--surface);  --color-ink: var(--ink);
  --color-muted-ink: var(--muted);  --color-line: var(--line);
  --color-brand: var(--accent);  --color-brand-2: var(--accent-2);
  --font-display: var(--font-display);  --font-body: var(--font-body);  --font-mono: var(--font-mono);
  --ease-out: cubic-bezier(.25, 1, .5, 1);
  --radius-inner: var(--r-inner);  --radius-outer: var(--r-outer);
}
```
Note the clash: shadcn's `--accent` means a subtle hover background, not your brand accent; rename your brand
variable (e.g. `--brand`) in Tailwind land to avoid confusion. Then restyle the components: radius by role, layered shadows,
real focus rings, your type scale. Delete default `rounded-xl border shadow-sm` repetition by creating two or three
named container variants.

## 4. Integration patterns

**Next.js App Router.** Server Components by default; put animation in small `"use client"` leaf components.
3D and heavy scroll scenes: `const Scene = dynamic(() => import("./Scene"), { ssr: false, loading: Poster })`.
Never import `gsap`, `three` or `lenis` in a server file.

**One animation library per concern, one per subtree.** Motion for UI state, GSAP for scroll scenes and
timelines, R3F for 3D. Share state via refs/stores, not by animating the same element from two libraries.

**Scroll value → render loop through a ref**, not state (see `scroll-and-3d.md` §7).

**Cleanup is part of the feature.** `useGSAP` (auto revert), `ScrollTrigger.kill()`, `lenis.destroy()`,
`renderer.dispose()`, remove ticker callbacks and observers on unmount. Strict Mode double-mount must not duplicate
triggers.

**Reduced motion everywhere.** `MotionConfig reducedMotion="user"`; `gsap.matchMedia`; a CSS block;
R3F: render a still frame / skip camera animation.

**Server-rendered content stays real.** Headings, paragraphs and links render as HTML; split-text and canvases
enhance them (`aria-label` on the split heading; hidden pieces `aria-hidden`).

**Images/fonts.** `next/image` / `next/font` with explicit dimensions and fallbacks; pick your own fonts, not
the `next/font` default (Inter) the template ships with.

## 5. Starter structure

```
src/
  styles/ tokens.css  globals.css           # palette roles, type, space, motion tokens
  components/
    ui/        # restyled primitives (Button, Dialog, Menu…): the design system
    motion/    # Reveal (once), Magnetic, Marquee, CountUp: shared behaviours w/ reduced-motion
    scenes/    # R3F / WebGL, lazy loaded, each with a Poster fallback
  lib/ gsap.ts (registerPlugin once)  lenis.tsx  use-reduced-motion.ts
  app/ …
```
`lib/gsap.ts` registers `useGSAP`, `ScrollTrigger`, `SplitText`, `Flip` once and re-exports `gsap`; components import
from there.

## 6. Dependency hygiene

- Every dependency needs a reason you can state in one sentence. No library for one effect you can do in 10 lines of CSS.
- Pin versions; check bundle impact (`next build` analyzer / `vite-bundle-visualizer`); lazy-load anything over ~30kB
  that isn't needed for first paint.
- Prefer copy-in source (shadcn-style) for components you will restyle; prefer packages for engines (GSAP, three, Motion).
- Read each library's licence (GSAP's current licence; font licences; model/asset licences).
