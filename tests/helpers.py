"""Tiny synthetic screenplays for tests (original text, same format as the input pack)."""
from __future__ import annotations


def ts(t: float, hours: bool = False) -> str:
    if hours:
        return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


def script(num: int | None, beats: list[tuple], scenes: bool = True, hours: bool = False, header: bool = True,
           logline: str = "A test episode.") -> str:
    """beats: (kind_or_speaker, tags, text, duration). kind is CAMERA / ACTION / SOUND FX, else a speaker.
    Every dialogue line gets a camera shot that starts with it, like the real scripts."""
    out = []
    if header:
        if num is not None:
            out.append(f"EPISODE NUMBER: Episode {num}")
        out += [f"EPISODE LOGLINE: {logline}", "", "--- SCRIPT START ---", ""]
    t = 0.0
    body = []
    for who, tags, text, d in beats:
        if who in ("CAMERA", "ACTION", "SOUND FX"):
            body += [f"**{who}:**", f"Start: ({ts(t, hours)}) | End: ({ts(t + d, hours)})", text, ""]
        else:
            body += ["**CAMERA:**", f"Start: ({ts(t, hours)}) | End: ({ts(t + d, hours)})", f"Close-up on {who.title()}.", ""]
            label = f"{who} ({tags})" if tags else who
            body += [f"**{label}:**", f"Start: ({ts(t + 0.1, hours)}) | End: ({ts(t + d - 0.1, hours)})", f'"{text}"', ""]
        t += d
    if scenes:
        out += ["SCENE 01", "Scene heading: INT. TEST ROOM – NIGHT", f"Scene start: {ts(0)}", f"Scene end: {ts(t)}", "",
                "Actions and dialogue:", ""]
    out += body
    if header:
        out.append("--- SCRIPT END ---")
    return "\n".join(out)


# A short, dramatic exchange (about 40 s) that should yield at least one promo.
DRAMA = [
    ("ACTION", "", "Nora slaps Victor hard across the face in front of the guests.", 2.0),
    ("VICTOR", "Furious, Shouting", "How dare you!", 2.0),
    ("NORA", "Cold", "You stole my company.", 2.5),
    ("VICTOR", "Smug", "I took what was never yours.", 3.0),
    ("NORA", "Trembling", "My father built it.", 2.5),
    ("VICTOR", "Mocking", "And your father is dead.", 2.5),
    ("ACTION", "", "The guests gasp and step back.", 2.5),
    ("NORA", "Desperate", "Then I will prove you lied.", 3.0),
    ("VICTOR", "Cruel", "Nobody will believe a liar.", 3.0),
    ("NORA", "Defiant", "They will believe the will.", 3.0),
    ("VICTOR", "Shocked", "What will?", 2.0),
    ("ACTION", "", "Nora pulls a sealed envelope from her bag and holds it up.", 3.0),
    ("NORA", "Steely", "The one you thought you burned.", 3.0),
    ("VICTOR", "Threatening", "Guards! Seize her!", 2.5),
    ("SOUND FX", "", "A sharp musical sting and cut to black.", 1.5),
]
