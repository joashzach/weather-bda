#!/usr/bin/env python3
"""
slop_scan.py - deterministic "does this look vibe-coded?" detector. Stdlib only.

  python3 slop_scan.py path/to/file_or_dir [more paths] [--json] [--min high|med|low]

Scans .html .htm .css .scss .jsx .tsx .js .ts .vue .svelte .astro .mdx
Exit code: 0 clean (no high findings), 2 high-severity findings, 1 bad input.

A clean run is evidence, not proof. Still look at the rendered result.
Each rule maps to a section in references/anti-slop.md.
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    from color import hex_to_oklch
except Exception:  # pragma: no cover
    hex_to_oklch = None

EXTS = {".html", ".htm", ".css", ".scss", ".jsx", ".tsx", ".js", ".ts", ".vue", ".svelte", ".astro", ".mdx"}
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".nuxt", "coverage", ".impeccable", "vendor"}
SEV = {"high": 3, "med": 2, "low": 1}

BAD_FONTS = ["inter", "roboto", "arial", "helvetica", "helvetica neue", "system-ui", "-apple-system",
             "blinkmacsystemfont", "segoe ui", "space grotesk", "dm sans", "poppins", "playfair display",
             "open sans", "lato", "montserrat", "nunito", "sf pro"]

AI_WORDS = ["elevate your", "seamless", "seamlessly", "unleash", "supercharge", "revolutionize", "cutting-edge",
            "next-generation", "next-gen", "game-changer", "game changing", "all-in-one", "empower",
            "unlock the power", "unlock your", "delve", "tapestry", "in today's fast-paced", "lorem ipsum",
            "acme", "john doe", "jane doe", "sarah chen", "take it to the next level", "built for the future",
            "reimagine", "harness the power", "streamline your", "effortless", "effortlessly", "blazing fast",
            "lightning-fast", "world-class", "robust solution", "one-stop"]

# (id, severity, message, fix) - used for reporting + the summary table
RULES = {
    "overused-font": ("high", "Reflex font as primary family", "Choose a deliberate pairing (references/foundations.md)."),
    "gradient-text": ("high", "Gradient-filled text (background-clip:text)", "Use a solid colour; emphasise with weight, size, or position."),
    "purple-gradient": ("high", "Purple/indigo/pink gradient", "Drop the gradient or pick a palette from a real subject world."),
    "pure-black-white": ("med", "Pure #000 / #fff used for text or surfaces", "Tint neutrals toward the brand hue (oklch chroma 0.005-0.02)."),
    "side-stripe": ("high", "Coloured left-border stripe on a card/alert", "Use full border, background tint, or an icon. Never a >1px side stripe."),
    "transition-all": ("med", "transition: all", "List exact properties: transition-property: opacity, transform."),
    "bounce-easing": ("high", "Bounce/elastic/overshoot easing", "Use ease-out-quart/expo or a spring with bounce:0."),
    "glow-shadow": ("med", "Large coloured glow shadow", "Use layered low-opacity shadows; glows are a dark-mode cliché."),
    "uniform-radius": ("med", "One border-radius on nearly everything", "Vary radius by hierarchy; nested radius = outer - padding."),
    "eyebrow-caps": ("med", "Tracked ALL-CAPS micro-labels used repeatedly", "Drop most eyebrows; only keep ones that encode real information."),
    "ai-copy": ("med", "Stock AI marketing copy / placeholder names", "Write specific, plain copy from the subject's real vocabulary."),
    "emoji-icons": ("med", "Emoji used as UI icons", "Use a consistent icon set or custom SVG."),
    "fade-up-everywhere": ("med", "Same fade-up entrance repeated on many elements", "Orchestrate one signature reveal; leave the rest static."),
    "hover-lift": ("low", "translateY/scale lift on many hovers", "Keep hover feedback to colour/underline; reserve motion for key controls."),
    "no-reduced-motion": ("high", "Motion present but no prefers-reduced-motion handling", "Add a reduced-motion block / gsap.matchMedia branch."),
    "focus-removed": ("high", "outline removed without :focus-visible replacement", "Style :focus-visible visibly; never remove outlines bare."),
    "zoom-disabled": ("high", "Viewport blocks pinch zoom", "Remove user-scalable=no / maximum-scale=1."),
    "tiny-text": ("med", "Text smaller than 12px", "Minimum 12px for captions, 16px for body on mobile inputs."),
    "default-shadcn": ("med", "Untouched default shadcn/ui zinc theme tokens", "Replace --background/--primary etc. with your own palette."),
    "default-tailwind-greys": ("low", "Heavy use of default Tailwind grey scale", "Define tinted neutrals as tokens."),
    "saas-card-kit": ("med", "Repeated 'rounded border shadow-sm p-6' card kit", "Vary containers; not everything is a card."),
    "nested-cards": ("med", "Card nested inside a card", "Flatten: use spacing, dividers, or background shift instead."),
    "tiny-hit-area": ("low", "Interactive element likely under 40x40px", "Extend hit area with padding or ::after."),
    "fake-metrics": ("low", "Round vanity metrics (10x, 99.9%, 1M+)", "Use real figures or none."),
    "infinite-float": ("low", "Infinite float/pulse decorative animation", "Remove ambient loops unless they carry meaning."),
    "bg-blob": ("low", "Blurred gradient blob/orb background", "Use a real image, texture, or flat colour field."),
}


class Finding:
    def __init__(self, rule, path, line, snippet):
        self.rule, self.path, self.line = rule, path, line
        self.snippet = snippet.strip()[:140]
        self.sev = RULES[rule][0]

    def as_dict(self):
        return {"rule": self.rule, "severity": self.sev, "file": self.path, "line": self.line,
                "message": RULES[self.rule][1], "fix": RULES[self.rule][2], "snippet": self.snippet}


def line_of(text, idx):
    return text.count("\n", 0, idx) + 1


def iter_files(paths):
    for p in paths:
        if os.path.isfile(p):
            yield p
        else:
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for f in files:
                    if os.path.splitext(f)[1].lower() in EXTS:
                        yield os.path.join(root, f)


def hue_is_purple(hexcolor):
    if not hex_to_oklch:
        return False
    try:
        h = hexcolor.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        L, C, H = hex_to_oklch("#" + h[:6])
        return C > 0.10 and 285 <= H <= 355  # violet..magenta in OKLCH hue degrees
    except Exception:
        return False


def mask_comments(text):
    """Blank out /* */ and <!-- --> comments, preserving newlines so line numbers stay right."""
    blank = lambda m: re.sub(r"[^\n]", " ", m.group(0))
    return re.sub(r"/\*[\s\S]*?\*/|<!--[\s\S]*?-->", blank, text)


def scan_text(path, text):
    text = mask_comments(text)
    out = []
    add = lambda rule, idx, snip: out.append(Finding(rule, path, line_of(text, idx), snip))
    low = text.lower()

    # --- fonts -------------------------------------------------------------
    for m in re.finditer(r"font-family\s*:\s*([^;}{]+)", text, re.I):
        first = m.group(1).split(",")[0].strip().strip("'\"").lower()
        if first in BAD_FONTS:
            add("overused-font", m.start(), m.group(0))
    for m in re.finditer(r"fonts\.googleapis\.com/css2?\?family=([^\"'&]+)", text, re.I):
        fam = re.split(r"[:;+]", m.group(1).replace("+", " "))[0].strip().lower()
        if fam in BAD_FONTS:
            add("overused-font", m.start(), m.group(0))
    for m in re.finditer(r"font-(?:sans|serif)\s*:\s*\[?['\"]?([A-Za-z ]+)", text):  # tailwind config
        if m.group(1).strip().lower() in BAD_FONTS:
            add("overused-font", m.start(), m.group(0))
    for m in re.finditer(r"from ['\"]next/font/google['\"]", text):
        for f in re.finditer(r"\b(Inter|Roboto|Poppins|Space_Grotesk|DM_Sans|Playfair_Display|Open_Sans|Montserrat)\b", text):
            add("overused-font", f.start(), f.group(0))
        break

    # --- gradients ---------------------------------------------------------
    for m in re.finditer(r"background-clip\s*:\s*text|bg-clip-text", text, re.I):
        ctx = text[max(0, m.start() - 300): m.end() + 300].lower()
        if "gradient" in ctx or "text-transparent" in ctx or "-webkit-text-fill-color: transparent" in ctx:
            add("gradient-text", m.start(), m.group(0))
    for m in re.finditer(r"(from|via|to)-(purple|violet|indigo|fuchsia|pink)-\d{2,3}", text):
        add("purple-gradient", m.start(), m.group(0))
    for m in re.finditer(r"(?:linear|radial|conic)-gradient\(([^;{}]*)\)", text, re.I | re.S):
        hexes = re.findall(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b", m.group(1))
        if sum(hue_is_purple(h) for h in hexes) >= 1 and len(hexes) >= 2:
            add("purple-gradient", m.start(), m.group(0))
        elif re.search(r"\b(purple|violet|indigo|fuchsia|magenta)\b", m.group(1), re.I):
            add("purple-gradient", m.start(), m.group(0))

    # --- colour tells ------------------------------------------------------
    for m in re.finditer(r"(?<![\w-])(color|background(?:-color)?)\s*:\s*(#000000|#000|#fff|#ffffff|black|white|rgb\(\s*0\s*,\s*0\s*,\s*0\s*\))\s*[;}\n]", text, re.I):
        # allow white text on dark brand fills? still flag: tint it
        add("pure-black-white", m.start(), m.group(0))
    for m in re.finditer(r"\b(?:text|bg)-(?:black|white)\b", text):
        add("pure-black-white", m.start(), m.group(0))

    # --- borders / cards ---------------------------------------------------
    for m in re.finditer(r"border-left\s*:\s*([2-9]|\d{2})px\s+solid|border-inline-start\s*:\s*([2-9])px\s+solid|\bborder-l-(?:[2-9]|\[[2-9]px\])\b", text, re.I):
        add("side-stripe", m.start(), m.group(0))

    # --- motion ------------------------------------------------------------
    for m in re.finditer(r"transition\s*:\s*all\b|\btransition-all\b|transition-property\s*:\s*all\b", text, re.I):
        add("transition-all", m.start(), m.group(0))
    for m in re.finditer(r"cubic-bezier\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)", text):
        try:
            y1, y2 = float(m.group(2)), float(m.group(4))
            if y1 < -0.05 or y1 > 1.05 or y2 < -0.05 or y2 > 1.05:
                add("bounce-easing", m.start(), m.group(0))
        except ValueError:
            pass
    for m in re.finditer(r"\b(ease-?in-?out-?back|ease-?out-?back|easeOutBack|easeOutElastic|elastic\.(?:out|in|inOut)|bounce\.(?:out|in|inOut)|Elastic|Bounce|back\.out)\b|bounce\s*:\s*(0\.[3-9]|[1-9])", text):
        add("bounce-easing", m.start(), m.group(0))
    for m in re.finditer(r"(?:box-shadow|drop-shadow|filter)\s*:?[^;{}\n]*?0\s+0\s+(\d{2,3})px", text, re.I):
        if int(m.group(1)) >= 30:
            add("glow-shadow", m.start(), m.group(0))
    for m in re.finditer(r"shadow-\[0_0_(\d{2,3})px", text):
        if int(m.group(1)) >= 30:
            add("glow-shadow", m.start(), m.group(0))
    fades = list(re.finditer(r"fade-?in-?up|fade-?up|animate-fade|slide-?up|whileInView|data-aos|\.reveal\b", text, re.I))
    if len(fades) >= 6:
        add("fade-up-everywhere", fades[0].start(), f"{len(fades)} fade/slide-up entrances in this file")
    lifts = list(re.finditer(r"hover:-translate-y|hover:scale-\[?1[01]|:hover\s*\{[^}]*translateY\(-|whileHover\s*=\s*\{\{\s*y\s*:\s*-", text, re.I))
    if len(lifts) >= 4:
        add("hover-lift", lifts[0].start(), f"{len(lifts)} hover-lift effects in this file")
    for m in re.finditer(r"animation\s*:[^;{}]*\binfinite\b|animate-(?:pulse|bounce|float|ping)\b", text, re.I):
        add("infinite-float", m.start(), m.group(0))
    for m in re.finditer(r"filter\s*:\s*blur\(\s*(\d{2,3})px\s*\)|\bblur-(?:2xl|3xl|\[\d{2,3}px\])\b", text, re.I):
        ctx = text[max(0, m.start() - 250): m.end() + 250].lower()
        if "gradient" in ctx or "rounded-full" in ctx or "border-radius: 50%" in ctx or "absolute" in ctx or "position: absolute" in ctx:
            add("bg-blob", m.start(), m.group(0))

    # --- a11y --------------------------------------------------------------
    for m in re.finditer(r"outline\s*:\s*(none|0)\b|\boutline-none\b", text, re.I):
        ctx = text[max(0, m.start() - 200): m.end() + 400].lower()
        if "focus-visible" not in ctx and "focus:ring" not in ctx and "focus-visible:" not in ctx and "ring-" not in ctx:
            add("focus-removed", m.start(), m.group(0))
    for m in re.finditer(r"user-scalable\s*=\s*(no|0)|maximum-scale\s*=\s*1(?:\.0)?\b", text, re.I):
        add("zoom-disabled", m.start(), m.group(0))
    for m in re.finditer(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", text, re.I):
        if float(m.group(1)) < 12:
            add("tiny-text", m.start(), m.group(0))
    for m in re.finditer(r"\btext-\[(\d+)px\]", text):
        if int(m.group(1)) < 12:
            add("tiny-text", m.start(), m.group(0))
    for m in re.finditer(r"\b(?:w|h)-(?:[1-5])\b(?=[^\"'`]*\b(?:button|onClick|href)\b)", text):
        pass  # too noisy; kept for future

    # --- copy --------------------------------------------------------------
    strings = re.sub(r"<style[\s\S]*?</style>|<script[\s\S]*?</script>", " ", low)
    hits = [w for w in AI_WORDS if w in strings]
    if hits:
        first = min(low.find(w) for w in hits if low.find(w) >= 0)
        out.append(Finding("ai-copy", path, line_of(text, first), "phrases: " + ", ".join(hits[:8])))
    emoji = re.findall(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", re.sub(r"<link[^>]*>|<title>[^<]*</title>", "", text))
    if len(emoji) >= 3 and os.path.splitext(path)[1].lower() in {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".astro"}:
        idx = re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", text).start()
        add("emoji-icons", idx, f"{len(emoji)} emoji in markup")
    for m in re.finditer(r"\b(10x|100x|99\.9%|1M\+|10k\+|50k\+|100k\+|1,000,000\+)\b", text, re.I):
        add("fake-metrics", m.start(), m.group(0))
        break

    # --- structural tells --------------------------------------------------
    caps = list(re.finditer(r"text-transform\s*:\s*uppercase|\buppercase\b", text))
    tracked = list(re.finditer(r"letter-spacing\s*:\s*0?\.(0[89]|[1-9]\d*)em|\btracking-(?:wider|widest)\b|tracking-\[0?\.[1-9]", text))
    if len(caps) >= 3 and len(tracked) >= 3:
        add("eyebrow-caps", tracked[0].start(), f"{len(caps)} uppercase + {len(tracked)} tracked labels")
    else:
        eb = list(re.finditer(r"class(?:Name)?\s*=\s*[\"'][^\"']*\b(?:eyebrow|kicker|overline|section-label|pre-?title)\b", text, re.I))
        if len(eb) >= 3:
            add("eyebrow-caps", eb[0].start(), f"{len(eb)} eyebrow/kicker labels in markup")
    radii = re.findall(r"border-radius\s*:\s*([^;}{]+)", text) + re.findall(r"\brounded(?:-[a-z0-9]+)?\b(?!-)", text)
    radii = [r.strip() for r in radii if r.strip() not in {"0", "0px", "50%", "9999px", "999px", "100%", "rounded-full", "inherit"}]
    if len(radii) >= 8:
        top = max(set(radii), key=radii.count)
        if radii.count(top) / len(radii) >= 0.8:
            out.append(Finding("uniform-radius", path, 1, f"'{top}' on {radii.count(top)}/{len(radii)} radii"))
    kit = re.findall(r"rounded-(?:xl|2xl|3xl)[^\"'`]*\bborder\b[^\"'`]*\bshadow-(?:sm|md)?\b|rounded-(?:xl|2xl|3xl)[^\"'`]*\bshadow-(?:sm|md)\b[^\"'`]*\bborder\b", text)
    if len(kit) >= 4:
        add("saas-card-kit", text.find(kit[0]), f"{len(kit)} identical rounded+border+shadow containers")
    if re.search(r"--background\s*:\s*0\s+0%\s+100%", text) and re.search(r"--primary\s*:\s*(222\.2\s+47\.4%\s+11\.2%|240\s+5\.9%\s+10%|0\s+0%\s+9%)", text):
        add("default-shadcn", text.find("--background"), "--background/--primary are shadcn defaults")
    greys = re.findall(r"\b(?:bg|text|border|ring|from|to)-(?:slate|gray|zinc|neutral|stone)-\d{2,3}\b", text)
    if len(greys) >= 25:
        add("default-tailwind-greys", text.find(greys[0]), f"{len(greys)} default grey utilities")

    if os.path.splitext(path)[1].lower() in {".html", ".htm"}:
        out += nested_cards(path, text)
    return out


def nested_cards(path, text):
    """HTML-only: a tag whose class contains 'card' nested in another such tag."""
    res, stack = [], []
    void = {"br", "img", "input", "hr", "meta", "link", "source", "path", "circle", "rect", "use"}
    for m in re.finditer(r"<(/?)([a-zA-Z][\w-]*)([^>]*)>", text):
        closing, tag, attrs = m.group(1), m.group(2).lower(), m.group(3)
        if tag in void or attrs.rstrip().endswith("/"):
            continue
        if closing:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i][0] == tag:
                    del stack[i:]
                    break
            continue
        cls = re.search(r"class(?:Name)?\s*=\s*[\"']([^\"']*)[\"']", attrs)
        is_card = bool(cls and re.search(r"(?:^|[\s-])card(?:$|[\s-])", cls.group(1)))
        if is_card and any(s[1] for s in stack):
            res.append(Finding("nested-cards", path, line_of(text, m.start()), m.group(0)))
        stack.append((tag, is_card))
    return res[:3]


def project_checks(files_text):
    """Cross-file checks."""
    out = []
    has_motion = any(re.search(r"@keyframes|animation\s*:|transition\s*:|gsap\.|ScrollTrigger|framer-motion|from ['\"]motion|animate-", t) for _, t in files_text)
    has_rm = any(re.search(r"prefers-reduced-motion|useReducedMotion|reduced-motion|reducedMotion", t) for _, t in files_text)
    if has_motion and not has_rm:
        out.append(Finding("no-reduced-motion", files_text[0][0], 1, "motion found; no prefers-reduced-motion anywhere"))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--min", choices=["low", "med", "high"], default="low")
    a = ap.parse_args()
    files = list(iter_files(a.paths))
    if not files:
        print("no scannable files", file=sys.stderr)
        sys.exit(1)
    found, texts = [], []
    for f in files:
        try:
            t = open(f, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        texts.append((f, t))
        found += scan_text(f, t)
    found += project_checks(texts)
    found = [x for x in found if SEV[x.sev] >= SEV[a.min]]
    found.sort(key=lambda x: (-SEV[x.sev], x.path, x.line))
    high = sum(1 for x in found if x.sev == "high")
    if a.json:
        print(json.dumps({"files": len(files), "findings": [x.as_dict() for x in found], "high": high}, indent=2))
    else:
        by = defaultdict(list)
        for x in found:
            by[x.rule].append(x)
        for rule, items in sorted(by.items(), key=lambda kv: (-SEV[RULES[kv[0]][0]], kv[0])):
            sev, msg, fix = RULES[rule]
            print(f"[{sev.upper():4}] {rule}: {msg}  x{len(items)}")
            for x in items[:4]:
                print(f"        {x.path}:{x.line}  {x.snippet}")
            if len(items) > 4:
                print(f"        ... +{len(items) - 4} more")
            print(f"        fix: {fix}")
        score = max(0, 100 - sum({"high": 12, "med": 5, "low": 2}[x.sev] for x in found))
        print(f"\n{len(files)} file(s), {len(found)} finding(s), {high} high.  Slop score: {score}/100 (higher is better)")
    sys.exit(2 if high else 0)


if __name__ == "__main__":
    main()
