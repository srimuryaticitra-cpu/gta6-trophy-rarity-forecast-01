# Build log — gta6-trophy-rarity-forecast-01

## Steps (in order)

1. Read the kit: `RULES.txt` in full, the house baseline in both
   `starter/main.ts` and `starter/main.py`, `input/NOTICE.txt`, and the
   practice cases `p00.in` / `p01.in`. Did not read `competition.yaml`.
2. Inspected the practice data: both histories are a single distinct read
   (638 players tracked, identical rates, 7–8 repeated reads). No growth
   signal exists in the practice — any slope must come from priors, and
   the spread must cover the refresh jump the practice straddles.
3. Chose Python (`main.py`), deleted `main.ts`. Wrote the first version
   of the model: separate earners / players-tracked power-law forecasts,
   de-duplication of stale identical reads, per-tier prior shrinkage,
   near-100% trophy handling, and a three-part logit spread
   (random walk + refresh jump + data scarcity).
4. Ran it on both practice cases: valid outputs, byte-identical across
   two runs, ~0.07 s. Compared band widths against the house baseline
   run on the same cases (mean 90% band 2.58 vs 0.41 logit units).
5. Revised the model (second edit of `main.py`): the growth fits now use
   the last 24 h of distinct reads when at least three exist, falling
   back to all distinct reads otherwise — launch night is a different
   regime from the days before the deadline. Removed an unused variable
   and documented the window in the module docstring.
6. Re-ran validation: practice outputs unchanged (the fallback path is
   identical with one distinct read), still valid and deterministic.
7. Built a synthetic final-like case (120 reads over 60 h, N growing
   638 → ~21k, per-tier earner growth, 4.5-day horizon) to exercise the
   fitting path the practice cannot: valid output, sensible medians
   (platinum 5.33% → 11.0%), mean 90% band width 3.41 logit units.
8. Wrote `README.md`, this `transcript.md`, and `.makefun/owner.json`
   in this session. Committed locally (no push, no submit).

## Modelling decisions

- **Earners and tracked players separately.** A rate is a ratio; when
  tracked players grow faster than earners, rates fall. The house
  baseline (persistence) and the house curve baseline (rate trend) both
  miss this dilution. The 04:30Z refresh proved it: 638 → 3,868 tracked
  and every rate but the 100% one fell.
- **Power laws in (1 + hours since release).** Cumulative unlock counts
  grow sub-linearly in log time; the form saturates naturally and
  extrapolates to the 4.5-day horizon better than a straight line in
  logit(rate).
- **De-duplicate stale reads.** Exophase repeats the same page for
  hours; keeping every copy would weight a flat stretch as many
  observations and flatten every fitted slope toward zero.
- **Last-24 h fitting window.** The final case's history spans launch
  night (tiny base, stale page) to the deadline; the recent regime is
  what the next 4.5 days most resemble.
- **Per-tier prior shrinkage.** Platinum/gold earners accumulate slower
  than early bronze ones. Priors carry the forecast only when the
  history is too thin to fit (the practice); with a rich final history
  the fits dominate (shrink weight n/(n+4)).
- **Honest spread.** Too narrow pays for every trophy outside the band
  (the house baseline scored 0% coverage on the practice refresh); too
  wide pays at every trophy. The spread grows with horizon, adds a
  fixed refresh-jump term, and widens when distinct reads are scarce.
- **The 100% trophy stays near 100%.** It held 100% even after tracked
  players grew 6x, so its earners track the player base; only its lower
  tail is widened.

## Validation numbers

- Practice p00/p01: valid outputs, 55 rows each, byte-identical across
  two runs, ~0.07 s for both cases, files 2,802 / 2,784 bytes.
- Median logit shift vs last read (practice): +0.23 (prior drift).
- Mean 90% band width, practice: 2.58 logit units (house: 0.41).
- Synthetic final-like case: valid, platinum median 5.33% → 11.0%,
  mean 90% band width 3.41 logit units, ~0.07 s.
- Practice pinball loss: not scored — answers are held by the house;
  the live Exophase page is not the practice answer, so no loss is
  claimed and none was fetched.
