"""Command line:  python -m promo_finder <scripts folder | .zip | .txt> [options]"""
from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

from .llm import Judge
from .parser import load_path
from .pipeline import run
from .report import write_all


def guess_title(path: str) -> str:
    """Show title from the folder inside a zip, or the file / folder name ('...-scripts' suffix removed)."""
    p = Path(path)
    name = p.name
    if p.suffix.lower() == ".zip" and p.exists():
        with zipfile.ZipFile(p) as z:
            tops = {n.split("/")[0] for n in z.namelist() if "/" in n and not n.startswith("__MACOSX")}
        if len(tops) == 1:
            name = tops.pop()
    name = re.sub(r"\.(zip|txt)$", "", name, flags=re.I)        # not .stem: titles contain dots
    return re.sub(r"[-_ ]?scripts.*$", "", name, flags=re.I).strip() or "Untitled show"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="promo_finder", description="Find and rank promo clips in microdrama screenplays.")
    ap.add_argument("input", help="folder of episode .txt files, a .zip of them, or one .txt")
    ap.add_argument("-o", "--out", default="outputs", help="output folder (default: outputs)")
    ap.add_argument("-t", "--title", default=None, help="show title (default: taken from the folder / zip name)")
    ap.add_argument("-m", "--model", default="rules",
                    help="rules (default) | gemini[:model] | groq[:model] | openai:<model> | anthropic:<model> | "
                         "openrouter:<model> | ollama[:model] | custom:<model>. Keys come from environment variables.")
    ap.add_argument("-n", "--top", type=int, default=20, help="single-clip promos in the ranked list (default 20)")
    ap.add_argument("-s", "--stitched", type=int, default=6, help="stitched promos in the ranked list (default 6)")
    ap.add_argument("--llm-top", type=int, default=40, help="how many shortlisted single clips the AI judge rates")
    ap.add_argument("--compare", action="store_true", help="also run rules-only and write ai_vs_rules.md / .csv")
    ap.add_argument("--no-cache", action="store_true", help="don't reuse or store AI replies in .llm_cache/")
    a = ap.parse_args(argv)

    warnings: list[str] = []
    try:
        eps = load_path(a.input, warnings)
    except (FileNotFoundError, zipfile.BadZipFile) as e:
        print(f"Can't read {a.input}: {e}", file=sys.stderr)
        return 1
    for w in warnings:
        print(f"Warning: {w}", file=sys.stderr)
    if not eps:
        print("No episodes found. Expecting .txt screenplays with timestamped beats "
              "('**SPEAKER:**' then 'Start: (MM:SS.ss) | End: (MM:SS.ss)').", file=sys.stderr)
        return 1
    title = a.title or guess_title(a.input)
    try:
        judge = Judge(a.model, use_cache=not a.no_cache)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    if a.compare:
        if not judge.active:
            print("--compare needs an AI model, e.g. -m gemini", file=sys.stderr)
            return 2
        from .compare import compare, to_csv, to_markdown
        rules, r, summary = compare(eps, title, judge, a.llm_top, progress=print)
        out = Path(a.out)
        files = write_all(r, out)
        (out / "ai_vs_rules.md").write_text(to_markdown(rules, r, summary), encoding="utf-8")
        (out / "ai_vs_rules.csv").write_text(to_csv(summary), encoding="utf-8")
        print(f"\nTop-10 overlap rules vs AI: {summary['top10_overlap']}/10 -> {out / 'ai_vs_rules.md'}")
    else:
        r = run(eps, title, judge, a.top, a.stitched, a.llm_top, progress=print)
        files = write_all(r, a.out)
    print(f"\nRanking mode: {r.model}")
    print("Top 5 to post first:")
    for p in r.promos[:5]:
        segs = " + ".join(f"Ep{s.ep} {s.start:.1f}-{s.end:.1f}s" for s in p.segments)
        print(f"  {p.rank}. {p.id} [{p.kind}] {p.duration:.0f}s  {segs}\n     hook: {p.hook_beat.short(80)}\n     cliff: {p.cliff_beat.short(80)}")
    print("\nWrote:", *[f"  {f}" for f in files.values()], sep="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
