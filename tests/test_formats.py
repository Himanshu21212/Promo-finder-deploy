"""Other script layouts: loose timed labels, inline times, SRT/VTT subtitles, and screenplays with no times.
Each test rewrites the original demo show into that layout and checks the full pipeline still finds promos."""
import io
import zipfile
from pathlib import Path

from promo_finder import load_path, run
from promo_finder.parser import _num_from_name, finalize, load_zip_bytes, parse_text
from promo_finder.report import timing_note, to_csv, to_markdown, to_pdf

DEMO = Path(__file__).resolve().parents[1] / "samples" / "demo_show.zip"
EPS = load_path(DEMO)
TITLE = "The Maid Was the Heiress"


def mmss(t):
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


def srt(t, sep=","):
    return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}{sep}{int(round((t % 1) * 1000)):03d}"


def label(b):
    return {"dialogue": b.speaker + (f" ({', '.join(b.tags)})" if b.tags else ""),
            "action": "ACTION", "sfx": "SOUND FX", "camera": "CAMERA"}[b.kind]


def rebuild(fmt):
    return finalize([parse_text(fmt(e), f"episode-{e.num:03d}.txt") for e in EPS])


def test_loose_labels_without_bold_or_brackets():
    eps = rebuild(lambda e: "\n\n".join(f"{label(b)}:\nStart: {mmss(b.start)} | End: {mmss(b.end)}\n{b.text}"
                                       for b in e.beats))
    assert [e.num for e in eps] == [1, 2] and eps[0].layout == "timed-labels" and not eps[0].timing_estimated
    assert len(eps[0].beats) == len(EPS[0].beats)
    assert run(eps, TITLE).promos


def test_inline_times_on_the_label_line():
    eps = rebuild(lambda e: "\n".join(f"[{mmss(b.start)} - {mmss(b.end)}] {label(b)}: {b.text}"
                                      for b in e.beats if b.kind != "camera"))
    mia = next(b for b in eps[0].beats if b.speaker == "MIA")
    assert mia.tags and mia.kind == "dialogue"
    assert run(eps, TITLE).promos


def test_srt_subtitles_keep_exact_times():
    def to_srt(e):
        cues = [b for b in e.beats if b.kind == "dialogue"]
        return "\n\n".join(f"{i + 1}\n{srt(b.start)} --> {srt(b.end)}\n{b.speaker}: {b.text}" for i, b in enumerate(cues))
    eps = rebuild(to_srt)
    assert eps[0].layout == "subtitles" and not eps[0].timing_estimated
    first = next(b for b in EPS[0].beats if b.kind == "dialogue")
    assert abs(eps[0].beats[0].start - first.start) < 0.01
    assert run(eps, TITLE).promos


def test_vtt_with_voice_tags_and_unnamed_lines():
    text = ("WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n<v Victoria>Careful, Mia.</v>\n\n"
            "00:00:03.500 --> 00:00:05.000 align:start\nWhy would you do that?\n\n"
            "00:00:05.000 --> 00:00:06.000\n[door slams]\n")
    ep = parse_text(text, "ep01.vtt")
    assert [(b.kind, b.speaker) for b in ep.beats] == [("dialogue", "VICTORIA"), ("dialogue", "VOICE"), ("sfx", "")]
    assert ep.beats[1].text == "Why would you do that?" and ep.num == 1


def test_screenplay_without_times_is_estimated_and_flagged():
    def to_screenplay(e):
        out = [f"EPISODE {e.num}", "", "EXT. HALE TOWER ROOFTOP - NIGHT", ""]
        for b in e.beats:
            if b.kind == "dialogue":
                out += [b.speaker] + ([f"({', '.join(b.tags)})"] if b.tags else []) + [b.text.strip('"'), ""]
            elif b.kind == "action":
                out += [b.text, ""]
        return "\n".join(out)
    eps = finalize([parse_text(to_screenplay(e), "script.txt") for e in EPS])
    assert [e.num for e in eps] == [1, 2]                        # from the 'EPISODE n' line
    assert all(e.timing_estimated and e.layout == "screenplay" for e in eps)
    assert any("estimated" in w for e in eps for w in e.warnings)
    r = run(eps, TITLE)
    assert r.promos and r.stats["estimated_timing_episodes"] == [1, 2]
    assert all(any(f.startswith("Estimated timing") for f in p.flags) for p in r.promos)
    assert "Estimated timing" in timing_note(r) and "Estimated timing" in to_markdown(r)
    assert "Estimated timing" in to_csv(r.promos)
    assert to_pdf(r).startswith(b"%PDF")


def test_exact_layout_is_not_marked_estimated():
    r = run(EPS, TITLE)
    assert r.stats["estimated_timing_episodes"] == [] and timing_note(r) == ""
    assert not any(f.startswith("Estimated timing") for p in r.promos for f in p.flags)


def test_plain_chat_style_is_still_rejected():
    ep = parse_text("Victoria: Careful, Mia.\nMia: Why would you do that?\nEthan: Take your hands off her.\n", "chat.txt")
    assert not ep.beats


def test_zip_reads_srt_files():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("show/ep01.srt", "1\n00:00:01,000 --> 00:00:03,000\nMIA: Hello.\n\n2\n00:00:03,000 --> 00:00:05,000\nETHAN: Hi.\n")
    eps = load_zip_bytes(buf.getvalue())
    assert len(eps) == 1 and eps[0].num == 1 and len(eps[0].beats) == 2


def test_episode_number_from_common_file_names():
    assert _num_from_name("episode-004.txt") == 4
    assert _num_from_name("Show_S01E07.srt") == 7
    assert _num_from_name("ep12.txt") == 12
    assert _num_from_name("03 - The Will.txt") == 3
    assert _num_from_name("notes.txt") == 0
