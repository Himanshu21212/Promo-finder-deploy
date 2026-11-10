# Promo Finder

Turns a season of microdrama scripts into an editor-ready shortlist of 20–60 second promo cuts, ranked for hooks and cliffhangers. Timestamped scripts and subtitle files give exact cut points; standard screenplays without timestamps get clearly labelled estimated timing.

**Live app:** [kuku-promo-finder-by-himanshu.streamlit.app](https://kuku-promo-finder-by-himanshu.streamlit.app/) · **Repository:** [github.com/Himanshu21212/Promo-finder-deploy](https://github.com/Himanshu21212/Promo-finder-deploy)

Built for Kuku's AI Generalist assignment (Problem 1: "Find the Promos").

## How it works

1. **Parse (code):** Scripts become timed beats (dialogue, action, camera, sound). Several layouts are read; see [Supported script formats](#supported-script-formats).
2. **Score (rules):** Editable lexicons rate hook strength, cliffhangers, and intensity.
3. **Generate (code):** Single and stitched cuts are built under hard rules: 20–60 seconds, hook within 3 seconds, valid timestamps, no cut inside a spoken line.
4. **Rank (rules):** Hook 28%, cliffhanger 24%, momentum 20%, new-viewer clarity 16%, length fit 6%, premise fit 6%.
5. **Validate (code):** Every selected cut is re-checked against the source. Soft risks are flagged for the editor.
6. **AI review (web app or optional CLI):** Sarvam reranks up to 50 candidates. Its score is blended 50/50 with the rules score.
7. **Human decision:** The editor reviews the shortlist and makes the final selection.

**Guardrails:** The AI cannot invent timestamps, invalid trims are rejected, and failures are shown as failures, never as successful AI reports. The only times not copied from a script are the estimated ones for screenplays that have no timestamps, and those are labelled on every cut.

## Supported script formats

Upload a `.zip` of episodes or individual `.txt`, `.srt` or `.vtt` files (50 MB per file). Each file is read with the first layout that fits:

| Layout | Example | Cut points |
|---|---|---|
| Promo Finder format (original) | `**MIA (Shocked):**` then `Start: (00:11.40) \| End: (00:13.30)` | Exact |
| Timed labels, other styles | `MIA (Shocked):` + `Start: 00:11 \| End: 00:13`, or `[00:11 - 00:13] MIA: line`, or `00:11 --> 00:13` | Exact |
| SRT / WebVTT subtitles | `00:00:11,400 --> 00:00:13,300` + `MIA: line` (VTT `<v Mia>` voice tags supported) | Exact |
| Standard screenplay, no timestamps | `EXT. ROOFTOP - NIGHT`, `MIA`, `(shocked)`, dialogue, action paragraphs | **Estimated** |

- **Estimated timing** uses about 2.5 spoken words per second for dialogue and 1.5–6 seconds per action line. The report shows a banner, and every affected cut carries a check note (also in CSV, JSON, HTML and PDF) telling the editor to match it to the video. Notes never change scoring or ranking.
- **Episode numbers** come from an `EPISODE NUMBER: Episode 3` or `EPISODE 3` line, or from file names such as `episode-003`, `ep03`, `S01E03` or `03 - Title`.
- **Not supported:** plain chat-style scripts with no times (`Mia: line`), and Word or PDF script files. Lines in subtitles with no speaker name are shown as "Voice".

## Quick start

Requires Python 3.11+.

```bash
pip install -r requirements.txt

# Rules-only run (no API key needed)
python -m promo_finder samples/demo_show.zip -m rules -o outputs_rules

# Web app
streamlit run app.py
```

**AI review with Sarvam:**

```bash
export SARVAM_API_KEY="your-key"
python -m promo_finder samples/demo_show.zip -m sarvam -o outputs_sarvam
```

`samples/demo_show.zip` is a two-episode demo written for this project. Use it instead of real screenplays.

**CLI model options:** `rules` (default), `sarvam`, `gemini`, `groq`, `openai:<model>`, `anthropic:<model>`, `openrouter:<model>`, `ollama:<model>`, `custom:<model>`, `mock` (test only).

## Web app

- **Home:** upload scripts, add an optional show title, and choose **Find Promos**.
- **How it Works:** a step-by-step guide to the pipeline.
- **Report:** ranked promos, top pick, best clip per episode, season map, all candidates, quality checks, and rules vs AI.
- **Downloads:** Report (PDF), Report (HTML), Ranked list (CSV) and Everything (JSON), plus per-tab CSVs (best clip per episode, rules vs AI).
- Works on desktop and phone layouts. Sidebar actions: **New analysis** and re-running with a different show title.

## Outputs

The CLI writes these files to the output folder:

| File | Purpose |
|---|---|
| `promo_report.html` | Interactive report with ranked promos, flags, and transcripts |
| `promos_ranked.csv` | Ranked promo list with segments, hook, cliffhanger, and scores |
| `promos_by_episode.csv` | Best usable single clip per episode |
| `all_candidates.csv` | Candidate records retained by the reporting pipeline |
| `promos.json` | Structured results and run metadata |
| `promos.md` | Compact text summary |
| `quality_checks.md` | Hard checks and soft editorial flags |
| `run_log.txt` | Run summary, mode, counts, and warnings |

## Results: full 50-episode baseline (rules-only)

| Metric | Result |
|---|---|
| Episodes parsed | 50 |
| Timed screenplay beats | 3,727 |
| Story duration | 102.7 minutes |
| Candidates generated | 14,247 (1,425 single, 12,822 stitched) |
| Ranked promos | 26 (one from each of 26 episodes) |
| Episodes with a usable single clip | 49 of 50 |
| Hard-rule checks | 58 of 58 passed |
| Runtime | 3.0 seconds |

This is a rules-only baseline and is not an AI-reviewed result. Scaling test (copies of one show, throughput only): 100 episodes took 5.3 s and 200 took 9.9 s.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Latest recorded run (Nov 2026): 74 tests, 67 passed. `tests/test_formats.py` covers every supported script layout and the estimated-timing labels, and `tests/test_smoke.py` covers the PDF report. Seven Streamlit app-interface tests in `test_usage.py`, `test_edge_cases.py` and `test_sarvam.py` fail; they were already failing before the November UI and parser changes and need updating to the current interface. The tests cover software behavior and guardrails. They do not measure promo quality or live AI accuracy.

## Deploy on Streamlit Community Cloud

1. Push this repository to GitHub.
2. Create an app from the repository and set `app.py` as the main file.
3. In **App settings → Secrets**, add `SARVAM_API_KEY = "your-key"`.
4. Reboot the app after changing secrets.

Optional: set `SARVAM_MODEL` to `sarvam-105b` (default) or `sarvam-105b-conversations`.

## Project structure

```
promo_finder/
  parser.py      scripts → timed beats (Promo Finder, timed-label, SRT/VTT and screenplay layouts); input warnings
  lexicon.py     hook words, cliffhanger cues, themes, context words
  scoring.py     beat scores and show premise
  candidates.py  single/stitched cuts, hard rules, candidate scores, flags
  rank.py        selection, posting order, rationale
  llm.py         AI judge and guardrails
  usage.py       server-side Sarvam configuration and usage
  compare.py     rules-only vs AI comparison
  checks.py      post-run validation
  report.py      PDF / HTML / CSV / JSON / Markdown exports
  ui.py          shared report and app UI components
  cli.py         command-line interface
app.py           Streamlit application
docs/            solution document source and PDF build script
samples/         demo screenplay ZIP
static/          fonts (Inter, JetBrains Mono, DejaVu Sans for PDFs) and app assets
tests/           automated tests
tools/           benchmark and prompt measurement utilities
```

## Limitations

- Analyzes screenplay text, not finished footage. It cannot judge whether a visual hook works on screen.
- Estimated timing for screenplays without timestamps is approximate. Editors must match those cut points to the video.
- Subtitle files usually have no emotion tags or action lines, so their promos tend to score lower than full screenplays.
- Hindi and other non-Latin scripts can be read, but the hook and cliffhanger lexicons are English and the PDF font does not include Devanagari.
- English lexicons are tuned mainly to romance and revenge microdramas. Other genres may be under-ranked.
- Rules-only "why it works" explanations are templated and can be inaccurate.
- Scores rank candidates within one show. They are not predictions of views or revenue.
- The AI can only rerank candidates it receives.
- No live AI quality evaluation has been completed yet. That requires a successful live run and human review.

## Confidentiality

Kuku's original screenplays are confidential and are not included in this repository. Outputs generated from real scripts reproduce screenplay content and should not be committed. Keep API keys in Streamlit secrets or local environment variables.
