# ADR-0001: Storage layer is parquet + DuckDB, not Postgres

**Status:** accepted
**Date:** 2026-05-08

## Context

The pipeline reads ~500k Form 4s/year, ~6k DEF 14As/year, plus 8-Ks, S-4s,
13Ds. Total historical corpus 2015–present is on the order of low millions of
filings. Each parsing/feature/scoring stage reads its inputs, runs a
deterministic transform, and writes outputs. The downstream consumers are
analytical queries and ML model fits — not OLTP.

The default instinct on a project this size is "stand up a Postgres." That
brings real costs:

* A long-running server to manage, secure, and back up.
* Schema migrations as the feature set evolves (and it will, weekly, in early
  phases).
* An ORM or hand-written SQL layer between the analytical code and the data.
* Worse columnar scan performance than a parquet+vectorized-engine stack for
  the queries we actually run.

## Decision

Storage layer is **parquet files on disk, queried with DuckDB and polars**.
No RDBMS.

* Each pipeline stage writes a parquet table (or partitioned dataset) to
  `data/parquet/<stage>/<table>.parquet`.
* DuckDB queries them in place — no ingestion step.
* Polars is the in-memory frame library for transforms.
* `data/duckdb/dark_arts.duckdb` is a single optional DuckDB file holding
  views over the parquet tables for ad-hoc exploration; it is rebuildable.

## Consequences

**Good:**

* Reproducibility comes free — re-running the pipeline regenerates every
  table from raw filings + code.
* Schema evolution is "rewrite the parquet"; no migration framework needed.
* Zero ops surface: no daemon, no auth, no port, no backup story beyond
  `data/`.
* Columnar scans on the actual hot paths (forward-return joins, decile
  groupbys) are faster than row-oriented Postgres without effort.
* Notebooks read the same files production code reads.

**Bad / accepted trade-offs:**

* No transactional semantics. We rely on stage idempotency: a partial
  parquet write is detected and re-run rather than rolled back.
* No concurrent writers. Fine — the cron is single-process.
* Updates ("change row 47 of grants") are awkward. We don't update; we
  recompute. Acceptable given dataset size and immutable filing inputs.
* If we ever need to expose the data over a network or to another service,
  we'll need an export step. Out of scope for v1.

## Revisit when

* Live monitoring outgrows a single host (Phase 8+).
* We start needing multi-user concurrent annotation of the watchlist.
* Parquet rewrite costs dominate iteration time on rebuild_features.
