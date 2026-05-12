"""Phase 1.4: build ``data/parquet/grants.parquet`` from the per-CIK cache.

Walks ``data/raw/form4/<cik>/`` for each ticker in
:data:`dark_arts.ingest.form4.CASE_STUDIES`, parses every cached Form 4
via :func:`iter_form4_rows`, concatenates into one typed polars frame, and
writes the Phase 1 deliverable.

Pure cache-reader — no EFTS / network calls — so the build is instant and
offline once :mod:`scripts.verify_case_studies` (or another ingest pass)
has populated the per-CIK tars. Re-run after any new ingest to refresh
the file; the write is atomic per polars semantics.

Schema and dtypes are defined by
:func:`dark_arts.parse.form4.form4_rows_to_frame`. We pull every cached
row per issuer (no window filter) so the deliverable includes any ad-hoc
spot-check pulls in addition to the registered case-study windows — the
LLM footnote extractor (step 5) wants as much data as we've got.
"""
from __future__ import annotations

import sys
import time

import datamule
import polars as pl

from dark_arts.ingest.form4 import CASE_STUDIES, iter_form4_rows, portfolio_dir_for_cik
from dark_arts.parse.form4 import form4_rows_to_frame
from dark_arts.paths import PARQUET

GRANTS_PATH = PARQUET / "grants.parquet"


def main() -> int:
    t0 = time.time()
    frames: list[pl.DataFrame] = []

    for cs in CASE_STUDIES:
        pdir = portfolio_dir_for_cik(cs.cik)
        tars = [p for p in pdir.iterdir() if p.suffix == ".tar"]
        if not tars:
            print(
                f"=> {cs.ticker:6s} {cs.cik}  no cached tars — "
                f"run scripts/verify_case_studies.py first",
                file=sys.stderr,
            )
            continue

        portfolio = datamule.Portfolio(str(pdir))
        rows = list(iter_form4_rows(portfolio))
        df = form4_rows_to_frame(rows)
        print(
            f"=> {cs.ticker:6s} {cs.cik}  "
            f"{len(tars):>4d} tars  "
            f"{df['accession_number'].n_unique():>4d} subs  "
            f"{df.height:>5d} tx",
            flush=True,
        )
        frames.append(df)

    if not frames:
        print("No cached data found for any case study.", file=sys.stderr)
        return 1

    grants = pl.concat(frames, how="vertical").sort(
        ["issuer_cik", "filed_at", "transaction_date", "accession_number"]
    )

    GRANTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    grants.write_parquet(GRANTS_PATH)

    elapsed = time.time() - t0
    size_kb = GRANTS_PATH.stat().st_size / 1024
    print()
    print(f"Wrote {grants.height} rows x {grants.width} cols to {GRANTS_PATH}")
    print(f"  size: {size_kb:.1f} KB    build: {elapsed:.1f}s")
    print(f"  issuers: {grants['issuer_cik'].n_unique()}    "
          f"distinct accessions: {grants['accession_number'].n_unique()}")
    print(f"  filed_at: {grants['filed_at'].min()} → {grants['filed_at'].max()}")
    print()
    print("Tx codes:")
    code_counts = (
        grants.group_by("transaction_code")
        .agg(pl.len().alias("n"))
        .sort("n", descending=True)
    )
    for row in code_counts.iter_rows(named=True):
        print(f"  {row['transaction_code']!s:>6s}  {row['n']:>5d}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
