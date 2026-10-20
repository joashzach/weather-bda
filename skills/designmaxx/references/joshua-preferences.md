# Joshua’s design preferences

## What he means by bold

Bold means strong, committed color and heavy, confident typography—not a palette of bright pastel hues or extra decoration. He explicitly approved Monsoon’s charcoal, signal-orange and amber direction after rejecting the pale/blue/purple/fuchsia/cyan iterations and the delicate serif headings. Treat the approved direction as a useful benchmark, not a requirement to make every project look like Monsoon.

- Prefer dark-first compositions with strong, rich colors. He generally dislikes light or blue-led palettes. A light theme is welcome as an optional toggle; use warm stone and clear dark ink rather than a pale blue wash.
- Use weight, width and scale to establish typographic authority. Heavy condensed sans-serif display text worked particularly well. Avoid reflex thin/dainty headings and single-word italic-serif accents. Keep supporting UI readable.
- Preserve clean composition, breathing room, hierarchy and restrained grouping. He specifically liked the less cluttered dashboard. More animation must not mean more boxes, labels or visual noise.
- Motion should be obvious, smooth and interactive across the page, not concentrated only in the hero. He asks for animated section tabs, buttons, map selection, metrics, charts and report interactions. A token fade-in on every section is insufficient.
- Use scroll storytelling with a clearly visible particle/3D or other signature field when appropriate. Particles must remain legible against the background and responsive to scrolling or the pointer. Smoothness and visibility matter more than particle count or elaborate geometry.
- Intro navigation should smoothly travel through the story and land at the content. Avoid abrupt jumps or bypassing the entire animation. Let the user interrupt programmatic travel.
- React Bits interactions and GSAP scroll choreography are welcome when they add noticeable, functional feedback. CSS Design Awards is a stronger visual reference than generic dashboard templates. Borrow craft, rhythm and interaction principles rather than copying a particular site.
- Avoid a dedicated “Motion on” toolbar control unless he requests it again. Continue honoring OS reduced-motion preferences. He explicitly requested a persistent dark/light theme toggle.
- Preserve usability: map selections must not jump to the top, active selections must toggle off, clear controls must be available, and visual polish must retain filters and review workflows.

## Approved Monsoon benchmark

Dark: background #181715, surface #211f1b, ink #f2ede4, muted #b5ac9d, signal orange #ff793b, amber #ffb94f.
Optional light: background #e5dfd3, surface #f2ede4, ink #241e17, muted #655b4f, dark orange #a7380c.
Type: Barlow Condensed 700/800 for large headings and totals; Hanken Grotesk for controls and reading text.
Composition: full-width atmospheric intro → ruled metrics and filters → map and event breakdown → report ledger.
Motion: visible amber particle globe dispersing with scroll, shared tab indicators, magnetic controls, pointer-following button sweeps, chart assembly, marker feedback and dialog entrance.

## How to apply without overfitting

Start with a subject-specific strong-color world and confident type. Keep layout disciplined, then design meaningful motion throughout the actual controls and data. Verify contrast, keyboard/touch behavior, mobile width and reduced motion. For a different subject, choose a different rich palette or display family if it fits better; preserve the qualities he approved. Do not turn his dislike of one palette into a ban on all blue or all light surfaces when a future brief explicitly asks for them.
