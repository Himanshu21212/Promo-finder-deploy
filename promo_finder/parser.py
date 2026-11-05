"""Screenplay parser: turns one timestamped microdrama script into structured beats.

Pure code, no AI. Every timestamp in the output comes from here, so the
tool can never invent a time that isn't in the script.
"""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# MM:SS(.ss) or HH:MM:SS(.ss)
TS = r"((?:\d{1,2}:)?\d{1,2}):(\d{2}(?:\.\d+)?)"
RE_TIMES = re.compile(rf"Start:\s*\({TS}\)\s*\|\s*End:\s*\({TS}\)", re.I)
RE_LABEL = re.compile(r"^\*\*(.+?):\*\*\s*$")
RE_EP_NUM = re.compile(r"EPISODE NUMBER:\s*Episode\s*(\d+)", re.I)
RE_SCENE = re.compile(r"^SCENE\s+(\d+)\s*$", re.I)
RE_SCENE_HEAD = re.compile(r"^Scene heading:\s*(.+)$", re.I)
RE_SCENE_START = re.compile(rf"^Scene start:\s*{TS}", re.I)
RE_SCENE_END = re.compile(rf"^Scene end:\s*{TS}", re.I)

KINDS = {"CAMERA": "camera", "ACTION": "action", "SOUND FX": "sfx", "SFX": "sfx", "MUSIC": "sfx"}


def to_sec(m: str, s: str) -> float:
    """'01', '05.5' -> 65.5 ; '1:02', '03' -> 3723 (hours allowed in the minutes group)."""
    parts = [int(x) for x in m.split(":")]
    mins = parts[-1] + (60 * parts[0] if len(parts) == 2 else 0)
    return mins * 60 + float(s)


SMALL = {"in", "of", "the", "with", "a", "an", "and", "to", "on", "at"}


def speaker_name(raw: str) -> str:
    """'LADY IN THE RED DRESS' -> 'Lady in the Red Dress', "THE KING'S GUARD" -> "The King's Guard"."""
    words = raw.lower().split()
    out = [w if (i and w in SMALL) else w[:1].upper() + w[1:] for i, w in enumerate(words)]
    return " ".join(out)


def fmt(t: float) -> str:
    """Seconds -> MM:SS.s (same style as the scripts)."""
    t = max(0.0, t)
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


@dataclass
class Beat:
    ep: int
    idx: int
    kind: str              # dialogue | action | camera | sfx
    start: float
    end: float
    text: str
    speaker: str = ""      # dialogue only
    tags: list[str] = field(default_factory=list)  # emotion / delivery tags
    scene: int = 1
    # filled by scoring.py
    hook: float = 0.0
    cliff: float = 0.0
    heat: float = 0.0
    context: float = 0.0
    tropes: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return speaker_name(self.speaker) if self.kind == "dialogue" else self.kind.upper()

    def short(self, n: int = 110) -> str:
        t = self.text.strip().strip('"')
        t = t if len(t) <= n else t[: n - 1].rstrip() + "…"
        if self.kind == "dialogue":
            return f'{speaker_name(self.speaker)}: "{t}"'
        return f"[{self.kind}] {t}"


@dataclass
class Scene:
    num: int
    heading: str
    start: float
    end: float


@dataclass
class Episode:
    num: int
    title: str
    logline: str
    continuity: str
    beats: list[Beat]
    scenes: list[Scene]
    source: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        ends = [b.end for b in self.beats] + [s.end for s in self.scenes]
        return max(ends) if ends else 0.0

    @property
    def lines(self) -> list[Beat]:
        return [b for b in self.beats if b.kind == "dialogue"]

    @property
    def shots(self) -> list[Beat]:
        return [b for b in self.beats if b.kind == "camera"]


def _split_label(label: str) -> tuple[str, str, list[str]]:
    """'LADY MIA (Confused, Breathless)' -> ('dialogue', 'LADY MIA', ['Confused','Breathless'])."""
    tags = []
    for grp in re.findall(r"\(([^)]*)\)", label):
        tags += [t.strip() for t in grp.split(",") if t.strip()]
    name = re.sub(r"\([^)]*\)", "", label).strip()
    kind = KINDS.get(name.upper())
    if kind:
        return kind, "", tags
    return "dialogue", name.upper(), tags


def parse_text(text: str, source: str = "") -> Episode:
    raw = text.replace("\r\n", "\n").replace("﻿", "")
    header, _, body = raw.partition("--- SCRIPT START ---")
    if not body:  # tolerate scripts without the marker
        body, header = raw, raw[:2000]
    body = body.split("--- SCRIPT END ---")[0]

    m = RE_EP_NUM.search(header)
    num = int(m.group(1)) if m else _num_from_name(source)
    logline = _field(header, "EPISODE LOGLINE")
    continuity = _field(header, "CONTINUITY NOTES")

    beats: list[Beat] = []
    scenes: list[Scene] = []
    cur_scene = 1
    skipped = inverted = 0
    lines = body.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if (sm := RE_SCENE.match(line)):
            cur_scene = int(sm.group(1))
            scenes.append(Scene(cur_scene, "", 0.0, 0.0))
        elif (hm := RE_SCENE_HEAD.match(line)) and scenes:
            scenes[-1].heading = hm.group(1).strip()
        elif (st := RE_SCENE_START.match(line)) and scenes:
            scenes[-1].start = to_sec(*st.groups())
        elif (en := RE_SCENE_END.match(line)) and scenes:
            scenes[-1].end = to_sec(*en.groups())
        elif (lm := RE_LABEL.match(line)):
            kind, speaker, tags = _split_label(lm.group(1))
            # next non-empty line should hold the times
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            tm = RE_TIMES.search(lines[j]) if j < len(lines) else None
            if not tm:
                skipped += 1
            if tm:
                s, e = to_sec(tm.group(1), tm.group(2)), to_sec(tm.group(3), tm.group(4))
                if e < s:
                    inverted += 1
                k = j + 1
                buf = []
                while k < len(lines) and lines[k].strip() and not RE_LABEL.match(lines[k].strip()):
                    buf.append(lines[k].strip())
                    k += 1
                txt = " ".join(buf).strip()
                if kind == "sfx":
                    txt = txt.strip("[]")
                beats.append(Beat(num, len(beats), kind, s, max(e, s), txt, speaker, tags, cur_scene))
                i = k
                continue
        i += 1

    beats.sort(key=lambda b: (b.start, b.end))
    for n, b in enumerate(beats):
        b.idx = n
    if not scenes:
        scenes = [Scene(1, "", 0.0, max((b.end for b in beats), default=0.0))]
    for s in scenes:  # repair missing scene ends
        if s.end <= s.start:
            s.end = max((b.end for b in beats if b.scene == s.num), default=s.start)
    ep = Episode(num, f"Episode {num}", logline, continuity, beats, scenes, source)
    name = source or f"Episode {num}"
    if skipped:
        ep.warnings.append(f"{name}: {skipped} block(s) had no Start/End time and were skipped")
    if inverted:
        ep.warnings.append(f"{name}: {inverted} block(s) ended before they started; end set to start")
    if not m:
        ep.warnings.append(f"{name}: no 'EPISODE NUMBER' line; number taken from the file name" if num
                           else f"{name}: no episode number found")
    return ep


def _field(header: str, name: str) -> str:
    m = re.search(rf"{name}:\s*(.+)", header, re.I)
    return m.group(1).strip() if m else ""


def _num_from_name(name: str) -> int:
    m = re.search(r"episode[-_ ]?0*(\d+)", name, re.I)
    return int(m.group(1)) if m else 0


def load_path(path: str | Path, warnings: list[str] | None = None) -> list[Episode]:
    """Load a folder of .txt scripts, a single .txt, or a .zip of them.
    Problems (unreadable files, duplicates, missing numbers) are appended to `warnings` if given."""
    p = Path(path)
    if p.is_dir():
        files = sorted(f for f in p.rglob("*.txt") if not f.name.startswith("."))
        return finalize([parse_text(f.read_text(encoding="utf-8", errors="replace"), f.name) for f in files], warnings)
    if p.suffix.lower() == ".zip":
        return load_zip_bytes(p.read_bytes(), warnings)
    return finalize([parse_text(p.read_text(encoding="utf-8", errors="replace"), p.name)], warnings)


def load_zip_bytes(data: bytes, warnings: list[str] | None = None) -> list[Episode]:
    eps = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for n in sorted(z.namelist()):
            base = n.rsplit("/", 1)[-1]
            if n.lower().endswith(".txt") and not base.startswith(".") and "__MACOSX" not in n:
                eps.append(parse_text(z.read(n).decode("utf-8", errors="replace"), base))
    return finalize(eps, warnings)


def finalize(eps: list[Episode], warnings: list[str] | None = None) -> list[Episode]:
    """Drop files with no timed beats, number un-numbered episodes, and remove duplicate numbers."""
    w = warnings if warnings is not None else []
    for e in eps:
        if not e.beats:
            w.append(f"{e.source or 'a file'}: no timestamped lines found, so it was skipped (not a screenplay in the expected format?)")
    eps = [e for e in eps if e.beats]
    numbered = sorted((e for e in eps if e.num), key=lambda e: e.num)
    nxt = max((e.num for e in numbered), default=0) + 1
    for e in eps:                      # files with no number anywhere go after the numbered ones, in file order
        if not e.num:
            e.num = nxt
            e.title = f"Episode {nxt}"
            for b in e.beats:
                b.ep = nxt
            w.append(f"{e.source}: treated as Episode {nxt}")
            nxt += 1
    by_num: dict[int, Episode] = {}
    for e in eps:
        if e.num in by_num:
            keep, drop = (e, by_num[e.num]) if len(e.beats) > len(by_num[e.num].beats) else (by_num[e.num], e)
            w.append(f"Two files claim Episode {e.num} ({keep.source}, {drop.source}); kept {keep.source}")
            by_num[e.num] = keep
        else:
            by_num[e.num] = e
    out = sorted(by_num.values(), key=lambda e: e.num)
    for e in out:
        w.extend(e.warnings)
    return out


_sorted = finalize  # backwards-compatible name
