"""Builds samples/demo_show.zip: a tiny ORIGINAL two-episode script in the same timestamped format
as the input pack, so anyone can try the app without Kuku's confidential scripts."""
import zipfile
from pathlib import Path

EP1 = ("The heiress is humiliated at her stepsister's engagement party, until the groom defends her.", [
    ("CAMERA", "", "", "Wide shot of a glittering rooftop engagement party at night.", 2.5),
    ("ACTION", "", "", "Mia, in a plain maid's uniform, carries a tray of champagne through the crowd.", 3.0),
    ("VICTORIA", "Mocking", "Careful, Mia. Those glasses cost more than you do.", 3.0),
    ("ACTION", "", "", "Victoria tips her glass and pours red wine down the front of Mia's uniform.", 2.5),
    ("MIA", "Shocked", "Why would you do that?", 2.0),
    ("VICTORIA", "Gloating, Cruel", "Because tonight everyone should see where you belong.", 3.2),
    ("MIA", "Trembling", "This was my mother's house.", 2.4),
    ("MRS. HALE", "Cold", "And now it is mine.", 2.0),
    ("ACTION", "", "", "Victoria raises her hand and slaps Mia hard across the face.", 1.5),
    ("SOUND FX", "", "", "A sharp slap echoes over the music; the crowd gasps.", 1.5),
    ("MIA", "Furious", "You knew he was mine before you ever met him!", 3.0),
    ("VICTORIA", "Smug", "Ethan is marrying me. Get used to it.", 2.6),
    ("MRS. HALE", "Shouting", "Security! Remove her!", 2.0),
    ("ACTION", "", "", "Two guards grab Mia by the arms and drag her toward the exit.", 3.0),
    ("ETHAN", "Low, Threatening", "Take your hands off her.", 2.2),
    ("CAMERA", "", "", "Close-up on Ethan stepping out of the elevator, jaw set.", 2.0),
    ("VICTORIA", "Confused", "Ethan? You said she was nobody.", 2.6),
    ("ETHAN", "Calm", "I said a lot of things to get close to your mother's accounts.", 3.4),
    ("MRS. HALE", "Alarmed", "What are you talking about?", 2.0),
    ("ETHAN", "Steely", "Mia is the real heir to Hale Group.", 2.6),
    ("ACTION", "", "", "The crowd falls silent as Mia stares at Ethan, stunned.", 2.5),
    ("MIA", "Breathless", "Who are you really?", 2.0),
    ("ACTION", "", "", "The elevator doors open behind them and a lawyer steps out holding a sealed envelope.", 3.0),
    ("SOUND FX", "", "", "An ominous low drone swells to a cliffhanger sting.", 2.0),
])
EP2 = ("The will is read in front of everyone, and Victoria refuses to lose.", [
    ("CAMERA", "", "", "Medium shot of the lawyer breaking the wax seal.", 2.5),
    ("LAWYER", "Formal", "The estate passes in full to Mia Hale.", 3.0),
    ("VICTORIA", "Outraged", "That is a forgery!", 2.0),
    ("ACTION", "", "", "Victoria snatches the will and tears it in half.", 2.0),
    ("LAWYER", "Dry", "That was a copy. The original is with the court.", 3.0),
    ("MRS. HALE", "Desperate", "Mia, darling, we are family.", 2.6),
    ("MIA", "Cold, Resolute", "You made me scrub your floors for six years.", 3.0),
    ("MIA", "Firm", "Get out of my mother's house.", 2.4),
    ("ACTION", "", "", "Police officers step onto the rooftop.", 2.0),
    ("OFFICER", "Authoritative", "Mrs. Hale, you are under arrest for fraud.", 3.0),
    ("MRS. HALE", "Screaming", "You can't do this to me!", 2.2),
    ("ACTION", "", "", "Ethan steps beside Mia and quietly takes her hand.", 2.5),
    ("ETHAN", "Gentle", "It's over.", 1.6),
    ("MIA", "Soft", "Is it?", 1.6),
    ("ACTION", "", "", "Behind them, Victoria pulls a small knife from her clutch, eyes wild.", 2.6),
    ("VICTORIA", "Venomous, Whispering", "It's not over until I say it is.", 2.8),
    ("ACTION", "", "", "Victoria lunges toward Mia's back.", 1.5),
    ("SOUND FX", "", "", "A sharp musical sting and cut to black.", 1.5),
])


def ts(t):
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


def build(num, logline, beats):
    t, lines = 0.0, [f"EPISODE NUMBER: Episode {num}", f"EPISODE LOGLINE: {logline}",
                     "CONTINUITY NOTES: Demo script written for testing.", "", "--- SCRIPT START ---", ""]
    body = []
    for b in beats:
        if len(b) == 5 and b[0] in ("CAMERA", "ACTION", "SOUND FX"):
            kind, _, _, text, d = b
            body += [f"**{kind}:**", f"Start: ({ts(t)}) | End: ({ts(t + d)})", text, ""]
        else:
            who, tags, text, d = b
            body += [f"**CAMERA:**", f"Start: ({ts(t)}) | End: ({ts(t + d + 0.3)})", f"Close-up on {who.title()}.", ""]
            body += [f"**{who} ({tags}):**", f"Start: ({ts(t + 0.1)}) | End: ({ts(t + d)})", f'"{text}"', ""]
            d += 0.3
        t += d
    lines += ["SCENE 01", "Scene heading: EXT. HALE TOWER ROOFTOP – NIGHT", f"Scene start: {ts(0)}",
              f"Scene end: {ts(t)}", "", "Actions and dialogue:", ""] + body + ["--- SCRIPT END ---"]
    return "\n".join(lines)


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "samples" / "demo_show.zip"
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("The Maid Was the Heiress/episode-001.txt", build(1, *EP1))
        z.writestr("The Maid Was the Heiress/episode-002.txt", build(2, *EP2))
    print("wrote", out)
