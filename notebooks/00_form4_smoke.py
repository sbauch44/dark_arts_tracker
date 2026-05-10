# %% [markdown]
# # 00 — Form 4 smoke test
#
# Phase 0 deliverable per `docs/plan.md` §6:
# *"Scratch notebook successfully pulls a single Form 4 via datamule and parses it."*
#
# Pulls a small batch of EKSO Bionics Form 4s from Nov-Dec 2025 (the window
# Mike Puangmalai flagged for the PSU grant), parses the XML into a flat
# polars frame, and prints the parsed transactions.
#
# This file is jupytext-formatted (cells marked with `# %%`). Open in VS Code
# or Jupyter directly, or run as a plain script: `python notebooks/00_form4_smoke.py`.

# %%
from __future__ import annotations

from typing import Any

import datamule
import polars as pl

from dark_arts.parse.form4 import parse_form4_xml
from dark_arts.paths import RAW

# %% [markdown]
# ## Pull via datamule
#
# `datamule.Portfolio(path)` is the entry point: it owns a local directory
# (one tar per submission) and exposes `.download_submissions(...)` plus
# iteration that yields `Submission` -> `Document` objects.
#
# We anchor on EKSO Bionics — Walker / Mike's Nov 2025 PSU example — and
# narrow to a 2-month filing window so the smoke test stays cheap (~8 filings,
# a few seconds).

# %%
TARGET_CIK = "0001549084"  # EKSO Bionics Holdings, Inc.
FILING_DATES = ("2025-11-01", "2025-12-31")

portfolio = datamule.Portfolio(str(RAW))
portfolio.download_submissions(
    cik=TARGET_CIK,
    submission_type="4",
    filing_date=FILING_DATES,
    quiet=True,
)

# %% [markdown]
# ## Parse the Form 4 XML
#
# `parse_form4_xml` lives in `dark_arts.parse.form4` (lifted out of this
# notebook in Phase 1). It returns one dict per non-derivative + derivative
# transaction with the per-filing footnote blob attached. See
# `tests/test_form4_parse.py` for the full schema contract.

# %% [markdown]
# ## Walk the portfolio and parse every Form 4 doc
#
# Iterating a `Submission` yields `Document`s whose `.content` is raw bytes.
# We keep only `type == '4'` XML docs (ignore the index headers etc.).

# %%
all_rows: list[dict[str, Any]] = []
for sub in portfolio:
    for doc in sub:
        if doc.type == "4" and doc.extension == ".xml":
            all_rows.extend(parse_form4_xml(doc.content))

print(f"Parsed {len(all_rows)} transaction(s) across {len(list(portfolio))} submission(s).")

# %% [markdown]
# ## As a polars frame
#
# This is the shape Phase 1 will write to `data/parquet/grants.parquet`,
# minus a few derived columns (accession_number, filed_at) we'll thread in
# from the submission metadata once the schema is finalised.

# %%
df = pl.DataFrame(
    [{k: v for k, v in r.items() if k != "footnotes"} for r in all_rows],
    infer_schema_length=None,
)
with pl.Config(tbl_cols=-1, tbl_width_chars=160, fmt_str_lengths=40):
    print(df)

# %% [markdown]
# ## Sanity check
#
# We expect:
# * Issuer = `EKSO BIONICS HOLDINGS, INC.`, ticker `EKSO`.
# * Multiple insiders (CEO + directors) reporting in this window.
# * Footnotes referencing PSU vesting / hurdles on at least some rows.

# %%
unique_owners = df.select("owner_name").unique().to_series().to_list()
print("Distinct reporting owners in window:", unique_owners)

footnote_blobs = [r["footnotes"] for r in all_rows if r["footnotes"]]
print(f"\nRows with footnotes: {len(footnote_blobs)} / {len(all_rows)}")
if footnote_blobs:
    sample_id, sample_text = next(iter(footnote_blobs[0].items()))
    print(f"Sample footnote {sample_id}: {sample_text[:300]}")

# %% [markdown]
# ## Next
#
# * ✅ Parser lifted into `src/dark_arts/parse/form4.py` with tests.
# * Pull the full case-study set (the 9 named tickers) and confirm we get
#   what we expect for KODK Jul 2020, STMP 2019, LHCG Mar 2022, etc.
# * Build the LLM extractor for footnote text (Phase 1).
