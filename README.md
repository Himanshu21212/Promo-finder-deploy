# Promo Finder

Give it a season of timestamped microdrama screenplays and it returns a ranked list of 20–60 second
promo cuts. Each cut comes with:

- the episode and exact start/end of every segment
- the line it opens on and the moment it ends on
- a one-line reason it works
- anything an editor should check first

Built for Kuku's AI Generalist assignment (Problem 1, "Find the Promos").

**Live app:** https://kuku-promo-finder-by-himanshu.streamlit.app/ (preview the sample report)

The web app uses Sarvam automatically: upload scripts, check the title and press **Find promos with AI**.
There is no provider picker, public API-key field, model name or endpoint field. Configure the
server once with `SARVAM_API_KEY`; existing Sarvam `LLM_API_KEY` / `LLM_BASE_URL` secrets also work.
The offline sample preview never spends credits. The CLI still defaults to rules and retains
other model adapters for reproducible comparisons and interview-time model swaps.

## Run it

Needs Python 3.11 or newer (tested on 3.11 and 3.13).

```bash
pip install -r requirements.txt

# Command line: a folder of episode .txt files, a .zip of them, or one .txt
python -m promo_finder "path/to/scripts-folder-or.zip" -o outputs

# Web app
streamlit run app.py
```

In the app, upload the .zip and press **Find promos with AI**.
The tested Streamlit runtime is pinned to 1.67.0 for reproducible UI and uploader tests.

Kuku's script pack is confidential, so it isn't in this repo. To try the tool without it, use
`samples/demo_show.zip`. It's a two-episode test script written for this project. In the app, the
**Preview sample report** button runs it offline and labels the result as a sample.

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
  account token limits can still trigger retries. Every candidate reports progress and errors.
  The AI phase stops starting new reviews after 60 s; an in-flight request still has to finish.
  HTTP connect/read inactivity timeouts are 5/20 s, not a strict wall-clock deadline. Remaining
  candidates keep their rules scores. Run time includes model latency and retries.
- Sarvam requests require JSON output and cap output at 4,096 tokens, including reasoning where
  applicable. Groq GPT-OSS uses low reasoning effort and a 2,048-token completion cap.

**Status.** Sarvam API-contract and Streamlit integration checks use simulated HTTP responses;
no live model or real API key was used for those checks. They test request format, token accounting,
fallback, rejected replies and timestamp guards, not editorial quality. After adding your key, upload
the demo ZIP and use **Find promos with AI**, then run the full input pack with comparison enabled
and manually review the results. **Preview sample report** always stays offline.
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
   **Sarvam AI enabled** when a server credential is configured; this is configuration status,
   not a live authentication or balance check. The page never exposes the stored key.
5. Upload the demo ZIP or real scripts and click **Find promos with AI**. Check successful review
   counts and reported usage. Keep **Include baseline comparison** under Output preferences enabled
   for the assignment. Download the report, JSON and comparison CSV into a private submission folder.

Optional owner setting: `SARVAM_MODEL` can be `sarvam-105b` (default) or
`sarvam-105b-conversations`. The app selects a supported endpoint automatically. Other provider
adapters are CLI-only and are not offered in the public web interface.

## Credits and live usage

- The sidebar updates estimated spend, API request count and reported tokens after each response.
  It records API-reported usage even when a response cannot become a valid rating.
- **View actual balance in Sarvam** opens the official dashboard. There is no documented public
  balance endpoint in the API reference reviewed for this implementation. The app does not invent
  one, scrape authenticated billing pages, or claim its counters are an organisation-wide live wallet.
- Sarvam has one shared organisation balance, covering all workspaces and products:
  https://docs.sarvam.ai/api/platform/billing
- For an estimate of remaining credits, enter the latest dashboard balance under **Update balance
  snapshot**. The estimate subtracts subsequently reported spend in this browser session only.
  It excludes tax and activity by other users, applications or sessions. It resets on a new browser
  session/server restart and when the configured credential changes.
- Rerendering the page does not count a run twice. If any later request has missing/incomplete usage,
  the remaining estimate becomes unavailable until a fresh dashboard snapshot is saved.
- A 402 response is shown as exhausted credits and stops further API requests for that run.
- No balance is hardcoded from an old screenshot. No credentials or account balance are cached globally.

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
  usage.py       Sarvam configuration and session-only usage / balance estimates
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

