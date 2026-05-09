# dark-arts-tracker

Detect MNPI-adjacent equity grants and other corporate dark-arts patterns from
SEC filings. Personal research project — flagging system, not auto-execution.

See [`docs/plan.md`](docs/plan.md) for the full project plan, signal taxonomy,
and phased build schedule.

## Status

**Phase 0** — scaffolding. The pipeline is not yet runnable end-to-end.

## Quick start

```bash
# install (creates .venv, installs all deps + dev extras)
uv sync --all-extras

# activate
source .venv/bin/activate

# sanity check
python -c "import dark_arts; print(dark_arts.__version__)"
```

## Layout

```
src/dark_arts/   package code (one submodule per pipeline stage)
docs/            plan, feature spec, labeling protocol, ADRs
scripts/         cron entry points (refresh_filings, score_today, ...)
notebooks/       exploratory work
tests/           pytest suite
data/            gitignored — raw filings, parquet, duckdb, labeled sets
```

## Pipeline

```
EDGAR ──ingest──▶ raw/ ──parse──▶ parquet/ ──label──▶ labeled/
                                            └──features──▶ features/
                                                          └──score──▶ scores/
                                                                      ├──backtest
                                                                      ├──watchlist
                                                                      └──alert
```

Storage layer is parquet + DuckDB; see [ADR-0001](docs/decisions/0001-parquet-duckdb-not-postgres.md).

## Development

```bash
ruff check .
ruff format .
pytest
```

## Disclaimer

This tracker reads public SEC filings and computes signals from them. Nothing
in this repo is investment advice. Outputs are research notes. Position-sizing
and execution are out of scope by design.
