# Promo Finder

Give it a season of timestamped microdrama screenplays and it returns a ranked list of 20–60 second
promo cuts. Each cut comes with:

- the episode and exact start/end of every segment
- the line it opens on and the moment it ends on
- a one-line reason it works
- anything an editor should check first

Built for Kuku's AI Generalist assignment (Problem 1, "Find the Promos").

**Live app:** https://kuku-promo-finder-by-himanshu.streamlit.app/

The web app uses Sarvam automatically: upload scripts, check the title and press **Find promos**.
The starting page has a working upload area, title field and Find promos button in the main
workspace. The sidebar offers the same workflow, with the current upload and title kept in sync.
Choose **New analysis** above any finished or failed report to return to a clean starting page.
Replacing scripts also clears the previous report; neither action calls the AI service.
There is no provider picker, public API-key field, model name or endpoint field. Configure the
server once with `SARVAM_API_KEY`; existing Sarvam `LLM_API_KEY` / `LLM_BASE_URL` secrets also work.
The sidebar contains only uploads, the show title and the primary action. The CLI defaults to
rules and retains other model adapters for reproducible comparisons and interview-time model swaps.

## Run it

Needs Python 3.11 or newer (tested on 3.11 and 3.13).

```bash
pip install -r requirements.txt

# Command line: a folder of episode .txt files, a .zip of them, or one .txt
python -m promo_finder "path/to/scripts-folder-or.zip" -o outputs

# Web app
streamlit run app.py
```

In the app, upload the .zip and press **Find promos**.
The tested Streamlit runtime is pinned to 1.67.0 for reproducible UI and uploader tests.

Kuku's script pack is confidential, so it isn't in this repo. To try the tool without it, use
`samples/demo_show.zip`. It's a two-episode test script written for this project. Upload that demo ZIP to the app to test the real AI workflow, or run it offline with the CLI.

## What you get

| File | What it is |
|---|---|
| `promo_report.html` | The report an editor reads: ranked promos, a season map and the best clip per episode. For each promo it shows the score breakdown, what to check, and the full cut line by line. |
| `promos_ranked.csv` | The ranked list in posting order: segments, hook, cliffhanger, why, flags, scores |
| `promos_by_episode.csv` | The best usable clip in every episode |
| `all_candidates.csv` | Every scored cut, so you can see why something did or didn't make the list |
| `promos.json` | Everything above plus the transcript of each cut |
| `promos.md` | A short text summary |
| `quality_checks.md` | Every promo re-checked against the script after the run |
| `run_log.txt` | What the run did, including any warnings about the input |

## How it works

1. **Parse (code).** Each script becomes a list of timed beats: dialogue, action, camera, sound, with
   speaker and emotion tags. The parser warns about blocks it can't time, duplicate episode numbers
   and files with no beats; it doesn't drop them silently.
2. **Score beats (rules).** Word lists in `promo_finder/lexicon.py` score each beat for hook strength,
   cliffhanger strength, intensity and "needs backstory". The show's premise is read from the title
   and the first episodes' loglines, so nothing is tuned to one show.
3. **Try every legal cut (code).** It tries every hook × cliffhanger pair in an episode. A cut must be
   20–60 s, hook within 3 s, never cut inside a spoken line, and start and end on real script
   timestamps. It also builds stitched promos: a hook from one moment plus a payoff from a later one.
4. **Rank (rules).** A score made of hook 28%, cliffhanger 24%, momentum 20%, new-viewer clarity 16%,
   length fit 6% and premise 6%. A greedy pick then:
   - skips overlapping cuts;
   - allows at most one single clip per episode;
   - refuses two promos built on the same hook or cliffhanger line.

   Posting order gives a small boost to early-season promos, since a viewer who taps through lands there.
5. **Check (code).** After the run, every promo is checked again against the script. Soft risks become
   plain-language flags for the editor, for example "Opens mid-conversation" or "From late in the
   season (Ep 40): may spoil or need context".
6. **AI review.** Sarvam reviews the shortlist in the web app. See below for CLI model options.
7. **Human.** An editor picks from the list, fixes flagged cuts and cuts the actual video.

## AI review and CLI model options

```bash
export SARVAM_API_KEY=...          # set your key locally; never commit it
python -m promo_finder scripts.zip -m sarvam -o outputs_ai
python -m promo_finder scripts.zip -m sarvam --compare -o outputs_ai   # also writes ai_vs_rules.md / .csv
```

| `-m` / `--model` | Needs |
|---|---|
| `rules` (default) | nothing |
| `sarvam` (recommended, default model `sarvam-105b`) | `SARVAM_API_KEY`; uses Sarvam credits |
| `gemini` (default model `gemini-3.8-flash`) | `GEMINI_API_KEY` |
| `groq` (default model `openai/gpt-oss-120b`) | `GROQ_API_KEY`; account free-plan limits apply |
| `openai:<model>` | `OPENAI_API_KEY` |
| `anthropic:<model>` | `ANTHROPIC_API_KEY` |
| `openrouter:<model>` | `OPENROUTER_API_KEY` |
| `ollama:<model>` | a local Ollama server |
| `custom:<model>` | `LLM_BASE_URL` + `LLM_API_KEY` (any OpenAI-compatible API) |
| `mock` | nothing. A fake judge for tests: its scores mean nothing and every output says so. |

**What the model is allowed to do.** It gets the top 50 shortlisted cuts (40 single clips, 10 stitched).
For each one it sees the numbered transcript and the three beats that come right after the cut.
It returns 1–10 scores, a reason and a risk, and may point at beat numbers to trim to.

**What it isn't allowed to do.**

- It never writes a timestamp. Code looks up every time and quote in the script.
- A suggested trim that breaks a hard rule is rejected.
- Its score is blended 50/50 with the rules score, so one odd reply can't push a weak cut to the top.

**When it fails.**

- With no key, it says so and ranks with rules only.
- Rate limits and server errors get at most one retry. A `Retry-After` over 5 s returns an error
  rather than blocking the interactive run. Request timeouts are not retried.
- A malformed reply keeps that cut's rules score.
- After 3 unusable reviews in a row it stops calling. If no review succeeded, it finishes on rules;
  otherwise the report identifies a partial AI review.
- An invalid key, exhausted credits, denied access or missing model (HTTP 401/402/403/404) stops
  further calls immediately. The app never switches to another external provider automatically.
- Empty, reasoning-only and token-truncated compatible-API responses are rejected as ratings.
- The report header always shows which mode produced the ranking.

**Cost.** I measured the prompts with a test transport on the 50-episode pack: 50 calls of about 3,000
characters each. That's roughly 38k input tokens and about 4k output tokens per show (estimated at
4 characters per token).

- At Sarvam's published `sarvam-105b` price (INR 15 input / 5 cached input / 60 output per 1M
  tokens), that illustrative workload is about INR 0.81 before additional reasoning, retries and tax.
  This is an estimate, not a live billing measurement. Rates checked 7 November 2026:
  https://docs.sarvam.ai/api/getting-started/pricing
- The compatible-API path records reported input/output, cached and reasoning tokens. Reasoning
  tokens are already included in output tokens, so they are not counted twice in the cost estimate.
  Sarvam cost estimates appear in the run log and report; the provider dashboard is authoritative.
- Sarvam calls are spaced at least 1 s apart. Groq's default is 30 s for short candidate prompts;
  account token limits can still trigger retries. Diagnostics record every candidate; the UI
  presents stage and clip progress without exposing those raw lines.
  The AI phase stops starting new reviews after 60 s; an in-flight request still has to finish.
  Sarvam connect/read inactivity timeouts are 5/35 s, not a strict wall-clock deadline.
  Other providers retain their 5/20 s inactivity timeouts.
  The first request timeout stops the AI run; it does not repeat that wait for more candidates. Remaining
  candidates keep their rules scores. Run time includes model latency and retries.
- Sarvam reviews default to V1 with `reasoning_effort: null` (the documented thinking-off switch)
  and a 768-token JSON response cap. These requests need a short rating object, not a long reasoning
  trace. Legacy Sarvam credentials are accepted on the V1 review path. An explicit owner
  `SARVAM_BASE_URL` override is respected; V2 does not
  receive the V1 thinking switch. This aims to reduce response overhead, but live latency has not
  been verified by these simulated tests. Groq GPT-OSS retains a 2,048-token completion cap.
  V1 reference: https://docs.sarvam.ai/api-reference/chat/chat-completions-v1

**Status.** Sarvam API-contract and Streamlit integration checks use simulated HTTP responses;
no live model or real API key was used for those checks. They test request format, token accounting,
fallback, rejected replies and timestamp guards, not editorial quality. After adding your key, upload
the demo ZIP and use **Find promos**, then run the full input pack with comparison enabled
and manually review the results.
An AI reviewer cannot recover a strong moment excluded by the rules shortlist; inspect excluded cuts too.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

The tests cover:

- **Bad input:** missing timestamps, wrong time formats, `HH:MM:SS` times, duplicate or missing episode
  numbers, missing scene headers, action-only scripts, a broken zip.
- **Unusual episodes:** very short and very long episodes, a calm episode with no promo, numbering
  that starts at 51.
- **Ranking:** no overlapping or repeated promos, and the checker catching invalid cuts.
- **AI judge:** rejecting invalid AI trims, odd and broken AI replies, the AI being unable to move a
  timestamp, the circuit breaker, 429 retries, missing-key fallback.
- **End to end:** determinism, the CLI, and the Streamlit app running the demo.
- **Sarvam integration:** request format, usage/cost accounting, credential redaction, immediate
  stop on invalid credentials/exhausted credits, empty/truncated replies and the Streamlit secret path.

## Deploy (free)

**Streamlit Community Cloud:**

1. Push this repo to GitHub.
2. In Streamlit Community Cloud, choose **Create app**, pick the repo, and set the main file to `app.py`.
3. Under **App settings → Secrets**, add `SARVAM_API_KEY = "your-key"` and save. Copy the
   format from `.streamlit/secrets.toml.example`, replacing the placeholder only inside Streamlit.
4. Reboot the app once after this update so every Python module reloads. The sidebar shows
   **AI review enabled** when a server credential is configured; this is configuration status,
   not a live authentication or balance check. The page never exposes the stored key.
5. Upload the demo ZIP or real scripts and click **Find promos**. Check successful review
   counts and reported usage. The baseline comparison is included automatically
   for the assignment. Download the report, JSON and comparison CSV into a private submission folder.

Optional owner setting: `SARVAM_MODEL` can be `sarvam-105b` (default) or
`sarvam-105b-conversations`. The app selects a supported endpoint automatically. Other provider
adapters are CLI-only and are not offered in the public web interface.

## Editor interface and usage

The sidebar contains upload, show title and Find promos only. It has no balance card, manual
balance snapshot, provider/model/key controls, preferences panel, sample button or technical footer.
The opening screen explains the task without displaying a previous sample as a new result.
During processing, one compact card shows Read scripts → Find moments → Review clips → Prepare
report. Clip counts come from real pipeline events; only successful reviews advance the clip bar.
It shows no model IDs, trope labels, raw HTTP errors or expanding diagnostic transcript. Logs are
retained in the collapsed Run details / Checks panels and downloadable reports.

When no AI review succeeds, the app shows a failure state and troubleshooting details. It does
not present a completed AI report or export buttons. An explicitly selected **Show backup ranking**
option exposes the rules fallback without making another API request. Partial AI coverage is labelled.

Token usage and estimated cost remain in the downloadable report and the collapsed run log under
Checks, rather than in the everyday editor flow. There is no invented zero-cost or remaining-balance
claim when usage is unavailable. The app does not scrape or invent a wallet endpoint.

## Confidentiality

Everything generated from the real scripts quotes them, so all of it is git-ignored:

- `data/` (the script pack) and any `.zip` except the demo
- `outputs/` and `evaluation/`
- the solution PDF and its HTML source

Share those through a private link. No API key is stored in the repo; `.env.example` lists the
variable names only.

## Known limits

- The input is the script, not the footage. The tool can't tell whether a visual hook reads on screen,
  so those promos are flagged.
- The word lists are English and tuned to romance and revenge microdramas. An episode built on a theme
  they don't cover can get no clip (one episode in the test pack got none).
- In rules mode, the "why it works" line is a template and is sometimes wrong. See
  `evaluation/spot_check_top16.md`.
- Scores rank cuts within one show. They are not a prediction of views or installs.

## Project map

```
promo_finder/
  parser.py      screenplay → timed beats; input warnings
  lexicon.py     the editable word lists: hook words, cliffhanger cues, themes, context words
  scoring.py     beat scores and the show's premise
  candidates.py  single and stitched cuts, hard rules, promo score, flags
  rank.py        selection, posting order, "why" lines
  llm.py         AI judge with guardrails
  usage.py       server-side Sarvam configuration
  compare.py     rules-only vs AI ranking on the same scripts
  checks.py      post-run checks
  report.py      HTML / CSV / JSON / Markdown
  ui.py          shared HTML components for the report and the app
  cli.py         command line
app.py           Streamlit app
docs/            solution doc source and PDF build script
samples/         demo script (written for this project)
static/          fonts (Inter and JetBrains Mono, SIL Open Font License) and icon
tests/
```

