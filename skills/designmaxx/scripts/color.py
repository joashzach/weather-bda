#!/usr/bin/env python3
"""
color.py - stdlib-only colour tooling for design-craft.

  python3 color.py contrast "#0F1B22" "#EEF2F4"        # WCAG 2.x + APCA Lc
  python3 color.py oklch "#0B6E99"                      # hex -> oklch()
  python3 color.py ramp "#0B6E99" --steps 11            # perceptual ramp, hue-drifted
  python3 color.py palette palette.json                 # audit a role palette
  python3 color.py tint 11 --hue 235 --chroma 0.012     # tinted neutral ramp

palette.json shape: {"bg":"#..","surface":"#..","ink":"#..","muted":"#..",
                     "accent":"#..","accent2":"#..","line":"#.."}
Never claim a contrast ratio you have not computed with this script.
"""
import argparse
import json
import math
import sys


def hex_to_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(c))):02X}" for c in rgb)


def _lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _unlin(c):
    c = max(0.0, min(1.0, c))
    return 255 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055)


def luminance(rgb):
    r, g, b = (_lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def wcag(fg, bg):
    l1, l2 = luminance(hex_to_rgb(fg)), luminance(hex_to_rgb(bg))
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def apca(fg, bg):
    """APCA-W3 0.0.98G-4g. Returns signed Lc.
    |Lc| 75+ body text, 60+ large text, 45+ minimum for UI glyphs."""
    def y(rgb):
        r, g, b = (c / 255 for c in rgb)
        v = 0.2126729 * r ** 2.4 + 0.7151522 * g ** 2.4 + 0.0721750 * b ** 2.4
        return v if v >= 0.022 else v + (0.022 - v) ** 1.414

    yt, yb = y(hex_to_rgb(fg)), y(hex_to_rgb(bg))
    if abs(yb - yt) < 0.0005:
        return 0.0
    if yb > yt:
        sapc = (yb ** 0.56 - yt ** 0.57) * 1.14
        out = 0 if sapc < 0.1 else sapc - 0.027
    else:
        sapc = (yb ** 0.65 - yt ** 0.62) * 1.14
        out = 0 if sapc > -0.1 else sapc + 0.027
    return out * 100


def rgb_to_oklab(rgb):
    r, g, b = (_lin(c) for c in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (math.copysign(abs(x) ** (1 / 3), x) for x in (l, m, s))
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def _oklch_to_lin(L, C, H):
    a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def hex_to_oklch(h):
    L, a, b = rgb_to_oklab(hex_to_rgb(h))
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def oklch_to_hex(L, C, H):
    """Gamut-map by reducing chroma until the colour fits sRGB."""
    for _ in range(60):
        lin = _oklch_to_lin(L, C, H)
        if all(-0.0005 <= c <= 1.0005 for c in lin):
            break
        C *= 0.95
    return rgb_to_hex(tuple(_unlin(c) for c in _oklch_to_lin(L, C, H)))


def fmt_oklch(h):
    L, C, H = hex_to_oklch(h)
    return f"oklch({L * 100:.1f}% {C:.3f} {H:.0f})"


def verdict(r):
    return "AAA" if r >= 7 else "AA" if r >= 4.5 else "AA-large/UI" if r >= 3 else "FAIL"


def cmd_contrast(a):
    r = wcag(a.fg, a.bg)
    print(f"WCAG {r:.2f}:1 ({verdict(r)})   APCA Lc {apca(a.fg, a.bg):+.1f}")


def cmd_oklch(a):
    print(fmt_oklch(a.color))


def cmd_ramp(a):
    _, C0, H0 = hex_to_oklch(a.color)
    n = a.steps
    for i in range(n):
        t = i / (n - 1)
        L = 0.97 - t * (0.97 - 0.18)  # light -> dark
        C = C0 * (0.12 + 1.05 * math.sin(math.pi * (0.1 + 0.8 * t)) ** 1.4)
        H = H0 + (t - 0.5) * a.drift  # hue drift keeps ramps alive
        label = 50 if i == 0 else i * 100 if i < n - 1 else 950
        print(f"--{a.name}-{label}: {oklch_to_hex(L, C, H)};  /* oklch({L * 100:.0f}% {C:.3f} {H % 360:.0f}) */")


def cmd_tint(a):
    n = a.steps
    for i in range(n):
        t = i / (n - 1)
        L = 0.98 - t * 0.86
        label = 50 if i == 0 else i * 100 if i < n - 1 else 950
        print(f"--n-{label}: {oklch_to_hex(L, a.chroma, a.hue)};")


def cmd_palette(a):
    """Audit a role palette. accent text-on-bg >= 3 (UI) and the best label colour
    (ink or bg) on each accent *fill* >= 4.5. accent2 is fill-only by convention."""
    p = json.load(open(a.file))
    bg = p["bg"]
    best = lambda fill: max((wcag(p["ink"], fill), "ink"), (wcag(p["bg"], fill), "bg"))
    rows = [("ink on bg", wcag(p["ink"], bg), 7.0, apca(p["ink"], bg)),
            ("muted on bg", wcag(p["muted"], bg), 4.5, apca(p["muted"], bg)),
            ("ink on surface", wcag(p["ink"], p["surface"]), 7.0, apca(p["ink"], p["surface"])),
            ("muted on surface", wcag(p["muted"], p["surface"]), 4.5, apca(p["muted"], p["surface"])),
            ("accent on bg (UI/links)", wcag(p["accent"], bg), 3.0, apca(p["accent"], bg))]
    lab, who = best(p["accent"])
    rows.append((f"label({who}) on accent fill", lab, 4.5, apca(p[who], p["accent"])))
    if "accent2" in p:
        lab2, who2 = best(p["accent2"])
        rows.append((f"label({who2}) on accent2 fill", lab2, 4.5, apca(p[who2], p["accent2"])))
    bad = 0
    for name, r, need, lc in rows:
        ok = r >= need
        bad += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {name:28} {r:5.2f}:1 (want {need})  Lc {lc:+.0f}")
    for k, v in p.items():
        if v.upper() in ("#000000", "#FFFFFF") and k != "surface":
            print(f"warn {k} is pure {v}; tint it")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("contrast")
    c.add_argument("fg")
    c.add_argument("bg")
    c.set_defaults(f=cmd_contrast)
    o = sub.add_parser("oklch")
    o.add_argument("color")
    o.set_defaults(f=cmd_oklch)
    r = sub.add_parser("ramp")
    r.add_argument("color")
    r.add_argument("--steps", type=int, default=11)
    r.add_argument("--drift", type=float, default=18)
    r.add_argument("--name", default="c")
    r.set_defaults(f=cmd_ramp)
    t = sub.add_parser("tint")
    t.add_argument("steps", type=int)
    t.add_argument("--hue", type=float, default=240)
    t.add_argument("--chroma", type=float, default=0.01)
    t.set_defaults(f=cmd_tint)
    p = sub.add_parser("palette")
    p.add_argument("file")
    p.set_defaults(f=cmd_palette)
    args = ap.parse_args()
    args.f(args)
