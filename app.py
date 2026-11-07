"""Promo Finder — Streamlit UI.   Run:  streamlit run app.py"""
from __future__ import annotations

import base64
import io
import os
import re
import zipfile
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
                   layout="wide", initial_sidebar_state="auto")

APP_CSS = """
[data-testid="stToolbarActions"],[data-testid="stMainMenu"],[data-testid="stDecoration"],#MainMenu,footer{display:none!important}
header[data-testid="stHeader"]{background:transparent;pointer-events:none}
header[data-testid="stHeader"] button{pointer-events:auto}
[data-testid="stExpandSidebarButton"],[data-testid="stSidebarCollapsedControl"]{visibility:visible!important;opacity:1!important}
[data-testid="stExpandSidebarButton"]{width:auto!important;height:auto!important;padding:9px 16px 9px 12px!important;border-radius:999px!important;background:#d6194a!important;box-shadow:0 2px 10px rgba(214,25,74,.35)!important;gap:6px!important}
[data-testid="stExpandSidebarButton"]:hover{background:#b3133d!important}
[data-testid="stExpandSidebarButton"] span{color:#fff!important}
[data-testid="stExpandSidebarButton"]::after{content:"Project";font:600 14px/1 Inter,sans-serif;color:#fff;white-space:nowrap}
@media (max-width:860px){.block-container{padding-top:4.6rem!important}}
.block-container{max-width:1200px;padding-top:2.2rem;padding-bottom:5rem}
section[data-testid="stSidebar"]>div{padding-top:.4rem}
[data-testid="stSidebarHeader"]{height:0!important;min-height:0!important;padding:0!important;margin:0!important;position:relative;z-index:3}
[data-testid="stSidebarCollapseButton"]{position:absolute!important;top:18px;right:14px;visibility:visible!important;opacity:1!important}
[data-testid="stSidebar"] button[aria-label="Collapse sidebar"]{visibility:visible!important;opacity:1!important}
[data-testid="stSidebarUserContent"]{padding-top:20px!important}
.pf-sbbrand .pf-brand{gap:12px;font-size:20px}
.pf-sbbrand .pf-logo{transform:scale(1.3);transform-origin:left center;margin-right:9px}
.pf-sbh{font:600 12px/1 Inter,sans-serif;letter-spacing:.06em;text-transform:uppercase;color:#55555f;margin:22px 0 4px;
display:flex;gap:8px;align-items:center}
.pf-sbh b{display:inline-grid;place-items:center;width:20px;height:20px;border-radius:6px;background:#121216;color:#fff;font-size:11px;letter-spacing:0}
[data-testid="stBaseButton-primary"]{font-weight:600!important}
[data-testid="stBaseButton-secondary"],[data-testid="stDownloadButton"] button{font-weight:600!important;background:#fff!important}
[data-testid="stFileUploaderDropzone"]{background:#fafaf8;border-radius:12px}
.stTabs [data-baseweb="tab-list"]{gap:4px;border-bottom:1px solid #e3e3de}
.stTabs [data-baseweb="tab"]{font-size:15px;font-weight:600;padding:12px 14px;height:auto}
.pf-intro{max-width:760px}
.pf-intro p{font-size:17px;color:var(--ink2);margin:12px 0 0}
.pf-intro ol{margin:10px 0 0 20px!important;padding:0!important}.pf-intro ol li{margin:0 0 6px!important;font-size:16px;color:var(--ink2)}
.pf-service{padding:12px 14px;background:#fafaf8;border:1px solid #e3e3de;border-radius:12px;font-size:14px;line-height:1.5}
.pf-service .dot{display:inline-block;width:7px;height:7px;background:#33845b;border-radius:50%;margin-right:8px}
.pf-review{max-width:900px;margin:24px auto;padding:30px;background:var(--surface);border:1px solid var(--line2);border-radius:16px}
.pf-review-heading{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-top:14px}
.pf-review-heading h2{font-size:23px;line-height:1.4;font-weight:600;margin:0;display:flex;align-items:center;gap:12px}
.pf-review-heading>span{font-size:13px;color:var(--mute);white-space:nowrap}
.pf-review p{font-size:15px;line-height:1.6;color:var(--mute);margin:9px 0 24px}
.pf-review-dot{width:8px;height:8px;border-radius:50%;background:var(--accent,#d6194a);animation:pf-breathe 1.6s ease-in-out infinite;flex-shrink:0}
.pf-review-track{height:5px;background:var(--line);border-radius:999px;overflow:hidden}
.pf-review-fill{height:100%;background:#d6194a;border-radius:999px;transition:width .25s ease}
.pf-review-pulse{height:100%;width:30%;background:#d6194a;border-radius:999px;animation:pf-sweep 1.8s ease-in-out infinite}
.pf-review-steps{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:25px}
.pf-review-step{display:flex;align-items:center;gap:7px;color:var(--mute);font-size:12px;line-height:1.4}
.pf-review-step span{display:inline-grid;place-items:center;flex-shrink:0;width:21px;height:21px;background:var(--surface2);border-radius:50%;font-size:11px}
.pf-review-step.active{color:#b3133d;font-weight:600}.pf-review-step.active span{background:#fbe8ed}
.pf-review-step.done span{color:#33845b;background:#e8f3ec}
@keyframes pf-sweep{from{transform:translateX(-100%)}to{transform:translateX(430%)}}
@keyframes pf-breathe{0%,100%{opacity:1}50%{opacity:.3}}
@media(max-width:600px){.pf-review{padding:23px 20px}.pf-review-heading{align-items:flex-start;flex-direction:column;gap:8px}.pf-review-heading h2{font-size:21px}.pf-review-steps{grid-template-columns:repeat(2,1fr);gap:13px}}
@media(prefers-reduced-motion:reduce){.pf-review-dot,.pf-review-pulse{animation:none}.pf-review-fill{transition:none}}
/* Final visual polish: keep the existing controls and report views. */
.block-container{max-width:1360px;padding-top:3.8rem}
.pf{--line:#e6e5ea;--line2:#d7d5de;--surface2:#f6f5f8;--surface3:#ebe9ef;--shadow:0 2px 8px rgba(25,18,40,.035)}
.pf-sbbrand{padding:0 0 17px;border-bottom:1px solid #eceaf0}
.pf-sbbrand .pf-brand{font-size:21px;letter-spacing:-.6px;gap:11px}
.pf-mascot{object-fit:contain;flex-shrink:0;display:block}
.pf-mascot-brand{width:48px;height:54px}
.pf-sbbrand p{line-height:1.65!important;max-width:240px}
.pf-sbh{letter-spacing:.065em;font-size:11px;margin-top:25px;color:#60606b}
.pf-sbh b{background:#f4edf1;color:#9d2347;border:1px solid #ecdde3;border-radius:7px}
[data-testid="stFileUploaderDropzone"]{border:1px dashed #d8d5df!important;background:#faf9fc!important;border-radius:14px!important;padding:18px 14px!important}
[data-testid="stTextInput"] input{font-size:14px!important}
[data-testid="stTextInputRootElement"],[data-baseweb="select"]>div{border-color:#e2dfe8!important;border-radius:10px!important}
[data-testid="stBaseButton-primary"]{border-radius:10px!important;box-shadow:0 3px 8px rgba(214,25,74,.12);min-height:44px}
[data-testid="stBaseButton-primary"]:disabled{box-shadow:none}
[data-testid="stBaseButton-secondary"],[data-testid="stDownloadButton"] button{border-color:#e0dde6!important;border-radius:10px!important;min-height:42px;transition:border-color .15s,box-shadow .15s}
[data-testid="stDownloadButton"] button:hover{border-color:#d394a7!important;box-shadow:0 2px 7px rgba(40,20,35,.045)}
.pf-service{background:#fafafc;border-color:#e6e4eb;font-size:13px;padding:11px 13px;border-radius:10px}
.pf-report-head{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:3px 0 17px}
.pf-report-head h1{font-size:30px;letter-spacing:-.75px;margin:6px 0 12px}
.pf-report-head .pf-label{font-size:11px;letter-spacing:.09em}
.pf-mascot-mobile{display:none}
.pf-mode{font-size:12px;border-radius:7px;padding:6px 10px}
.pf-mode.ai{color:#59428a;background:#f1edf8}
.pf-summary{border:1px solid #e6e4eb;border-radius:12px;background:#fff;padding:15px 18px;margin-bottom:4px;gap:9px 23px;font-size:13px;line-height:1.65}
.pf-summary b{font-weight:600}
.stTabs{margin-top:9px}
.stTabs [data-baseweb="tab-list"]{gap:0;border-bottom-color:#e6e3eb}
.stTabs [data-baseweb="tab"]{font-size:14px;font-weight:500;padding:12px 13px;white-space:nowrap}
.pf-clist{border-color:#e4e1e9;border-radius:14px;box-shadow:0 2px 8px rgba(25,18,40,.035)}
.pf-chead{background:#f8f7fa;font-size:11px;letter-spacing:.055em;padding-top:12px;padding-bottom:12px}
.pf-crow>summary{padding-top:17px;padding-bottom:17px}
.cr-hook{font-size:16px;line-height:1.6}
.cr-cliff{line-height:1.65;font-size:13px}
.cr-cuts{font-size:12px;color:#64616e}
.cr-tags .pf-badge{font-size:11px;padding:5px 7px;border-radius:6px}
.pf-rank.top{background:#24212a;border-color:#24212a}
.pf-crow>summary:hover,.pf-crow[open]>summary{background:#fcfafd}
.pf-review{box-shadow:0 3px 14px rgba(25,18,40,.035)}
.pf-intro h1{letter-spacing:-.8px}
.pf-intro-top{display:flex;align-items:center;justify-content:space-between;gap:25px}
.pf-mascot-welcome{width:88px;height:98px}
@media(max-width:860px){.pf-report-head h1{font-size:26px;overflow-wrap:anywhere}.pf-mascot-mobile{display:block;width:52px;height:62px}.pf-summary{font-size:12px;padding:14px;gap:7px 18px}.stTabs [data-baseweb="tab"]{font-size:13px;padding:11px 12px}.cr-hook{font-size:15px}.pf-mascot-welcome{width:64px;height:74px}.pf-intro-top{gap:15px}}
@media(prefers-reduced-motion:reduce){[data-testid="stBaseButton-secondary"],[data-testid="stDownloadButton"] button{transition:none}}
.st-key-home_upload_panel{margin-top:26px;background:#fff;border:1px solid #e4e0e9;border-radius:16px;padding:25px}
.st-key-home_upload_panel [data-testid="stFileUploaderDropzone"]{min-height:150px;padding:22px!important}
.pf-home-title{font-size:21px;font-weight:600;letter-spacing:-.4px;margin:0 0 5px}
.pf-home-hint{font-size:14px;color:var(--mute);line-height:1.6;margin-bottom:12px!important}
.pf-start-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;margin-top:25px}
.pf-start-step{border:1px solid var(--line);border-radius:13px;padding:18px;background:var(--surface)}
.pf-start-step .n{display:inline-grid;place-items:center;width:25px;height:25px;border-radius:8px;background:var(--hook-bg);color:var(--hook);font-size:12px;font-weight:600;margin-bottom:12px}
.pf-start-step h3{font-size:14px;font-weight:600;margin-bottom:6px}.pf-start-step p{font-size:13px;color:var(--mute);line-height:1.7}
@media(max-width:600px){.st-key-home_upload_panel{padding:18px}.pf-start-steps{grid-template-columns:1fr;gap:10px}.pf-start-step{padding:15px}.pf-start-step .n{float:left;margin:0 12px 20px 0}.pf-home-title{font-size:19px}}
"""

st.html(ui.css("static") + f"<style>{APP_CSS}</style>")


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
    return f'<img class="pf-mascot {class_name}" src="data:image/webp;base64,{image}" alt="Promo Finder clapperboard mascot" />'


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


def select_uploads(widget_key: str) -> None:
    clear_report()
    st.session_state.source_files = list(st.session_state.get(widget_key) or [])
    suggested = guess_title(st.session_state.source_files)
    st.session_state.show_title = suggested
    st.session_state.home_title = suggested


def sync_title(source: str, target: str) -> None:
    st.session_state[target] = st.session_state[source]


def new_analysis() -> None:
    clear_report()
    st.session_state.source_files = []
    st.session_state.show_title = ""
    st.session_state.home_title = ""
    st.session_state.home_upload_version = st.session_state.get("home_upload_version", 0) + 1


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.html(f'<div class="pf pf-sbbrand" style="margin:0"><div class="pf-brand">{mascot("pf-mascot-brand")}<span>Promo Finder</span></div><p style="font-size:14px;color:var(--mute);margin-top:10px">'
            'Finds promo cuts in microdrama scripts.</p></div>')
    sb_head("1", "Your scripts")
    files = list(st.session_state.get("source_files", []))
    if files:
        st.caption("Current upload: " + ", ".join(f.name for f in files))
    else:
        st.caption("Add your ZIP or TXT scripts in the main workspace to get started.")
    go = False
    title = st.session_state.get("show_title", "")
    if "result" in st.session_state:
        sb_head("2", "Review settings")
        title = st.text_input("Show title", key="show_title", placeholder="e.g. The Maid Was the Heiress",
                          on_change=sync_title, args=("show_title", "home_title"),
                          help="The title tells the tool what the show promises (for example a secret Duke), so promos that sell it rank higher.")
        go = st.button("Find promos", type="primary", width="stretch", disabled=not files or not config.configured)
    if config.configured:
        st.html('<div class="pf-service"><span class="dot"></span>AI review enabled</div>')
    else:
        st.info("AI review is unavailable. Contact the app owner.")

# ---------------------------------------------------------------- first visit
if "result" not in st.session_state and not go:
    st.html(f'<div class="pf"><div class="pf-intro-top"><div class="pf-intro"><div class="pf-label accent">Promo Finder</div>' + """
<h1 class="pf-h2" style="font-size:32px;margin-top:8px">Find promo cuts in a season of scripts</h1>
<p>Turn timestamped screenplays into a ranked shortlist of 20–60 second promos, with exact cut points,
hooks and cliffhangers ready for an editor to review.</p></div>""" + mascot("pf-mascot-welcome") + """</div>
</div>""")
    with st.container(key="home_upload_panel"):
        st.html('<div class="pf"><h2 class="pf-home-title">Upload scripts to get started</h2>'
                '<p class="pf-home-hint">Choose a season ZIP or individual episode TXT files. You can also drag them into the upload area.</p></div>')
        home_upload_key = f'home_files_{st.session_state.get("home_upload_version", 0)}'
        st.file_uploader("Upload scripts", type=["zip", "txt"], accept_multiple_files=True,
                         key=home_upload_key, on_change=select_uploads, args=(home_upload_key,),
                         label_visibility="collapsed", help="Timestamped screenplays. ZIP and TXT files, up to 50 MB per file.")
        if files:
            st.caption("Ready: " + ", ".join(f.name for f in files))
        home_title = st.text_input("Show title", key="home_title", placeholder="e.g. The Maid Was the Heiress",
                      on_change=sync_title, args=("home_title", "show_title"),
                      help="Check the title before starting. It helps the reviewer understand the show's premise.")
        go = st.button("Find promos", key="find_home", type="primary", width="stretch",
                       disabled=not files or not config.configured)
        if go:
            title = home_title
        if not files:
            st.caption("Upload your scripts to enable Find promos.")
    if not go:
        st.html('''<div class="pf"><div class="pf-start-steps">
<div class="pf-start-step"><span class="n">1</span><h3>Upload your story</h3><p>One episode or a full season. Use timestamped screenplay files.</p></div>
<div class="pf-start-step"><span class="n">2</span><h3>Review the strongest moments</h3><p>Compare 20–60 second cuts with opening hooks, cliffhangers and editorial notes.</p></div>
<div class="pf-start-step"><span class="n">3</span><h3>Take it to your editor</h3><p>Export exact cut points and ranked recommendations, then start a new analysis anytime.</p></div>
</div></div>''')
        st.stop()

# ---------------------------------------------------------------- run
if go:
    review = ReviewProgress()
    progress_panel = st.empty()
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
nav_left, nav_right = st.columns([3, 1], vertical_alignment="center")
nav_left.caption("Your promo report · Analyse another script whenever you’re ready.")
nav_right.button("New analysis", key="new_analysis", on_click=new_analysis, width="stretch", icon=":material/add:")
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
