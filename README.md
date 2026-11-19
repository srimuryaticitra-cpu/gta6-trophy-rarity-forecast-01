# GTA VI Trophy Rarity Forecaster

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/srimuryaticitra-cpu/gta6-trophy-rarity-forecast-01/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/srimuryaticitra-cpu/gta6-trophy-rarity-forecast-01/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

Forecasts every GTA VI (PS5) trophy's Exophase earn rate at
2026-11-26T00:00:00Z as five quantiles (5%, 25%, 50%, 75%, 95%),
for bounty `gta6-trophy-rarity-forecast-01` on make.fun.

## The model

A trophy's rate is earners / players-tracked, so the two are forecast
separately and divided instead of extrapolating the rate series.
Exophase refreshes counts in jumps: when tracked players grow faster
than earners, rates **fall**, so a rate-only trend misses the dilution.

- Cumulative earners `E_i(t)` and players-tracked `N(t)` are each modelled
  as a power law in `(1 + hours since release)`, fit by least squares on
  log-log scale over the case's distinct reads.
- Consecutive identical reads are de-duplicated first: a stale Exophase
  page repeats verbatim for hours and would otherwise drag every fitted
  slope to zero.
- The fit uses the last 24 h of distinct reads when there are at least
  three of them (launch night is a different regime from the days before
  the deadline); otherwise it falls back to all distinct reads.
- Fitted slopes are shrunk toward per-tier priors (platinum 0.9, gold 1.0,
  silver 1.1, bronze 1.2 for earners; 0.7 for players-tracked).
- A trophy already at ~100% keeps its median near 100% (its earners grow
  with the player base) with a wider lower tail.
- Spread, on the logit scale, combines a random-walk term that grows with
  the horizon, a fixed refresh-jump term, and a data-scarcity term that
  widens the band when the history has few distinct reads. The practice
  cases are a single flat read, so the priors carry the median and the
  wide band does the work of covering the refresh the practice straddles.

## How to run

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Python 3.13, standard library only, no network, deterministic.
Reads every `*.in` in the input directory, writes one `.out` per case.

## Validation (local, practice cases p00/p01)

- Outputs valid: yes — one row per trophy (55), ids 1–55 each once,
  quantiles non-decreasing in 0–100, files 2,802 / 2,784 bytes (< 65,536).
- Byte-identical across two runs: yes (`diff -r` clean).
- Runtime: ~0.07 s for both cases together (limit 8 s per case).
- Median vs last read (logit shift): +0.23 (prior-driven drift; the
  practice histories are a single flat read, so no slope can be fit).
- Mean 90% band width (logit units): 2.58 vs the house baseline's 0.41
  on the practice — the house band scored 0% coverage on the refresh,
  this one is built to cover it.
- Synthetic final-like case (120 reads over 60 h, 4.5-day horizon):
  valid, medians rise sensibly (platinum 5.33% → 11.0%), mean 90% band
  width 3.41 logit units, runtime ~0.07 s.
- Pinball loss on the practice: **not scored** — the practice answers
  are held by the house and the live Exophase page is not the practice
  answer, so no loss figure is claimed.
