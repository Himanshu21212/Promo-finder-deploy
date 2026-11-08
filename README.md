Promo Finder

Turn a season of timestamped microdrama screenplays into an
editor-ready shortlist of 20--60 second promos.

Promo Finder parses screenplay files, finds potential hooks and
cliffhangers, generates valid promo cuts, ranks them, and produces a
reviewable report with exact source timestamps. The Streamlit app uses
Sarvam AI for editorial reranking; deterministic rules and code
remain responsible for parsing, candidate generation, timestamp
integrity, and hard validation.

Live app: https://kuku-promo-finder-by-himanshu.streamlit.app/\
Repository: https://github.com/Himanshu21212/Promo-finder-deploy

Built for Kuku's AI Generalist assignment --- Problem 1: "Find the
Promos".
What the product does
Upload a ZIP of episode .txt screenplays (or individual .txt files),
provide or edit the show title, and select Find promos.

The tool returns ranked 20--60 second promo candidates. Each promo
includes:
- Episode and exact start/end timestamp for every segment
- The opening hook and ending cliffhanger
- A concise explanation of why the moment may work as a promo
- Editorial flags and checks for issues such as late-season spoilers,
  slow stretches, or references that may need context
- A transcript of the selected cut and its score breakdown
It supports both continuous single-episode cuts and stitched promos
assembled from multiple moments. An editor remains responsible for
reviewing the shortlist and selecting the final footage.
Current web-app experience
The current Streamlit interface is designed around one central workflow:
1. Upload screenplay ZIP/TXT files in the main workspace.
2. Check or edit the show title.
3. Select Find promos to start the analysis.
4. Follow the top-of-page processing stages: Read scripts → Find
   moments → Review clips → Prepare report.
5. Explore the generated report and download the available outputs.
6. Select New analysis to clear the current files and begin another
   run.
The interface includes a mascot, a centred upload/action area, seven
report tabs, and four primary export formats. The sidebar provides
current analysis context and report settings. Provider, model, API-key,
endpoint, and billing controls are not exposed to reviewers.

Uploading or removing files, changing the title, or resetting the
workspace does not itself trigger an AI request. The review starts only
when Find promos is selected. If AI review fails, the app shows a
failure state rather than presenting a failed run as a successful AI
report. A rules-only backup ranking can be explicitly requested where
available.

The hosted app is configured to use Sarvam automatically. Configure the
server with SARVAM_API_KEY; legacy Sarvam LLM_API_KEY /
LLM_BASE_URL secrets are also supported. The CLI retains model
adapters for reproducible comparisons and interview-time model swaps.
Full input-pack baseline run
A fresh, unedited rules-only CLI run was completed on the full
50-episode Kuku input pack. This is the reproducible baseline included
in the raw-output archive; it is not represented as a live AI
evaluation.

  Measure                                                    Result
  Episodes parsed                                                50
Timed screenplay beats                                      3,727
Story duration                                      102.7 minutes
Single-clip candidates generated                            1,425
Stitched candidates generated                              12,822
Total candidates generated                                 14,247
Ranked promos selected                                         26
Episodes represented in ranked list                            26
Episodes with at least one usable single clip            49 of 50
Automatic hard-rule checks                        58 of 58 passed
Rules-only run time in this run                       3.0 seconds

The 58 hard-rule checks cover the selected promo cuts: duration (20--60
seconds), hook within the first three seconds, valid screenplay
timestamps, no cut inside a spoken line, and segment ordering. These are
structural checks, not proof that every promo is editorially effective.

The best-clip-per-episode export contains 49 episodes. Episode 50 did
not yield a usable single-clip candidate under the current rules. The
ranked list contains 26 selected promos across 26 episodes.
Scaling benchmark
The rules-only benchmark processed repeated copies of the same show's
episodes. It is a throughput check, not a test across independent shows.
  Input size   Candidates   Runtime

 50 episodes       14,247     2.6 s
100 episodes       29,083     5.3 s
200 episodes       52,716     9.9 s
The separate full-pack run recorded 3.0 seconds. Runtime varies by
environment.
How it works
1. Parse (code). Each screenplay becomes timed beats such as
   dialogue, action, camera, and sound, with speaker and emotion tags.
   The parser reports untimed blocks, duplicate episode numbers, and
   files with no usable beats instead of silently dropping them.
2. Score beats (rules). Editable lexicons score hook strength,
   cliffhanger strength, intensity, and dependence on backstory. The
   show's premise is inferred from its title and early loglines rather
   than hard-coded for one show.
3. Generate candidates (code). The system tests hook/cliffhanger
   combinations and creates single and stitched cuts. Hard constraints
   require a 20--60 second duration, a hook within three seconds, valid
   source timestamps, and no cut inside a spoken line.
4. Rank candidates. The rules score combines hook (28%),
   cliffhanger (24%), momentum (20%), new-viewer clarity (16%), length
   fit (6%), and premise fit (6%). Selection avoids overlapping cuts,
   repeated hook/cliffhanger lines, and excessive single-episode
   duplication. Posting order gives a modest preference to
   earlier-season moments.
5. Validate and flag (code). Every selected cut is checked again
   against the source screenplay. Soft risks are surfaced as
   editor-facing flags, for example a late-season moment that may spoil
   a reveal or a clip that opens mid-conversation.
6. AI editorial review (web app / optional CLI). Sarvam reviews the
   shortlist and can score editorial strength, explain its judgement,
   flag risks, and suggest trims using numbered screenplay beats.
7. Human decision. The editor reviews the ranked list, checks the
   flags and source context, and makes the final selection before
   editing footage.
AI review and guardrails
The web app uses Sarvam for AI reranking. The model reviews a shortlist
of up to 50 cuts (40 single clips and 10 stitched clips). It receives
the numbered transcript and nearby context, then returns structured
ratings, a reason, a risk, and optional beat references for a trim.

The model is deliberately constrained:
- It cannot invent timestamps. Code resolves every timestamp and quote
  against the original screenplay.
- A suggested trim that violates a hard rule is rejected.
- The AI score is blended with the rules score (50/50) so one unusual
  model response cannot independently push a weak cut to the top.
- The report identifies the ranking mode and whether AI coverage was
  complete or partial.
Failure handling
- If no key is configured, the system reports that AI is unavailable
  and can use rules-only ranking.
- Rate limits and server errors receive at most one retry; long
  Retry-After values do not hold up the interactive run.
- Malformed or unusable model replies do not become ratings; the
  affected candidate retains its rules score.
- Repeated unusable reviews trigger a circuit breaker.
- Invalid credentials, exhausted credits, denied access, or missing
  models stop further calls; the app does not silently switch to
  another provider.
- Request timeouts stop the AI run rather than repeatedly waiting on
  more candidates.
Evidence and limitations of the AI evaluation
The included full 50-episode raw-output archive is explicitly a
rules-only baseline (model: rules, real_ai_calls: 0). The
automated Sarvam integration tests use simulated HTTP responses to test
request formatting, usage accounting, error handling, fallback, and
timestamp guards. They do not measure real-model editorial quality.

The deployed app is configured for Sarvam AI reranking, but the
full-pack baseline archive must not be interpreted as an AI-reviewed
result. A real AI quality comparison requires a successful live run, its
unedited outputs, and human review of the resulting clips.

An AI reviewer cannot recover a strong moment that candidate generation
excluded. For that reason, excluded candidates should also be inspected
during evaluation.
Cost and runtime notes
A prompt-size simulation on the 50-episode pack measured 50
candidate-review prompts, approximately 3,007 input characters per call
on average. It estimated roughly 37.6k input tokens and 3.9k output
tokens for the show. This is a prompt-size estimate, not a live model
usage measurement.

At the published Sarvam sarvam-105b rates checked on 7 November 2026,
that illustrative token workload was estimated at approximately ₹0.81
before additional reasoning, retries, and tax. This is not a live
billing measurement; the provider dashboard is authoritative.

Sarvam requests are spaced at least one second apart. The AI phase stops
starting new reviews after its configured review budget; an in-flight
request still needs to finish. Actual run time depends on model latency,
retries, and provider availability.

References: - Sarvam pricing:
https://docs.sarvam.ai/api/getting-started/pricing - Sarvam Chat
Completions V1:
https://docs.sarvam.ai/api-reference/chat/chat-completions-v1
Outputs
The app and CLI generate downloadable artifacts, including:
  File                                Purpose
  promo_report.html                 Interactive/editor-facing report
with ranked promos, season
overview, score breakdowns, flags,
and cut transcripts

  promos_ranked.csv                 Ranked promo list with segments,
hook, cliffhanger, rationale,
flags, and scores

  promos_by_episode.csv             Best usable single clip per episode

  all_candidates.csv                Export of candidate records
retained by the reporting pipeline;
see run metadata for total
generated candidates

  promos.json                       Structured results, selected-cut
transcripts, scores, and run
metadata

  promos.md                         Compact text summary

  quality_checks.md                 Post-run hard checks and soft
editorial flags
run_log.txt                       Run summary, mode, counts, and
warnings
The raw-output archive also includes console output, test results,
scaling benchmark, prompt-size simulation, and provenance metadata.
Run locally
Requires Python 3.11 or newer.
pip install -r requirements.txt

# CLI: a folder of episode .txt files, a ZIP, or one .txt file
python -m promo_finder "path/to/scripts-folder-or.zip" -o outputs

# Streamlit web app
streamlit run app.py
To try the workflow without Kuku's confidential screenplay pack, use
samples/demo_show.zip, a two-episode demo script written for this
project.
# Rules-only baseline
python -m promo_finder samples/demo_show.zip -m rules -o outputs_rules

# Sarvam AI review
export SARVAM_API_KEY="your-key"
python -m promo_finder samples/demo_show.zip -m sarvam -o outputs_sarvam

# Compare rules and AI rankings
python -m promo_finder samples/demo_show.zip -m sarvam --compare -o outputs_compare
Do not commit API keys. The hosted Streamlit app reads secrets from
server-side configuration.
Model adapters
The CLI supports the following model choices:
  -m / --model                    Configuration
  rules (default)                   No API key required

  sarvam                            SARVAM_API_KEY

  gemini                            GEMINI_API_KEY

  groq                              GROQ_API_KEY

  openai:<model>                    OPENAI_API_KEY

  anthropic:<model>                 ANTHROPIC_API_KEY

  openrouter:<model>                OPENROUTER_API_KEY

  ollama:<model>                    Local Ollama server

  custom:<model>                    LLM_BASE_URL and LLM_API_KEY
for an OpenAI-compatible endpoint
mock                              Test-only fake judge; its scores
are not real AI evaluations
The public web interface does not expose a provider picker. It uses the
configured Sarvam service. Other adapters are available through the CLI
for local experiments and model comparisons.
Tests
Run:
pip install -r requirements-dev.txt
python -m pytest -q
The latest recorded test run completed with 64 passed.

Coverage includes malformed screenplay inputs, unusual episode lengths,
duplicate/missing episode numbering, ranking constraints, invalid AI
trims, malformed model replies, timestamp protection, rate-limit
handling, missing-key fallback, circuit breaking, Streamlit upload/reset
flows, and Sarvam integration behavior using simulated responses.

These tests establish software behavior and guardrails; they do not
establish promo conversion performance or live AI editorial accuracy.
Deploy on Streamlit Community Cloud
1. Push the repository to GitHub.
2. In Streamlit Community Cloud, create an app from this repository and
   set app.py as the main file.
3. In App settings → Secrets, add:
   SARVAM_API_KEY = "your-key"
4. Reboot the app after changing secrets.
5. Open the app, upload the demo ZIP or permitted screenplay files, and
   select Find promos.
6. Review the report and download the outputs.
The sidebar's AI-enabled indicator reflects server configuration; it is
not a live authentication or account-balance check. The stored key is
not shown in the public interface.

Optional owner setting: SARVAM_MODEL supports sarvam-105b (default)
or sarvam-105b-conversations. The app selects a supported endpoint
automatically. Other model adapters are CLI-only.
Confidentiality
Kuku's original screenplay pack is confidential and is not included in
this repository. Outputs generated from the real scripts quote or
reproduce screenplay content and should be shared only through the
private assignment-submission link, not committed to the public
repository.

The repository does not contain API keys. Keep SARVAM_API_KEY in
Streamlit secrets or a local environment variable. The input pack,
generated outputs, evaluation artifacts, and solution document should
remain excluded from public version control.
Known limitations
- The tool analyses screenplay text, not finished footage. It cannot
  verify whether a visual hook is clear or compelling on screen.
- The current English lexicons are tuned primarily to romance and
  revenge microdramas; unfamiliar genres or story structures may be
  under-ranked or missed.
- Rules-only "why it works" explanations are templated and can be
  inaccurate.
- Structural validity does not guarantee that a promo is emotionally
  compelling, self-contained, or likely to convert viewers.
- Scores rank candidates within a show; they are not predictions of
  views, installs, or revenue.
- A model can only rerank candidates it receives; it cannot recover
  moments omitted during candidate generation.
- The full-pack raw-output evidence is rules-only. Real AI editorial
  quality still needs a successful live run and independent
  human/editor validation.
Project structure
promo_finder/
  parser.py      screenplay → timed beats; input warnings
  lexicon.py     hook words, cliffhanger cues, themes, context words
  scoring.py     beat scores and show premise
  candidates.py  single/stitched cuts, hard rules, candidate scores, flags
  rank.py        selection, posting order, rationale
  llm.py         AI judge and guardrails
  usage.py       server-side Sarvam configuration and usage
  compare.py     rules-only vs AI comparison
  checks.py      post-run validation
  report.py      HTML / CSV / JSON / Markdown exports
  ui.py          shared report and app UI components
  cli.py         command-line interface
app.py           Streamlit application
docs/            solution document source and PDF build script
samples/         demo screenplay ZIP
static/          fonts and app assets
tests/           automated tests
tools/            benchmark and prompt measurement utilities

Project owner: Himanshu
Kuku assignment: AI Generalist --- Problem 1, Find the Promos
