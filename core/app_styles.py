"""The app's chrome: theme, left rail, page header, and the small display atoms.

The app read as a form rather than a product, and the cause was chrome rather
than colour. A person landing on Match saw a heading and a stack of inputs with
nothing around them, so there was no sense of being *somewhere* inside a tool.
Three things fix most of that, and they are all here:

  1. A persistent left rail with the five destinations, so the product has a
     shape you can hold in your head, and Profile stops being invisible.
  2. A real header on every page that says where you are.
  3. One surface hierarchy used consistently: ground, surface, raised. Depth is
     what separates a panel from the page behind it.

The palette is unchanged: the same near-black ground, the same gold accent. Two
semantic colours are added for status, and only two, because an offer and a
rejection cannot be told apart by weight alone. Both were contrast-checked
against every surface they are drawn on; the ratios are in PALETTE below.
"""
import streamlit as st

# --- Palette -----------------------------------------------------------------
# Contrast ratios below are against the surface the colour is actually drawn on,
# computed from the WCAG 2.1 relative-luminance formula. AA body text needs 4.5.
GROUND = "#0F1117"       # the page behind everything
SURFACE = "#1A1D27"      # cards, sidebar, inputs
RAISED = "#2D3148"       # a panel on top of a card; also the border colour
LINE = "#2D3148"
INK = "#FFFFFF"          # 18.6 on ground
MUTED = "#A0A7B8"        # 7.8 on ground, 7.0 on surface, 5.3 on raised
GOLD = "#C9A84C"         # 8.3 on ground, 5.6 on raised
GOLD_LIGHT = "#E0BC5E"
GOOD = "#5FBE90"         # new: 7.4 on surface, 5.6 on raised
BAD = "#F09189"          # new: 7.3 on surface, 5.5 on raised

# Numbers are data and should read as data. A proportional face gives 1 a
# narrower advance than 8, so a column of scores does not line up and 58 and 88
# look more alike than they are. Tabular figures fix both.
MONO = ('ui-monospace, "SF Mono", SFMono-Regular, "JetBrains Mono", '
        '"Cascadia Mono", Menlo, Consolas, "Liberation Mono", monospace')

# The five destinations, in the order someone actually needs them. Profile is
# first because a new user cannot do anything until they have uploaded a resume,
# and it was previously reachable but invisible.
NAV = [
    ("app.py", "Home", "◎"),
    ("pages/0_Profile.py", "Profile", "👤"),
    ("pages/1_Track.py", "Track", "☑️"),
    ("pages/2_Match.py", "Match", "🎯"),
    ("pages/3_Guide.py", "Guide", "🗺️"),
]

# Pipeline stages. Tone is one of: neutral, live, good, bad. Stages in flight
# carry the accent; the two terminal outcomes carry the two semantic colours.
STATUS_TONE = {
    "recruiter_outreach": ("neutral", "Recruiter outreach"),
    "applied": ("neutral", "Applied"),
    "screening": ("live", "Screening"),
    "interview": ("live", "Interview"),
    "offer": ("good", "Offer"),
    "rejected": ("bad", "Rejected"),
    "withdrawn": ("neutral", "Withdrawn"),
}


def apply_theme(active: str = ""):
    """Paint the theme and, when signed in, the left rail.

    `active` is the nav label for the current page. Callers that pass nothing
    still get the theme, which keeps every existing call site working.
    """
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
    .stApp {{ background-color: {GROUND}; color: {INK}; }}

    /* ---------- left rail ---------- */
    [data-testid="stSidebar"] {{ background-color: {SURFACE}; border-right: 1px solid {LINE}; }}
    [data-testid="stSidebar"] * {{ color: {MUTED} !important; }}
    [data-testid="stSidebar"] a:hover {{ color: {GOLD} !important; }}
    /* Streamlit's own generated page list is replaced by the rail below, which
       controls its own labels, order and active state. */
    [data-testid="stSidebarNav"] {{ display: none; }}
    .rail-brand {{ display:flex; align-items:center; gap:10px; padding:4px 0 14px 0; }}
    .rail-mark {{ width:22px; height:22px; border-radius:50%; border:3px solid {GOLD};
      position:relative; flex:none; }}
    .rail-mark::after {{ content:""; position:absolute; inset:5px; border-radius:50%; background:{GOLD}; }}
    .rail-word {{ color:{GOLD} !important; font-weight:700; letter-spacing:-0.02em; font-size:17px; }}
    .rail-label {{ font-size:11px; text-transform:uppercase; letter-spacing:.09em;
      color:{MUTED} !important; margin:6px 0 4px 2px; }}
    [data-testid="stSidebar"] [data-testid="stPageLink"] a {{
      border-radius:7px; padding:7px 10px; border:1px solid transparent; }}
    [data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {{
      background:{RAISED}; border-color:{RAISED}; }}
    .rail-here {{ background:rgba(201,168,76,.12); border:1px solid rgba(201,168,76,.32);
      border-radius:7px; padding:6px 10px; margin:1px 0; font-weight:600;
      color:{GOLD} !important; font-size:14px; }}
    .rail-foot {{ font-size:12px; color:{MUTED} !important; line-height:1.6; }}

    /* ---------- page header ---------- */
    .page-head {{ border-bottom:1px solid {LINE}; padding-bottom:14px; margin-bottom:20px; }}
    .page-eyebrow {{ font-size:11px; letter-spacing:.11em; text-transform:uppercase;
      color:{MUTED}; margin-bottom:5px; }}
    .page-title {{ font-size:30px; font-weight:700; color:{INK}; letter-spacing:-0.02em;
      margin:0 0 4px 0; display:flex; align-items:center; gap:10px; }}
    .page-sub {{ font-size:15px; color:{MUTED}; margin:0; }}

    /* ---------- surface hierarchy ---------- */
    h1 {{ color:{INK}; font-weight:700; }}
    h2 {{ color:{INK}; font-weight:600; }}
    h3 {{ color:{GOLD}; font-weight:600; }}
    [data-testid="stExpander"] {{ background-color:{SURFACE}; border:1px solid {LINE};
      border-radius:10px; color:{INK}; }}
    [data-testid="stExpander"] p, [data-testid="stExpander"] li {{ color:{INK}; }}
    [data-testid="stExpander"] label {{ color:{INK} !important; }}
    [data-testid="stExpanderDetails"] {{ color:{INK}; }}
    .streamlit-expanderContent, .streamlit-expanderContent p,
    .streamlit-expanderContent li {{ color:{INK}; }}
    /* A panel inside a card sits one step up, so it reads as on top rather
       than as another slab of the same thing. */
    [data-testid="stExpander"] [data-testid="stExpander"] {{ background-color:{RAISED};
      border-color:rgba(255,255,255,.09); }}
    hr {{ border-color:{LINE}; }}
    .stAlert {{ border-radius:10px; border:none; }}
    [data-testid="stChatMessage"] {{ background-color:{SURFACE}; border-radius:10px;
      border:1px solid {LINE}; }}
    .stDataFrame {{ border:1px solid {LINE}; border-radius:10px; }}
    [data-testid="stFileUploader"] {{ background-color:{SURFACE}; border:1px dashed {LINE};
      border-radius:10px; }}
    .stSpinner > div {{ border-top-color:{GOLD} !important; }}

    /* ---------- numbers are data ---------- */
    [data-testid="metric-container"], [data-testid="stMetric"] {{
      background-color:{SURFACE}; border:1px solid {LINE}; border-radius:10px; padding:16px; }}
    [data-testid="metric-container"] label, [data-testid="stMetricLabel"] {{
      color:{MUTED} !important; font-size:12px; text-transform:uppercase; letter-spacing:.5px; }}
    [data-testid="metric-container"] [data-testid="stMetricValue"],
    [data-testid="stMetricValue"] {{
      color:{INK}; font-weight:700; font-family:{MONO};
      font-variant-numeric:tabular-nums; font-feature-settings:"tnum" 1; letter-spacing:-0.01em; }}
    .num {{ font-family:{MONO}; font-variant-numeric:tabular-nums;
      font-feature-settings:"tnum" 1; letter-spacing:-0.01em; }}

    /* ---------- status as shape and colour ---------- */
    /* The fill is a wash of the ground colour rather than a tint of the chip's
       own colour. A tint lightens with whatever is behind it, so the same chip
       met AA on a resting row and missed it on a hovered one at 4.2. Washing
       towards ground darkens instead, which means the chip reads the same on
       every surface and gets brighter rather than dimmer under hover. */
    .chip {{ display:inline-block; padding:3px 10px; border-radius:100px; font-size:11.5px;
      font-weight:600; letter-spacing:.02em; white-space:nowrap; border:1px solid;
      background:rgba(15,17,23,.55); }}
    .chip-neutral {{ color:{MUTED}; border-color:rgba(160,167,184,.34); }}
    .chip-live {{ color:{GOLD}; border-color:rgba(201,168,76,.38); }}
    .chip-good {{ color:{GOOD}; border-color:rgba(95,190,144,.40); }}
    .chip-bad {{ color:{BAD}; border-color:rgba(240,145,137,.40); }}

    /* ---------- pipeline rows ---------- */
    .prow {{ display:grid; grid-template-columns: minmax(0,2.4fr) 1fr 1.25fr 0.9fr;
      gap:14px; align-items:center; padding:11px 14px; border:1px solid {LINE};
      border-radius:10px; background:{SURFACE}; margin-bottom:7px; transition:background .15s ease,
      border-color .15s ease; }}
    .prow:hover {{ background:{RAISED}; border-color:rgba(201,168,76,.3); }}
    .prow-head {{ display:grid; grid-template-columns: minmax(0,2.4fr) 1fr 1.25fr 0.9fr;
      gap:14px; padding:0 14px 7px 14px; font-size:11px; text-transform:uppercase;
      letter-spacing:.09em; color:{MUTED}; }}
    .prow-co {{ color:{INK}; font-weight:600; font-size:14.5px; line-height:1.25;
      overflow:hidden; text-overflow:ellipsis; }}
    .prow-role {{ color:{MUTED}; font-size:12.5px; line-height:1.3;
      overflow:hidden; text-overflow:ellipsis; }}
    .prow-fit {{ display:flex; align-items:center; gap:9px; }}
    .fitbar {{ flex:1; height:6px; border-radius:100px; background:rgba(160,167,184,.16);
      overflow:hidden; min-width:44px; }}
    .fitbar > span {{ display:block; height:100%; border-radius:100px; }}
    .prow-date {{ color:{MUTED}; font-size:12.5px; }}

    /* ---------- controls ---------- */
    .stButton > button {{ background-color:{GOLD}; color:{GROUND}; border:none; border-radius:7px;
      font-weight:600; padding:8px 20px; transition:all .2s ease; }}
    .stButton > button:hover {{ background-color:{GOLD_LIGHT}; color:{GROUND}; transform:translateY(-1px); }}
    .stButton > button[kind="primary"] {{ background-color:{GOLD}; color:{GROUND}; }}
    .stTextInput > div > div > input, .stTextArea > div > div > textarea,
    .stSelectbox > div > div {{ background-color:{SURFACE}; border:1px solid {LINE};
      color:{INK}; border-radius:7px; }}
    .stTextInput > div > div > input:focus, .stTextArea > div > div > textarea:focus {{
      border-color:{GOLD}; box-shadow:0 0 0 2px rgba(201,168,76,.2); }}
    </style>
    """, unsafe_allow_html=True)
    hide_admin_nav()
    if active:
        nav_rail(active)


def nav_rail(active: str = ""):
    """The persistent left rail. Renders only for a signed-in account."""
    tester = st.session_state.get("tester_name", "")
    if not tester:
        return

    with st.sidebar:
        st.markdown(
            '<div class="rail-brand"><span class="rail-mark"></span>'
            '<span class="rail-word">Telos</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="rail-label">Your campaign</div>', unsafe_allow_html=True)
        for path, label, icon in NAV:
            if label == active:
                # The page you are on is a location, not a link to itself.
                st.markdown(f'<div class="rail-here">{icon}&nbsp; {label}</div>',
                            unsafe_allow_html=True)
            else:
                st.page_link(path, label=label, icon=None if icon == "◎" else icon)

        try:
            from core.plans import is_owner
            if is_owner(tester):
                st.markdown('<div class="rail-label">Owner</div>', unsafe_allow_html=True)
                st.page_link("pages/4_Admin.py", label="Admin", icon="🔧")
        except Exception:
            pass


def page_header(title: str, subtitle: str = "", eyebrow: str = "Telos"):
    """A real header, so every page says where you are before it asks anything."""
    parts = [f'<div class="page-head"><div class="page-eyebrow">{eyebrow}</div>',
             f'<div class="page-title">{title}</div>']
    if subtitle:
        parts.append(f'<div class="page-sub">{subtitle}</div>')
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


# --- display atoms -----------------------------------------------------------

def status_chip(status: str) -> str:
    """A pipeline status as a shape and a colour rather than a bare word."""
    tone, label = STATUS_TONE.get(status, ("neutral", str(status).replace("_", " ").capitalize()))
    return f'<span class="chip chip-{tone}">{label}</span>'


def fit_bar(score, width_hint: str = "") -> str:
    """A match score as a number you can compare and a bar you can scan."""
    if score is None:
        return f'<span class="prow-fit"><span class="num" style="color:{MUTED}">--</span></span>'
    try:
        pct = max(0, min(100, int(score)))
    except (TypeError, ValueError):
        return f'<span class="prow-fit"><span class="num" style="color:{MUTED}">--</span></span>'
    colour = GOOD if pct >= 75 else (GOLD if pct >= 60 else BAD)
    return (f'<span class="prow-fit"><span class="num" style="color:{colour};min-width:34px">'
            f'{pct}%</span><span class="fitbar"><span style="width:{pct}%;background:{colour}">'
            f'</span></span></span>')


def num(value) -> str:
    """Inline number in the tabular face, so columns of them line up."""
    return f'<span class="num">{value}</span>'


def hide_admin_nav():
    """Remove the Admin entry from the sidebar for anyone who is not the owner.

    This is presentation only. The Admin page enforces its own access control;
    hiding the link just stops the demo and ordinary users being shown a door
    they cannot open and should not know about.
    """
    try:
        from core.plans import is_owner
        if is_owner(st.session_state.get("tester_name", "")):
            return
    except Exception:
        pass  # if anything fails, err towards hiding

    st.markdown("""
    <style>
    [data-testid="stSidebarNav"] a[href$="/Admin"],
    [data-testid="stSidebarNav"] a[href*="4_Admin"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)


def show_help(page_name: str):
    from core.help_content import HELP_CONTENT
    content = HELP_CONTENT.get(page_name, HELP_CONTENT["app"])
    with st.sidebar:
        st.markdown("---")
        with st.expander("❓ Help: " + content["title"]):
            for i, step in enumerate(content["steps"], 1):
                st.markdown(f"**{i}.** {step}")
            st.markdown("---")
            st.info(f"💡 {content['tip']}")
        tester = st.session_state.get("tester_name", "")
        if tester:
            st.markdown(f'<div class="rail-foot">Signed in as<br>{tester}</div>',
                        unsafe_allow_html=True)
