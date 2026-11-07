"""Promo Finder — Streamlit UI.   Run:  streamlit run app.py"""
from __future__ import annotations

import io
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from promo_finder import load_path, ui
from promo_finder.checks import run_checks
from promo_finder.compare import compare, cut_key, to_csv as compare_csv, to_markdown as compare_md
from promo_finder.llm import Judge
from promo_finder.parser import finalize, fmt, load_zip_bytes, parse_text
from promo_finder.pipeline import run
from promo_finder.report import to_csv, to_html, to_json, to_markdown
from promo_finder.usage import BILLING_URL, SarvamConfig, UsageLedger

ROOT = Path(__file__).parent
DEMO = ROOT / "samples" / "demo_show.zip"
st.set_page_config(page_title="Promo Finder", page_icon=str(ROOT / "static" / "favicon.png"),
                   layout="wide", initial_sidebar_state="auto")

APP_CSS = """
[data-testid="stToolbarActions"],[data-testid="stMainMenu"],[data-testid="stDecoration"],#MainMenu,footer{display:none!important}
header[data-testid="stHeader"]{background:transparent}
[data-testid="stExpandSidebarButton"],[data-testid="stSidebarCollapsedControl"]{visibility:visible!important;opacity:1!important}
[data-testid="stExpandSidebarButton"]{width:auto!important;height:auto!important;padding:9px 16px 9px 12px!important;border-radius:999px!important;background:#d6194a!important;box-shadow:0 2px 10px rgba(214,25,74,.35)!important;gap:6px!important}
[data-testid="stExpandSidebarButton"]:hover{background:#b3133d!important}
[data-testid="stExpandSidebarButton"] span{color:#fff!important}
[data-testid="stExpandSidebarButton"]::after{content:"Upload & settings";font:600 14px/1 Inter,sans-serif;color:#fff;white-space:nowrap}
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
.pf-sbnote{font-size:13px;color:#55555f;line-height:1.5;margin-top:8px}
[data-testid="stBaseButton-primary"]{font-weight:600!important}
[data-testid="stBaseButton-secondary"],[data-testid="stDownloadButton"] button{font-weight:600!important;background:#fff!important}
[data-testid="stFileUploaderDropzone"]{background:#fafaf8;border-radius:12px}
.stTabs [data-baseweb="tab-list"]{gap:4px;border-bottom:1px solid #e3e3de}
.stTabs [data-baseweb="tab"]{font-size:15px;font-weight:600;padding:12px 14px;height:auto}
.pf-intro{max-width:760px}
.pf-intro p{font-size:17px;color:var(--ink2);margin:12px 0 0}
.pf-intro ol{margin:10px 0 0 20px!important;padding:0!important}.pf-intro ol li{margin:0 0 6px!important;font-size:16px;color:var(--ink2)}
.pf-wallet{border:1px solid #e3e3de;border-radius:14px;padding:16px;background:#fafaf8;margin:10px 0}
.pf-wallet .label{font-size:12px;color:#65656e;line-height:1.4}
.pf-wallet .balance{font:650 26px/1.3 Inter,sans-serif;color:#121216;margin:5px 0}
.pf-wallet .cost{display:flex;justify-content:space-between;gap:12px;font-size:13px;margin:14px 0 8px;padding-top:12px;border-top:1px solid #e3e3de}
.pf-wallet .foot{font-size:12px;color:#65656e;line-height:1.5}
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
if st.session_state.get("usage_scope") != config.scope:
    st.session_state.usage_scope = config.scope
    st.session_state.usage_ledger = UsageLedger()
ledger: UsageLedger = st.session_state.usage_ledger


def wallet_html() -> str:
    if ledger.last_error_code == 402:
        label, balance = "Credit status", "Out of credits"
        note = "Sarvam rejected the last request for insufficient credits. Check the account balance."
    elif ledger.snapshot_balance is None:
        label, balance = "Account balance", "View in Sarvam"
        note = "Save a balance snapshot below to estimate credits left."
    elif ledger.remaining is None:
        label, balance = "Estimated credits left", "Update snapshot"
        note = "Some requests did not report usage. Check Sarvam and save a fresh balance."
    else:
        label, balance = "Estimated credits left", f"₹{ledger.remaining:.4f}"
        note = "From your saved balance, minus reported spend in this session."
    extra = " Some requests did not report usage." if ledger.unreported else ""
    return (f'<div class="pf-wallet"><div class="label">{label}</div><div class="balance">{balance}</div>'
            f'<div class="foot">{note}</div><div class="cost"><span>Estimated session spend</span>'
            f'<b>₹{ledger.spend:.4f}</b></div><div class="foot">'
            f'{ledger.total("calls")} API requests · '
            f'{ledger.total("prompt_tokens") + ledger.total("completion_tokens"):,} reported tokens<br>'
            f'Estimates exclude tax and activity outside this browser session.{extra}</div></div>')


@st.cache_resource(show_spinner=False)
def demo_result():
    return run(load_path(DEMO), "The Maid Was the Heiress") if DEMO.exists() else None


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
        st.html('<div class="pf-service"><span class="dot"></span><b>Sarvam AI enabled</b><br>'
                '<span style="font-size:12px;color:#65656e">Reviews hooks, cliffhangers and new-viewer clarity.</span></div>')
    else:
        st.info(config.error or "AI is not connected. Ask the app owner to connect Sarvam.")
        with st.expander("App owner setup"):
            st.caption('In Streamlit Settings → Secrets, add SARVAM_API_KEY. Existing Sarvam '
                       'LLM_API_KEY / LLM_BASE_URL settings are also supported. Never publish the key.')
    go = st.button("Find promos with AI", type="primary", width="stretch", disabled=not files or not config.configured)
    st.html('<div class="pf-sbh" style="margin-top:24px">Credits & usage</div>')
    credits_panel = st.empty()
    credits_panel.html(wallet_html())
    st.link_button("View actual balance in Sarvam ↗", BILLING_URL, width="stretch")
    with st.expander("Update balance snapshot"):
        st.caption("Open Sarvam → Settings → Billing, then enter its current balance here. "
                   "This creates a session estimate, not a live account balance.")
        with st.form("balance_snapshot"):
            snapshot = st.number_input("Balance shown in Sarvam (₹)", min_value=0.0, value=None,
                                       step=1.0, format="%.2f", placeholder="Enter your current balance")
            save_snapshot = st.form_submit_button("Save balance snapshot", width="stretch")
        if save_snapshot:
            if snapshot is None:
                st.warning("Enter the balance shown in Sarvam first.")
            else:
                ledger.set_snapshot(snapshot)
                credits_panel.html(wallet_html())
                st.success("Balance snapshot saved for this session.")
        if ledger.snapshot_at:
            stamp = datetime.fromisoformat(ledger.snapshot_at).astimezone(ZoneInfo("Asia/Kolkata"))
            st.caption(f"Snapshot saved {stamp:%d %b, %H:%M} IST. Resets when this browser session ends.")
    with st.expander("Output preferences"):
        n_single = st.slider("Single-clip promos", 5, 40, 20)
        n_stitched = st.slider("Stitched promos", 0, 12, 6)
        llm_top = st.slider("AI review depth", 10, 80, 40,
                            help="Maximum single-clip candidates reviewed by AI. Higher depth may use more credits.")
        compare_too = st.checkbox("Include baseline comparison", value=True)
    st.write("")
    demo = st.button("Preview sample report", width="stretch",
                     help="Fictional scripts, ranked offline. Uses no API credits.")
    st.html('<p class="pf-sbnote">Scripts are processed in memory. Nothing is saved on the server, '
            'and AI replies are not cached in the app.</p>')

preview_sample = (demo or st.session_state.pop("demo_req", False)) and DEMO.exists()
if preview_sample:
    class _Demo:  # make the demo look like an uploaded file
        name = DEMO.name

        def getvalue(self):
            return DEMO.read_bytes()
    files, go, title = [_Demo()], True, "The Maid Was the Heiress"

# ---------------------------------------------------------------- first visit
if "result" not in st.session_state and not go:
    d = demo_result()
    example = ui.card(d.promos[0]) if d and d.promos else ""
    st.html(f"""<div class="pf"><div class="pf-intro"><div class="pf-label accent">Promo Finder</div>
<h1 class="pf-h2" style="font-size:32px;margin-top:8px">Find promo cuts in a season of scripts</h1>
<p>Upload the episode screenplays and get a ranked list of 20–60 second promo cuts. Each one comes with the exact
timestamps to cut, the line it opens on, the moment it ends on, and a note on anything an editor should check.</p>
<ol><li>Upload a <b>.zip</b> of the episode scripts in the sidebar (on a phone, tap <b>Upload &amp; settings</b> at the top).</li>
<li>Check the show title (it's read from the zip).</li>
<li>Press <b>Find promos with AI</b>. Watch each review and its estimated spend as it runs.</li></ol>
<p style="font-size:15px;color:var(--mute)">Explore a sample report using fictional scripts. No API credits are used:</p></div></div>""")
    st.button("Preview sample report", key="demo_main", type="primary", on_click=lambda: st.session_state.update(demo_req=True))
    st.html(f'<div class="pf"><p style="font-size:15px;color:var(--mute);margin:4px 0 12px">Sample output · fictional scripts · offline preview:</p>{example}</div>')
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
    judge = None
    if not preview_sample:
        if not config.configured:
            st.error("AI is not connected. Ask the app owner to connect Sarvam before running a review.")
            st.stop()
        try:
            judge = Judge(f"sarvam:{config.model}", api_key=config.api_key,
                          base_url=config.base_url, use_cache=False)
        except (ValueError, TypeError):
            st.error("The AI reviewer could not start. If the app was just updated, use Manage app → "
                     "Reboot app to finish loading the update. Otherwise ask the app owner to check its configuration.")
            st.stop()
        ok, why_not = judge.ready()
        if not ok:
            st.warning(f"AI judge not used ({why_not}). Ranking with rules only.")
    else:
        compare_too = False
    run_id = uuid4().hex

    def show_progress(message: str) -> None:
        st.write(message)
        if judge:
            ledger.record(run_id, judge.stats)
            credits_panel.html(wallet_html())

    with st.status("Finding promos…", expanded=True) as status:
        try:
            if judge and compare_too:
                rules_res, res, cmp = compare(eps, title or "Untitled show", judge, llm_top, progress=show_progress,
                                               n_single=n_single, n_stitched=n_stitched)
                st.session_state.compare = (rules_res, cmp)
            else:
                res = run(eps, title or "Untitled show", judge or "rules", n_single, n_stitched, llm_top,
                          progress=show_progress, warnings=warnings)
                st.session_state.pop("compare", None)
        except Exception as e:  # show a clear message instead of a stack trace
            status.update(label="Run failed", state="error")
            detail = str(e).replace(config.api_key, "[redacted]") if config.api_key else str(e)
            st.error(f"Something went wrong while ranking: {type(e).__name__}: {detail}")
            st.stop()
        finally:
            if judge:
                ledger.record(run_id, judge.stats)
                credits_panel.html(wallet_html())
        status.update(label=f"Done: {len(res.promos)} promos in {res.stats['seconds']} s", state="complete", expanded=False)
    if res.stats.get("ai", {}).get("last_error_code") == 402:
        st.warning("Sarvam reported that the account is out of credits. Open Sarvam Billing to check the balance. "
                   "This report uses the automatic backup ranking.")
    elif judge and res.model == "rules" and res.stats.get("ai", {}).get("calls"):
        st.warning("AI review returned no usable ratings. This report uses rules only; see Checks → Run log.")
    elif res.stats.get("ai", {}).get("failed"):
        st.warning("Some AI reviews failed. Those candidates kept their rules scores; see Checks → Run log.")
    st.session_state.result = res
    st.session_state.checks = run_checks(res)
    st.session_state.sample_preview = bool(preview_sample)

res = st.session_state.result
checks = st.session_state.get("checks") or run_checks(res)
s = res.stats

if st.session_state.get("sample_preview"):
    st.info("Sample report · fictional scripts · offline preview. No AI call or credit usage.")

st.html(f"""<div class="pf"><div class="pf-label accent">Promo report</div>
<h1 class="pf-h2" style="font-size:28px;margin:4px 0 10px">{ui.e(res.title)}</h1>
<div style="margin-bottom:8px">{ui.mode_badge(res.model, s.get("ai"))}</div>{ui.run_summary(s, checks)}</div>""")
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
