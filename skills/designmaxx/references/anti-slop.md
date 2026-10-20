# Anti-slop: how not to look vibe-coded

Read this before you plan a design and again before you call it done.

## Contents
1. Why slop happens
2. The 30-second Slop Test
3. The catalog of tells (type, colour, layout, surface, motion, copy, imagery, code)
4. Diversification protocol (how to actively diverge)
5. When a "banned" thing is actually right
6. Self-critique scoring

---

## 1. Why slop happens

Models produce the statistical middle of every landing page they were trained on. Left unsteered, every
project converges on the same handful of choices: a reflex sans-serif, a purple-to-blue gradient, a grid of
identical rounded cards, a fade-up on every section. The fix is not "be more creative". Creativity prompts
collapse to the same average. The fix is **specificity**: decisions that could only have been made for this
subject, this audience, this job, plus **forbidden defaults** you check mechanically.

Two consequences:
- Banning a font or colour alone does not work; models just move to the next-most-likely one (Inter → Space
  Grotesk → DM Sans → Plus Jakarta). Name the *category* of default and then make a subject-derived choice.
- The tells compound. One is fine. Three together and the page reads as generated in two seconds.

## 2. The 30-second Slop Test

Run it on the plan *and* on the finished build (screenshot it if you can).

1. **Squint test.** Blur your eyes. Is there one clear focal point and a clear order of three levels? Or an even
   grey wash of same-sized boxes?
2. **Swap test.** Replace the logo and copy with a different industry's. Does the design still "work"
   unchanged? If yes, it was never designed for this subject.
3. **Cliché census.** Count tells from section 3. Three or more = redo that layer.
4. **Default-font test.** Would the font pairing have been your answer for any brief? Then it's a default.
5. **Motion test.** Remove all motion. Does anything feel missing that mattered? If not, the motion was
   decoration. Then ask the reverse: is there *one* moment of motion people will remember?
6. **Copy test.** Read only the headings aloud. Do they say something specific, or could a SaaS startup,
   a dentist and a bank all use them?

Run `python3 scripts/slop_scan.py <path>` for the mechanical half (fonts, gradients, side stripes, bounce
easing, `transition: all`, missing reduced-motion, etc.). It cannot judge composition, so tests 1, 2, 4, 6 stay
manual.

## 3. The catalog of tells

Format: **tell** → why it reads as generated → do this instead.

### Typography
- **Inter / Roboto / Arial / system-ui as the primary face; also the "alternatives" everyone reaches for next
  (Space Grotesk, DM Sans, Poppins, Plus Jakarta, Outfit, Playfair Display)** → it is the font of
  unconfigured software. → Choose from `foundations.md` §Typography by subject. If the brand dictates Inter,
  fine; then express personality through scale, weight contrast, tracking and layout.
- **Single word of a headline in italic/colour/gradient** ("Build *faster*") → the most common AI headline
  device. → Emphasise by position, scale, or by restructuring the sentence. Or don't emphasise.
- **Gradient-filled text** (`background-clip: text`) → decoration masquerading as hierarchy. → Solid colour.
- **Tracked ALL-CAPS eyebrow above every heading** ("FEATURES", "HOW IT WORKS") → free filler. → Keep an
  eyebrow only if it encodes information (a date, a category, a section index that's real). Max one or two per page.
- **Mono font for every small label / "technical" feel** → costume. → Use mono for actual code, data, IDs.
- **Everything centred** (headline, paragraph, buttons, cards) → safe and weak. → Left-align reading text;
  centre only short, ceremonial lines.
- **Weights only 400 and 700, sizes within a 1.1× ratio** → flat hierarchy. → Real scale (≥1.25 steps between
  levels), and use weight *and* width/optical-size axes where the face has them.
- **Headline at 48px with 1.5 line-height** → body leading on display type. → Display leading 0.9–1.1,
  tracking −2% to −4%.

### Colour
- **Purple→blue or purple→pink gradient** (hero wash, button, blob) → the single most recognisable AI tell.
- **Cream background + high-contrast serif + terracotta/clay accent** → the "warm editorial" attractor.
- **Near-black background + one acid-green / electric-lime / vermilion accent** → the "dev tool" attractor.
- **Pure `#000` / `#fff`** → harsh and unconsidered. → Tint every neutral toward the palette hue (OKLCH chroma
  0.005–0.02). The page should have a temperature.
- **Grey text on a coloured background** → washes out. → Use a tint of the background hue, or the ink colour at
  reduced opacity *and verify contrast*.
- **Default Tailwind slate/zinc/gray + an indigo-500 accent; untouched shadcn theme** → recognisable at a
  glance. → Replace the tokens entirely (`assets/tokens.css`).
- **5+ accent colours "for variety"** → noise. → One accent, one secondary fill at most, rest neutral.
- **Neon glow on dark** (coloured box-shadow with blur ≥ 30px) → → Layered low-opacity tinted shadows, or none.
→ Instead: derive the palette from the subject's materials, light and culture (`foundations.md` §Colour).

### Layout
- **Hero = big headline + subline + two buttons + gradient/blob behind** → the template. → Open with the most
  characteristic thing in the subject's world: the product itself, a live demo, an image, a data moment, a
  specimen, a map.
- **Grid of 3 identical cards, each with a rounded-square icon tile, a heading and two lines** → the SaaS kit.
  → Vary size and role: one large feature, two small; or drop containers and use a ruled list, a table, a
  timeline, or an annotated image.
- **Cards nested inside cards** → border soup. → One container level. Use spacing, a background shift or a
  hairline for inner grouping.
- **Everything is a card** → containers are information; use them only when the content is a discrete object.
- **Bento grid as default** → it was fresh in 2023. → Only if tiles really differ in importance and content type.
- **Identical section rhythm** (same padding, same centred header, same 3-col grid, repeated 6×) → monotony.
  → Vary density, alignment and scale between sections; let one section break the grid.
- **Numbered 01 / 02 / 03 markers on non-sequential content** → fake structure. → Only for real steps.
- **Logo wall of generic or invented brands; fake testimonials from "Sarah Chen, VP Product"; round vanity
  metrics (10×, 99.9%, 1M+)** → fabricated social proof. → Real quotes/figures, or leave the section out.
- **Floating glassmorphism panels over blurred blobs** → → Real layered content with real depth cues.
- **Sticky translucent nav with blur + pill CTA, always** → fine, but it's a default. → Consider the subject:
  a side rail, an index, a minimal wordmark + menu.

### Surfaces
- **One border-radius (usually 12–16px) on everything** → no hierarchy. → Radius scale by role; nested radius
  = outer − padding is wrong, it's **outer = inner + padding** (see `surfaces-and-feel.md`).
- **Same soft grey shadow under every card (`rgba(0,0,0,.1)`)** → → Layered, hue-tinted shadows, depth only
  where elevation is meaningful.
- **Coloured left-border stripe on cards/alerts/quotes** → a top-5 AI tell. → Full border, background tint or
  icon.
- **Rounded-square icon tile above every heading; Lucide icons in default weight, all the same size** →
  → Fewer icons; make them earn their place; match stroke weight to the type weight; or use none.
- **Blurred gradient orbs / mesh gradients as background decoration** → → A real image, texture, pattern
  derived from the subject, or flat colour.
- **Emoji as icons** → → SVG icons or no icon.

### Motion
- **Fade-up-and-slide on every section, every card, same easing and stagger** → the scroll-reveal default.
  → One orchestrated moment (hero load, or one scroll sequence). The rest stays still.
- **Hover = lift + shadow on every card** → → Hover changes colour/underline/cursor; motion reserved for
  things that move *because of* the action (menus, toggles, drag).
- **Bounce / elastic / overshoot easing** → dated, toy-like. → Out-quart/expo; springs with `bounce: 0`.
- **Ambient infinite animations** (floating blobs, pulsing glows, shimmering text) → → Cut them.
- **`transition: all`** → animates things you didn't mean to (layout, colour flashes, perf). → List properties.
- **Parallax on everything; scroll-jacking with no narrative reason** → → Scroll effects must carry the story
  (a reveal, a comparison, a build-up), not just move things.
- **Animation plays on first paint for the whole page** → → Skip initial animation on already-visible state.
- **No `prefers-reduced-motion` branch** → an accessibility defect, and a slop tell.

### Copy
- **"Elevate / Seamless / Unleash / Supercharge / Revolutionize / Cutting-edge / All-in-one / Empower /
  Next-generation / Effortless / Blazing-fast"** → → Say what it does, for whom, in the user's words.
- **Triads and parallel fragments** ("Fast. Simple. Powerful." / "No setup. No hassle. Just results.") →
  → One concrete sentence.
- **Em-dash-heavy, "It's not just X, it's Y" constructions; "Built for X, designed for Y"** → → Plain
  declarative sentences.
- **Lorem ipsum / Acme / John Doe / Jane Smith / example.com** → → Write real, subject-specific content.
- **Buttons "Get started →", "Learn more →", "Submit"** → → "Book a site visit", "Download the 2026 tide
  table", "Save changes". Arrow suffix only where direction matters.
- **Middle-dot meta strings** ("Design · Engineering · Product") and `WORD — fragment` labels → template chrome.

### Imagery
- **Stock-photo smiling team; generic 3D blob renders; AI-gloss abstract art** → → Subject-specific photography,
  diagrams, real product UI, specimens, maps, charts with real data. If you can't source images, use
  typography, colour fields and diagrams, not filler.
- **Dashboard screenshot with fake data on a floating perspective-tilted device frame** → → A cropped,
  honest, readable product crop with realistic data.

### Code
- **`rounded-2xl border bg-card p-6 shadow-sm` repeated everywhere**, arbitrary `gradient-to-br from-*`
  utilities, div soup, `!important` fights, `px` everywhere, magic numbers. → Tokens; semantic HTML; one spacing
  scale; `rem`/`clamp`.
- **No focus styles; `outline: none`** → fails keyboard users and is a slop tell.
- **No hover/focus/active/disabled/loading/empty/error states** → the page only works in the screenshot.
  → Design every state.
- **Pinch-zoom disabled; text < 12px; hit areas < 40px.**

## 4. Diversification protocol (how to actively diverge)

Do these in the planning pass, before any code.

1. **Write the default.** In two sentences, describe the page you would produce for this brief with zero
   effort. That is the attractor. Your plan must differ from it on at least three axes (palette, type,
   composition, motion idea, imagery).
2. **Pick a reference world** from the subject, not from "design": its materials, tools, paperwork, signage,
   instruments, maps, packaging, archival forms. (A tide-table site borrows from nautical charts and almanacs;
   a CNC shop from drawings and tolerance callouts; a bakery from ticket stubs and flour-dusted paper.)
   Extract 3 concrete visual devices from that world (a rule style, a numbering convention, a label system,
   a texture, a grid).
3. **Roll a constraint hand.** Pick one from each list at random (or by dice, `random.choice`) and justify
   it against the subject; discard and re-roll if it contradicts the brief:
   - Palette world (`foundations.md`, 10 palettes) or a custom one
   - Type pairing (10 pairings)
   - Composition archetype (`foundations.md` §Layout archetypes)
   - Signature motion (one of: type reveal, scroll-scrubbed object, pinned sequence, DOM-synced shader,
     direct manipulation, view-transition, none)
4. **Thumbnail triage.** Sketch three ASCII wireframes for the first screen. Delete the one that looks most
   like a normal landing page. Merge the best of the other two.
5. **Spend boldness in one place.** One memorable element, everything else quiet and disciplined. Decoration
   that doesn't serve the brief gets cut. (Chanel: take one thing off before you leave the house.)
6. **Keep a memory.** If the environment allows, write `.design-notes.md` listing the palette, type, layout
   and motion choices made for this project. At the start of the next design for the same person/team,
   read it and choose differently unless they ask for consistency.

## 5. When a "banned" thing is actually right

The brief's words always win. If the client or brand says "we use Inter", "cream and terracotta", "dark with
a green accent", or "glassmorphism", use it, and then make the *other* choices distinctive. Equally, some
tells are correct in context: a tracked-caps label on a legal notice, a left stripe on a *blockquote in a
printed-style essay*, numbered markers on a real 5-step process, a gradient in a brand that is
literally a sunset. The test: could you defend it to a client by pointing at the subject? If the only defence is
"it looks modern", it's a default.

## 6. Self-critique scoring

Score the build 1–10 on each axis, be harsh, and fix anything below 7 before shipping.

| Axis | 9–10 looks like | ≤5 looks like |
|---|---|---|
| Typography | Chosen pairing, real scale, display leading/tracking tuned, good measure | Reflex font, flat sizes, body leading on headlines |
| Colour | Subject-derived, tinted neutrals, one accent, verified contrast | Grey + indigo, gradients, pure black/white |
| Spacing | One scale, clear proximity groups, varied section rhythm | Uniform padding, boxes floating, cramped or lost |
| Composition | Clear focal point, deliberate asymmetry or grid break | Centred stack of identical blocks |
| Motion | One orchestrated moment, interruptible UI, reduced-motion handled | Fade-up everywhere, bounce, no reduced-motion |
| Originality | Fails the swap test (could only be this subject) | Passes the swap test (could be anything) |

Report the scores honestly in your handoff note only if the user asked for a critique; otherwise just fix.
