# Surfaces and feel: the details that compound

Great interfaces are rarely one big idea. They are many small correct details. This file is the polish
pass: apply it to every build, then use the checklist at the end. (Principles adapted from Jakub Krehel's
"Details that make interfaces feel better" and its agent skill, plus Impeccable's polish guidance.)

## Contents
1. Surfaces: radius, optical alignment, shadows, outlines, hit areas
2. Typography details
3. Animation details
4. Performance details
5. Review output format
6. Review checklist

---

## 1. Surfaces

**1. Concentric border radius.** Nested rounded shapes share a centre of curvature:
`outer radius = inner radius + padding`. A 12px-padded card holding an 8px-radius button gets a 20px
radius. Same radius on parent and child is the most common reason an interface "feels off". In
`tokens.css`: `--r-outer: calc(var(--r-inner) + var(--pad-card))`. If padding is large (≥ the inner radius × 2),
stop nesting radii, since the curves no longer relate visually; use independent radii.

**2. Optical over geometric alignment.** Geometric centring often looks wrong. Fix by eye:
- A "play" triangle needs to shift right ~8–10% of its width.
- A button with an icon on one side takes less padding on the icon side.
- Asymmetric glyphs (arrows, carets, chevrons) are nudged until their visual mass sits at the centre.
- Round shapes (circles, "O") overshoot baselines/cap-height slightly (~1–2%) to look equal to flat ones.
- Fix SVGs at the source (adjust the path/viewBox) where possible, not with a one-off margin.

**3. Shadows over borders (for elevation).** Layer several transparent shadows for natural depth; they adapt to any
background, where a solid border doesn't. Pattern: a 1px ring + a tight contact shadow + one or two large
soft shadows with negative spread. Tint with the ink colour, not black: use `color-mix(in oklab, var(--ink) 6%, transparent)`.
(`--shadow-1/2/3` in `tokens.css`.) Use real borders for *separation* (inputs, tables, dividers) and
shadows for *elevation* (popovers, raised cards). Don't use both on one element unless the border is the ring.

**4. Image outlines.** Give photos/avatars a 1px inset outline at 10% opacity with `outline-offset: -1px`.
The colour must be **pure black in light mode (`rgb(0 0 0 / .1)`) and pure white in dark (`rgb(255 255 255 / .1)`)**.
A tinted outline picks up the surface under it and looks like dirt on the edge. (This is the one place pure
black/white is correct.)

**5. Minimum hit area.** Interactive targets are ≥ 40×40px (44 on touch). Extend small controls with a
pseudo-element (`.hit::after { inset: -8px }`), never by enlarging the visual. Two targets' hit areas must
never overlap.

**6. Hierarchy of surfaces.** Not everything gets elevation. Page < surface < raised < overlay. If two adjacent
elements have the same elevation and the same container treatment, merge them into one container.

---

## 2. Typography details

**7. Font smoothing.** `-webkit-font-smoothing: antialiased` on the root (macOS renders light-on-dark and
small text too heavy otherwise); keep `text-rendering: optimizeLegibility`.

**8. Tabular numbers.** `font-variant-numeric: tabular-nums` on anything that changes or aligns: counters,
timers, prices, table cells. Prevents jitter and layout shift as digits change width.

**9. Text wrapping.** `text-wrap: balance` for headings and short centred blocks; `text-wrap: pretty` for body
copy to avoid single-word orphans.

(See `foundations.md` §Typography for scale, measure, leading and tracking.)

---

## 3. Animation details

**10. Interruptible animations.** Interactive state changes (hover, toggles, menus, drag) use **CSS transitions**
or springs: they retarget smoothly if the user reverses mid-flight. Keyframe animations are for staged
sequences that run once (an intro). If a user can click again before it finishes, don't use keyframes.

**11. Split and stagger enters.** Don't animate one big container. Break content into semantic chunks
(eyebrow/heading/body/actions or image/caption) and stagger each by ~60–100ms (`--stagger`), capping the
total near 600ms. Each chunk gets a small `translateY` (8–16px), `opacity`, and optionally `blur(4px)`.

**12. Subtle exits.** Exits are softer and shorter than enters: a small fixed `translateY` (~8–12px) plus
fade, ~60–70% of the enter duration. Never animate full height/width out of the way; the user has already
decided to leave.

**13. Contextual icon swaps.** When an icon changes state (copy → check, play → pause), animate with opacity,
scale and blur instead of toggling visibility: scale `0.25 → 1`, opacity `0 → 1`, blur `4px → 0`. With Motion:
`transition: { type: "spring", duration: 0.3, bounce: 0 }`; **bounce is always 0**. Without a library, keep both
icons in the DOM (one absolutely positioned) and cross-fade with `cubic-bezier(0.2, 0, 0, 1)`, which gives
enter and exit with no dependency.

**14. Scale on press.** Buttons get `scale(0.96)` on `:active` for tactile feedback. Always 0.96; never below
0.95, because it feels exaggerated. Provide a `static` option to disable it where motion distracts
(e.g. dense toolbars, destructive confirmations).

**15. Don't animate on first paint.** Elements that are visible on load should *be* there. In Motion use
`<AnimatePresence initial={false}>`; in CSS, apply enter animations only when state changes
(`@starting-style` or a class toggled after mount). Verify you haven't killed an intentional hero entrance.

---

## 4. Performance details

**16. Never `transition: all`.** List exact properties (`transition-property: scale, opacity`). `all` animates
layout and colour changes you didn't intend and defeats the compositor. Tailwind's `transition-transform`
covers `transform, translate, scale, rotate`.

**17. `will-change` sparingly.** Only `transform`, `opacity`, `filter` (compositor-friendly), only on elements that
visibly stutter on the first frame, and remove it after the animation. Never `will-change: all`.

**18. Animate the cheap properties.** `transform`, `opacity`, `filter`, `clip-path`. Avoid animating
`width/height/top/left/margin` (use FLIP, `grid-template-rows: 0fr → 1fr`, or `interpolate-size`).

---

## 5. Review output format

When asked to review or polish existing UI, present changes as a markdown table per principle with
**Before** and **After** columns, citing file and property when not obvious. One diff per row. Omit principles
where nothing changed.

```
#### Concentric border radius
| Before | After |
|---|---|
| `rounded-xl` on card + `rounded-xl` on inner button (`p-2`) | `rounded-2xl` on card (12 + 8 → 20), `rounded-lg` on button |

#### Scale on press
| Before | After |
|---|---|
| `scale(0.9)` on `.btn:active` | `scale(0.96)`; below 0.95 feels exaggerated |
```

## 6. Review checklist

- [ ] Nested rounded elements use concentric radius
- [ ] Icons and glyphs are optically centred
- [ ] Elevation uses layered tinted shadows; borders only for separation
- [ ] Images/avatars have a 1px pure-black/white 10% outline
- [ ] Every interactive element has ≥ 40×40px hit area, and no overlaps
- [ ] Font smoothing applied; `tabular-nums` on dynamic numbers
- [ ] Headings `text-wrap: balance`; body `text-wrap: pretty`
- [ ] UI state changes are interruptible (transitions/springs, not keyframes)
- [ ] Enters are split + staggered; exits are subtle and shorter
- [ ] Icon swaps animate scale/opacity/blur with `bounce: 0`
- [ ] Press feedback is `scale(0.96)` (not < 0.95), with an opt-out
- [ ] No animation on first paint for already-visible state
- [ ] No `transition: all`; `will-change` only where needed
- [ ] Hover effects gated behind `@media (hover: hover)`
- [ ] Focus-visible styles exist and are visible on every interactive element
- [ ] Reduced-motion branch exists
