"""Promo Finder — Streamlit UI.   Run:  streamlit run app.py"""
from __future__ import annotations

import base64
import io
import os
import re
import zipfile
from html import escape as html_escape
from pathlib import Path

import pandas as pd
import streamlit as st

from promo_finder import ui
from promo_finder.checks import run_checks
from promo_finder.compare import compare, cut_key, to_csv as compare_csv, to_markdown as compare_md
from promo_finder.llm import Judge
from promo_finder.parser import finalize, fmt, load_zip_bytes, parse_text
from promo_finder.pipeline import run
from promo_finder.progress import ReviewProgress
from promo_finder.report import to_csv, to_html, to_json, to_markdown
from promo_finder.usage import SarvamConfig

ROOT = Path(__file__).parent
st.set_page_config(
    page_title="Promo Finder — Microdrama Cut Detector",
    page_icon=str(ROOT / "static" / "favicon.png"),
    layout="wide",
    initial_sidebar_state="expanded"
)

# Modernized UI Styling System (Top Space Fix & Clean Compact Layout)
st.markdown("""
<style>
/* Completely hide Streamlit default top header bar & eliminate top whitespace */
header[data-testid="stHeader"], 
[data-testid="stHeader"],
.stAppHeader {
    display: none !important;
    height: 0px !important;
    min-height: 0px !important;
    padding: 0px !important;
    margin: 0px !important;
}

[data-testid="stAppViewContainer"] > .main .block-container,
.main .block-container,
.block-container {
    padding-top: 0rem !important;
    margin-top: 0rem !important;
    max-width: 100% !important;
}

@media(min-width:861px){
    .main .block-container {
        padding-top: 0rem !important;
        padding-left: 40px !important;
        padding-right: 40px !important;
        padding-bottom: 32px !important;
    }
}

/* Global Modern Reset & Typography */
.pf {
    --bg: #FBF9F9;
    --surface: #ffffff;
    --surface2: #F6F5F8;
    --surface3: #EBE9EF;
    --line: #E6E5EA;
    --line2: #D7D5DE;
    --ink: #171719;
    --ink2: #414148;
    --mute: #5B5B63;
    --faint: #8A8A92;
    --hook: #E11D26;
    --hook-bg: #FDEBEC;
    --cliff: #A85400;
    --cliff-bg: #FFF6E8;
    --stitch: #5B3FD6;
    --stitch-bg: #F2EEFF;
    --ok: #137A3D;
    --ok-bg: #EAF7EF;
    --warn: #8A5A00;
    --warn-bg: #FFF8E1;
    --bad: #B42318;
    --bad-bg: #FDECEB;
    --accent: #E11D26;
    --grad: linear-gradient(135deg, #D71920 0%, #9E0F15 100%);
    --shadow: 0 4px 14px rgba(25, 18, 40, 0.04);
    --sans: 'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif;
    --mono: 'JetBrains Mono', monospace;
    color: var(--ink);
    font-family: var(--sans);
    font-size: 16px;
    line-height: 1.6;
}

.stApp, [data-testid="stAppViewContainer"] {
    background: #FBF9F9 !important;
    background-image: radial-gradient(ellipse at 96% 0%, rgba(245, 190, 196, 0.12), transparent 35%) !important;
}

/* Sidebar Custom Styling */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D0D0E 0%, #151516 100%) !important;
    border-right: 1px solid #252528 !important;
}

section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
    color: #B5B5BC !important;
}

section[data-testid="stSidebar"] .st-key-nav_home button,
section[data-testid="stSidebar"] .st-key-nav_how button {
    width: 100% !important;
    height: 52px !important;
    min-height: 52px !important;
    border-radius: 12px !important;
    justify-content: flex-start !important;
    text-align: left !important;
    padding: 0 16px !important;
    font-size: 15px !important;
    font-weight: 600 !important;
    box-shadow: none !important;
}

section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
    color: #fff !important;
    background: linear-gradient(100deg, #D71920 0%, #9E0F15 100%) !important;
    border: 1px solid #D71920 !important;
}

section[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
    color: #fff !important;
    background: #171719 !important;
    border: 1px solid #303034 !important;
}

section[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {
    background: #242427 !important;
    border-color: #48484D !important;
}

/* Card & Interactive Panel Enhancements */
.pf-how-card, .pf-step, .pf-start-step {
    background: #FFFFFF;
    border: 1px solid #F0E6E7;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 4px 16px rgba(20, 0, 0, 0.03);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.pf-how-card:hover, .pf-start-step:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(20, 0, 0, 0.06);
}

/* Upload Panel Refinements */
.st-key-home_upload_panel {
    background: #FFFFFF !important;
    border: 1px solid #F0E6E7 !important;
    border-radius: 20px !important;
    box-shadow: 0 8px 24px rgba(20, 0, 0, 0.05) !important;
    padding: 24px !important;
}

.st-key-upload_zone [data-testid="stFileUploaderDropzone"] {
    background: #FFF5F5 !important;
    border: 1.5px dashed #F1B7BB !important;
    border-radius: 16px !important;
    transition: border-color 0.15s ease, background-color 0.15s ease;
}

.st-key-upload_zone [data-testid="stFileUploaderDropzone"]:hover {
    border-color: #E11D26 !important;
    background: #FFF0F0 !important;
}

[data-testid="stBaseButton-primary"] {
    border-radius: 12px !important;
    box-shadow: 0 4px 12px rgba(214, 25, 74, 0.18) !important;
    font-weight: 700 !important;
}

/* Tab Styling Overrides */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    border-bottom: 1px solid #E6E3EB;
}

.stTabs [data-baseweb="tab"] {
    font-size: 15px;
    font-weight: 600;
    padding: 10px 16px;
    border-radius: 8px 8px 0 0;
}
</style>
""", unsafe_allow_html=True)


def sb_head(n: str, text: str) -> None:
    st.html(f'<div class="pf-sbh"><b>{n}</b>{text}</div>')


def secret(name: str) -> str:
    try:
        return st.secrets.get(name, "") or os.getenv(name, "")
    except Exception:
        return os.getenv(name, "")


config = SarvamConfig.load(secret)
n_single, n_stitched, llm_top, compare_too = 20, 6, 40, True


def mascot(class_name: str) -> str:
    image = base64.b64encode((ROOT / "static" / "mascot.webp").read_bytes()).decode("ascii")
    dimensions = {
        "pf-mascot-brand": (44, 44),
        "pf-mascot-welcome": (140, 140),
        "pf-mascot-mobile": (52, 62),
    }.get(class_name, (44, 44))
    width, height = dimensions
    return (f'<img class="pf-mascot {class_name}" width="{width}" height="{height}" '
            f'style="width:{width}px;height:{height}px;max-width:{width}px;max-height:{height}px;object-fit:contain;'
            f'display:block;flex:0 0 auto" src="data:image/webp;base64,{image}" '
            f'alt="Promo Finder clapperboard mascot" />')


def feature_svg_icon(name: str) -> str:
    artwork = {
        "bolt": '<path d="M13.5 2.5 5 13h6l-.7 8.5L19 10.5h-6.2l.7-8z" fill="#E11D26" stroke="#E11D26" stroke-width="1.2" stroke-linejoin="round"/>',
        "target": '<circle cx="11" cy="13" r="8" fill="none" stroke="#E11D26" stroke-width="2"/><circle cx="11" cy="13" r="4.5" fill="none" stroke="#E11D26" stroke-width="2"/><circle cx="11" cy="13" r="1.5" fill="#E11D26"/><path d="m16.8 7.2 4-4m-4 0h4v4" fill="none" stroke="#E11D26" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
        "layers": '<path d="m12 3 9 5-9 5-9-5 9-5z" fill="none" stroke="#E11D26" stroke-width="2" stroke-linejoin="round"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5" fill="none" stroke="#E11D26" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    }
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
            f'aria-hidden="true" style="display:block;width:24px;height:24px;flex:0 0 24px">{artwork.get(name, "")}</svg>')


def feature_item(icon: str, title: str, detail: str, bordered: bool = True) -> str:
    border = "border-right:1px solid #E5E5E8;" if bordered else ""
    return (
        f'<div class="pf-feature" style="display:flex;align-items:center;gap:13px;min-width:0;'
        f'box-sizing:border-box;padding:7px 18px;{border}">'
        f'<span class="pf-feature-icon" style="width:46px;height:46px;min-width:46px;flex:0 0 46px;'
        f'display:flex;align-items:center;justify-content:center;border-radius:12px;'
        f'background:#FDEBEC;color:#E11D26">{feature_svg_icon(icon)}</span>'
        f'<span style="display:flex;flex-direction:column;align-items:flex-start;justify-content:center;'
        f'gap:3px;min-width:0;text-align:left">'
        f'<b style="display:block;font-size:16px;line-height:1.25;font-weight:700;color:#1A1A1C;'
        f'white-space:normal;overflow-wrap:anywhere">{title}</b>'
        f'<small style="display:block;font-size:14px;line-height:1.35;font-weight:400;color:#5B5B63;'
        f'white-space:normal;overflow-wrap:anywhere">{detail}</small>'
        f'</span></div>'
    )


def process_step(number: int, icon: str, title: str, detail: str) -> str:
    symbols = {"upload": "↑", "list": "☷", "clapper": "▤"}
    glyph = symbols.get(icon, "•")
    return (
        f'<div style="position:relative;display:flex;align-items:center;gap:14px;min-height:112px;'
        f'box-sizing:border-box;padding:18px 16px 16px 25px;background:#FFFFFF;border:1px solid #F0E6E7;'
        f'border-radius:16px;box-shadow:0 5px 16px rgba(20,0,0,.035)">'
        f'<span style="position:absolute;top:12px;left:12px;width:25px;height:25px;display:flex;'
        f'align-items:center;justify-content:center;border-radius:50%;background:#FDEBEC;color:#E11D26;'
        f'font-size:13px;font-weight:700">{number}</span>'
        f'<span style="width:48px;height:48px;min-width:48px;margin-left:15px;display:flex;'
        f'align-items:center;justify-content:center;border-radius:12px;background:#FDEBEC;color:#E11D26;'
        f'font-size:27px;font-weight:700">{glyph}</span>'
        f'<span style="display:flex;flex-direction:column;gap:5px;min-width:0">'
        f'<b style="display:block;font-size:16px;line-height:1.3;color:#1A1A1C;font-weight:700">{title}</b>'
        f'<small style="display:block;font-size:14px;line-height:1.45;color:#5B5B63">{detail}</small>'
        f'</span></div>'
    )


def film_ribbon() -> str:
    return """<svg class="pf-film-ribbon" viewBox="0 0 420 190" preserveAspectRatio="none" aria-hidden="true">
<path d="M-20 145 C70 25 128 35 190 110 S310 200 445 55" fill="none" stroke="#F5C5C8" stroke-width="64"/>
<path d="M-20 145 C70 25 128 35 190 110 S310 200 445 55" fill="none" stroke="#FFF" stroke-width="49"/>
<path d="M-20 145 C70 25 128 35 190 110 S310 200 445 55" fill="none" stroke="#F4BFC3" stroke-width="1.5" stroke-dasharray="4 8"/>
<path d="M-20 116 C70 -4 128 6 190 81 S310 171 445 26" fill="none" stroke="#F4BFC3" stroke-width="1.5" stroke-dasharray="4 8"/>
</svg>"""


def feature_hero_art() -> str:
    return film_ribbon() + mascot("pf-mascot-welcome") + (
        '<svg class="pf-home-spark" viewBox="0 0 48 48" fill="none" stroke="#E11D26" '
        'stroke-width="3.2" stroke-linecap="round" aria-hidden="true">'
        '<path d="M23 2 20 13M38 8l-7 9M45 25l-10 1"/>'
        '</svg>')


def guess_title(files) -> str:
    z = next((f for f in files if f.name.lower().endswith(".zip")), None)
    if not z:
        return ""
    try:
        with zipfile.ZipFile(io.BytesIO(z.getvalue())) as zf:
            tops = {n.split("/")[0] for n in zf.namelist() if "/" in n and not n.startswith("__MACOSX")}
    except zipfile.BadZipFile:
        tops = set()
    base = tops.pop() if len(tops) == 1 else re.sub(r"\.zip$", "", z.name, flags=re.I)
    return re.sub(r"[-_ ]?scripts.*$", "", base, flags=re.I).strip()


def clear_report() -> None:
    for name in ("result", "checks", "compare", "kind", "tiers", "kind2", "backup_ranking"):
        st.session_state.pop(name, None)


MAX_FILE_BYTES = 50 * 1024 * 1024


def select_uploads(widget_key: str) -> None:
    clear_report()
    incoming = list(st.session_state.get(widget_key) or [])
    valid, errors = [], []
    for uploaded in incoming:
        suffix = Path(uploaded.name).suffix.lower()
        if suffix not in {".zip", ".txt"}:
            errors.append(f"{uploaded.name}: only ZIP and TXT files are accepted.")
        elif uploaded.size > MAX_FILE_BYTES:
            errors.append(f"{uploaded.name}: exceeds the 50MB per-file limit.")
        else:
            valid.append(uploaded)
    st.session_state.source_files = valid
    st.session_state.upload_error = " ".join(errors)
    suggested = guess_title(valid)
    st.session_state.show_title = suggested
    st.session_state.home_title = suggested
    if errors:
        st.session_state.home_upload_version = st.session_state.get("home_upload_version", 0) + 1


def sync_title(source: str, target: str) -> None:
    st.session_state[target] = st.session_state[source]


def new_analysis() -> None:
    clear_report()
    st.session_state.source_files = []
    st.session_state.show_title = ""
    st.session_state.home_title = ""
    st.session_state.upload_error = ""
    st.session_state.active_page = "Home"
    st.session_state.home_upload_version = st.session_state.get("home_upload_version", 0) + 1


def render_how_it_works_page() -> None:
    st.html("""<div class="pf pf-page-head">
<div class="pf-label accent">PRODUCT GUIDE</div><h1>How Promo Finder works</h1>
<p>From timestamped screenplay files to a ranked, editor-ready promo shortlist.</p>
</div>
<div class="pf pf-how-grid">
  <article class="pf-how-card"><span class="num">01</span><h3>Upload your scripts</h3>
  <p>Upload a ZIP of episode .txt files or individual .txt screenplays. Promo Finder reads dialogue, action and source timestamps, and reports files or blocks it cannot parse.</p></article>
  <article class="pf-how-card"><span class="num">02</span><h3>Find hooks and cliffhangers</h3>
  <p>The rules engine scores screenplay beats for hook strength, cliffhanger strength, intensity and dependence on backstory. The show premise is inferred from its title and early episode loglines.</p></article>
  <article class="pf-how-card"><span class="num">03</span><h3>Generate valid promo cuts</h3>
  <p>It builds single-episode and stitched candidates. Each cut must run 20–60 seconds, hook the viewer within the first 3 seconds, use real source timestamps and avoid cutting through a spoken line.</p></article>
  <article class="pf-how-card"><span class="num">04</span><h3>Rank the strongest moments</h3>
  <p>The rules score weighs hook (28%), cliffhanger (24%), momentum (20%), new-viewer clarity (16%), length fit (6%) and premise fit (6%). Selection avoids overlapping cuts and repeated hook or cliffhanger lines.</p></article>
  <article class="pf-how-card"><span class="num">05</span><h3>AI editorial review</h3>
  <p>The configured AI reviewer evaluates a shortlist, returns scores, reasons and risks, and may suggest trims by referring to numbered screenplay beats. Its score is blended with the rules score.</p></article>
  <article class="pf-how-card"><span class="num">06</span><h3>Validate every cut</h3>
  <p>Code checks AI trim suggestions against the original screenplay. It rejects suggestions that break duration, timestamp, hook or spoken-line constraints. Unusable AI replies retain the rules score.</p></article>
  <article class="pf-how-card"><span class="num">07</span><h3>Review and export</h3>
  <p>Editors inspect the ranked list, top pick, episode library, season map and quality checks. Download HTML, CSV, JSON and Markdown reports to take the cut points into editing.</p></article>
</div>
<div class="pf pf-how-note"><b>Human approval stays in the loop.</b> Promo Finder analyses screenplay text, not finished footage. Editors should check visual impact, pacing, context and spoiler risk before publishing. AI can only rerank candidates found by the rules pipeline; it cannot recover moments that candidate generation missed.</div>""")


# ---------------------------------------------------------------- Sidebar Nav
if "active_page" not in st.session_state:
    st.session_state.active_page = "Home"


def set_active_page(name: str) -> None:
    st.session_state.active_page = name


with st.sidebar:
    st.html(
        f'<div style="display:flex;align-items:center;gap:12px;margin:0 0 7px">'
        f'{mascot("pf-mascot-brand")}'
        '<b style="font-size:24px;line-height:1.1;font-weight:700;letter-spacing:-.6px;color:#FFFFFF">Promo Finder</b>'
        '</div>'
        '<p style="font-size:15px;line-height:1.55;color:#B5B5BC;margin:7px 0 26px;max-width:250px">'
        'Finds promo cuts in microdrama scripts.</p>'
    )
    for label, key, nav_icon in (("Home", "home", ":material/home:"),
                                   ("How it Works", "how", ":material/info:")):
        active = st.session_state.active_page == label
        st.button(label, key=f"nav_{key}", icon=nav_icon,
                  type="primary" if active else "secondary",
                  width="stretch", on_click=set_active_page, args=(label,))

    st.html('<div style="height:1px;background:#2A2A2D;margin:24px 0"></div>')
    if config.configured:
        st.html('<div style="display:flex;align-items:center;gap:11px;padding:17px 16px;'
                'background:#161618;border:1px solid #232326;border-radius:14px;color:#FFFFFF;'
                'font-size:16px;font-weight:600;margin:0 0 28px">'
                '<span style="width:12px;height:12px;border-radius:50%;background:#22C55E;'
                'box-shadow:0 0 0 4px rgba(34,197,94,.12),0 0 12px rgba(34,197,94,.55)"></span>'
                'AI review enabled</div>')
    else:
        st.html('<div style="display:flex;align-items:center;gap:11px;padding:17px 16px;'
                'background:#161618;border:1px solid #232326;border-radius:14px;color:#FFFFFF;'
                'font-size:16px;font-weight:600;margin:0 0 28px">'
                '<span style="width:12px;height:12px;border-radius:50%;background:#F59E0B"></span>'
                'AI review unavailable</div>')

    st.html(
        '<div style="padding:20px;background:#161618;border:1px solid #232326;border-radius:18px;margin:0">'
        '<div style="font-size:18px;font-weight:700;color:#FFFFFF;margin:0 0 16px">Quick Stats</div>'
        '<div style="display:flex;align-items:center;gap:14px;margin:13px 0 0">'
        '<span style="width:48px;height:48px;min-width:48px;display:flex;align-items:center;justify-content:center;'
        'border-radius:12px;background:#2A1213;color:#E11D26;font-size:25px;font-weight:700">▶</span>'
        '<span style="display:flex;flex-direction:column;gap:3px">'
        '<b style="font-size:18px;line-height:1.2;color:#FFFFFF">20 – 60 sec</b>'
        '<small style="font-size:14px;line-height:1.3;color:#B5B5BC">Promo length</small></span></div>'
        '<div style="display:flex;align-items:center;gap:14px;margin:13px 0 0">'
        '<span style="width:48px;height:48px;min-width:48px;display:flex;align-items:center;justify-content:center;'
        'border-radius:12px;background:#2A1213;color:#E11D26;font-size:24px;font-weight:700">▱</span>'
        '<span style="display:flex;flex-direction:column;gap:3px">'
        '<b style="font-size:18px;line-height:1.2;color:#FFFFFF">4</b>'
        '<small style="font-size:14px;line-height:1.3;color:#B5B5BC">Export formats</small></span></div>'
        '</div>'
    )

    if "result" in st.session_state:
        st.button("New analysis", key="sidebar_new_analysis", width="stretch",
                  on_click=new_analysis)

    page = st.session_state.active_page
    go = False
    title = st.session_state.get("show_title", "")
    files = list(st.session_state.get("source_files", []))
    if page == "Home" and "result" in st.session_state:
        st.html('<div style="height:1px;background:#2A2A2D;margin:22px 0"></div>')
        title = st.text_input("Show title", key="show_title", placeholder="e.g. The Maid Was the Heiress",
                              on_change=sync_title, args=("show_title", "home_title"),
                              help="The title helps the system understand the show's premise.")
        go = st.button("Find Promos", type="primary", width="stretch",
                       disabled=not files)

if page == "How it Works":
    render_how_it_works_page()
    st.stop()

progress_panel = st.empty()

# ---------------------------------------------------------------- Landing Screen
if page == "Home" and "result" not in st.session_state and not go:
    features = "".join([
        feature_item("bolt", "AI + Rules Engine", "Scores & reranks promos", True),
        feature_item("target", "Script-accurate", "Exact timestamps", True),
        feature_item("layers", "Editor-ready", "Reports, CSV & more", False),
    ])
    steps = (
        process_step(1, "upload", "Upload your story",
                     "One episode or a full season of timestamped screenplays.")
        + '<div style="font-size:27px;color:#E11D26;text-align:center">→</div>'
        + process_step(2, "list", "Review the strongest moments",
                       "Ranked 20–60 second cuts, with hooks and cliffhangers.")
        + '<div style="font-size:27px;color:#E11D26;text-align:center">→</div>'
        + process_step(3, "clapper", "Take it to your editor",
                       "Exact cut points, editorial notes and reports to share.")
    )
    st.html(f"""
<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin:0 0 10px">
  <div style="flex:1 1 auto;min-width:0;max-width:900px">
    <div style="font-size:14px;line-height:1.2;font-weight:700;letter-spacing:.5px;color:#E11D26;text-transform:uppercase">PROMO FINDER</div>
    <h1 style="font-family:Inter,system-ui,sans-serif;font-size:46px;line-height:1.05;letter-spacing:-1.5px;font-weight:750;color:#1A1A1C;margin:6px 0 8px">
      Find the moments <span style="color:#E11D26">worth promoting</span>
    </h1>
    <p style="font-size:17px;line-height:1.4;color:#5B5B63;margin:0;max-width:850px">
      Find ranked 20–60 second promo cuts, with hooks and cliffhangers ready for your editor.
    </p>
  </div>
  <div style="position:relative;display:flex;align-items:flex-start;justify-content:flex-end;width:160px;min-width:140px;height:120px;overflow:hidden">
    {mascot("pf-mascot-welcome")}
  </div>
</div>
<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));align-items:center;margin:8px 0 20px">
  {features}
</div>
""")

  with st.container(key="home_upload_panel"):
        st.html(
            '<div style="text-align:center;padding:0 0 10px">'
            '<div style="font-size:24px;line-height:1.2;font-weight:700;letter-spacing:-.55px;color:#1A1A1C">'
            'Upload your microdrama scripts</div>'
            '<div style="font-size:14px;color:#5B5B63;margin-top:4px">'
            'Drag & drop a ZIP or TXT file here.</div></div>'
        )
        
        st.markdown("""
        <style>
        /* 1. Center uploader & style upload button */
        [data-testid="stFileUploaderDropzone"] {
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: center !important;
            text-align: center !important;
            padding: 16px 20px !important;
            min-height: 120px !important;
            background: #FFF5F5 !important;
            border: 1.5px dashed #F1B7BB !important;
            border-radius: 14px !important;
        }
        [data-testid="stFileUploaderDropzoneInstructions"] {
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: center !important;
            width: 100% !important;
        }
        [data-testid="stFileUploaderDropzone"] button {
            background: linear-gradient(135deg, #E11D26 0%, #9E0F15 100%) !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 10px !important;
            padding: 10px 24px !important;
            font-weight: 700 !important;
            font-size: 15px !important;
            margin: 0 auto !important;
            box-shadow: 0 4px 12px rgba(225, 29, 38, 0.2) !important;
        }
        [data-testid="stFileUploaderDropzone"] button:hover {
            background: linear-gradient(135deg, #C8141D 0%, #7A0A0F 100%) !important;
        }

        /* 2. Style single file display card & action icons */
        [data-testid="stFileUploaderFile"] {
            margin: 8px auto 0 !important;
            max-width: 480px !important;
            border-radius: 10px !important;
            background: #FFFFFF !important;
            border: 1px solid #E5E5E8 !important;
        }

        /* 3. Action Row Layout & Centering */
        .st-key-find_home button {
            height: 48px !important;
            font-size: 16px !important;
            border-radius: 10px !important;
            transition: all 0.25s ease !important;
            margin: 0 !important;
        }
        
        .st-key-find_home button:disabled {
            background: #E5E5E8 !important;
            color: #8A8A92 !important;
            border: none !important;
            box-shadow: none !important;
        }
        
        .st-key-find_home button:not(:disabled) {
            background: linear-gradient(135deg, #8E0E12 0%, #5C080B 100%) !important;
            color: #FFFFFF !important;
            box-shadow: 0 4px 14px rgba(142, 14, 18, 0.3) !important;
            border: 1px solid #730A0E !important;
        }
        .st-key-find_home button:not(:disabled):hover {
            background: linear-gradient(135deg, #A61217 0%, #700B0F 100%) !important;
        }
        </style>
        """, unsafe_allow_html=True)

        upload_key = f'home_files_{st.session_state.get("home_upload_version", 0)}'

        # Native Streamlit file uploader (handles uploaded file view automatically)
        st.file_uploader(
            "Upload your microdrama scripts", type=["zip", "txt"], accept_multiple_files=True,
            key=upload_key, on_change=select_uploads, args=(upload_key,),
            label_visibility="collapsed", max_upload_size=50,
        )

        upload_error = st.session_state.get("upload_error", "")
        if upload_error:
            st.html(f'<div style="padding:8px 12px;margin:8px auto;max-width:500px;border:1px solid #F3B7BA;'
                    f'background:#FFF1F1;border-radius:8px;color:#B4232A;font-size:13px;line-height:1.4;text-align:center;">'
                    f'{html_escape(upload_error)}</div>')

        # Compact Side-by-Side Action Row
        st.html('<div style="height:12px"></div>')
        input_col, button_col = st.columns([2.5, 1.2], gap="small", vertical_alignment="bottom")
        
        with input_col:
            home_title = st.text_input(
                "Show title (optional)",
                key="home_title",
                placeholder="e.g. The Maid Was the Heiress",
                on_change=sync_title,
                args=("home_title", "show_title"),
            )
        with button_col:
            go = st.button("Find Promos", key="find_home", type="primary",
                           use_container_width=True, disabled=not files)
            
        if go:
            title = home_title
    if not go:
        st.html(f'<div style="display:grid;grid-template-columns:minmax(0,1fr) 28px minmax(0,1fr) 28px minmax(0,1fr);'
                f'gap:12px;align-items:center;margin:18px auto 0">{steps}</div>')
        st.stop()

# ---------------------------------------------------------------- Analysis Execution
if go:
    review = ReviewProgress()
    progress_panel.html(review.html())
    warnings: list[str] = []
    raw = []
    for f in files:
        data = f.getvalue()
        if f.name.lower().endswith(".zip"):
            try:
                raw += load_zip_bytes(data, [])
            except zipfile.BadZipFile:
                warnings.append(f"{f.name}: not a valid zip file")
        else:
            raw.append(parse_text(data.decode("utf-8", errors="replace"), f.name))
    eps = finalize(raw, warnings)
    for w in warnings:
        st.warning(w)
    if not eps:
        progress_panel.empty()
        st.error("No timestamped episodes found. Each script needs blocks like '**SPEAKER:**' followed by "
                 "'Start: (MM:SS.ss) | End: (MM:SS.ss)'.")
        st.stop()
    review.stage = 1
    progress_panel.html(review.html())
    show_title = title.strip() or (f"Episode {eps[0].num}" if len(eps) == 1 else "Series promo report")
    if not config.configured:
        progress_panel.empty()
        st.error("AI review is unavailable. Contact the app owner.")
        st.stop()
    try:
        judge = Judge(f"sarvam:{config.model}", api_key=config.api_key,
                      base_url=config.base_url, use_cache=False)
    except (ValueError, TypeError) as e:
        progress_panel.empty()
        st.error("AI review is currently unavailable. Please contact the app owner.")
        with st.expander("Run details"):
            st.code(str(e).replace(config.api_key, "[redacted]"), language=None)
        st.stop()

    def show_progress(message: str) -> None:
        before = review.html()
        review.update(message)
        after = review.html()
        if after != before:
            progress_panel.html(after)

    try:
        if compare_too:
            rules_res, res, cmp = compare(eps, show_title, judge, llm_top, progress=show_progress,
                                          n_single=n_single, n_stitched=n_stitched)
            st.session_state.compare = (rules_res, cmp)
        else:
            res = run(eps, show_title, judge, n_single, n_stitched, llm_top,
                      progress=show_progress, warnings=warnings)
            st.session_state.pop("compare", None)
    except Exception as e:
        st.error("We couldn’t finish this review. Please try again.")
        with st.expander("Run details"):
            st.code(str(e).replace(config.api_key, "[redacted]"), language=None)
        st.stop()
    finally:
        progress_panel.empty()
    st.session_state.result = res
    st.session_state.checks = run_checks(res)
    st.rerun()

res = st.session_state.result
checks = st.session_state.get("checks") or run_checks(res)
s = res.stats

ai = s.get("ai", {})
st.caption("Your promo report · Analyse another script whenever you’re ready.")
if not ai.get("judged", 0):
    reason = {
        401: "The AI connection needs attention. Contact the app owner.",
        403: "The AI connection needs attention. Contact the app owner.",
        402: "AI review is paused because the service is out of credits.",
        429: "The AI service is busy. Please try again shortly.",
    }.get(ai.get("last_error_code"), "The AI service did not return a usable review. Please try again.")
    if ai.get("error_kind") == "timeout":
        reason = "The AI service took too long to respond. Please try again."
    st.error(reason)
    st.caption("No AI-ranked report was produced. Your scripts are still uploaded; choose Find promos to retry.")
    with st.expander("Run details"):
        st.code("\n".join(res.log), language=None)
    if not st.checkbox("Show backup ranking", value=False, key="backup_ranking"):
        st.stop()
    badge = '<span class="pf-mode">Backup ranking · AI review unavailable</span>'
else:
    if ai.get("stopped") or ai.get("failed"):
        st.warning(f'AI reviewed {ai["judged"]} of {ai.get("shortlisted", 0)} shortlisted clips. '
                   'The report includes backup scores for the remaining clips.')
    badge = (f'<span class="pf-mode ai">AI reviewed {ai["judged"]} of '
             f'{ai.get("shortlisted", 0)} shortlisted clips</span>')

st.html(f"""<div class="pf"><div class="pf-report-head"><div><div class="pf-label accent">Promo report</div>
<h1 class="pf-h2">{ui.e(res.title)}</h1><div>{badge}</div></div>{mascot("pf-mascot-mobile")}</div>
{ui.run_summary({**s, "ai": {}}, checks)}</div>""")
slug = re.sub(r"\W+", "_", res.title.lower()).strip("_")[:40] or "show"
d1, d2, d3, d4 = st.columns(4)
d1.download_button("Report (HTML)", to_html(res), f"{slug}_promo_report.html", "text/html", width="stretch")
d2.download_button("Ranked list (CSV)", to_csv(res.promos), f"{slug}_promos_ranked.csv", "text/csv", width="stretch")
d3.download_button("Everything (JSON)", to_json(res), f"{slug}_promos.json", "application/json", width="stretch")
d4.download_button("Summary (Markdown)", to_markdown(res), f"{slug}_promos.md", "text/markdown", width="stretch")

tabs = ["Ranked promos", "Top pick", "By episode", "Season map", "All candidates", "Checks"]
if "compare" in st.session_state:
    tabs.append("Rules vs AI")
t = st.tabs(tabs)

with t[0]:
    st.html('<p class="pf" style="font-size:15px;color:var(--mute);margin:4px 0 0">In posting order. Click a row to see how its '
            'score adds up, what to check, and the full cut line by line.</p>')
    c1, c2, c3, c4 = st.columns([2.1, 1.7, 1.4, 1.4], vertical_alignment="bottom")
    kind = c1.segmented_control("Type", ["All", "Single clips", "Stitched"], default="All", key="kind")
    tiers = c2.pills("Tier", ["A", "B", "C"], selection_mode="multi", default=["A", "B", "C"], key="tiers",
                      help="A = strong, B = usable, C = weak")
    clean = c3.toggle("Hide flagged", value=False, help="Hide promos that have something for a human to check")
    order = c4.selectbox("Sort by", ["Posting order", "Score", "Episode"])
    shown = [p for p in res.promos
             if (kind in (None, "All") or (kind == "Single clips") == (p.kind == "single"))
             and ui.tier(p) in (tiers or ["A", "B", "C"]) and not (clean and p.flags)]
    if order == "Score":
        shown.sort(key=lambda p: -p.scores["total"])
    elif order == "Episode":
        shown.sort(key=lambda p: (min(p.episodes), p.segments[0].start))
    st.caption(f"Showing {len(shown)} of {len(res.promos)} promos")
    if shown:
        st.html(f'<div class="pf">{ui.compact_list(shown)}</div>')
    else:
        st.info("No promos match these filters.")

with t[1]:
    def _label(p):
        line = p.hook_beat.text.strip().strip('"')
        return f"#{p.rank} · Ep {' + '.join(map(str, p.episodes))} · {line[:70]}"
    labels = {p.id: _label(p) for p in res.promos}
    if labels:
        pick = st.selectbox("Choose a promo", list(labels), format_func=labels.get)
        p = next(x for x in res.promos if x.id == pick)
        st.html(f'<div class="pf">{ui.spotlight(p, eyebrow=f"Ranked #{p.rank} of {len(res.promos)}")}</div>')

with t[2]:
    have = {p.episodes[0]: p for p in res.by_episode}
    ep_nums = [e.num for e in res.episodes]
    c1, c2 = st.columns([1, 3])
    ep = c1.selectbox("Episode", ep_nums, format_func=lambda n: f"Episode {n}" + ("" if n in have else " (no clip)"))
    epi = next(e for e in res.episodes if e.num == ep)
    c2.html(f'<div class="pf" style="font-size:15px;color:var(--ink2);padding-top:30px">{ui.e(epi.logline)}</div>')
    in_ranked = [p for p in res.promos if ep in p.episodes]
    if in_ranked:
        st.caption("In the ranked list: " + ", ".join(f"#{p.rank}" for p in in_ranked))
    if ep in have:
        st.html(f'<div class="pf">{ui.card(have[ep])}</div>')
    else:
        st.info("No cut in this episode passed the rules (no strong opening line followed by an unresolved ending within 20–60 s).")
    ranked_keys = {cut_key(p) for p in res.promos}
    others = sorted((p for p in res.candidates if p.kind == "single" and p.episodes == [ep]),
                    key=lambda p: -p.scores.get("rules_total", p.scores["total"]))[:8]
    if others:
        st.markdown("**Other candidate cuts in this episode**")
        st.dataframe(pd.DataFrame([{
            "Cut": f"{fmt(p.segments[0].start)} → {fmt(p.segments[0].end)}",
            "Length": f"{p.duration:.0f} s", "Opens on": p.hook_beat.short(70), "Cuts on": p.cliff_beat.short(70),
            "Score": round(100 * p.scores.get("rules_total", p.scores["total"])),
            "Ranked": "yes" if cut_key(p) in ranked_keys else "",
            "To check": " | ".join(p.flags)} for p in others]), hide_index=True, width="stretch")
    st.download_button("Download best clip per episode (CSV)", to_csv(res.by_episode), f"{slug}_promos_by_episode.csv", "text/csv")

with t[3]:
    st.html(f'<div class="pf"><p class="pf-sub" style="margin:4px 0 16px">Where each ranked promo is cut from. Hover a block to see its cut points.</p>'
            f'{ui.season_map(res.episodes, res.promos, res.by_episode, link=False)}</div>')

with t[4]:
    allc = pd.read_csv(io.StringIO(to_csv(sorted(res.candidates, key=lambda p: -p.scores["total"])[:3000])), keep_default_na=False)
    st.html('<p class="pf" style="font-size:15px;color:var(--mute);margin:4px 0 0">Every scored cut, best first. '
            'Use this to check why a cut did or didn\'t make the list.</p>')
    c1, c2, c3 = st.columns([2, 1.4, 1.6], vertical_alignment="bottom")
    epf = c1.multiselect("Episodes", sorted({e.num for e in res.episodes}), placeholder="All episodes")
    kind2 = c2.segmented_control("Type", ["single", "stitched"], selection_mode="multi", default=["single", "stitched"],
                                 format_func=lambda k: "Single clips" if k == "single" else "Stitched", key="kind2")
    mins = c3.slider("Minimum score", 0.0, 1.0, 0.7, 0.01)
    view = allc[allc.total >= mins]
    if epf:
        view = view[view.episodes.astype(str).apply(lambda x: any(str(e) in x.split() for e in epf))]
    if kind2:
        view = view[view.kind.isin(kind2)]
    st.caption(f"Showing {len(view):,} of the top {len(allc):,} candidates")
    st.dataframe(
        view[["rank", "segments", "duration_s", "hook", "cliffhanger", "total", "hook_score", "cliff_score", "standalone", "kind", "flags"]],
        hide_index=True, height=560,
        column_config={
            "rank": st.column_config.TextColumn("Rank", width="small"),
            "segments": st.column_config.TextColumn("Cut points", width="medium"),
            "duration_s": st.column_config.NumberColumn("Length", format="%.0f s", width="small"),
            "hook": st.column_config.TextColumn("Opens on", width="large"),
            "cliffhanger": st.column_config.TextColumn("Cuts on", width="large"),
            "total": st.column_config.ProgressColumn("Score", min_value=0, max_value=1, format="%.2f"),
            "hook_score": st.column_config.ProgressColumn("Hook", min_value=0, max_value=1, format="%.2f"),
            "cliff_score": st.column_config.ProgressColumn("Cliffhanger", min_value=0, max_value=1, format="%.2f"),
            "standalone": st.column_config.ProgressColumn("New viewer", min_value=0, max_value=1, format="%.2f"),
            "kind": st.column_config.TextColumn("Type", width="small"),
            "flags": st.column_config.TextColumn("To check", width="medium"),
        })

with t[5]:
    st.html(f'<div class="pf" style="margin-top:4px">{ui.checks_panel(checks)}</div>')
    with st.expander("Run log"):
        st.code("\n".join(res.log), language=None)

if "compare" in st.session_state:
    with t[6]:
        rules_res, cmp = st.session_state.compare
        if cmp["mock"]:
            st.warning("Mock judge: these 'AI' scores are fake test values.")
        st.markdown(compare_md(rules_res, res, cmp))
        st.download_button("Download comparison (CSV)", compare_csv(cmp), f"{slug}_ai_vs_rules.csv", "text/csv")

        # --- FINAL LAYOUT OVERRIDE ---
# This forces the mascot to the top right and kills the empty header space
st.markdown("""
<style>
/* 1. Nuke the invisible Streamlit header completely */
header[data-testid="stHeader"], [data-testid="stHeader"] { 
    display: none !important; 
    height: 0px !important; 
}
.main .block-container { 
    padding-top: 1.5rem !important; 
}

/* 2. Force the hero text and mascot to align to the TOP, not the middle */
.pf-home-hero {
    align-items: flex-start !important;
    width: 100% !important;
    max-width: 100% !important;
}

/* 3. Push the mascot flush into the empty top-right corner */
.pf-home-art {
    justify-content: flex-end !important;
    margin-top: -5px !important; /* Lifts the mascot up to match the text */
    flex-grow: 1 !important;
}

/* 4. Let the feature cards expand to fill the horizontal right-side gap */
.pf-feature-row {
    width: 100% !important;
    max-width: 100% !important;
}
</style>
""", unsafe_allow_html=True)
# --- PROFESSIONAL DARK RED & CENTERED BUTTON OVERRIDE ---
st.markdown("""
<style>
/* 1. Darker, Executive Crimson Red for Sidebar Active Items */
section[data-testid="stSidebar"] .st-key-nav_home [data-testid="stBaseButton-primary"],
section[data-testid="stSidebar"] .st-key-nav_how [data-testid="stBaseButton-primary"],
section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, #8E0E12 0%, #5C080B 100%) !important;
    border: 1px solid #730A0E !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35) !important;
}

section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:hover {
    background: linear-gradient(135deg, #A61217 0%, #700B0F 100%) !important;
}

/* 2. Primary Action Button ("Find Promos") Darker Red */
[data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, #8E0E12 0%, #61080B 100%) !important;
    border: 1px solid #750A0D !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
}

[data-testid="stBaseButton-primary"]:hover {
    background: linear-gradient(135deg, #A61217 0%, #720B0F 100%) !important;
}

/* 3. Center the Action Button Row inside the Upload Panel */
.st-key-home_upload_panel [data-testid="stHorizontalBlock"] {
    justify-content: center !important;
    align-items: center !important;
}

.st-key-find_home {
    display: flex !important;
    justify-content: center !important;
    width: 100% !important;
}

.st-key-find_home button {
    margin: 0 auto !important;
    display: block !important;
    width: 100% !important;
    max-width: 220px !important;
}

/* 4. Remove Duplicate Helper Text under File Uploader */
.st-key-home_upload_panel + div:has(.pf-upload-limit) {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)