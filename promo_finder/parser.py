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

SCRIPT_EXTS = (".txt", ".srt", ".vtt")   # files read as scripts (also inside a ZIP)
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
    timing_estimated: bool = False   # True when the script had no timestamps and times were estimated
    layout: str = "promo-finder"     # which reader understood the file

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

    # Fallback readers for other common layouts (the exact layout above always wins when it matches).
    layout, estimated, num_found = "promo-finder", False, bool(m)
    if not beats:
        if not m and (loose_num := _loose_ep_num(header)):
            num, num_found = loose_num, True
        loose = _parse_loose_timed(body, num)
        if loose:
            beats, scenes, layout = loose[0], loose[1], loose[2]
            skipped = inverted = 0
        else:
            est = _parse_screenplay_estimated(body, num)
            if est:
                beats, scenes = est
                layout, estimated = "screenplay", True
                skipped = inverted = 0

    beats.sort(key=lambda b: (b.start, b.end))
    for n, b in enumerate(beats):
        b.idx = n
    if not scenes:
        scenes = [Scene(1, "", 0.0, max((b.end for b in beats), default=0.0))]
    for s in scenes:  # repair missing scene ends
        if s.end <= s.start:
            s.end = max((b.end for b in beats if b.scene == s.num), default=s.start)
    ep = Episode(num, f"Episode {num}", logline, continuity, beats, scenes, source,
                 timing_estimated=estimated, layout=layout)
    name = source or f"Episode {num}"
    if estimated:
        ep.warnings.append(f"{name}: no timestamps found, so timing was estimated from the text "
                           "(about 2.5 spoken words per second). Check cut points against the video.")
    if skipped:
        ep.warnings.append(f"{name}: {skipped} block(s) had no Start/End time and were skipped")
    if inverted:
        ep.warnings.append(f"{name}: {inverted} block(s) ended before they started; end set to start")
    if not num_found:
        ep.warnings.append(f"{name}: no 'EPISODE NUMBER' line; number taken from the file name" if num
                           else f"{name}: no episode number found")
    return ep


# ----------------------------------------------------------------- fallback readers
# A time like 05.5 / 00:05.60 / 1:02:03 / 00:00:05,600 (SRT uses a comma).
_T = r"(?:\d{1,2}:)?\d{1,2}:\d{2}(?:[.,]\d+)?"
RE_RANGE = re.compile(
    rf"(?:Start\s*:?\s*)?[\[(]?\s*({_T})\s*[\])]?\s*(?:\||-->|–|—|-|to|,|/)?\s*(?:End\s*:?\s*)?[\[(]?\s*({_T})\s*[\])]?", re.I)
RE_ONE = re.compile(rf"^[\[(]\s*({_T})\s*[\])]")             # start-only stamp at line start: [00:05]
RE_LOOSE_LABEL = re.compile(r"^\**\s*([A-Za-z][A-Za-z0-9 .'’&-]{0,40}?)\s*((?:\([^)]*\)\s*)*):\s*\**\s*(.*)$")
RE_VTT_VOICE = re.compile(r"^<v(?:\.[^\s>]*)?\s+([^>]+)>(.*?)(?:</v>)?$", re.I)
RE_SLUG = re.compile(r"^(?:\d+[A-Z]?[.)]?\s+)?(?:INT|EXT|INT\.?\s*/\s*EXT|EXT\.?\s*/\s*INT|I/E)[.\s]", re.I)
RE_TRANSITION = re.compile(r"^(?:FADE (?:IN|OUT|TO)|CUT TO|SMASH CUT|MATCH CUT|DISSOLVE TO|THE END|CONTINUED|END OF EPISODE)\b", re.I)
RE_CUE_EXT = re.compile(r"\((?:V\.?O\.?|O\.?S\.?|O\.?C\.?|CONT'?D|CONT’D|CONTINUED)\)", re.I)
_NOT_SPEAKERS = {"EPISODE NUMBER", "EPISODE LOGLINE", "CONTINUITY NOTES", "SCENE HEADING", "SCENE START", "SCENE END",
                 "START", "END", "ACTIONS AND DIALOGUE", "NOTE", "NOTES", "TITLE", "WRITTEN BY", "AUTHOR", "DRAFT",
                 "LOGLINE", "SYNOPSIS", "SUMMARY", "WEBVTT", "KIND", "LANGUAGE", "TIME", "DURATION"}
_UNNAMED = "VOICE"  # subtitle lines with no speaker name


def _secs(tok: str) -> float:
    parts = tok.replace(",", ".").split(":")
    total = 0.0
    for p in parts:
        total = total * 60 + float(p)
    return total


def _loose_ep_num(header: str) -> int:
    for line in header.split("\n")[:20]:
        mm = re.match(r"^\s*#*\s*(?:EPISODE|EP)\s*(?:NO\.?|NUMBER|#)?\s*[:#.\-]?\s*(\d+)\b", line.strip(), re.I)
        if mm:
            return int(mm.group(1))
    return 0


def _is_speaker(name: str) -> bool:
    name = name.strip()
    words = name.split()
    return (0 < len(words) <= 4 and name.upper() not in _NOT_SPEAKERS
            and not re.search(r"[.!?]$", name) and not name.lower().startswith(("http", "www")))


def _kind_of(label: str) -> tuple[str, str]:
    up = label.upper().strip()
    kind = KINDS.get(up)
    return (kind, "") if kind else ("dialogue", up)


def _parse_loose_timed(body: str, num: int):
    """Timed scripts in other layouts: labels without **bold**, times on the label line, [a - b] / a --> b
    ranges, SRT and WebVTT subtitles. Every time still comes from the file; only a missing END is filled
    from the next line's start. Returns (beats, scenes, layout) or None when fewer than 2 timed lines."""
    blocks: list[dict] = []
    cur: dict | None = None
    scene, scenes = 1, []
    subtitle = bool(re.search(rf"{_T}\s*-->\s*{_T}", body))

    def new(**kw) -> dict:
        nonlocal cur
        cur = {"start": None, "end": None, "label": None, "tags": [], "text": [], "scene": scene, **kw}
        blocks.append(cur)
        return cur

    for raw in body.split("\n"):
        line = raw.strip()
        if not line or line.upper().startswith(("WEBVTT", "NOTE ", "STYLE", "REGION")) or line.isdigit():
            continue
        if RE_SCENE.match(line) or RE_SLUG.match(line):
            scene = len(scenes) + 1
            scenes.append(Scene(scene, "" if RE_SCENE.match(line) else line, 0.0, 0.0))
            continue
        if re.match(r"^(Scene (heading|start|end)|Actions and dialogue)\s*:", line, re.I):
            continue
        rng = RE_RANGE.search(line)
        one = None if rng else RE_ONE.match(line)
        if rng or one:
            s = _secs((rng or one).group(1))
            e = _secs(rng.group(2)) if rng else None
            if cur is None or cur["start"] is not None and cur["text"] or cur["start"] is not None and not cur["label"]:
                new()
            cur["start"], cur["end"] = s, e
            line = (line[:(rng or one).start()] + " " + line[(rng or one).end():]).strip(" |:-–—*")
            line = re.sub(r"(?:^|\s)(?:align|position|line|size|vertical|region):\S+", "", line).strip()  # VTT cue settings
            if not line:
                continue
        speaker = tags = None
        if (vm := RE_VTT_VOICE.match(line)):
            speaker, line = vm.group(1).strip(), vm.group(2).strip()
        elif (lm := RE_LOOSE_LABEL.match(line)) and _is_speaker(lm.group(1)):
            speaker, line = lm.group(1).strip(), lm.group(3).strip()
            tags = [t.strip() for grp in re.findall(r"\(([^)]*)\)", lm.group(2)) for t in grp.split(",") if t.strip()]
        line = re.sub(r"</?[a-z][^>]*>", "", line).strip().lstrip("-– ").strip()  # subtitle markup / dash
        if speaker is not None:
            if cur is not None and not cur["text"] and (cur["label"] is None):
                cur["label"] = speaker
            else:
                new(start=None, label=speaker)
            cur["tags"] = tags or []
        if line:
            if cur is None:
                new()
            cur["text"].append(line)

    # fill missing times from neighbours; drop blocks that never got a time
    timed = [b for b in blocks if b["text"] or b["label"]]
    for i, b in enumerate(timed):
        if b["start"] is None and i and timed[i - 1]["start"] is not None:
            prev = timed[i - 1]
            b["start"] = prev["end"] if prev["end"] is not None else prev["start"]
            b["end"] = None
    for i, b in enumerate(timed):
        if b["start"] is not None and b["end"] is None:
            nxt = next((x["start"] for x in timed[i + 1:] if x["start"] is not None and x["start"] > b["start"]), None)
            b["end"] = nxt if nxt is not None else b["start"] + _estimate(" ".join(b["text"]), "dialogue")
    timed = [b for b in timed if b["start"] is not None and b["text"]]
    if len(timed) < 2:
        return None

    beats = []
    for b in timed:
        text = " ".join(b["text"]).strip()
        if b["label"]:
            kind, speaker = _kind_of(b["label"])
        elif re.fullmatch(r"[\[(♪].*[\])♪]", text):
            kind, speaker = "sfx", ""
        else:
            kind, speaker = "dialogue", _UNNAMED
        if kind == "sfx":
            text = text.strip("[]()♪ ")
        beats.append(Beat(num, len(beats), kind, b["start"], max(b["end"], b["start"]), text, speaker, b["tags"], b["scene"]))
    for s in scenes:
        own = [b for b in beats if b.scene == s.num]
        if own:
            s.start, s.end = min(b.start for b in own), max(b.end for b in own)
    return beats, scenes, "subtitles" if subtitle else "timed-labels"


def _estimate(text: str, kind: str) -> float:
    words = len(text.split())
    if kind == "dialogue":
        return round(min(12.0, max(1.2, words / 2.5 + 0.4)), 2)
    return round(min(6.0, max(1.5, words / 4 + 1.0)), 2)


def _parse_screenplay_estimated(body: str, num: int):
    """Standard screenplay layout (INT./EXT. headings, CHARACTER cue on its own line, (parenthetical),
    dialogue, action paragraphs) with NO timestamps. Times are ESTIMATED from word count; the episode
    is marked timing_estimated so the report can say so. Returns (beats, scenes) or None."""
    paras, buf = [], []
    for raw in body.split("\n"):
        if raw.strip():
            buf.append(raw.strip())
        elif buf:
            paras.append(buf)
            buf = []
    if buf:
        paras.append(buf)

    def is_cue(line: str) -> bool:
        name = RE_CUE_EXT.sub("", line).strip()
        name = re.sub(r"\([^)]*\)$", "", name).strip()   # trailing (mocking) on the cue line
        return (bool(re.search(r"[A-Z]", name)) and name == name.upper() and len(name) <= 40
                and len(name.split()) <= 5 and not RE_SLUG.match(line) and not RE_TRANSITION.match(line)
                and not name.endswith((":", ".", "!", "?")) and name.upper() not in _NOT_SPEAKERS)

    beats, scenes, t, scene, dialogue_lines = [], [], 0.0, 1, 0
    for para in paras:
        first = para[0]
        if RE_SLUG.match(first) or RE_SCENE.match(first):
            scene = len(scenes) + 1
            scenes.append(Scene(scene, first if RE_SLUG.match(first) else "", t, t))
            para = para[1:]
            if not para:
                continue
            first = para[0]
        if RE_TRANSITION.match(first) or re.match(r"^[A-Za-z ]{2,30}:\s*\S", first) and first.split(":")[0].upper() in _NOT_SPEAKERS:
            continue
        # a paragraph may hold several cue+dialogue groups only if separated by blank lines, so one cue per para
        if is_cue(first) and len(para) > 1:
            cue = RE_CUE_EXT.sub("", first).strip()
            tags = [x.strip() for g in re.findall(r"\(([^)]*)\)", cue) for x in g.split(",") if x.strip()]
            speaker = re.sub(r"\([^)]*\)", "", cue).strip().upper()
            said = []
            for ln in para[1:]:
                if re.fullmatch(r"\(.*\)", ln):
                    tags += [x.strip() for x in ln.strip("()").split(",") if x.strip()]
                else:
                    said.append(ln)
            text = " ".join(said).strip()
            if not text:
                continue
            kind, spk = _kind_of(speaker)
            d = _estimate(text, kind)
            beats.append(Beat(num, len(beats), kind, round(t, 2), round(t + d, 2), text, spk, tags, scene))
            dialogue_lines += kind == "dialogue"
            t += d
        else:
            text = " ".join(para).strip()
            d = _estimate(text, "action")
            beats.append(Beat(num, len(beats), "action", round(t, 2), round(t + d, 2), text, "", [], scene))
            t += d
    if len(beats) < 3 or dialogue_lines < 1:
        return None
    for s in scenes:
        own = [b for b in beats if b.scene == s.num]
        s.start, s.end = (min(b.start for b in own), max(b.end for b in own)) if own else (s.start, s.start)
    return beats, scenes


def _field(header: str, name: str) -> str:
    m = re.search(rf"{name}:\s*(.+)", header, re.I)
    return m.group(1).strip() if m else ""


def _num_from_name(name: str) -> int:
    m = (re.search(r"episode[-_ ]?0*(\d+)", name, re.I)
         or re.search(r"(?:^|[^a-z])e(?:p)?[-_ ]?0*(\d+)", name, re.I)      # ep01, e03, s01e03
         or re.match(r"^0*(\d+)\b", name))                                   # 01.txt, 3 - title.txt
    return int(m.group(1)) if m else 0


def load_path(path: str | Path, warnings: list[str] | None = None) -> list[Episode]:
    """Load a folder of .txt scripts, a single .txt, or a .zip of them.
    Problems (unreadable files, duplicates, missing numbers) are appended to `warnings` if given."""
    p = Path(path)
    if p.is_dir():
        files = sorted(f for f in p.rglob("*") if f.suffix.lower() in SCRIPT_EXTS and not f.name.startswith("."))
        return finalize([parse_text(f.read_text(encoding="utf-8", errors="replace"), f.name) for f in files], warnings)
    if p.suffix.lower() == ".zip":
        return load_zip_bytes(p.read_bytes(), warnings)
    return finalize([parse_text(p.read_text(encoding="utf-8", errors="replace"), p.name)], warnings)


def load_zip_bytes(data: bytes, warnings: list[str] | None = None) -> list[Episode]:
    eps = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for n in sorted(z.namelist()):
            base = n.rsplit("/", 1)[-1]
            if n.lower().endswith(SCRIPT_EXTS) and not base.startswith(".") and "__MACOSX" not in n:
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
