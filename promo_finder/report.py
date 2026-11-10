"""Writers: JSON (machine), CSV (spreadsheet), Markdown (quick read), HTML (visual report), PDF (print/share)."""
from __future__ import annotations

import csv
import html
import io
import json
from pathlib import Path

from .candidates import Promo
from .parser import fmt, speaker_name
from .pipeline import Result
from . import ui


tier = ui.tier


def _beat_dict(b, seg_start: float, offset: float) -> dict:
    return {"episode": b.ep, "timestamp": fmt(b.start), "at_s": round(offset + b.start - seg_start, 1),
            "type": b.kind, "speaker": speaker_name(b.speaker) if b.speaker else "", "text": b.text}


def promo_dict(p: Promo) -> dict:
    segs, transcript, off = [], [], 0.0
    hook = cliff = None
    for s in p.segments:
        segs.append({"episode": s.ep, "start": fmt(s.start), "end": fmt(s.end),
                     "start_s": round(s.start, 2), "end_s": round(s.end, 2), "duration_s": round(s.dur, 1)})
        for b in s.beats:
            if b.kind != "camera":
                transcript.append(_beat_dict(b, s.start, off))
            if b is p.hook_beat:
                hook = _beat_dict(b, s.start, off)
            if b is p.cliff_beat:
                cliff = _beat_dict(b, s.start, off)
        off += s.dur
    return {
        "id": p.id, "rank": p.rank or None, "kind": p.kind, "tier": tier(p),
        "duration_s": p.duration, "episodes": p.episodes, "segments": segs,
        "hook": hook, "cliffhanger": cliff, "why_it_works": p.why, "post_reason": p.post_reason,
        "tropes": p.tropes, "flags": p.flags,
        "scores": {k: round(v, 3) for k, v in p.scores.items()}, "ai_judge": p.llm, "transcript": transcript,
    }


def to_json(r: Result) -> str:
    return json.dumps({
        "show": r.title, "model": r.model, "stats": r.stats, "premise_tropes": sorted(r.premise),
        "ranked_promos": [promo_dict(p) for p in r.promos],
        "best_promo_per_episode": [promo_dict(p) for p in r.by_episode],
        "episodes_without_a_promo": sorted({e.num for e in r.episodes} - {p.episodes[0] for p in r.by_episode}),
        "log": r.log,
    }, indent=2, ensure_ascii=False)


CSV_COLS = ["rank", "id", "kind", "tier", "episodes", "segments", "duration_s", "hook_at_s", "hook",
            "cliffhanger", "why_it_works", "post_reason", "total", "hook_score", "cliff_score", "body",
            "standalone", "flags"]


def _row(p: Promo) -> dict:
    d = promo_dict(p)
    q = lambda b: f'{b["speaker"] or b["type"].upper()}: {b["text"]}' if b else ""  # noqa: E731
    return {"rank": p.rank or "", "id": p.id, "kind": p.kind, "tier": d["tier"],
            "episodes": " ".join(map(str, p.episodes)),
            "segments": "; ".join(f'Ep {s["episode"]} {s["start"]}-{s["end"]}' for s in d["segments"]),
            "duration_s": p.duration, "hook_at_s": p.hook_at, "hook": q(d["hook"]), "cliffhanger": q(d["cliffhanger"]),
            "why_it_works": p.why, "post_reason": p.post_reason, "total": p.scores["total"],
            "hook_score": p.scores["hook"], "cliff_score": p.scores["cliff"], "body": p.scores["body"],
            "standalone": p.scores["standalone"], "flags": " | ".join(p.flags)}


def to_csv(promos: list[Promo]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLS)
    w.writeheader()
    for p in promos:
        w.writerow(_row(p))
    return buf.getvalue()


def to_markdown(r: Result) -> str:
    s = r.stats
    out = [f"# Promo Finder — {r.title}", "",
           f"Model: `{r.model}` · {s['episodes']} episodes · {s['minutes']} min · "
           f"{s['candidates']:,} candidates scored · {s['promos']} promos ranked · {s['seconds']} s", ""]
    out += ["## Ranked promos (post in this order)", ""]
    for p in r.promos:
        d = promo_dict(p)
        out += [f"### {p.rank}. {p.id} · {p.kind} · tier {d['tier']} · {p.duration:.1f}s",
                "", "Segments: " + " + ".join(f"**Ep {x['episode']}** `{x['start']} → {x['end']}`" for x in d["segments"]),
                f"- **Hook ({p.hook_at:.1f}s):** {p.hook_beat.short(160)}",
                f"- **Cliffhanger:** {p.cliff_beat.short(160)}",
                f"- **Why it works:** {p.why}",
                f"- **Why post it now:** {p.post_reason}"]
        if p.flags:
            out.append(f"- **Check:** {'; '.join(p.flags)}")
        out.append("")
    out += ["## Best single clip in every episode", "",
            "| Ep | Clip | Len | Tier | Hook | Cliffhanger |", "|---|---|---|---|---|---|"]
    for p in r.by_episode:
        sg = p.segments[0]
        out.append(f"| {sg.ep} | `{fmt(sg.start)}–{fmt(sg.end)}` | {p.duration:.0f}s | {tier(p)} | "
                   f"{p.hook_beat.short(60).replace('|', '/')} | {p.cliff_beat.short(60).replace('|', '/')} |")
    missing = sorted({e.num for e in r.episodes} - {p.episodes[0] for p in r.by_episode})
    if missing:
        out += ["", f"No qualifying promo found in: Ep {', '.join(map(str, missing))}"]
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------- PDF
FONT_DIR = Path(__file__).resolve().parent.parent / "static" / "fonts"
_RED, _INK, _MUTE, _LINE, _AMBER = (225, 29, 38), (26, 26, 28), (91, 91, 99), (236, 228, 229), (138, 90, 0)


def to_pdf(r: Result) -> bytes:
    """Printable report for producers and reviewers: same content as the Markdown summary."""
    from fpdf import FPDF  # local import: only needed when a PDF is requested

    regular, bold = FONT_DIR / "DejaVuSans.ttf", FONT_DIR / "DejaVuSans-Bold.ttf"
    unicode_ok = regular.exists() and bold.exists()

    def t(text) -> str:
        text = str(text)
        return text if unicode_ok else text.encode("latin-1", "replace").decode("latin-1")

    class _PDF(FPDF):
        def footer(self):
            self.set_y(-12)
            self.set_font(fam, "", 8)
            self.set_text_color(*_MUTE)
            self.cell(0, 6, t(f"Promo Finder · {r.title}"), align="L")
            self.set_x(self.l_margin)
            self.cell(0, 6, f"Page {self.page_no()}/{{nb}}", align="R")

    pdf = _PDF(format="A4")
    if unicode_ok:
        pdf.add_font("DejaVu", "", str(regular))
        pdf.add_font("DejaVu", "B", str(bold))
        fam = "DejaVu"
    else:
        fam = "Helvetica"
    pdf.set_margins(16, 16, 16)
    pdf.set_auto_page_break(True, margin=18)
    pdf.set_title(t(f"Promo report: {r.title}"))
    pdf.set_author("Promo Finder")
    pdf.add_page()

    def label(text: str, color=_RED) -> None:
        pdf.set_font(fam, "B", 8.5)
        pdf.set_text_color(*color)
        pdf.cell(0, 5, t(text.upper()), new_x="LMARGIN", new_y="NEXT")

    def field(doc, name: str, value: str, color=_INK) -> None:
        doc.set_font(fam, "B", 9.5)
        doc.set_text_color(*color)
        doc.write(5.2, t(f"{name}  "))
        doc.set_font(fam, "", 9.5)
        doc.write(5.2, t(value))
        doc.ln(6.4)

    def rule(target=None) -> None:
        target = target or pdf
        target.set_draw_color(*_LINE)
        target.cell(0, 0, "", border="T", new_x="LMARGIN", new_y="NEXT")

    # Header
    s = r.stats
    label("Promo report")
    pdf.set_font(fam, "B", 22)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(0, 10, t(r.title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(fam, "", 10)
    pdf.set_text_color(*_MUTE)
    pdf.multi_cell(0, 5.5, t(f"{s['episodes']} episodes · {s['minutes']} min of script · "
                             f"{s['candidates']:,} possible cuts scored · {s['promos']} promos ranked"),
                   new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    rule()
    pdf.ln(6)

    # Ranked promos
    label("Ranked promos · post in this order")
    pdf.ln(2)
    if not r.promos:
        pdf.set_font(fam, "", 10)
        pdf.set_text_color(*_MUTE)
        pdf.multi_cell(0, 5.5, t("No promo passed the rules for these scripts."), new_x="LMARGIN", new_y="NEXT")
    for p in r.promos:
        d = promo_dict(p)
        kind = "Single clip" if p.kind == "single" else "Stitched"
        cuts = "  +  ".join(f"Ep {x['episode']}  {x['start']} → {x['end']}" for x in d["segments"])
        with pdf.unbreakable() as doc:
            doc.set_font(fam, "B", 12.5)
            doc.set_text_color(*_RED)
            doc.cell(10, 7, t(f"{p.rank}."))
            doc.set_text_color(*_INK)
            doc.cell(0, 7, t(f"{kind} · Tier {d['tier']} · {p.duration:.0f} s · Score {ui.score100(p)}"),
                     new_x="LMARGIN", new_y="NEXT")
            doc.ln(1)
            field(doc, "Cut points", cuts)
            field(doc, f"Hook ({p.hook_at:.1f} s)", p.hook_beat.short(160))
            field(doc, "Cliffhanger", p.cliff_beat.short(160))
            field(doc, "Why it works", p.why)
            field(doc, "Why post it now", p.post_reason)
            if p.flags:
                field(doc, "Check", "; ".join(p.flags), color=_AMBER)
            doc.ln(2)
            rule(doc)
            doc.ln(5)

    # Best clip per episode
    if r.by_episode:
        pdf.ln(2)
        with pdf.unbreakable() as doc:
            label("Best single clip in every episode")
            doc.ln(2)
        from fpdf.fonts import FontFace

        pdf.set_font(fam, "", 8.5)
        pdf.set_text_color(*_INK)
        pdf.set_draw_color(*_LINE)
        with pdf.table(col_widths=(8, 24, 10, 9, 49.5, 49.5), text_align="LEFT", line_height=4.6,
                       headings_style=FontFace(emphasis="BOLD", color=_INK, fill_color=(253, 235, 236)),
                       borders_layout="HORIZONTAL_LINES", padding=1.6) as table:
            row = table.row()
            for h in ("Ep", "Clip", "Len", "Tier", "Hook", "Cliffhanger"):
                row.cell(t(h))
            for p in r.by_episode:
                sg = p.segments[0]
                row = table.row()
                for v in (sg.ep, f"{fmt(sg.start)}–{fmt(sg.end)}", f"{p.duration:.0f}s", tier(p),
                          p.hook_beat.short(80), p.cliff_beat.short(80)):
                    row.cell(t(v))
    missing = sorted({e.num for e in r.episodes} - {p.episodes[0] for p in r.by_episode})
    if missing:
        pdf.ln(3)
        pdf.set_font(fam, "", 9)
        pdf.set_text_color(*_MUTE)
        pdf.multi_cell(0, 5, t(f"No qualifying promo found in: Ep {', '.join(map(str, missing))}"),
                       new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


# ----------------------------------------------------------------- HTML
REPORT_CSS = """
html{scroll-behavior:smooth}
body.pf{margin:0;background:var(--bg);min-height:100vh}
.pf-wrap{max-width:1180px;margin:0 auto;padding:0 28px 96px}
.pf-nav{position:sticky;top:0;z-index:30;background:color-mix(in srgb,var(--bg) 88%,transparent);
backdrop-filter:saturate(1.4) blur(12px);-webkit-backdrop-filter:saturate(1.4) blur(12px);border-bottom:1px solid var(--line)}
.pf-nav .in{max-width:1180px;margin:0 auto;padding:12px 28px;display:flex;align-items:center;gap:20px}
.pf-nav .show{color:var(--mute);font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:300px;
border-left:1px solid var(--line2);padding-left:16px}
.pf-nav .links{display:flex;gap:22px;margin-left:auto}
.pf-nav .links a{color:var(--mute);text-decoration:none;font-size:14px;font-weight:500}
.pf-nav .links a:hover{color:var(--ink)}
.pf-btn{cursor:pointer;border:1px solid var(--line2);background:var(--surface);color:var(--ink2);border-radius:8px;padding:7px 12px;
font:600 13px var(--sans);display:inline-flex;align-items:center;gap:8px}
.pf-btn:hover{border-color:var(--ink2);color:var(--ink)}
.pf-moon{display:inline-block;width:12px;height:12px;border-radius:50%;background:linear-gradient(90deg,currentColor 50%,transparent 50%);
box-shadow:inset 0 0 0 1.5px currentColor}
.pf-hero{padding:56px 0 0}
.pf-hero .pf-sub{font-size:18px;margin:14px 0 28px}
.pf-filters{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:16px}
.pf-chip{cursor:pointer;font:600 14px var(--sans);padding:8px 14px;border-radius:8px;border:1px solid var(--line2);background:var(--surface);color:var(--ink2)}
.pf-chip:hover{border-color:var(--ink2)}
.pf-chip.on{background:var(--ink);color:var(--surface);border-color:var(--ink)}
.pf-count{color:var(--mute);font-size:14px;margin-left:6px}
.pf-copy{cursor:pointer;align-self:flex-start;border:1px solid var(--line2);background:var(--surface);color:var(--ink2);border-radius:8px;
padding:6px 10px;font:600 13px var(--sans)}
.pf-copy:hover{border-color:var(--ink2);color:var(--ink)}
.pf-morelib>summary{cursor:pointer;list-style:none;margin-top:16px;display:inline-flex}
.pf-morelib>summary::-webkit-details-marker{display:none}
.pf-foot{margin-top:72px;padding-top:24px;border-top:1px solid var(--line);display:flex;justify-content:space-between;gap:16px;
flex-wrap:wrap;color:var(--mute);font-size:14px}
@media (max-width:860px){.pf-nav .links,.pf-nav .show{display:none}.pf-btn{margin-left:auto}.pf-wrap{padding:0 16px 72px}
.pf-nav .in{padding:12px 16px}.pf-hero{padding-top:32px}}
@media print{.pf-nav,.pf-filters,.pf-copy{display:none}.pf-row{break-inside:avoid}}
"""

REPORT_JS = """
(function(){
  var b=document.body;
  try{var saved=localStorage.getItem('pf-theme'); if(saved){b.dataset.theme=saved;}}catch(e){}
  var tb=document.getElementById('pf-theme');
  if(tb){tb.addEventListener('click',function(){b.dataset.theme=b.dataset.theme==='dark'?'light':'dark';
    try{localStorage.setItem('pf-theme',b.dataset.theme)}catch(e){}});}
  var chips=[].slice.call(document.querySelectorAll('[data-filter]'));
  function apply(f){var n=0;[].slice.call(document.querySelectorAll('#promos .pf-crow')).forEach(function(c){
    var ok=f==='all'||(f==='single'&&c.dataset.kind==='single')||(f==='stitched'&&c.dataset.kind==='stitched')||
      (f==='A'&&c.dataset.tier==='A')||(f==='clean'&&c.dataset.flag==='0');
    c.style.display=ok?'':'none'; if(ok)n++;});
    var el=document.getElementById('pf-count'); if(el) el.textContent=n+(n===1?' promo':' promos');}
  chips.forEach(function(c){c.addEventListener('click',function(){chips.forEach(function(x){x.classList.remove('on')});
    c.classList.add('on'); apply(c.dataset.filter);});});
  [].slice.call(document.querySelectorAll('.pf-crow[data-cut]')).forEach(function(row){
    var side=row.querySelector('.cr-actions'); if(!side) return;
    var btn=document.createElement('button'); btn.className='pf-copy'; btn.type='button'; btn.textContent='Copy cut points';
    btn.addEventListener('click',function(){var t=row.dataset.cut;
      function done(){btn.textContent='Copied'; setTimeout(function(){btn.textContent='Copy cut points'},1500);}
      if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(done,done);}else{done();}});
    side.appendChild(btn);});
})();
"""


def _section(anchor: str, label: str, title: str, sub: str, body: str) -> str:
    return (f'<section class="pf-section" id="{anchor}"><div class="pf-section-head"><div class="pf-label accent">{label}</div>'
            f'<h2 class="pf-h2">{title}</h2>{f"<p class=pf-sub>{sub}</p>" if sub else ""}</div>{body}</section>')


def to_html(r: Result, theme: str | None = None, embed: bool = False) -> str:
    """Standalone visual report. Light by default; theme='dark' starts dark; embed=True drops the nav and header."""
    from .checks import run_checks
    s = r.stats
    ranked_ids = {p.id for p in r.promos}
    top = r.promos[0] if r.promos else None
    checks = run_checks(r)
    badge, summary = ui.mode_badge(r.model, s.get("ai")), ui.run_summary(s, checks)
    nav = "" if embed else f"""<nav class="pf-nav"><div class="in">{ui.logo()}<span class="show">{ui.e(r.title)}</span>
<div class="links"><a href="#spotlight">Top pick</a><a href="#promos">Promos</a><a href="#map">Season map</a><a href="#library">Episodes</a><a href="#checks">Checks</a></div>
<button class="pf-btn" id="pf-theme" type="button" title="Switch light / dark"><span class="pf-moon"></span>Theme</button></div></nav>"""
    hero = "" if embed else f"""<header class="pf-hero"><div class="pf-label accent">Promo report</div>
<h1 class="pf-h1" style="margin-top:10px">{ui.e(r.title)}</h1>
<p class="pf-sub">Promo cuts found by reading the episode scripts. Each one opens on a hook within 3 seconds and ends on
an unresolved moment. Timestamps are copied from the scripts, so they can go straight into the edit.</p>
<div style="margin-bottom:14px">{badge}</div>{summary}</header>"""
    spot = _section("spotlight", "Top pick", "Post this one first",
                    "The highest-ranked promo, shown the way it would play in the feed.", ui.spotlight(top, eyebrow=f"Ranked #1 of {len(r.promos)}")) if top else ""
    filters = ('<div class="pf-filters"><button class="pf-chip on" data-filter="all">All</button><button class="pf-chip" data-filter="single">Single clips</button>'
               '<button class="pf-chip" data-filter="stitched">Stitched</button><button class="pf-chip" data-filter="A">Tier A only</button>'
               '<button class="pf-chip" data-filter="clean">Nothing to check</button>'
               f'<span class="pf-count" id="pf-count">{len(r.promos)} promos</span></div>')
    rows = ui.compact_list(r.promos)
    lib_extra = [p for p in r.by_episode if p.id not in ranked_ids]
    lib_rows = ui.compact_list(lib_extra)
    missing = sorted({e.num for e in r.episodes} - {p.episodes[0] for p in r.by_episode})
    miss = f" No clip met the rules in Ep {', '.join(map(str, missing))}." if missing else ""
    method = "".join(f'<div class="pf-step"><span class="n">{n}</span><b>{t}</b><p>{d}</p><span class="tag pf-badge">{tag}</span></div>' for n, t, d, tag in [
        ("1", "Read", "Every scene, line, action and sound cue is parsed with its timestamp, including delivery tags like “(Furious, Shouting)”.", "Code"),
        ("2", "Score", "Each moment gets a hook, cliffhanger, intensity and needs-backstory score from an editable word list.", "Rules"),
        ("3", "Cut", "Every hook × cliffhanger pair that obeys the rules is tried: 20–60 s, hook within 3 s, cuts on shot boundaries.", "Code"),
        ("4", "Rank", "The best non-overlapping cuts are ordered for posting, with early episodes first and no back-to-back repeats.", "Code + optional AI"),
    ])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{ui.e(r.title)} · Promo report</title><meta name="color-scheme" content="light dark">{ui.css('embed')}<style>{REPORT_CSS}</style></head>
<body class="pf" data-theme="{theme or 'light'}">{nav}<main class="pf-wrap">{hero}{spot}
{_section("promos", "Ranked list", f"All {len(r.promos)} promos, in the order to post them",
          "Best first, with a small boost for early episodes because that's where a new viewer who taps lands. Late reveals are flagged as spoilers. Click a row for the score breakdown, what to check and the full cut.",
          filters + rows)}
{_section("map", "Season map", "Where the promos come from",
          f"All {len(r.episodes)} episodes side by side. Click a block to jump to that promo.", ui.season_map(r.episodes, r.promos, r.by_episode))}
{_section("library", "Every episode", "The best clip in each episode",
          f"A menu for the editor, including episodes that didn't make the ranked list. Tier C means probably skip.{miss}",
          ui.episode_index(r.episodes, r.by_episode) + ui.library_table(r.by_episode, ranked_ids) +
          f'<details class="pf-morelib"><summary><span class="pf-chip">Show the {len(lib_extra)} clips that are not in the ranked list</span></summary>'
          f'<div style="margin-top:16px">{lib_rows}</div></details>')}
{_section("checks", "Quality", "Checked against the script", "", ui.checks_panel(checks))}
{_section("method", "Method", "How a promo gets picked", "", f'<div class="pf-steps">{method}</div>')}
<footer class="pf-foot"><span>{ui.logo()}</span><span>Made from screenplay text only; no footage was watched. Ranking mode: {ui.e(r.model)} · run time {s['seconds']} s.</span></footer>
</main><script>{REPORT_JS}</script></body></html>"""


def write_all(r: Result, out_dir: str | Path) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = {
        "json": out / "promos.json", "csv": out / "promos_ranked.csv", "lib": out / "promos_by_episode.csv",
        "all": out / "all_candidates.csv", "md": out / "promos.md", "html": out / "promo_report.html",
        "log": out / "run_log.txt", "checks": out / "quality_checks.md",
    }
    files["json"].write_text(to_json(r), encoding="utf-8")
    files["csv"].write_text(to_csv(r.promos), encoding="utf-8")
    files["lib"].write_text(to_csv(r.by_episode), encoding="utf-8")
    # every single-clip candidate + the 300 best stitched ones (all ~13k stitched combos would be noise)
    singles = [p for p in r.candidates if p.kind == "single"]
    stitched = sorted((p for p in r.candidates if p.kind == "stitched"), key=lambda p: -p.scores["total"])[:300]
    files["all"].write_text(to_csv(sorted(singles + stitched, key=lambda p: -p.scores["total"])), encoding="utf-8")
    files["md"].write_text(to_markdown(r), encoding="utf-8")
    files["html"].write_text(to_html(r), encoding="utf-8")
    from .checks import checks_markdown, run_checks
    files["checks"].write_text(checks_markdown(run_checks(r)), encoding="utf-8")
    files["log"].write_text("\n".join(r.log) + "\n" + json.dumps(r.stats, indent=2) + "\n", encoding="utf-8")
    return files
