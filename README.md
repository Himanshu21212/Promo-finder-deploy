Promo Finder: Summary

In short: Promo Finder turns a season of timestamped microdrama screenplays into a ranked shortlist of 20–60 second promo cuts, each with exact source timestamps. Code handles parsing, candidate generation, and validation. In the web app, Sarvam AI reranks the shortlist. An editor makes the final call.

Built for Kuku’s AI Generalist assignment (Problem 1: “Find the Promos”).
Live app - https://kuku-promo-finder-by-himanshu.streamlit.app/
Repository - https://github.com/Himanshu21212/Promo-finder-deploy

What each promo includes
Episode and exact start/end timestamps for every segment
Opening hook and ending cliffhanger
Why it may work
Editorial flags, such as late-season spoilers, slow stretches, or missing context
Transcript and score breakdown

Promos can be single continuous clips or stitched from multiple moments.

How to use it
Upload a ZIP of episode files, or individual TXT files.
Check the show title.
Click Find promos. Nothing runs before this step.
Follow the stages: Read scripts → Find moments → Review clips → Prepare report.
Review the report and download outputs.
Click New analysis to start over.
Results: full 50-episode run
Metric	Result
Episodes parsed	50
Timed screenplay beats	3,727
Story duration	102.7 minutes
Candidates generated	14,247 (1,425 single, 12,822 stitched)
Ranked promos	26, one from each of 26 episodes
Episodes with a usable single clip	49 of 50
Hard-rule checks	58 of 58 passed
Runtime	3.0 seconds

Important: This is a rules-only baseline. It is not an AI-reviewed result.

Scaling (throughput only): 100 episodes took 5.3 seconds and 200 took 9.9 seconds. The test used copies of one show, not independent shows.

How ranking works

The rules score weights six factors:

Hook: 28%
Cliffhanger: 24%
Momentum: 20%
New-viewer clarity: 16%
Length fit: 6%
Premise fit: 6%

Pipeline: Parse (code) → Score beats (rules) → Generate candidates (code, with hard constraints) → Rank → Validate and flag (code) → AI review (web app only) → Human decision

AI guardrails
The AI cannot invent timestamps. Code checks every timestamp and quote against the source.
Invalid trims are rejected.
The AI score is blended 50/50 with the rules score, so one odd reply cannot push a weak cut to the top.
The report states the ranking mode and whether AI coverage was complete or partial.
Failures are shown as failures, never as successful AI reports. Retries are capped, and a circuit breaker stops repeated bad reviews.
Testing

64 tests passed. They verify software behavior: malformed input handling, timestamp protection, fallback logic, and rate-limit handling. They do not measure promo quality or real AI accuracy.

Limitations to know before presenting
It reads screenplay text, not footage. It cannot tell whether a visual hook works on screen.
The English lexicons are tuned mainly to romance and revenge microdramas. Other genres may be under-ranked.
In rules-only mode, the “why it works” explanations are templated and can be inaccurate.
A structurally valid promo is not necessarily emotionally compelling or likely to convert.
Scores rank candidates within one show. They do not predict views or revenue.
There is no live AI quality evaluation yet. That requires a successful live run and human review.
The AI can only rerank candidates it receives. It cannot recover moments excluded during generation.

Cost estimate
About ₹0.81 for a 50-episode AI review, based on roughly 37.6k input and 3.9k output tokens. This excludes retries and tax.
This is a prompt-size estimate, not a billing measurement. The Sarvam dashboard is authoritative.

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
tools/           benchmark and prompt measurement utilities

