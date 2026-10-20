# Foundations: colour, typography, spacing, layout

## Contents
1. Colour: strategy, rules, ten verified palettes, tooling
2. Typography: selection, ten pairings, scale, setting rules, loading
3. Spacing and grid
4. Layout archetypes (non-template compositions)
5. Responsive and density

---

## 1. Colour

### Pick a commitment level first
How much of the surface does colour own? Choose deliberately; most AI work defaults to "restrained" by accident.

| Level | What it means | Use for |
|---|---|---|
| Restrained | Tinted neutrals; one accent on < 10% of area (links, key CTA, data highlight) | Tools, documentation, editorial, trust-heavy brands |
| Committed | One brand colour owns key sections or large fields; neutrals support | Product marketing, campaigns, most brand sites |
| Full palette | 3–4 hues with explicit roles (not "variety") | Playful brands, education, data-rich storytelling |
| Drenched | The surface *is* the colour; ink and one contrast colour sit on top | Posters, launches, showcase / awards-style sites |

### Rules
- **Define roles, not swatches.** `bg, surface, ink, muted, line, accent, accent-2, on-accent`. Components only
  reference roles (`assets/tokens.css`).
- **Work in OKLCH.** Equal lightness steps look equal; hue/chroma can be adjusted independently. Convert with
  `python3 scripts/color.py oklch "#hex"`.
- **Tint every neutral.** Chroma 0.005–0.02 toward the brand hue (or its complement for tension). No `#000`,
  no `#fff` for large areas; `surface` may be near-white but still tinted.
- **Ramps drift in hue.** When generating tints/shades, shift hue a little (lights toward warm/yellow, darks
  toward cool/blue) and let chroma peak mid-lightness. `color.py ramp "#hex" --drift 18`.
- **Accent discipline.** One accent for action and emphasis. Secondary colour is a *fill* (badge, chart series,
  highlight); text on it uses `ink` or `bg`, whichever tests higher.
- **Semantic colours belong to the palette.** Tune success/warning/danger to the same lightness/chroma family;
  don't paste default #22c55e / #ef4444.
- **Contrast is computed, never asserted.** Body text ≥ 4.5:1 (aim 7:1); large text and UI glyphs ≥ 3:1;
  APCA Lc ≥ 75 body, ≥ 60 large, ≥ 45 incidental UI. Never convey meaning by colour alone. Use
  `color.py contrast` and `color.py palette`.
- **Dark mode is a second palette**, not an inversion: raise surfaces with elevation (lighter = closer), drop
  chroma 10–15%, use an off-white ink, re-verify every pair.
- **Data viz:** ≤ 6 categorical hues at similar lightness; sequential = one hue, lightness-ordered; check
  colour-blind simulations; label directly instead of relying on a legend where possible.
- **Gradients:** only when the subject has one (sunset, spectrum, heat map, a physical material). If used:
  same-hue or analogous, noise/grain overlay to avoid banding, never purple→blue/pink by default.

### Derive colour from the subject
Ask: what are its **materials** (concrete, linen, copper), its **light** (fluorescent lab, candlelit,
overcast harbour), its **paperwork/signage** (ledger green, hazard orange, blueprint blue), its **culture**
(tea, ink, lacquer)? Pick the 2 most characteristic, push one into the accent, soften the other into
neutrals. That is how you leave the attractors (cream+terracotta, near-black+acid-green, grey+indigo).

### Ten palettes (every pair below computed with `scripts/color.py`)
All pass: ink/bg ≥ 12:1, muted/bg ≥ 5.2:1, accent/bg ≥ 4.6:1 (light) or higher (dark), and the best label colour
on both accent fills ≥ 4.6:1. `accent-2` is **fill-only**.

| # | Palette | bg | surface | ink | muted | accent | accent-2 | line |
|---|---|---|---|---|---|---|---|---|
| 1 | Glacier Lab | `#EBF0F3` | `#F8FAFB` | `#0E1A22` | `#4F616C` | `#0A6C99` | `#E0A21B` | `#CBD5DB` |
| 2 | Petrol & Saffron *(dark)* | `#0B2A2F` | `#123A40` | `#E9F2EF` | `#9FBBB7` | `#F2B134` | `#7ED3C1` | `#25535B` |
| 3 | Moss & Plum | `#E4E9DC` | `#F2F5EC` | `#1B2519` | `#546350` | `#7B2D5E` | `#B8891A` | `#C5CEB9` |
| 4 | Concrete & Signal | `#D8D9D6` | `#E8E9E6` | `#16181B` | `#4A4E53` | `#AE2E04` | `#1D4ED8` | `#B8BAB6` |
| 5 | Ink & Sakura | `#F5ECEE` | `#FBF6F7` | `#2B1E2E` | `#6A5568` | `#B8294F` | `#2F5576` | `#E2D0D5` |
| 6 | Abyss & Ice *(dark)* | `#060D1F` | `#0E1A36` | `#DDE8FF` | `#93A6CC` | `#5FE3E8` | `#FF5C93` | `#223156` |
| 7 | Wine & Blush *(dark)* | `#2A0E19` | `#3A1624` | `#F7E9E4` | `#CFA9A6` | `#EDB8A3` | `#CDA656` | `#5A2A3B` |
| 8 | Sea Glass Clinic | `#EEF6F5` | `#FAFDFC` | `#0D2829` | `#466566` | `#0A7478` | `#C23E17` | `#C6DAD8` |
| 9 | Chalk & Cobalt | `#EEF0F4` | `#FAFAFC` | `#101420` | `#555D70` | `#1F3FE0` | `#F2542D` | `#D0D5E0` |
| 10 | Orchard Night *(dark)* | `#171A14` | `#20251B` | `#EDF0E4` | `#A3AD94` | `#E26D5A` | `#C9D86B` | `#38412F` |

| # | Reads as | Good for | Pairs with type # | Watch out |
|---|---|---|---|---|
| 1 | Cold, precise, daylight | Climate, civic data, research, B2B science | 1, 3, 9 | Amber accent-2 only as fill/highlight |
| 2 | Deep water, brass lamp | Hospitality, maritime, premium food, finance with warmth | 8, 5 | Saffron is for one CTA, not decoration |
| 3 | Garden, fermentation | Botanical, wellness, slow food, craft, books | 5, 10 | Plum + moss is distinctive; keep neutrals earthy |
| 4 | Poured concrete, hazard tape | Industrial, construction, logistics, transit | 2, 4 | Orange is loud; give it room and keep type sturdy |
| 5 | Paper, ink, blossom | Publishing, tea, stationery, cultural venues | 10, 3 | Keep layouts airy; avoid pink-gradient drift |
| 6 | Night sea, sonar | **3D / WebGL showcases**, space, deep tech | 9, 7 | Cyan-on-navy is an "AI" cliché; use only when the subject is genuinely technical/spatial |
| 7 | Cellar, velvet | Fashion, wine, jewellery, hospitality | 6, 8 | Blush is soft; give large display type |
| 8 | Glass, sterile light | Health, labs, clinics, water, wellbeing | 3, 8 | Don't add stock-photo smiles to compensate |
| 9 | Chalk, ultramarine | Fintech, B2B, tools, studios | 9, 8 | Generic risk is high; rescue with composition and type |
| 10 | Orchard dusk | Bars, music venues, dark food/drink, events | 7, 5 | Lime accent-2 is fill-only; keep it small |

Custom palette workflow: pick hue family from the subject → `color.py ramp` for the accent → `color.py tint 11
--hue H --chroma 0.012` for neutrals → write roles to JSON → `color.py palette file.json` until it exits 0.

---

## 2. Typography

Typography carries the personality. Spend your first design decision here.

### Selection (4 steps)
1. **Voice:** three adjectives for the brand (e.g. *measured, nautical, dry*).
2. **Display face by personality and anatomy:** contrast, x-height, aperture, width, terminals. A condensed grotesque is
   urgent, a soft serif is warm, a wide grotesque is confident, a sharp high-contrast didone is luxurious.
3. **Body face for legibility at 16–20px:** open apertures, moderate x-height, even colour, a bold weight that
   doesn't clog. Serif or sans, whichever the voice wants.
4. **Pair by contrast of structure** (serif + sans; wide + normal; display + workhorse), with similar x-heights.
   Never two similar sans. One family with weight/width/optical-size axes is often the best pairing.

### Ten pairings (all on Google Fonts, so they also load in sandboxed pages that allow only fonts.googleapis.com)
Confirm availability and licence before shipping; always provide a fallback stack.

| # | Display | Body / UI | Mono | World | Notes |
|---|---|---|---|---|---|
| 1 | Bricolage Grotesque (opsz+wdth+wght) | Source Serif 4 | IBM Plex Mono | Field guides, civic, science | Variable axes give you a one-family display system |
| 2 | Archivo, wdth 112–125, 600–800 | Archivo, wdth 100, 400 | IBM Plex Mono | Industrial, engineering, logistics | Expanded width on display, normal on body |
| 3 | Newsreader (opsz 72) | Schibsted Grotesk | none | Long-form journalism, research | Serif display + crisp UI sans |
| 4 | Big Shoulders Display | Libre Franklin | none | Sport, transit, posters, signage | Condensed + humanist workhorse |
| 5 | Young Serif | Work Sans | none | Food, craft, community, hospitality | Chunky warm serif, plain body |
| 6 | Bodoni Moda (opsz) | Jost | none | Fashion, luxury, culture | High contrast: large sizes only (≥ 40px) |
| 7 | Unbounded | Onest | none | Music, youth, bold consumer fintech | Wide and loud; keep body quiet |
| 8 | Gloock | Geist | Geist Mono | Law, finance, architecture | Confident serif headline + neutral UI |
| 9 | Familjen Grotesk | Familjen Grotesk (400) | Spline Sans Mono | Dev tools, labs, data products | Quirky grotesk; mono for real data only |
| 10 | Libre Caslon Display | Public Sans | none | Museums, publishing, nonprofits | Classical display + civic sans |

If you can self-host (not a sandboxed page): Fontshare/other foundries offer distinctive families (e.g.
Cabinet Grotesk, Clash Display, Satoshi, General Sans, Switzer, Erode, Gambetta, Sentient, Boska). Even
good fonts become tells when everyone uses them; pick by voice, not by trend.

### Scale
- **Ratio by context:** 1.2 (dense apps) · 1.25 (general product/marketing; the default) · 1.333 (editorial) ·
  1.5+ (display moments). Each hierarchy step should differ by ≥ 1.25×; if two levels look alike, merge them.
- **Fluid, not breakpointed.** `assets/tokens.css` ships `--step--2 … --step-7` computed for 320→1240px, body
  16→19px, ratio 1.2→1.25. For heroes use the separate `--display-m/l` (clamp with `vw`, line-height 0.9–1.0,
  tracking −3.5%).
- **Use `rem`** so user font-size settings work. Don't set `html { font-size: 62.5% }`.
- **Roles, not sizes:** `caption, ui, body, lede, h3, h2, h1, display`. Name them; reuse them.

### Setting rules
- **Measure:** 45–75ch, aim 60–70. Serifs tolerate slightly longer. Constrain `p, li, blockquote` with `max-width: 66ch`.
- **Leading:** display 0.9–1.1 · headings 1.1–1.25 · sans body 1.4–1.55 · serif body 1.5–1.65 · captions 1.3–1.4.
- **Tracking:** display −2% to −4% · headings −1% to −2% · body 0 · small text +1–2% · ALL-CAPS +4–8%.
- **Wrapping:** `text-wrap: balance` on headings and short blocks; `text-wrap: pretty` on paragraphs;
  `hyphens: auto` with `lang` set for justified or narrow columns.
- **Numerals:** `font-variant-numeric: tabular-nums` for anything that updates or aligns in columns; `lining-nums`
  in tables, `oldstyle-nums` in serif prose if the face has them.
- **Typographic punctuation:** real ’ “ ” – — … and `×`, non-breaking spaces before units, hanging punctuation
  on quotes (`hanging-punctuation: first` where supported).
- **Variable-font axes are free design material:** `font-optical-sizing: auto`; animate `wght` or `wdth` on
  hover/scroll for a kinetic headline (keep to ±200 wght to avoid reflow jitter, or fix width with
  `font-stretch`).
- **Emphasis hierarchy:** size → weight → colour → italic/caps. Prefer the earlier ones; reserve caps for short
  labels (< 20 characters).
- **Don't fake it:** no synthetic bold/italic; load the weights you use (≤ 4 font files total).

### Loading
`<link rel="preconnect">` to the font host, `font-display: swap`, preload the display face, define a fallback
with `size-adjust`/`ascent-override` to prevent layout shift, subset when self-hosting.

---

## 3. Spacing and grid

- **One scale.** 4pt base: `4 8 12 16 24 32 48 64 96 128 192` (`--s-1 … --s-11`). Never invent 13px or 22px.
- **Proximity is grouping.** Space *inside* a group ≤ ½ the space *between* groups. If labels float equidistant
  from two fields, the form is ambiguous.
- **Prefer `gap` to margins;** one owner for each space. Use `.flow > * + *` for prose rhythm. Avoid margin
  collapse surprises and per-element margin tweaks.
- **Optical padding.** Controls: inline padding ≈ 2× block padding (e.g. 12/24). Icon-text gap ≈ 0.5em. Card
  padding should relate to its radius (see concentric radius).
- **Vertical rhythm.** Section padding `clamp(4rem, 2rem + 9vw, 10rem)`; vary it per section (tight for dense
  data, vast for statements) instead of repeating one value six times.
- **Grid.** 4 columns (mobile) → 8 (tablet) → 12 (desktop); fluid gutters (`clamp(1rem, .5rem + 2.5vw, 2.5rem)`).
  Text-heavy container 64–78rem; galleries and showcases up to full-bleed. Let one element break the grid on purpose.
- **Intrinsic layouts:** `grid-template-columns: repeat(auto-fit, minmax(min(100%, 18rem), 1fr))`, `subgrid` for
  aligned card internals, **container queries** for components (`container-type: inline-size`), logical
  properties (`margin-inline`, `padding-block`).
- **Viewport units:** `svh/dvh/lvh`, never `100vh` for full-screen sections on mobile. Respect `env(safe-area-inset-*)`.
- **Whitespace is composition.** Empty cells and wide margins should be *intentional asymmetry*, not leftover.

---

## 4. Layout archetypes (leave the card grid)

Pick one per page as the backbone; mix in a second for contrast.

| Archetype | Structure | Great for |
|---|---|---|
| **Spine & margin** | Narrow text column with sidenotes/figures hanging into one margin | Editorial, research, docs |
| **Ledger / index** | Ruled rows (name · detail · year · tag); hover or scroll reveals an image/preview | Portfolios, catalogues, archives, pricing |
| **Type poster** | Viewport-wide type; image/shape colliding with it; very little else | Launches, events, studios |
| **Split stage** | One half is sticky (object/diagram); the other half scrolls through copy, changing the object | Product explainers, how-it-works |
| **Horizontal rail** | Pinned section translates sideways through panels | Timelines, galleries, process |
| **Collage / overlap** | Images and type at varied scale with negative margins and deliberate overlaps | Fashion, culture, hospitality |
| **Annotated object** | Central product/diagram with leader-line callouts | Hardware, instruments, anatomy-of |
| **Data-first** | The hero *is* a live chart, table or map | Analytics, civic, finance |
| **Asymmetric 5/7 or 3/9** | Uneven columns with intentional empty cells | Brand sites, case studies |
| **Stacked chapters** | Full-viewport chapters, each with its own background and rhythm; optional scroll-snap | Storytelling, annual reports |
| **Control panel** | Docked panels, dense but ordered, clear focus states | Apps, tools, dashboards |

Sketch the first screen as an ASCII wireframe before building:

```
┌────────────────────────────────────────────────────────┐
│ wordmark                                   menu        │
│                                                        │
│  TIDE                                  ┌────────────┐  │
│  TABLES                                │  live chart│  │   Data-first + type poster
│  for the                               │  (real     │  │
│  Cape Fear coast                       │   data)    │  │
│  ───────────────────                   └────────────┘  │
│  today 06:12 high · 12:34 low                          │
└────────────────────────────────────────────────────────┘
```

---

## 5. Responsive and density

- **Design mobile-first, then expand**; check 360, 768, 1024, 1440, and ultra-wide (a max-width keeps it sane).
- **Fluid over breakpoints;** use breakpoints only for structural changes (nav pattern, rail → stack).
- **Touch:** ≥ 44px targets where possible (≥ 40px minimum); no hover-only affordances; `@media (hover: hover)`
  gate for hover effects; `@media (pointer: coarse)` for larger controls.
- **Density modes:** apps 4/8/12 spacing, 14–15px UI text; marketing 16–19px body with generous rhythm;
  editorial 18–21px body, measure-driven.
- **Content resilience:** long names, empty states, 200% zoom, RTL where relevant, text expansion ~30%.
- **Images:** `aspect-ratio`, `object-fit`, `srcset/sizes`, `loading="lazy"` below the fold, explicit
  dimensions to avoid CLS; decorative images get `alt=""`.
