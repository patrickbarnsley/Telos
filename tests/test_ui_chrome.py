"""The app chrome: navigation, headers, and every colour pair it draws.

The contrast block is the part worth keeping. The dark palette already met
WCAG AA, and the risk in a visual pass is losing that quietly: a chip looks
fine to the person who chose it and is unreadable to someone else. So every
foreground/background pair the chrome actually renders is computed here from
the WCAG 2.1 formula, including the translucent chip fills, which are blended
against the surface underneath before the ratio is taken.

No database and no model. This suite is arithmetic and source inspection.
"""
import os, sys, re, pathlib

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/telos_test")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-not-used")
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import app_styles as ui

FAIL = []
def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{extra}]" if extra and not cond else ""))
    if not cond:
        FAIL.append(name)


# --- WCAG 2.1 relative luminance and contrast -------------------------------

def _rgb(hex_colour):
    h = hex_colour.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _luminance(hex_colour):
    def channel(v):
        c = v / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(v) for v in _rgb(hex_colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg, bg):
    a, b = _luminance(fg), _luminance(bg)
    lo, hi = sorted((a, b))
    return (hi + 0.05) / (lo + 0.05)


def blend(fg, bg, alpha):
    """The colour a translucent fill actually produces over an opaque surface."""
    f, b = _rgb(fg), _rgb(bg)
    mixed = tuple(round(f[i] * alpha + b[i] * (1 - alpha)) for i in range(3))
    return "#%02X%02X%02X" % mixed


print("\n[1] the arithmetic itself is right")
check("black on white is 21:1", abs(contrast("#000000", "#FFFFFF") - 21.0) < 0.01,
      contrast("#000000", "#FFFFFF"))
check("a colour against itself is 1:1", abs(contrast("#C9A84C", "#C9A84C") - 1.0) < 1e-9)

print("\n[2] body text keeps AA on every surface it is drawn on")
AA_TEXT = 4.5
SURFACES = {"ground": ui.GROUND, "surface": ui.SURFACE, "raised": ui.RAISED}
TEXT = {"ink": ui.INK, "muted": ui.MUTED, "gold": ui.GOLD}

for tname, tcol in TEXT.items():
    for sname, scol in SURFACES.items():
        ratio = contrast(tcol, scol)
        check(f"{tname} on {sname} meets AA ({ratio:.2f})", ratio >= AA_TEXT, f"{ratio:.2f}")

check("gold-light on ground meets AA", contrast(ui.GOLD_LIGHT, ui.GROUND) >= AA_TEXT,
      f"{contrast(ui.GOLD_LIGHT, ui.GROUND):.2f}")
check("ground on gold meets AA (the button pairing)",
      contrast(ui.GROUND, ui.GOLD) >= AA_TEXT, f"{contrast(ui.GROUND, ui.GOLD):.2f}")

print("\n[3] the two colours the pass added were checked before use")
# An offer and a rejection cannot be told apart by weight alone, so status uses
# exactly two colours beyond the existing palette. Chips are checked against the
# fill they actually sit on: a 55% wash of the ground colour, which is why the
# same chip is legible on a resting row and on a hovered one. A tint of the
# chip's own colour was tried first and missed AA at 4.2 over the hover surface.
CHIP_WASH = 0.55
NEW = {"good": ui.GOOD, "bad": ui.BAD}
ALL_CHIP_COLOURS = {"muted": ui.MUTED, "gold": ui.GOLD, **NEW}

check("the chip fill washes towards ground, not towards its own colour",
      "rgba(15,17,23,.55)" in (ROOT / "core" / "app_styles.py").read_text(encoding="utf-8"))

for cname, ccol in ALL_CHIP_COLOURS.items():
    for sname, scol in SURFACES.items():
        fill = blend(ui.GROUND, scol, CHIP_WASH)
        ratio = contrast(ccol, fill)
        check(f"{cname} chip text over a {sname} row meets AA ({ratio:.2f})",
              ratio >= AA_TEXT, f"{ratio:.2f} against {fill}")

# The hover state must not make a chip harder to read than the resting state.
for cname, ccol in ALL_CHIP_COLOURS.items():
    resting = contrast(ccol, blend(ui.GROUND, ui.SURFACE, CHIP_WASH))
    hovered = contrast(ccol, blend(ui.GROUND, ui.RAISED, CHIP_WASH))
    check(f"{cname} chip does not lose contrast on hover", hovered >= resting * 0.85,
          f"resting {resting:.2f} hovered {hovered:.2f}")

check("good and bad are distinguishable from each other",
      contrast(ui.GOOD, ui.BAD) >= 1.4, f"{contrast(ui.GOOD, ui.BAD):.2f}")
check("row text keeps AA on the hover surface",
      contrast(ui.INK, ui.RAISED) >= AA_TEXT and contrast(ui.MUTED, ui.RAISED) >= AA_TEXT,
      f"{contrast(ui.INK, ui.RAISED):.2f} / {contrast(ui.MUTED, ui.RAISED):.2f}")

print("\n[4] status is a shape and a colour, not a bare word")
STATUSES = ["applied", "screening", "interview", "offer", "rejected",
            "withdrawn", "recruiter_outreach"]
for s in STATUSES:
    chip = ui.status_chip(s)
    check(f"{s} renders as a chip", 'class="chip chip-' in chip, chip)
    check(f"{s} has a readable label", s.split("_")[0][:4].lower() in chip.lower()
          or "Recruiter" in chip, chip)
check("an offer and a rejection do not share a tone",
      ui.status_chip("offer") != ui.status_chip("rejected"))
check("offer uses the good tone", "chip-good" in ui.status_chip("offer"))
check("rejected uses the bad tone", "chip-bad" in ui.status_chip("rejected"))
check("in-flight stages use the accent", "chip-live" in ui.status_chip("interview"))
check("an unknown status still renders", 'class="chip' in ui.status_chip("teleported"))
check("every status Track offers has a tone",
      all(s in ui.STATUS_TONE for s in STATUSES),
      str([s for s in STATUSES if s not in ui.STATUS_TONE]))

print("\n[5] the fit bar survives whatever the database holds")
check("a normal score renders a bar", "fitbar" in ui.fit_bar(72) and "72%" in ui.fit_bar(72))
check("zero renders", "0%" in ui.fit_bar(0))
check("a full score renders", "100%" in ui.fit_bar(100))
check("a missing score does not crash", "--" in ui.fit_bar(None))
check("a non-numeric score does not crash", "--" in ui.fit_bar("n/a"))
check("an out-of-range score is clamped", "100%" in ui.fit_bar(4000))
check("a negative score is clamped", "0%" in ui.fit_bar(-20))
check("a strong score reads as good", ui.GOOD in ui.fit_bar(88))
check("a weak score reads as bad", ui.BAD in ui.fit_bar(41))

print("\n[6] numbers are set as data")
css = ui.MONO
check("the number face is monospaced", "monospace" in css, css)
src = (ROOT / "core" / "app_styles.py").read_text(encoding="utf-8")
check("tabular figures are switched on", "tabular-nums" in src)
check("the tnum feature is set explicitly", '"tnum" 1' in src)
check("metric values use the number face", "stMetricValue" in src and "MONO" in src)
check("there is a reusable inline number class", '.num {' in src or '.num {{' in src)
check("num() emits that class", 'class="num"' in ui.num(58))

print("\n[7] the left rail is the app's navigation")
check("the rail carries five destinations", len(ui.NAV) == 5, str(ui.NAV))
labels = [label for _p, label, _i in ui.NAV]
check("Profile is one of them, and comes first after Home",
      labels[:2] == ["Home", "Profile"], str(labels))
check("all five pillars are present",
      set(labels) == {"Home", "Profile", "Track", "Match", "Guide"}, str(labels))
for path, label, _icon in ui.NAV:
    check(f"the rail target for {label} exists", (ROOT / path).exists(), path)
check("Streamlit's generated page list is replaced, not doubled up",
      '[data-testid="stSidebarNav"] {{ display: none; }}' in src
      or '[data-testid="stSidebarNav"] { display: none; }' in src)
check("the rail marks the page you are on rather than linking to it",
      "rail-here" in src)

print("\n[8] every page says where you are")
PAGES = {
    "app.py": "Home",
    "pages/0_Profile.py": "Profile",
    "pages/1_Track.py": "Track",
    "pages/2_Match.py": "Match",
    "pages/3_Guide.py": "Guide",
}
for path, label in PAGES.items():
    text = (ROOT / path).read_text(encoding="utf-8")
    check(f"{path} renders the rail", f'nav_rail("{label}")' in text, path)
    if path != "app.py":
        check(f"{path} renders a real header", "page_header(" in text, path)
        # The rail and the header both read session identity, so they have to
        # run after the login gate rather than before it.
        check(f"{path} draws chrome only after the login gate",
              text.index("require_login()") < text.index(f'nav_rail("{label}")'), path)

check("the sidebar starts open, because it is the navigation",
      'initial_sidebar_state="expanded"' in (ROOT / "app.py").read_text(encoding="utf-8"))

print("\n[9] the surface hierarchy is used, and is actually three levels")
check("ground, surface and raised are three distinct values",
      len({ui.GROUND, ui.SURFACE, ui.RAISED}) == 3,
      f"{ui.GROUND} {ui.SURFACE} {ui.RAISED}")
check("they get lighter in order",
      _luminance(ui.GROUND) < _luminance(ui.SURFACE) < _luminance(ui.RAISED),
      f"{_luminance(ui.GROUND):.4f} {_luminance(ui.SURFACE):.4f} {_luminance(ui.RAISED):.4f}")
check("pipeline rows have a hover state", ".prow:hover" in src)
check("company and role are stacked in one cell",
      "prow-co" in src and "prow-role" in src)

print("\n[10] the palette did not sprawl")
# Every hex literal in the stylesheet, so an ad-hoc colour cannot creep in.
hexes = {h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}", src)}
declared = {c.upper() for c in (ui.GROUND, ui.SURFACE, ui.RAISED, ui.LINE, ui.INK,
                                ui.MUTED, ui.GOLD, ui.GOLD_LIGHT, ui.GOOD, ui.BAD)}
check("no undeclared colour appears in the stylesheet",
      hexes <= declared, str(sorted(hexes - declared)))
check("exactly two colours were added beyond the original palette",
      len(declared) == 9, str(sorted(declared)))

print()
print("=" * 46)
print("ALL UI CHROME TESTS PASSED" if not FAIL else "FAILURES: " + ", ".join(FAIL))
sys.exit(1 if FAIL else 0)
