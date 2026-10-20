---
name: Monsoon
description: An atmospheric observatory for weather intelligence and report review.
colors:
  accent: "#ff793b"
  signal: "#ffb94f"
  midnight: "#181715"
  map: "#24211b"
  map-land: "#433a2b"
  carbon-soft: "#24211d"
  ice: "#181715"
  surface: "#f2ede4"
  ink: "#f2ede4"
  muted: "#b5ac9d"
  line: "#494238"
  wash: "#34271f"
  light-ink: "#f2ede4"
  light-muted: "#cec2ac"
  tab-fill: "#ff793b"
  tab-ink: "#21150d"
  amber: "#ffb94f"
  amber: "#775b1b"
  red: "#964646"
typography:
  display:
    fontFamily: "Barlow Condensed, Georgia, serif"
    fontSize: "clamp(88px, 9.6vw, 156px)"
    fontWeight: 400
    lineHeight: 0.85
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Barlow Condensed, Georgia, serif"
    fontSize: "clamp(46px, 5vw, 72px)"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Barlow Condensed, Georgia, serif"
    fontSize: "34px"
    fontWeight: 400
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Hanken Grotesk, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 400
  label:
    fontFamily: "Hanken Grotesk, Segoe UI, sans-serif"
    fontSize: "12px"
    fontWeight: 400
rounded:
  panel: "0px"
  sm: "6px"
  map: "16px"
  pill: "100px"
spacing:
  compact: "12px"
  control: "20px"
  group: "32px"
  section: "40px"
  gutter: "56px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "46px"
  button-primary-hover:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface}"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "46px"
  button-hero:
    backgroundColor: "{colors.tab-fill}"
    textColor: "{colors.tab-ink}"
    rounded: "{rounded.pill}"
    padding: "0 22px"
    height: "54px"
  search:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    height: "44px"
    width: "150px"
  nav-item:
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "12px 13px"
    height: "44px"
  period-chip:
    backgroundColor: "{colors.wash}"
    textColor: "{colors.muted}"
    rounded: "{rounded.pill}"
    padding: "0 18px"
    height: "38px"
  map-container:
    backgroundColor: "{colors.map}"
    textColor: "{colors.light-ink}"
    rounded: "{rounded.map}"
---

# Design System: Monsoon

## Overview

**Creative North Star: "The Atmospheric Observatory"**

Monsoon combines a cinematic weather world with a precise editorial workspace. Its primary visual references are the immersive pacing of CSS Design Awards projects Lusion v3 and Oryzo AI. Electric ultramarine fields, signal orange and amber particles, generous negative space, and expressive serif type establish the atmosphere; restrained sans-serif controls make the data usable.

The user explicitly requested a full reset from the previous orange/cream identity and dense dashboard treatment. Bold motion is part of the identity: the introductory particle globe rotates, expands, and disperses into a field as scrolling advances. The workspace is quieter so that report review remains legible. Demo and model limitations remain visible.

**Key Characteristics:**

- Immersive, scroll-driven atmosphere.
- Large serif statements with italic counterpoints.
- Open analytical sections and sparse horizontal navigation.
- Clear separation of sample data, model suggestions, and human verification.

## Colors

The vivid palette uses large carbon fields, signal orange controls, amber selection feedback, and a pale lavender workspace. The earlier motion toggle is removed; OS reduced-motion preferences remain supported.

### Primary

- **Observatory Blue:** Primary actions, selected navigation, focus, and data accents.
- **Signal Light:** Particle field, geographic markers, and active states on dark surfaces.

### Neutral

- **Midnight:** Full-bleed introductory world and deepest background.
- **Map / Map Land / Carbon Soft:** Geographic surface and layered dark controls.
- **Ice / Surface:** Workspace background and quiet container surfaces.
- **Ink / Muted / Line / Wash:** Reading hierarchy, separators, and selected-control grounds.
- **Light Ink / Light Muted:** Reading hierarchy on dark scenes.
- **Amber / Red:** Review warnings and error semantics, subordinate to the main palette.

**The Signal Rule.** Reserve luminous blue for atmosphere, interaction, and information emphasis; it should not become a decorative fill on every section.

## Typography

**Display Font:** Barlow Condensed, with Georgia and serif fallback.

**Body Font:** Hanken Grotesk, with Segoe UI and sans-serif fallback.

**Character:** The serif supplies a fluid, editorial voice. The sans-serif supplies compact, even, readable interface text. Display and operational typography have distinct jobs.

### Hierarchy

- **Display:** Introductory statements; paired upright and italic lines. Mobile uses a viewport-based scale and slightly looser line height.
- **Headline:** Section openings with low weight and tight tracking.
- **Title:** Map and distribution headings; report headings have a larger editorial treatment.
- **Body:** Standard interface reading; supporting prose uses generous line height.
- **Label:** Sentence-case navigation and controls. Small annotations remain secondary.

**The Two Voices Rule.** Use serif for statements and section headings; retain sans-serif for metrics, controls, tables, and annotations.

## Layout

The introductory world fills the viewport. The desktop navigation is a fixed horizontal strip; its color follows the dark-to-light scene transition. The analytical content uses a centered container with a maximum width of (1320px), internal desktop gutters of (56px), and a larger-screen container of (1480px).

The metrics form four open columns divided by thin vertical rules. The main visual area pairs a wide map with a narrower distribution column, with a (40px) gap. The reports section spans the container and scrolls horizontally when its table exceeds available width. Sections use space and rules rather than a grid of floating cards.

Responsive steps occur at (1700px), (1250px), (1020px), and (720px). Mobile uses (22px) gutters, two-column metrics, a single-column visual area, icon navigation, and a separate utility strip. Filters wrap and period controls stretch across the available width.

## Elevation & Depth

Most analytical surfaces are flat. Tonal contrast and separators establish hierarchy; the map and introduction provide the deep visual field. Perspective movement belongs to the map entrance, while particle projection supplies atmospheric depth. Shadows are reserved for transient overlays.

### Shadow Vocabulary

- **Review dialog:** Broad midnight shadow for a blocking detail surface.
- **Toast:** Soft, smaller shadow for temporary feedback.

**The Flat Workspace Rule.** Keep normal data sections free of decorative elevation; reserve depth for atmosphere and transient layers.

## Shapes

Open sections and tables use square geometry. Buttons and segmented periods use fully rounded pills. The map and dialog have softened corners (16px), while small fields and error areas use a modest corner (6px). Charts and marker dots use circles because their geometry carries information.

## Components

### Buttons

Quiet, tactile controls with clear state changes. Primary buttons use blue; outline buttons inherit the workspace ground. Hover changes the surface to ink and reverses text. The hero pill reverses from transparent to light. Press scales controls slightly. Export, pagination, map controls, and the hero entry use React Bits magnetic feedback for fine pointers, with deliberately limited travel.

### Chips

Period controls share a washed pill track and a light selected pill. Verification badges use muted green, amber, and red grounds with explicit text. Color never replaces the status label.

### Cards / Containers

The map is the signature dark container. Distribution and reports are open, unboxed sections. Avoid adding nested borders and unnecessary internal shells. Panel headings pair serif titles with short sans-serif explanations.

### Inputs / Fields

Filters are simple transparent selects; search uses an underline. Mobile filters gain a light surface and modest corners for touch clarity. Maintain visible keyboard focus and readable placeholders.

### Navigation

Sparse horizontal navigation with a growing underline on hover and an accented active item. Icons replace text at narrower desktop widths; mobile retains an operable fixed row and utility strip. Do not recreate the earlier full-height sidebar.

### Atmospheric introduction

A deterministic local particle field is a visual metaphor, not measured weather. A pinned GSAP ScrollTrigger timeline advances clipped text scenes while the globe rotates and disperses. The introduction includes an immediate skip control. React Bits CountUp animates metrics and Magnet enhances controls; and map, donut, and report rows enter on scroll. OS reduced-motion preferences suppress pinned and decorative movement while preserving content and task access.

## Do's and Don'ts

### Do:

- **Do** use CSS Design Awards references for pacing, scale, and technical ambition.
- **Do** preserve generous open space and one clear reading order.
- **Do** make scroll movement visibly respond to progress and keep controls immediately usable.
- **Do** keep demo labels, trust distinctions, skip access, and reduced-motion behavior.

### Don't:

- **Don't** restore the rejected orange/cream identity or dense card grid.
- **Don't** replace the editorial serif pairing with generic heavy dashboard headings.
- **Don't** scatter glow, badges, and decorative labels across every component.
- **Don't** present the particle field or demo classifications as live weather or real AI inference.

### Selection and animated tabs

Location filters replace only the dashboard region. Keep the pinned introduction mounted and preserve viewport/focus during filtering. Retain contextual map markers; the selected marker is amber and can be toggled off with click, Enter or Space, or the clear button. The section indicator slides between active navigation items; navigation labels roll on hover. Period selectors share a signal orange sliding pill. Motion follows OS reduced-motion preferences; there is no manual motion switch.


## Current direction — storm instruments

The attached design-craft (1).skill governs this pass. Weather analysts filter reports and review provenance in a product dashboard with an explicitly requested showcase motion tier. The reference world is weather-station instruments: carbon housings, orange signal controls, amber plotted observations. Dark is the default; the optional light palette uses stone and dark burnt orange.

Palette: bg #181715, surface #211f1b, ink #f2ede4, muted #b5ac9d, accent #ff793b, signal #ffb94f. Light: bg #e5dfd3, surface #f2ede4, ink #241e17, muted #655b4f, accent #a7380c. Barlow Condensed 700/800 headings and tabular totals pair with Hanken Grotesk UI. No italic accent headline.

Layout: left-aligned full-screen particle field and headline → ruled filters and metrics → geographic view / event breakdown → report ledger. Preserve the uncluttered layout. Motion beats: globe arrival → scroll-driven dispersal → chart/metric assembly → report inspection. The field uses 2,600 precomputed points, three depth bands, fillRect drawing, capped DPR, timestamp-based time, interpolated pointer/progress, and visibility pausing. Both intro buttons run the scroll sequence in 2.8 seconds; wheel, touch, and keyboard interrupt it. Theme choice persists locally and does not rebuild the page.

Throughout the workspace: React Bits magnetic controls, pointer-centred button sweeps, shared tab indicators, metric masks, staggered breakdown rows, trend-bar growth, marker selection feedback, report icon interaction and dialog entrance. Reduced motion disables choreography. Partial data/map updates retain the existing pinned intro and scroll position.

Compared with the default soft dashboard, this direction changes palette, weight/width hierarchy and particle rendering. Principles: geographic context before charts; strong headings with quiet supporting data; animated feedback belongs to real controls. Retain sample-data disclosure.

