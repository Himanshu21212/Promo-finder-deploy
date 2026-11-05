"""Build the 2-page solution PDF from docs/solution_doc.html.

    python docs/build_pdf.py

Every number in the doc comes from the run outputs, so the PDF can't drift from them:
  outputs/promos.json        promo counts, run time, cut points
  outputs/quality_checks.md  the hard-rule re-check
  outputs/test_results.txt   pytest -v output
  outputs/benchmark.txt      tools/bench.py output
  outputs/ai_prompt_size.txt tools/measure_prompt.py output
  evaluation/spot_check_top16.md  the script read of the top 16
Elements marked data-rank + data-cut are checked against promos.json; the build stops on a mismatch.
Links come from docs/links.json. Empty links are left out (never a placeholder).
Needs: pip install playwright && python -m playwright install chromium
"""
from __future__ import annotations

import html as H
import json
import re
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parent
sys.path.insert(0, str(root))
from promo_finder.ui import font_faces  # noqa: E402

out, ev = root / "outputs", root / "evaluation"


def die(msg: str):
    sys.exit(f"build_pdf: {msg}")


def cut_text(p: dict) -> str:
    return " + ".join(f"Ep {s['episode']} {s['start']}–{s['end']}" for s in p["segments"])


data = json.loads((out / "promos.json").read_text(encoding="utf-8"))
s, ranked = data["stats"], data["ranked_promos"]
if data["model"] != "rules":
    die(f"outputs/ were made in '{data['model']}' mode, but the doc says the results are rules-only")

m = re.search(r"\*\*(\d+) / (\d+) promos pass", (out / "quality_checks.md").read_text(encoding="utf-8"))
if not m:
    die("can't find the pass count in outputs/quality_checks.md")
passed, checked = m.groups()

m = re.search(r"(\d+) passed", (out / "test_results.txt").read_text(encoding="utf-8"))
if not m or re.search(r"\d+ failed", (out / "test_results.txt").read_text(encoding="utf-8")):
    die("outputs/test_results.txt is missing or has failures")
tests = m.group(1)

bench = re.findall(r"(\d+) episodes: ([\d.]+) s", (out / "benchmark.txt").read_text(encoding="utf-8"))
bench_txt = ", ".join(f"{n} episodes in {t} s" for n, t in bench if n != "50")
m = re.search(r"estimated input tokens: (\d+) total", (out / "ai_prompt_size.txt").read_text(encoding="utf-8"))
prompt_k = round(int(m.group(1)) / 1000) if m else die("can't read outputs/ai_prompt_size.txt")

spot = (ev / "spot_check_top16.md").read_text(encoding="utf-8")
rows = re.findall(r"^\| (\d+) \|[^|]*\| (✅|⚠️|❌) \|", spot, flags=re.M)
if len(rows) != 16:
    die(f"expected 16 rows in the spot check, found {len(rows)}")
tally = {v: sum(r[1] == v for r in rows) for v in ("✅", "⚠️", "❌")}
claim = re.search(r"Tally: (\d+) of 16 look postable as they are, (\d+) need a small fix, (\d+) is a reject", spot)
if not claim or tuple(map(int, claim.groups())) != (tally["✅"], tally["⚠️"], tally["❌"]):
    die("the tally sentence in the spot check doesn't match its table")

def short_link(url: str) -> str:
    """Readable link text that keeps the links row on one line."""
    host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
    path = re.sub(r"^https?://[^/]+/?", "", url).split("?")[0].rstrip("/")
    if host == "github.com":
        return path
    if host in ("drive.google.com", "docs.google.com"):
        return "Google Drive"
    if host in ("youtu.be", "youtube.com", "loom.com"):
        return host
    return host


links = json.loads((here / "links.json").read_text(encoding="utf-8"))
shown = [(k, v.strip()) for k, v in links.items() if v.strip()]
missing = [k for k, v in links.items() if not v.strip()]
links_html = ('<div class="links">' + "".join(
    f'<a href="{H.escape(v)}"><b>{H.escape(k)}</b> {H.escape(short_link(v))}</a>'
    for k, v in shown) + "</div>") if shown else ""

fill = {
    "promos": len(ranked), "covered": s["episodes_covered"], "library": s["library"], "episodes": s["episodes"],
    "seconds": s["seconds"], "minutes": s["minutes"], "beats": f"{s['beats']:,}",
    "beats_avg": round(s["beats"] / s["episodes"]), "candidates": f"{s['candidates']:,}",
    "passed": passed, "checked": checked, "tests": tests, "bench": bench_txt, "prompt_k": prompt_k,
    "spot_ok": tally["✅"], "spot_fix": tally["⚠️"], "spot_bad": tally["❌"],
    "no_clip": ", ".join(map(str, data["episodes_without_a_promo"])) or "none", "links": links_html,
}
doc = (here / "solution_doc.html").read_text(encoding="utf-8")
doc = re.sub(r"\{\{(\w+)\}\}", lambda mm: str(fill[mm.group(1)]) if mm.group(1) in fill else die(f"unknown {{{{{mm.group(1)}}}}}"), doc)

by_rank = {p["rank"]: p for p in ranked}
for rank, cut in re.findall(r'data-rank="(\d+)" data-cut="([^"]+)"', doc):
    p = by_rank.get(int(rank))
    if not p or cut_text(p) != cut:
        die(f"the doc says #{rank} is '{cut}', but promos.json has '{cut_text(p) if p else 'nothing'}'")
if re.search(r"‹|placeholder|TODO|\{\{", doc):
    die("placeholder text left in the doc")

html = doc.replace("</head>", f"<style>{font_faces('embed')}</style></head>", 1)
from playwright.sync_api import sync_playwright  # noqa: E402

pdf = here / "Promo_Finder_Solution_Doc.pdf"
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page()
    pg.set_content(html, wait_until="load")
    pg.wait_for_timeout(300)
    over = pg.evaluate("""[...document.querySelectorAll('.page')].map((p, i) => {
        const r = p.getBoundingClientRect(); const foot = p.querySelector('.foot').getBoundingClientRect();
        const last = [...p.children].filter(c => !c.classList.contains('foot')).pop().getBoundingClientRect();
        return last.bottom > foot.top - 4 ? `page ${i + 1} overflows by ${Math.round(last.bottom - foot.top + 4)} px` : '' })""")
    if any(over):
        die("; ".join(o for o in over if o))
    pg.pdf(path=str(pdf), format="A4", print_background=True, margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
    b.close()
print(f"wrote {pdf}")
if missing:
    print(f"note: no link yet for {', '.join(missing)} (left out of the PDF). Add them to docs/links.json and rebuild.")
