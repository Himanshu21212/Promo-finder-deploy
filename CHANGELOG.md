# Changelog

## Review pass (Nov 2026)

A review and polish of the first submission. It keeps the same pipeline, scoring weights and output
files.

### Fixed

- **Repeated story beats.** Two ranked promos could be built on the same line (two clips from one
  episode shared an opening line). Selection now refuses a promo whose hook or cliffhanger line already
  appears in another ranked promo.
- **Input problems were silent.** Blocks without a time, inverted times, files with no beats,
  duplicate episode numbers and missing episode numbers now produce warnings. They show up in the
  app, on stderr and in `run_log.txt`.
- **Episode files.** Duplicate episode files were both loaded; now the one with more beats is kept.
  `HH:MM:SS` timestamps are now parsed instead of ignored.
- **Season position.** "Early episode" and "late-season spoiler" assumed the season starts at Ep 1.
  They now use the loaded range, so a pack numbered 51–100 works.
- **AI judge:**
  - a non-numeric score ("8/10", "85") no longer crashes the run;
  - after an AI trim the promo is rescored, and the hook and cliffhanger must sit inside the new cut;
  - a missing key falls back to rules with a clear message;
  - 429 and 5xx responses are retried, honouring `Retry-After`;
  - a circuit breaker stops after 3 connection failures in a row;
  - calls are spaced for free tiers;
  - the run reports which mode actually produced the ranking.
- **API keys in the app.** Keys were put into `os.environ`, which is shared across sessions on a
  hosted app. They're now passed straight to the judge and never cached to disk in the app.
- **Speed on long seasons.** Stitched-promo search grew faster than linearly. Capping its candidate
  pools brought 200 episodes from 28 s to about 16 s, with no change to the 50-episode ranking.
- **Smaller fixes:**
  - the setup-objects flag didn't match its score penalty;
  - the best-clip-per-episode list mixed AI-blended and rules-only scores;
  - `.gitignore` excluded the demo script the app needs;
  - the report overflowed sideways on phones.

### Added

- **Rules vs AI comparison** (`--compare`, and a tab in the app). It shows:
  - top-10 overlap and rank correlation;
  - what entered or left the top 10;
  - where the two disagree most.
- **A `mock` judge for testing.** Every output it touches is labelled as fake.
- **Explanations in the report and app:**
  - a score breakdown for each promo (each part × its weight, plus the early-episode boost);
  - a table of segment cut points;
  - an episode index.
- **App:** a "By episode" view with the best clip and other candidates for any episode, plus an
  "All candidates" filter.
- **Tests:** 24 new tests (29 in total) for:
  - bad and unusual input;
  - overlapping and invalid cuts;
  - AI failure modes;
  - the CLI;
  - the Streamlit app.
- **Tools and setup files:**
  - `tools/bench.py` and `tools/measure_prompt.py`;
  - `requirements-dev.txt` and `.env.example`;
  - a PDF build that fills every number from the outputs and stops if a cut point in the doc doesn't
    match them.

### Changed

- **Wording.** Plain language throughout: flags, "why" lines and labels. For example, "She is left at
  the altar" replaces "Jilted at the altar — instant, universal injustice".
- **Less scrolling.** The ranked list in the app and the report is now one row per promo (opens on → cuts on, cut
  points, length, score, notes). Click a row for the full details. The report went from about 17,100 px
  to 8,000 px tall on a laptop screen, and the per-episode table is one line per episode.
- **Visual style.** Gradients, glow and decorative icons are gone. The app's first screen is now a
  short how-to and an example promo instead of a marketing page.
- **AI defaults.** The default Gemini model is now `gemini-3.8-flash`. The AI judge also sees the
  three beats right after a cut, so it can tell whether the ending is really unresolved.
- **The solution doc:**
  - corrected the run time, check count and spot-check wording;
  - removed the editor-time claim, which was never measured;
  - stated plainly that no AI model was run and how Claude was used.

### Removed

- `docs/make_map_svg.py`, which nothing used.
