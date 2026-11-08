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
st.set_page_config(page_title="Promo Finder", page_icon=str(ROOT / "static" / "favicon.png"),
                   layout="wide", initial_sidebar_state="expanded")



st.html(ui.css("static"))
st.html(ROOT / "static" / "promo-finder.css")


def sb_head(n: str, text: str) -> None:
    st.html(f'<div class="pf-sbh"><b>{n}</b>{text}</div>')


def secret(name: str) -> str:
    try:
        return st.secrets.get(name, "") or os.getenv(name, "")
    except Exception:  # no secrets file configured
        return os.getenv(name, "")


config = SarvamConfig.load(secret)
n_single, n_stitched, llm_top, compare_too = 20, 6, 40, True


def mascot(class_name: str) -> str:
    image = base64.b64encode((ROOT / "static" / "mascot.webp").read_bytes()).decode("ascii")
    # Explicit dimensions are a hard fallback if a browser/theme drops custom CSS.
    dimensions = {
        "pf-mascot-brand": (44, 44),
        "pf-mascot-welcome": (188, 188),
        "pf-mascot-mobile": (52, 62),
    }.get(class_name, (44, 44))
    width, height = dimensions
    return (f'<img class="pf-mascot {class_name}" width="{width}" height="{height}" '
            f'style="width:{width}px;height:{height}px;max-width:{width}px;max-height:{height}px;object-fit:contain;'
            f'display:block;flex:0 0 auto" src="data:image/webp;base64,{image}" '
            f'alt="Promo Finder clapperboard mascot" />')


def svg_icon(name: str, size: int = 24, class_name: str = "") -> str:
    """Inline Lucide-style line icons for the landing screen."""
    paths = {
        "home": '<path d="m3 10 9-7 9 7"/><path d="M5 9v11h14V9"/><path d="M9 20v-6h6v6"/>',
        "info": '<circle cx="12" cy="12" r="9"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
        "bolt": '<path d="m13 2-3 8h7l-6 12 2-9H6l7-11z"/>',
        "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/><path d="m16.5 7.5 4-4"/>',
        "layers": '<path d="m12 3 9 5-9 5-9-5 9-5z"/><path d="m3 12 9 5 9-5"/><path d="m3 16 9 5 9-5"/>',
        "cloud-upload": '<path d="M16 16l-4-4-4 4"/><path d="M12 12v9"/><path d="M20 16.5a4.5 4.5 0 0 0-.7-8.95A7 7 0 0 0 5.2 9.4 4 4 0 0 0 5 17h3"/>',
        "upload": '<path d="M12 16V4m-5 5 5-5 5 5"/><path d="M20 16.5v2A1.5 1.5 0 0 1 18.5 20h-13A1.5 1.5 0 0 1 4 18.5v-2"/>',
        "play": '<path d="m8 5 12 7-12 7z"/>',
        "list": '<path d="M9 6h12M9 12h12M9 18h12"/><path d="M4 6h.01M4 12h.01M4 18h.01"/>',
        "clapper": '<path d="M4 8h16v12H4z"/><path d="m4 8 2-5h16l-2 5"/><path d="M9 3 7 8m7-5-2 5m7-5-2 5"/><circle cx="9" cy="14" r="1"/><path d="m12 18 3-2 2 2"/>',
    }
    return (f'<svg class="{class_name}" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{paths.get(name, "")}</svg>')


def feature_item(icon: str, title: str, detail: str) -> str:
    return (f'<div class="pf-feature"><span class="pf-feature-icon">{svg_icon(icon, 25)}</span>'
            f'<span><b>{title}</b><small>{detail}</small></span></div>')


def process_step(number: int, icon: str, title: str, detail: str) -> str:
    return (f'<div class="pf-start-step"><span class="n">{number}</span>'
            f'<span class="step-icon">{svg_icon(icon, 25)}</span><h3>{title}</h3><p>{detail}</p></div>')


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
    """Validate upload choices only; the AI workflow begins only on Find Promos."""
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
        # Force a fresh uploader widget while retaining any valid files in session state.
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


# ---------------------------------------------------------------- sidebar
if "active_page" not in st.session_state:
    st.session_state.active_page = "Home"


def set_active_page(name: str) -> None:
    st.session_state.active_page = name


with st.sidebar:
    st.html(f'<div class="pf-sidebar-brand">{mascot("pf-mascot-brand")}<b>Promo Finder</b></div>'
            '<p class="pf-sidebar-tagline">Finds promo cuts in microdrama scripts.</p>')
    for label, key, icon in (("Home", "home", "home"), ("How it Works", "how", "info")):
        active = st.session_state.active_page == label
        icon_col, button_col = st.columns([0.42, 3.58], gap="small", vertical_alignment="center")
        with icon_col:
            st.html(f'<div class="pf-sidebar-nav-icon">{svg_icon(icon, 22)}</div>')
        with button_col:
            st.button(label, key=f"nav_{key}", type="primary" if active else "secondary",
                      width="stretch", on_click=set_active_page, args=(label,))

    st.html('<div class="pf-sidebar-divider"></div>')
    if config.configured:
        st.html('<div class="pf-sidebar-status"><span class="dot"></span><span>AI review enabled</span></div>')
    else:
        st.html('<div class="pf-sidebar-status"><span class="dot" style="background:#F59E0B"></span>'
                '<span>AI review unavailable</span></div>')

    st.html(f"""
<div class="pf-quickstats">
  <h4>Quick Stats</h4>
  <div class="pf-quickstat"><span class="ico">{svg_icon("play", 24)}</span>
    <div><b>20 – 60 sec</b><small>Promo length</small></div></div>
  <div class="pf-quickstat"><span class="ico">{svg_icon("layers", 24)}</span>
    <div><b>4</b><small>Export formats</small></div></div>
</div>""")

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

# The guide page is independent of the upload and analysis workflow.
if page == "How it Works":
    render_how_it_works_page()
    st.stop()

# Reserve the first main-area slot so progress appears above the upload form.
progress_panel = st.empty()

# ---------------------------------------------------------------- first visit
if page == "Home" and "result" not in st.session_state and not go:
    features = "".join([
        feature_item("bolt", "AI + Rules Engine", "Scores & reranks promos"),
        feature_item("target", "Script-accurate", "Exact timestamps"),
        feature_item("layers", "Editor-ready", "Reports, CSV & more"),
    ])
    steps = (
        process_step(1, "upload", "Upload your story",
                     "One episode or a full season of timestamped screenplays.")
        + '<div class="pf-step-arrow">→</div>'
        + process_step(2, "list", "Review the strongest moments",
                       "Ranked 20–60 second cuts, with hooks and cliffhangers.")
        + '<div class="pf-step-arrow">→</div>'
        + process_step(3, "clapper", "Take it to your editor",
                       "Exact cut points, editorial notes and reports to share.")
    )
    st.html(f"""
<div class="pf-home-hero">
  <div class="pf-home-hero-copy">
    <div class="pf-home-eyebrow">PROMO FINDER</div>
    <h1 style="font-size:clamp(48px,4.1vw,64px);line-height:1.05;letter-spacing:-1.9px;font-weight:750;color:#1A1A1C;margin:12px 0 13px">Find the moments<br><span style="color:#E11D26">worth promoting</span></h1>
    <p>Find ranked 20–60 second promo cuts, with hooks and cliffhangers ready for your editor.</p>
  </div>
  <div class="pf-home-art" style="position:relative;width:300px;min-width:250px;height:190px;flex:0 0 300px;display:flex;align-items:center;justify-content:center;overflow:hidden">{feature_hero_art()}</div>
</div>
<div class="pf-feature-row">{features}</div>
""")

    with st.container(key="home_upload_panel"):
        upload_key = f'home_files_{st.session_state.get("home_upload_version", 0)}'
        with st.container(key="upload_zone"):
            st.file_uploader(
                "Upload your microdrama scripts",
                type=["zip", "txt"],
                accept_multiple_files=True,
                key=upload_key,
                on_change=select_uploads,
                args=(upload_key,),
                label_visibility="collapsed",
                help="ZIP or TXT screenplays · 50MB maximum per file.",
            )
            if not files:
                st.html(f"""
<div class="pf-dropzone-overlay">
  <div class="cloud">{svg_icon("cloud-upload", 56)}</div>
  <h2>Upload your microdrama scripts</h2>
  <p>Drag &amp; drop a ZIP or TXT file here, or <span class="pf-inline-link">choose files</span></p>
  <div class="limit">Up to 50MB per file • ZIP, TXT</div>
</div>""")

        upload_error = st.session_state.get("upload_error", "")
        if upload_error:
            st.html(f'<div class="pf-upload-error">{svg_icon("info", 17)}<span>{html_escape(upload_error)}</span></div>')
        if files:
            names = ", ".join(html_escape(file.name) for file in files)
            st.html(f'<div class="pf-ready-files">Selected: {names}</div>')

        label_col, divider_col, input_col, action_col = st.columns(
            [0.65, 0.02, 4.30, 1.45], gap="small", vertical_alignment="center"
        )
        with label_col:
            st.html('<div class="pf-action-label">Show title</div>')
        with divider_col:
            st.html('<div class="pf-action-divider"></div>')
        with input_col:
            home_title = st.text_input(
                "Show title",
                key="home_title",
                placeholder="e.g. The Maid Was the Heiress",
                label_visibility="collapsed",
                on_change=sync_title,
                args=("home_title", "show_title"),
            )
        with action_col:
            go = st.button("Find Promos", key="find_home", type="primary",
                           width="stretch", disabled=not files)

        if go:
            title = home_title

    if not go:
        st.html(f'<div class="pf-start-steps">{steps}</div>')
        st.stop()

# ---------------------------------------------------------------- run
if go:
    review = ReviewProgress()
    progress_panel.html(review.html())
    warnings: list[str] = []
    raw = []
    for f in files:
        data = f.getvalue()
        if f.name.lower().endswith(".zip"):
            try:
                raw += load_zip_bytes(data, [])     # finalize() below reports problems once, across all files
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
