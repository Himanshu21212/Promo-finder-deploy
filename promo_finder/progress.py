"""Translate pipeline diagnostics into a small editor-facing progress view."""
from __future__ import annotations

from dataclasses import dataclass, field
import re


STAGES = ("Read scripts", "Find moments", "Review clips", "Prepare report")


@dataclass
class ReviewProgress:
    stage: int = 0
    current: int = 0
    total: int = 0
    reviewed: set[int] = field(default_factory=set)

    def update(self, message: str) -> None:
        text = message.strip()
        if text.startswith("Parsed "):
            self.stage = max(self.stage, 1)
        elif text.startswith("Generated "):
            self.stage = max(self.stage, 2)
        match = re.search(r"rating (\d+) shortlisted candidates", text)
        if match:
            self.total = int(match[1])
            self.stage = max(self.stage, 2)
        match = re.fullmatch(r"Reviewing candidate (\d+)/(\d+)…", text)
        if match:
            self.current, self.total = map(int, match.groups())
            self.stage = max(self.stage, 2)
        match = re.fullmatch(r"Candidate (\d+): review complete\.", text)
        if match:
            self.reviewed.add(int(match[1]))
        summary = re.match(r"(\d+)/(\d+) rated by the model", text)
        if summary and int(summary[1]) > 0:
            self.stage = 3

    def html(self) -> str:
        titles = ("Reading your scripts", "Finding compelling moments", "Reviewing your shortlist", "Preparing your report")
        subtitles = ("Checking episode structure and cut points.", "Looking for strong openings and unresolved endings.",
                     "Checking hooks, cliffhangers and new-viewer clarity.", "Ranking your clips and checking the cut points.")
        detail = f"Clip {self.current} of {self.total}" if self.stage == 2 and self.current else ""
        if self.stage == 2 and self.total:
            pct = min(100, 100 * len(self.reviewed) / self.total)
            bar = (f'<div class="pf-review-track" role="progressbar" aria-label="Clips reviewed" '
                   f'aria-valuemin="0" aria-valuemax="{self.total}" aria-valuenow="{len(self.reviewed)}">'
                   f'<div class="pf-review-fill" style="width:{pct:.2f}%"></div></div>')
        else:
            bar = '<div class="pf-review-track"><div class="pf-review-pulse"></div></div>'
        steps = "".join(f'<div class="pf-review-step {"done" if i < self.stage else "active" if i == self.stage else ""}">'
                        f'<span>{"✓" if i < self.stage else i + 1}</span>{label}</div>' for i, label in enumerate(STAGES))
        return (f'<div class="pf pf-review" aria-live="polite"><div class="pf-label accent">Finding promos</div>'
                f'<div class="pf-review-heading"><h2><i class="pf-review-dot" aria-hidden="true"></i>{titles[self.stage]}</h2><span>{detail}</span></div>'
                f'<p>{subtitles[self.stage]}</p>{bar}<div class="pf-review-steps">{steps}</div></div>')
