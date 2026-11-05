"""How big are the AI judge's prompts? Runs the AI path with a fake transport (no model, no network)
and reports characters sent per call. Tokens are estimated at 4 characters per token.

    python tools/measure_prompt.py <scripts folder or .zip>
"""
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from promo_finder.cli import guess_title  # noqa: E402
from promo_finder.llm import SYSTEM, Judge  # noqa: E402
from promo_finder.parser import load_path  # noqa: E402
from promo_finder.pipeline import run  # noqa: E402

REPLY = json.dumps({"hook": 7, "cliffhanger": 7, "standalone": 7, "overall": 7, "hook_beat": 1, "cliff_beat": 3,
                    "trim_start_beat": None, "trim_end_beat": None,
                    "why": "About twenty words explaining why this cut would work as an ad for someone who has never seen the show.",
                    "risk": "Names a character new viewers have not met"})
sizes = []


def fake(prompt: str) -> str:
    sizes.append(len(SYSTEM) + len(prompt))
    return REPLY


src = sys.argv[1]
run(load_path(src), guess_title(src), Judge("gemini", api_key="not-a-real-key", transport=fake, use_cache=False, min_interval=0))
print(f"calls: {len(sizes)}")
print(f"input characters: {sum(sizes)} total, {statistics.mean(sizes):.0f} mean, {max(sizes)} max per call")
print(f"estimated input tokens: {sum(sizes) // 4} total ({statistics.mean(sizes) / 4:.0f} per call)")
print(f"estimated output tokens at a {len(REPLY)}-character reply: {len(REPLY) * len(sizes) // 4} total "
      "(excludes any 'thinking' tokens a model bills as output)")
