"""Beat-level scores (pure rules, no AI).

For every timed beat we estimate:
  hook    - would this stop a scroll if it played in the first 3 seconds?
  cliff   - is this an unresolved moment worth cutting on?
  heat    - general dramatic intensity (keeps the middle of a promo from sagging)
  context - how much prior knowledge a brand-new viewer needs to follow it
"""
from __future__ import annotations

import re
from functools import lru_cache

from . import lexicon as L
from .parser import Beat, Episode


@lru_cache(maxsize=None)
def _rx(p: str) -> re.Pattern:
    return re.compile(p, re.I)


def _tiered(text: str, tiers) -> float:
    for w, pat in tiers:
        if _rx(pat).search(text):
            return w
    return 0.0


def tag_heat(tags: list[str]) -> float:
    return max([_tiered(t, L.TAG_HEAT) for t in tags] + [0.0])


# Looser words used only to read a show's *title / opening loglines* (works for any show).
PREMISE_HINTS = {
    "secret_identity": r"\bduke|prince|\bheir|billionaire|\bceo\b|secret|hidden|disguis|\bking\b|royal|alpha|mafia",
    "proposal": r"married|marry|\bwed\b|bride|husband|wife|contract|proposal",
    "altar_betrayal": r"altar|jilt|abandon|left at|fianc|cheat|cast aside",
    "protector": r"soldier|bodyguard|warrior|protect|guard|rescued|defends",
    "humiliation": r"humiliat|outcast|disown|mock|\bpoor\b|nobody|cast aside",
    "family_betrayal": r"sister|stepmother|her family|disown",
}


def premise_tropes(title: str, episodes: list[Episode]) -> set[str]:
    """Tropes named in the show title and the first three loglines = what the show *promises*."""
    text = " ".join([title] + [e.logline for e in episodes[:3]])
    found = {k for k, (pat, *_) in L.TROPES.items() if _rx(pat).search(text)}
    found |= {k for k, pat in PREMISE_HINTS.items() if _rx(pat).search(text)}
    return found


def character_names(episodes: list[Episode]) -> set[str]:
    """Named characters (from speaker labels + 'Lord X' style mentions), used for the context check."""
    generic = {"LADY", "LORD", "THE", "SIR", "FATHER", "MOTHER", "DUKE", "DUCHESS", "OLD", "YOUNG", "HIGH",
               "ROYAL", "ELDER", "NOBLE", "MYSTERIOUS", "BEARDED", "STRANGER", "MAN", "WOMAN", "GUARD", "MAID",
               "PRIEST", "JUDGE", "IN", "GOLD", "GOWN", "FORMER", "GROOM", "THUG", "WITH", "CAP", "DOWAGER",
               "NOBLEMAN", "NOBLEWOMAN", "MATRIARCH", "BLOND", "VOICE", "OFF-SCREEN", "CROWN", "OFFICIAL",
               "POLICE", "CONSTABLE", "PEASANT", "VILLAGER", "HOUSEKEEPER", "BUTLER", "FOOTMAN", "TALL", "BALD",
               "THIRD", "CART", "DRIVER", "TOWNSMAN", "LOYALIST", "SCOUT", "FIGHTER", "SENTRY", "SCARRED",
               "ARISTOCRATIC", "INFORMANT", "CONSPIRATOR"}
    names = set()
    for e in episodes:
        for b in e.lines:
            for tok in re.findall(r"[A-Z][A-Z'-]+", b.speaker):
                if tok not in generic and len(tok) > 2:
                    names.add(tok.title())
            for m in re.finditer(r"\b(?:Lord|Lady|Father|Sir|Master)\s+([A-Z][a-z]+)", b.text):
                names.add(m.group(1))
    return names


def score_beat(b: Beat, ep: Episode) -> None:
    text = b.text
    if b.kind == "dialogue":
        th = tag_heat(b.tags)
        lh = _tiered(text, L.LINE_HOOK)
        bang = 0.15 if "!" in text else 0.0
        short = 0.1 if len(text) < 45 else 0.0          # punchy lines land in < 3 s
        b.heat = min(1.0, 0.55 * th + 0.45 * lh + bang)
        b.hook = min(1.0, 0.6 * lh + 0.4 * th + bang + short)
        b.cliff = _tiered(text, L.CLIFF_LINE) * (0.6 + 0.4 * th)
        if _rx(L.CONTINUATION_START).search(text):
            b.context += 0.5
        if _rx(L.CONTEXT_NOUNS).search(text):
            b.context += 0.3
    elif b.kind in ("action", "camera"):
        vh = _tiered(text, L.VISUAL_HOOK)
        b.heat = vh * (1.0 if b.kind == "action" else 0.8)
        b.hook = b.heat * 0.9
        b.cliff = _tiered(text, L.CLIFF_ACTION) * (1.0 if b.kind == "action" else 0.7)
        if b.kind == "camera" and _rx(r"cut to black|smash cut|freeze").search(text):
            b.cliff = max(b.cliff, 0.6)
    elif b.kind == "sfx":
        vh = _tiered(text, L.VISUAL_HOOK)
        b.heat = vh * 0.7
        b.hook = vh * 0.8
        b.cliff = _tiered(text, L.CLIFF_SFX)
    if _rx(L.RESOLVED).search(text):
        b.cliff *= 0.3
    # Writers put the episode's cliffhanger in its final seconds.
    if ep.duration - b.end < 6.0:
        b.cliff = min(1.0, b.cliff + 0.35)
    b.tropes = [k for k, (pat, *_) in L.TROPES.items() if _rx(pat).search(text)]


def score_episodes(episodes: list[Episode]) -> None:
    for ep in episodes:
        for b in ep.beats:
            b.hook = b.cliff = b.heat = b.context = 0.0
            score_beat(b, ep)
