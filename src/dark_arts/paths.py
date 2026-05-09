"""Canonical filesystem paths for the pipeline.

The ``data/`` tree is fully gitignored and treated as a derived artifact
of the code + raw filings. Importing this module ensures the directories
exist; nothing else in the package should mkdir directly.
"""

from __future__ import annotations

from pathlib import Path

# Repo root = parent of src/. This file lives at src/dark_arts/paths.py,
# so go up three levels.
REPO_ROOT = Path(__file__).resolve().parents[2]

DATA = REPO_ROOT / "data"
RAW = DATA / "raw"            # SGML/HTML/XML blobs from EDGAR via datamule
PARQUET = DATA / "parquet"    # parsed structured tables (grants, comp tables, ...)
LABELED = DATA / "labeled"    # labeled positive/negative training sets
DUCKDB = DATA / "duckdb"      # optional DuckDB views over the parquet tables

DOCS = REPO_ROOT / "docs"

_ALL_DIRS = (DATA, RAW, PARQUET, LABELED, DUCKDB)


def ensure_dirs() -> None:
    """Create every data directory if missing. Idempotent."""
    for d in _ALL_DIRS:
        d.mkdir(parents=True, exist_ok=True)


# Cheap enough to do on import — this module is only imported by code that
# is about to read or write a data file.
ensure_dirs()
