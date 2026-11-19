"""gta6-trophy-rarity-forecast-01: forecast each GTA VI trophy's Exophase earn rate.

Model (standard library only, deterministic, no network):
  A trophy's rate is earners / players-tracked, so the two are forecast
  separately and divided, instead of extrapolating the rate series itself.
  Exophase refreshes counts in jumps: when tracked players grow faster
  than earners, rates FALL, so a rate-only trend misses the dilution.

  For each trophy i and for players-tracked N, cumulative counts are
  modelled as power laws in (1 + hours since release):

      E_i(t) = E_i(last) * ((1 + h_t) / (1 + h_last)) ** gE_i
      N(t)   = N(last)   * ((1 + h_t) / (1 + h_last)) ** gN
      rate   = 100 * E_i(t) / N(t)

  gN is fit by least squares on log N vs log(1 + h) over the case's
  distinct reads (consecutive identical reads are de-duplicated first,
  because a stale Exophase page repeats the same numbers for hours and
  would otherwise drag every slope to zero), shrunk toward a prior.
  The fit uses the last 24 h of distinct reads when there are at least
  three of them -- launch night is a different regime from the days
  before the deadline -- and falls back to all distinct reads otherwise.
  gE_i is fit the same way on log earners (earners = rate * N / 100),
  shrunk toward a per-tier prior: late, hard trophies (platinum, gold)
  accumulate earners more slowly than early bronze ones.  With too few
  distinct reads to fit anything (the practice cases are one flat read),
  the priors carry the forecast and the spread below does the work.

  Spread, on the logit scale, is honest about three things the house
  baseline ignores: a random-walk term that grows with the horizon, a
  fixed refresh-jump term (rates move in steps at Exophase refreshes,
  not smoothly), and a data-scarcity term that widens the band when the
  case's history has few distinct reads.  A trophy already at ~100%
  keeps its median near 100% (every tracked player had earned it even
  after a 6x jump in tracked players) but gets a wider lower tail.

  Usage: mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0, 0.674, 1.645]

# Prior log-log growth slopes (earners vs 1 + hours since release).
TIER_PRIOR = {"platinum": 0.9, "gold": 1.0, "silver": 1.1, "bronze": 1.2}
GROWTH_N_PRIOR = 0.7
# How strongly a fitted slope counts, by number of distinct reads.
SHRINK_N = 3.0   # players-tracked series (one shared series)
SHRINK_E = 4.0   # per-trophy earners series (noisier)
# Spread, in logit units: random-walk variance per day, refresh-jump
# variance, and the data-scarcity term's base and per-missing-read part.
RW_VAR_PER_DAY = 0.20
REFRESH_VAR = 0.09
SCARCE_BASE = 0.30
SCARCE_PER = 0.50
SCARCE_READS = 6.0


def parse_time(text):
    """ISO 8601 UTC timestamp -> aware datetime."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def clamp(x, lo=0.01, hi=99.99):
    return min(hi, max(lo, x))


def logit(pct):
    p = clamp(pct)
    return math.log(p / (100 - p))


def inv_logit(lg):
    if lg >= 0:
        return 100 / (1 + math.exp(-lg))
    e = math.exp(lg)
    return 100 * e / (1 + e)


def round4(x):
    """x rounded to 4 decimals, half up (as the house baseline rounds)."""
    scaled = x * 10000
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 10000
    return int(value) if float(value).is_integer() else value


def ols_slope(xs, ys):
    """Least-squares slope of ys on xs; None when it cannot be fit."""
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / sxx


def shrink(fit, prior, n, shrink_k, lo, hi):
    """Blend a fitted slope with its prior; clip to a sane range."""
    if fit is None:
        return prior
    w = n / (n + shrink_k)
    return min(hi, max(lo, w * fit + (1 - w) * prior))


def distinct_reads(history):
    """Reads with a changed (players, rates) vector, first occurrence kept.

    A stale Exophase page repeats verbatim for hours; keeping every copy
    would weight a flat stretch as if it were many observations and drag
    every fitted slope toward zero.
    """
    out = []
    prev = None
    for read in history:
        key = (read["players_tracked"], tuple(read["rates"]))
        if key != prev:
            out.append(read)
            prev = key
    return out


def forecast_case(case, name):
    if case["levels"] != LEVELS:
        raise ValueError(f"{name} asks for levels {case['levels']}, not {LEVELS}")
    if not case["history"]:
        raise ValueError(f"{name} has no history")

    release = case.get("game", {}).get("release_date")
    if release:
        t0 = datetime.fromisoformat(release + "T00:00:00+00:00")
    else:
        t0 = parse_time(case["history"][0]["at"])

    def hours_since_release(when):
        h = (parse_time(when) - t0).total_seconds() / 3600.0
        return max(h, 0.0)

    reads = distinct_reads(case["history"])
    xs = [math.log1p(hours_since_release(r["at"])) for r in reads]

    # Fit on the last 24 h of distinct reads when there are enough of
    # them: launch night is a different regime (tiny tracked base, a
    # stale page that never moved) from the days before the deadline,
    # and the recent regime is what the next 4.5 days most resemble.
    # With too little recent data, fall back to all distinct reads.
    last_h = hours_since_release(case["history"][-1]["at"])
    recent = [(x, r) for x, r in zip(xs, reads) if last_h - (math.expm1(x)) <= 24.0]
    if len(recent) >= 3:
        fit_reads = [r for _, r in recent]
        fit_xs = [x for x, _ in recent]
    else:
        fit_reads, fit_xs = reads, xs

    # --- players-tracked growth -------------------------------------------
    log_n = [math.log(max(r["players_tracked"], 1)) for r in fit_reads]
    g_n = shrink(
        ols_slope(fit_xs, log_n), GROWTH_N_PRIOR, len(fit_reads), SHRINK_N, 0.0, 2.5
    )

    last = case["history"][-1]
    n_last = max(last["players_tracked"], 1)
    h_last = hours_since_release(last["at"])
    h_target = hours_since_release(case["target"])
    ratio = (1.0 + h_target) / (1.0 + h_last)
    n_target = n_last * (ratio ** g_n)

    days = case["horizon_minutes"] / 1440.0
    rows = []
    for i, trophy in enumerate(case["trophies"]):
        # Last non-null rate for this trophy (earlier reads may lack it).
        rate_last = None
        for read in reversed(case["history"]):
            if read["rates"][i] is not None:
                rate_last = read["rates"][i]
                break
        if rate_last is None:
            rate_last = 0.0
        e_last = max(rate_last / 100.0 * n_last, 0.5)

        # Earners series for this trophy, from the fitting reads that list it.
        ex, ey = [], []
        for read, x in zip(fit_reads, fit_xs):
            rate = read["rates"][i]
            if rate is None:
                continue
            ex.append(x)
            ey.append(math.log(max(rate / 100.0 * max(read["players_tracked"], 1), 0.5)))
        tier = trophy.get("tier", "bronze")
        prior = TIER_PRIOR.get(tier, 1.2)
        g_e = shrink(ols_slope(ex, ey), prior, len(ex), SHRINK_E, -0.2, 3.0)

        # A trophy at ~100% has earners == tracked players: its earners
        # grow with the player base, so its rate stays near 100%.
        near_full = rate_last >= 99.5
        if near_full:
            g_e = g_n

        e_target = e_last * (ratio ** g_e)
        if e_target > n_target:
            e_target = n_target
        rate_med = clamp(100.0 * e_target / n_target)
        centre = logit(rate_med)

        # --- honest spread -------------------------------------------------
        scarce = SCARCE_BASE + SCARCE_PER * max(0.0, 1.0 - len(ex) / SCARCE_READS)
        sigma = math.sqrt(RW_VAR_PER_DAY * days + REFRESH_VAR + scarce * scarce)
        sigma_lo = sigma + (0.6 if near_full else 0.0)
        sigma_hi = 0.3 if near_full else sigma

        qs = []
        prev_q = None
        for z in Z:
            s = sigma_lo if z < 0 else sigma_hi
            q = round4(inv_logit(centre + z * s))
            q = min(100.0, max(0.0, q))
            if prev_q is not None and q < prev_q:
                q = prev_q
            qs.append(q)
            prev_q = q
        rows.append({"id": trophy["id"], "q": qs})
    return {"trophies": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        out = OUTPUT_DIR / f"{path.stem}.out"
        out.write_text(json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
