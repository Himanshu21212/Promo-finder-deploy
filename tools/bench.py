"""Timing on bigger seasons: repeats the given show's episodes to make 50 / 100 / 200-episode inputs.

    python tools/bench.py <scripts folder or .zip> [50 100 200]
"""
import copy
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from promo_finder.cli import guess_title  # noqa: E402
from promo_finder.parser import load_path  # noqa: E402
from promo_finder.pipeline import run  # noqa: E402

src = sys.argv[1]
base = load_path(src)
for n in [int(a) for a in sys.argv[2:]] or [50, 100, 200]:
    eps = []
    for i in range(n):
        e = copy.deepcopy(base[i % len(base)])
        e.num = i + 1
        for b in e.beats:
            b.ep = i + 1
        eps.append(e)
    t = time.time()
    r = run(eps, guess_title(src))
    print(f"{n} episodes: {time.time() - t:.1f} s, {r.stats['candidates']} candidates, {len(r.promos)} promos")
