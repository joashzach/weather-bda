---
name: designmaxx
description: Design and refine distinctive web interfaces with strong typography, deliberate color, clean composition, and smooth interactive motion. Includes Joshua’s design preferences, color verification, UI polish, GSAP scroll storytelling, React animation guidance, and an anti-slop scanner. Use for frontend design, redesign, and animation work.
---

# designmaxx

Build interfaces that feel *chosen*, not generated. This skill combines: an art-direction process that
forces subject-specific decisions; foundations (colour, type, space, layout) with verified values; the
small-details polish layer; a motion system (UI transitions, scroll storytelling, 3D); and mechanical
anti-slop checks. It complements the built-in `frontend-design` skill (read it too if it is available) and
adds depth, numbers, recipes and a scanner.

Sources distilled here: Impeccable (design vocabulary, anti-pattern catalog, critique/polish workflow),
Transitions.dev (token-driven UI transitions), the official GSAP agent skills (core, timeline,
ScrollTrigger, React, performance), "make-interfaces-feel-better" (16 polish rules), CSS Design Awards /
Awwwards patterns, OKLCH/typography/spacing design-system skills, and the R3F + animated-component React
ecosystem.

## Personal design preferences

Read [Joshua’s preferences](references/joshua-preferences.md) before choosing a visual direction for his work. These are user-specific defaults inferred from direct feedback and his explicit approval of the Monsoon storm-instruments edition. They override conflicting aesthetic defaults in this skill for Joshua’s projects; they are not universal design laws. A newer brief, existing mandatory brand system, accessibility, or functional needs can supersede them. Do not infer deployment, messaging, account access, or other external authorization from this profile.

## Reference map (read only what the task needs)

| When | Read |
|---|---|
| **Always, before planning and before finishing** | `references/anti-slop.md` |
| Choosing palette, fonts, spacing, layout archetype | `references/foundations.md` |
| Polish pass, reviewing existing UI, "feels off" | `references/surfaces-and-feel.md` |
| Menus, modals, toasts, tabs, number/text swaps, page transitions, easing, React enter/exit | `references/motion.md` |
| Scroll animation, pinning, parallax, smooth scroll, shader images, 3D, CSS 3D, performance budgets, sandboxed pages | `references/scroll-and-3d.md` |
| React/Next.js stack, component libraries, shadcn/Tailwind theming | `references/react-ecosystem.md` |
| Showcase / awards-style work, craft checklist | `references/awards-patterns.md` |

Assets and scripts (all offline, stdlib-only):
- `assets/tokens.css`: drop-in tokens (palette roles, fluid type, 4pt space, radii, layered shadows, motion, base rules, reduced motion).
- `scripts/color.py`: `contrast`, `oklch`, `ramp`, `tint`, `palette` (WCAG 2.x + APCA). Never claim a contrast ratio you haven't computed.
- `scripts/slop_scan.py`: deterministic detector for fonts, gradients, side stripes, bounce easing, `transition: all`, missing reduced-motion, AI copy, nested cards, and more. Exit 2 on high-severity findings.

## Workflow

### 0. Intake (state it in 3–5 lines; confirm only if truly ambiguous)
- **Subject:** one concrete sentence about what this is (a tide-table service, a CNC shop, a jazz club).
- **Audience and primary job:** who arrives, what must they do or feel.
- **Surface type:** product UI · marketing/brand · showcase/portfolio · component/animation only.
- **Motion tier** (`motion.md` §2): 0 Quiet · 1 Branded · 2 Showcase. Default: tools → 0, marketing → 1, "wow"/awards/portfolio → 2.
- **Constraints:** stack (plain HTML, React, Next), brand assets, existing design system, deadlines, sandbox limits.
If an existing codebase or design system exists, read it first and preserve its identity; improve within it.
The user's own words about look and feel always override the defaults in this skill.

### 1. Direction (plan before code)
Produce a compact plan:
1. **Concept** in one sentence + a **reference world** from the subject's materials, paperwork, signage, tools (`anti-slop.md` §4).
2. **Colour:** palette roles as named hex values (start from `foundations.md` §1 or derive a custom one), commitment level, dark-mode intent.
3. **Type:** display + body (+ mono only if real code/data), roles, scale ratio, measure.
4. **Layout:** an archetype from `foundations.md` §4 and an ASCII wireframe of the first screen and the page's rhythm (alignment stated: left, centred, justified, where).
5. **Motion:** tier, the *one* signature moment, tokens, reduced-motion behaviour.
6. **Principles:** 3 lines that make this page unlike the default.
7. **Default check:** write the page you would have made with zero effort; ensure the plan differs on ≥ 3 axes. If any part reads like that default, revise it and say what changed.

### 2. Build, in this order
1. **Tokens first.** Copy `assets/tokens.css`, replace the palette block, set font stacks. No raw hex in components.
2. **Semantic HTML & content.** Real copy written from the user's perspective (specific, sentence case, active verbs, honest empty/error states). No lorem, no invented logos/testimonials/metrics.
3. **Layout & type.** Grid, spacing scale, type roles, measure, fluid sizes.
4. **Surfaces.** Radius by role (concentric when nested), layered tinted shadows or none, borders for separation.
5. **States.** Hover (gated by `@media (hover: hover)`), focus-visible, active, disabled, loading, empty, error.
6. **Motion layer last.** CSS first; Motion for React state; GSAP for timelines/scroll; WebGL/3D only if the story earns it.
7. **Responsive.** Mobile is designed (adapt interactions), not shrunk; 360 → 1440+.

### 3. Polish pass
Apply `surfaces-and-feel.md` fully: concentric radius, optical alignment, tabular numbers, `text-wrap`, 0.96 press
scale, subtle exits, split-and-stagger entrances, no `transition: all`, 40px hit areas, image outlines.

### 4. Verify (do not skip; do not announce the checklist, just fix)
1. `python3 scripts/slop_scan.py <paths>`: must exit 0. Fix every HIGH; justify or fix MED.
2. `python3 scripts/color.py palette palette.json` (or `contrast`) for every text/UI pair; fix failures.
3. Slop Test (`anti-slop.md` §2): squint, swap, cliché census, default-font, motion, copy.
4. Render and look if the environment can (screenshots at mobile/desktop; dark mode if present). A picture beats 1000 tokens.
5. Quality floor: keyboard navigation and visible focus; reduced-motion path; no-JS content; no horizontal scroll;
   zoom to 200%; LCP/CLS/INP sensible; no console errors.
6. Remove one accessory: cut a decoration, an effect, a colour, an eyebrow. Then ship.

### 5. Handoff
Two to four sentences: the concept, the palette/type choices in plain words, the one signature moment, anything
left out on purpose. For reviews, use the Before/After table format in `surfaces-and-feel.md` §5.

## Non-negotiable design laws

**Distinctiveness**
- Specificity beats creativity: every major choice must be defensible by pointing at the subject.
- Spend boldness in one place. One memorable element; everything else quiet and disciplined.
- Open with the most characteristic thing in the subject's world, not the SaaS hero template.
- The brief's explicit instructions beat these defaults, including when they ask for a "banned" look.

**Typography**
- A deliberate pairing, not a reflex font (Inter/Roboto/Arial/system, or its look-alikes). One family with axes is a valid pairing.
- Real scale (≥ 1.25 between levels), display leading 0.9–1.1 and tracking −2% to −4%, body measure 45–75ch.
- No gradient text; no single-word accent in headlines; no tracked-caps eyebrow on every heading; no `01/02/03` unless content is a sequence.

**Colour**
- Roles not swatches; OKLCH; tinted neutrals (never `#000`/`#fff` for large areas); one accent; second palette for dark mode.
- Derive from the subject's materials/light/culture. Avoid the attractors: purple→blue gradients, cream + terracotta, near-black + acid-green, default grey + indigo.
- Contrast computed: body ≥ 4.5:1 (aim 7), large/UI ≥ 3:1.

**Layout & surfaces**
- One spacing scale (4pt). Proximity groups; gap over margin; vary section rhythm.
- Not everything is a card; never nest cards; no coloured side-stripe borders; no rounded-square icon tile above every heading.
- Radius by role; outer = inner + padding. Layered, hue-tinted shadows, not one grey blur everywhere.

**Motion**
- Motion answers (state change) or narrates (scroll story). Otherwise cut it.
- Tokens for every duration/easing; ease-out by default; **never bounce/elastic/overshoot**; springs `bounce: 0`.
- Interruptible UI uses transitions/springs; keyframes for one-shot sequences.
- One orchestrated entrance, not fade-up on every section. Hover rarely moves things.
- `prefers-reduced-motion` respected in CSS *and* JS. Animate only `transform`, `opacity`, `filter`, `clip-path`.

**Scroll & 3D**
- Write the scroll story as beats first. Pin ≤ ~3 viewports; never hijack native scroll; content works without JS.
- Scrubbed tweens use `ease: "none"`; ScrollTrigger on the timeline; `gsap.matchMedia` for responsive + reduced motion; `useGSAP` in React.
- 3D must carry the story; progress via ref into the render loop; lazy-load; poster/static fallback; clamp DPR; budget enforced.

**Quality floor**
- Responsive to mobile, visible keyboard focus, hit areas ≥ 40px, no pinch-zoom blocking, text ≥ 12px, semantic HTML, alt text, every interactive state designed.

## Copy rules (words are design)
Write for the end user in plain, specific language. Name things by what users understand ("Notifications", not
"Webhook config"). Buttons state the outcome ("Save changes", "Book a site visit"); the same action keeps the same
name through the flow (button "Publish" → toast "Published"). Errors say what happened and how to fix it, without
apologising. Empty states invite the next action. Sentence case, active voice, no filler, none of the stock AI
phrases in `anti-slop.md` §3. Add an arrow to a link only when direction matters.

## Modes

- **Build new:** workflow 0→5.
- **Redo/improve existing:** read the code and current look; keep the identity; run `slop_scan.py` on it first to get a baseline; fix structure → type → colour → surfaces → motion; show Before/After.
- **Critique only:** score the six axes (`anti-slop.md` §6), list the top 5 fixes by impact, don't rewrite unless asked.
- **Component/animation only:** skip the full direction plan; still pick tokens, states, reduced-motion, and the right tool (`motion.md` §6).
- **Bolder / quieter:** bolder = scale contrast, committed or drenched colour, one signature moment; quieter = fewer colours, remove effects, increase whitespace, smaller type scale ratio.
- **Distil:** strip to essence: flatten nested containers, merge near-duplicate styles, cut decoration, reduce the palette.

## Environment notes
- **Delivery format follows the host environment's rules** (for example, publishing a self-contained HTML page, or presenting a file). This skill governs design quality, not delivery mechanics.
- **Sandboxed/published HTML:** only allow-listed script hosts (cdnjs, jsDelivr npm, Tailwind CDN, jQuery CDN), Google Fonts only, no remote images or network calls, pinned versions, `localStorage` in try/catch. See `scroll-and-3d.md` §11. Use Google-Fonts pairings from `foundations.md`; go procedural for 3D.
- **Python scripts need no network or installs.** If scripts can't run, apply the same rules by hand and say verification was manual.
- If screenshots are possible, take them; otherwise reason carefully about the rendered result and state that it wasn't visually verified.

## Quick reference

```
Radius: outer = inner + padding        Press: scale(0.96), never < 0.95
Enter: 240–420ms ease-out, stagger 60–100ms (cap ~600ms); exit ≈ 60–70% of enter, smaller travel
Body: 16–20px, 1.4–1.65 leading, 45–75ch   Display: 0.9–1.1 leading, −2…−4% tracking
Scale ratio ≥ 1.25 per step   Spacing: 4 8 12 16 24 32 48 64 96 128
Contrast: body ≥ 4.5:1 (7 ideal)  large/UI ≥ 3:1   APCA Lc 75 body / 60 large
Hit area ≥ 40×40   Pins ≤ ~3 viewports   Scrub ease: "none"   Spring bounce: 0
Animate: transform · opacity · filter · clip-path     Never: transition: all
```
