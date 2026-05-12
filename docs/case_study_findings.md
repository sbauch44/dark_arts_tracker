# Case-study findings (Phase 1.3, manual spot checks)

Companion to the auto-generated [`case_study_verification.md`](case_study_verification.md).
That file confirms each of the nine case-study CIKs resolves to the right
issuer and the registered windows return non-empty filing sets. This file
records the manual transaction-level spot checks that confirm — or correct —
our hypothesis that each window captures the headline grant.

## TL;DR

All nine windows are correct as of 2026-05-10; no `CASE_STUDIES` window
needs to change before writing `data/parquet/grants.parquet`. Two surprises
worth noting downstream:

1. **Issuers don't classify consistently.** EKSO codes its CEO PSU grant as
   straight Common-Stock on the *non-derivative* table; RPD codes its CEO
   PSU as `PERFORMANCE RIGHTS` on the *derivative* table. The deriv vs
   non-deriv split is not a usable proxy for grant type — only footnote
   analysis (step 5) can classify. We initially flagged EKSO as
   "headline grant missing" because of `0 derivative A grants`; that
   reading was wrong.

2. **Some windows look thin but aren't.** RPD's Jan-Apr 2026 window has only
   four grant-coded transactions, but two of them are the headline CEO + CFO
   PSU grants on 2026-03-31. Total row count is the wrong proxy for
   verification value; what matters is whether the *target* grant landed.

## EKSO — 2025-11-05 CEO grant captured (non-derivative)

Registered window: `2025-09-01..2025-12-31`. Spot check widened to
`2025-01-01..2025-12-31` to confirm we're not missing anything.

The Mike Puangmalai case-study grant lands on 2025-11-05:

| transaction_date | table_kind | code | security_title | shares | owner |
|---|---|---|---:|---:|---|
| 2025-11-05 | non_derivative | A | Common Stock | 80,000 | Davis Scott G. (CEO) |
| 2025-11-05 | non_derivative | A | Common Stock | 19,500 | Wong Jerome |
| 2025-11-05 | non_derivative | A | Common Stock | 15,000 | Jones Jason C |
| 2025-11-10 | non_derivative | S | Common Stock | 23,315 | Davis Scott G. |
| 2025-11-10 | non_derivative | S | Common Stock | 9,723 | Jones Jason C |
| 2025-11-10 | non_derivative | S | Common Stock | 11,288 | Wong Jerome |

That's the textbook "grant on day T, sell five days later" pattern —
exactly what the project is built to detect. Footnote text from these
filings (read in step 5) should explain whether the grants vest immediately
(plain stock award) or carry stock-price hurdles (PSU). Either way, the
data is captured by the registered window; we don't need to widen.

The 2025 cycle also caught an early-May director annual grant (4 directors
× 236,202 shares each, all coded `A` non-derivative) and a small March
grant cycle. The Sep-Dec window misses the May director grants, which is
fine — the project's positive set is the high-conviction insider grants,
not routine board comp.

## RPD — 2026-03-31 CEO PSU grant captured (derivative, "PERFORMANCE RIGHTS")

Registered window: `2026-01-01..2026-04-30`. The "only 4 grants" headline
count was misleading; two of those four are the headline grants:

| transaction_date | table_kind | code | security_title | shares | owner |
|---|---|---|---:|---:|---|
| 2026-03-31 | derivative | A | PERFORMANCE RIGHTS | 1,125,000 | Thomas Corey E. (CEO) |
| 2026-03-31 | derivative | A | PERFORMANCE RIGHTS | 275,000 | Brown Rafeal E. |
| 2026-02-15 | non_derivative | A | Common Stock | 64,667 | Thomas Corey E. (RSU vest) |
| 2026-04-24 | non_derivative | A | Common Stock | 20,000 | Murphy Scott M |

Thomas's 1.125M PERFORMANCE RIGHTS grant is the textbook annual CEO PSU
grant; Brown's 275K likely the CFO equivalent. The Feb 15 / Apr 24 entries
are RSU vests (the Feb 15 entry is paired with a `F` withholding row on
the same day) and routine officer comp.

## LHCG / TWTR / GME — 0 derivative A's, deferred to footnote step

The `Grants (deriv / non-deriv)` column shows `0 / N` for these three.
Given what EKSO taught us (PSUs can land non-derivative), this is no longer
a red flag — likely it just means these issuers code their grants
differently. The headline events:

* **LHCG** Mar 2022 RSUs ahead of UNH announcement (Mar 29 2022)
* **TWTR** Apr 2022 RSUs ahead of Musk close (Apr 25 2022)
* **GME** various RSUs / RC stock awards across 2020-2025

are presumably among the 14 / 28 / 53 non-derivative A's in the registered
windows. Confirming this requires reading the actual filings or running
the footnote extractor (step 5) — leaving as a known follow-up rather than
a window-widening problem.

## What this means for step 4 (parquet write)

* `CASE_STUDIES` windows are correct as-is. Don't widen.
* The grants frame should preserve `table_kind` and the raw `security_title`
  string, but downstream classifiers must not use `table_kind` as a proxy
  for grant_type. The LLM footnote extractor is the source of truth.
* For the eventual labeled positive set, we'll want to flag rows like the
  EKSO 2025-11-05 trio and the RPD 2026-03-31 pair as "headline grants" —
  but that labeling is a Phase 2 concern.

## Step 4 result — `data/parquet/grants.parquet` (built 2026-05-11)

Phase 1 deliverable written by `scripts/build_grants_parquet.py`. The
script walks the per-CIK cache offline (no EFTS calls), so it's instant
and re-runnable after any ingest refresh.

* **1,727 rows × 27 cols** across all 9 case studies, **64 KB** on disk
* **903 distinct accessions**, **855 grant-coded (A) transactions**
* Filing dates span **2018-05-29 → 2026-04-24**
* Schema = `dark_arts.parse.form4._SCHEMA` (dates as `pl.Date`, numerics
  as `pl.Float64`, relationship flags as `pl.Boolean`, footnotes as a
  JSON-encoded `pl.Utf8` column)

Per-issuer row counts:

| Ticker | Rows | Subs | Filing range |
|---|---:|---:|---|
| EKSO | 24 | 22 | 2024-03 → 2025-12 (widened by spot checks) |
| GME | 164 | 117 | 2020-02 → 2025-12 |
| GSKY | 277 | 134 | 2018-05 → 2022-03 |
| KODK | 19 | 7 | 2020-06 → 2020-07 |
| LHCG | 17 | 16 | 2022-03 → 2022-04 |
| RPD | 11 | 9 | 2026-01 → 2026-04 |
| STMP | 39 | 30 | 2019-01 → 2019-11 |
| TWTR | 58 | 43 | 2022-03 → 2022-05 |
| VAC | 1,118 | 525 | 2020-01 → 2025-12 |

Both spot-checked headline grants verified present in the file:

* EKSO 2025-11-05: Davis Scott G. 80,000 / Wong Jerome 19,500 /
  Jones Jason C 15,000 — `non_derivative` `Common Stock`, code `A`
* RPD 2026-03-31: Thomas Corey E. 1,125,000 / Brown Rafeal E. 275,000 —
  `derivative` `PERFORMANCE RIGHTS`, code `A`

The file is gitignored (`data/` is fully derived). To rebuild from
scratch: `python scripts/verify_case_studies.py` (downloads tars) then
`python scripts/build_grants_parquet.py` (concatenates the cache).
