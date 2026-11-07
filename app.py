"""Promo Finder — Streamlit UI.   Run:  streamlit run app.py"""
from __future__ import annotations

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
from promo_finder.report import to_csv, to_html, to_json, to_markdown
from promo_finder.usage import SarvamConfig

ROOT = Path(__file__).parent
st.set_page_config(page_title="Promo Finder", page_icon=str(ROOT / "static" / "favicon.png"),
                   layout="wide", initial_sidebar_state="auto")

APP_CSS = """
[data-testid="stToolbarActions"],[data-testid="stMainMenu"],[data-testid="stDecoration"],#MainMenu,footer{display:none!important}
header[data-testid="stHeader"]{background:transparent}
[data-testid="stExpandSidebarButton"],[data-testid="stSidebarCollapsedControl"]{visibility:visible!important;opacity:1!important}
[data-testid="stExpandSidebarButton"]{width:auto!important;height:auto!important;padding:9px 16px 9px 12px!important;border-radius:999px!important;background:#d6194a!important;box-shadow:0 2px 10px rgba(214,25,74,.35)!important;gap:6px!important}
[data-testid="stExpandSidebarButton"]:hover{background:#b3133d!important}
[data-testid="stExpandSidebarButton"] span{color:#fff!important}
[data-testid="stExpandSidebarButton"]::after{content:"Upload scripts";font:600 14px/1 Inter,sans-serif;color:#fff;white-space:nowrap}
@media (max-width:860px){.block-container{padding-top:4.6rem!important}}
.block-container{max-width:1200px;padding-top:2.2rem;padding-bottom:5rem}
section[data-testid="stSidebar"]>div{padding-top:.4rem}
[data-testid="stSidebarHeader"]{height:0!important;min-height:0!important;padding:0!important;margin:0!important;position:relative;z-index:3}
[data-testid="stSidebarCollapseButton"]{position:absolute!important;top:18px;right:14px}
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


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.html(f'<div class="pf pf-sbbrand" style="margin:0">{ui.logo()}<p style="font-size:14px;color:var(--mute);margin-top:10px">'
            'Finds promo cuts in microdrama scripts.</p></div>')
    sb_head("1", "Upload scripts")
    files = st.file_uploader("Episode scripts", type=["zip", "txt"], accept_multiple_files=True, label_visibility="collapsed",
                             help="A .zip of the season, or the episode .txt files. Timestamped screenplays, one per episode.")
    guess = ""
    if files:
        z = next((f for f in files if f.name.lower().endswith(".zip")), None)
        if z:
            try:
                with zipfile.ZipFile(io.BytesIO(z.getvalue())) as zf:  # prefer the folder name inside the zip
                    tops = {n.split("/")[0] for n in zf.namelist() if "/" in n and not n.startswith("__MACOSX")}
            except zipfile.BadZipFile:
                tops = set()
            base = tops.pop() if len(tops) == 1 else re.sub(r"\.zip$", "", z.name, flags=re.I)
            guess = re.sub(r"[-_ ]?scripts.*$", "", base, flags=re.I).strip()
    sb_head("2", "Check the show title")
    title = st.text_input("Show title", value=guess, placeholder="e.g. The Maid Was the Heiress",
                          help="The title tells the tool what the show promises (for example a secret Duke), so promos that sell it rank higher.")
    sb_head("3", "Find promos")
    if config.configured:
        st.html('<div class="pf-service"><span class="dot"></span>AI review enabled</div>')
    else:
        st.info("AI review is unavailable. Contact the app owner.")
    go = st.button("Find promos", type="primary", width="stretch", disabled=not files or not config.configured)

# ---------------------------------------------------------------- first visit
if "result" not in st.session_state and not go:
    st.html("""<div class="pf"><div class="pf-intro"><div class="pf-label accent">Promo Finder</div>
<h1 class="pf-h2" style="font-size:32px;margin-top:8px">Find promo cuts in a season of scripts</h1>
<p>Turn timestamped screenplays into a ranked shortlist of 20–60 second promos, with exact cut points,
hooks and cliffhangers ready for an editor to review.</p></div>
<div style="margin-top:36px;padding:48px 28px;border:1px dashed var(--line2);border-radius:16px;text-align:center;background:var(--surface)">
<div aria-hidden="true" style="font-size:30px;color:var(--mute);margin-bottom:16px">▷</div>
<h2 style="font-size:21px;font-weight:600;margin:0 0 10px">Your promo shortlist starts here</h2>
<p style="color:var(--mute);font-size:15px;margin:0">Upload a ZIP or episode scripts in the sidebar, check the show title, then choose Find promos.</p>
<div style="display:flex;justify-content:center;flex-wrap:wrap;gap:12px;margin-top:24px;font-size:13px;color:var(--mute)">
<span>20–60 second clips</span><span aria-hidden="true">·</span><span>Exact cut points</span><span aria-hidden="true">·</span><span>Hooks &amp; cliffhangers</span>
</div></div></div>""")
    st.stop()

# ---------------------------------------------------------------- run
if go:
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
        st.error("No timestamped episodes found. Each script needs blocks like '**SPEAKER:**' followed by "
                 "'Start: (MM:SS.ss) | End: (MM:SS.ss)'.")
        st.stop()
    show_title = title.strip() or (f"Episode {eps[0].num}" if len(eps) == 1 else "Series promo report")
    if not config.configured:
        st.error("AI review is unavailable. Contact the app owner.")
        st.stop()
    try:
        judge = Judge(f"sarvam:{config.model}", api_key=config.api_key,
                      base_url=config.base_url, use_cache=False)
    except (ValueError, TypeError):
        st.error("The AI reviewer could not start. If the app was just updated, use Manage app → "
                 "Reboot app. Otherwise contact the app owner.")
        st.stop()

    def show_progress(message: str) -> None:
        st.write(message)

    with st.status("Finding promos…", expanded=True) as status:
        try:
            if judge and compare_too:
                rules_res, res, cmp = compare(eps, show_title, judge, llm_top, progress=show_progress,
                                               n_single=n_single, n_stitched=n_stitched)
                st.session_state.compare = (rules_res, cmp)
            else:
                res = run(eps, show_title, judge or "rules", n_single, n_stitched, llm_top,
                          progress=show_progress, warnings=warnings)
                st.session_state.pop("compare", None)
        except Exception as e:  # show a clear message instead of a stack trace
            status.update(label="Run failed", state="error")
            detail = str(e).replace(config.api_key, "[redacted]") if config.api_key else str(e)
            st.error(f"Something went wrong while ranking: {type(e).__name__}: {detail}")
            st.stop()
        if res.stats.get("ai", {}).get("judged", 0):
            status.update(label=f"Report ready · {len(res.promos)} promos", state="complete", expanded=False)
        else:
            status.update(label="AI review unavailable", state="error", expanded=False)
    st.session_state.result = res
    st.session_state.checks = run_checks(res)

res = st.session_state.result
checks = st.session_state.get("checks") or run_checks(res)
s = res.stats

ai = s.get("ai", {})
if not ai.get("judged", 0):
    reason = {
        401: "The AI connection needs attention. Contact the app owner.",
        403: "The AI connection needs attention. Contact the app owner.",
        402: "AI review is paused because the service is out of credits.",
        429: "The AI service is busy. Please try again shortly.",
    }.get(ai.get("last_error_code"), "The AI service did not return a usable review. Please try again.")
    st.error(reason)
    st.caption("No AI-ranked report was produced. Your scripts are still uploaded; choose Find promos to retry.")
    with st.expander("Run details"):
        st.code("\n".join(res.log), language=None)
    if not st.checkbox("Show backup ranking", value=False):
        st.stop()
    badge = '<span class="pf-mode">Backup ranking · AI review unavailable</span>'
else:
    if ai.get("stopped") or ai.get("failed"):
        st.warning(f'AI reviewed {ai["judged"]} of {ai.get("shortlisted", 0)} shortlisted clips. '
                   'The report includes backup scores for the remaining clips.')
    badge = (f'<span class="pf-mode ai">AI reviewed {ai["judged"]} of '
             f'{ai.get("shortlisted", 0)} shortlisted clips</span>')

st.html(f"""<div class="pf"><div class="pf-label accent">Promo report</div>
<h1 class="pf-h2" style="font-size:28px;margin:4px 0 10px">{ui.e(res.title)}</h1>
<div style="margin-bottom:8px">{badge}</div>{ui.run_summary({**s, "ai": {}}, checks)}</div>""")
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
