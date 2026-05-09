# %% [markdown]
# # 00 — Form 4 smoke test
#
# Phase 0 deliverable per `docs/plan.md` §6:
# *"Scratch notebook successfully pulls a single Form 4 via datamule and parses it."*
#
# Pick a known case-study grant (EKSO November 2025 PSU disclosure on Form 4),
# pull the filing, parse the XML into a flat record, and eyeball the result.
#
# This file is jupytext-formatted (cells marked with `# %%`). Open in VS Code
# or Jupyter directly, or run as a plain script: `python notebooks/00_form4_smoke.py`.

# %%
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import polars as pl

from dark_arts.paths import RAW

# %% [markdown]
# ## Target filing
#
# We anchor on EKSO Bionics — Mike Puangmalai's November 2025 PSU example.
# Replace with a different accession number to test other case-study tickers
# (the canonical 9 are GME, EKSO, VAC, RPD, KODK, STMP, LHCG, TWTR, GSKY).

# %%
TARGET_CIK = "0001549084"  # EKSO Bionics Holdings, Inc.
# TODO: confirm the exact accession number of the November 2025 PSU grant Form 4
# once we can hit EDGAR. Until then, this notebook resolves "the most recent
# Form 4 for this CIK" as a stand-in.

# %% [markdown]
# ## Pull via datamule
#
# `datamule` exposes a downloader that pulls SEC filings by (CIK, form type)
# and writes raw blobs to a local cache. We point its cache at our `data/raw/`.

# %%
# Imports deferred so the notebook still parses on a machine where datamule
# hasn't been installed yet.
import datamule  # noqa: E402

# TODO[Phase 0]: confirm the actual datamule entry-point shape.
# The API surface evolves; treat the next two lines as a sketch and fix them
# against the installed version.
downloader = datamule.Downloader(destination=str(RAW))
filings = downloader.download(cik=TARGET_CIK, form="4", limit=1)

print(f"Pulled {len(filings)} filing(s) into {RAW}")
for f in filings:
    print(" -", f)

# %% [markdown]
# ## Parse the Form 4 XML
#
# Form 4 is XML with a fairly stable schema. We extract a minimal flat
# record matching the columns we want in `grants.parquet`:
#
# * `accession_number`
# * `cik` (issuer)
# * `reporting_owner_cik` (insider)
# * `transaction_date`
# * `transaction_code`
# * `security_title`
# * `shares`
# * `price_per_share`
# * `footnote_text` — the free-text vesting/hurdle prose (LLM-extracted later)

# %%
def parse_form4(xml_path: Path) -> dict:
    """Extract a flat record from a single Form 4 XML."""
    root = ET.parse(xml_path).getroot()

    def first(tag: str) -> str | None:
        el = root.find(f".//{tag}")
        return el.text.strip() if el is not None and el.text else None

    # Footnotes live as <footnote id="F1">text</footnote> children of <footnotes>.
    footnotes = {
        fn.get("id"): (fn.text or "").strip()
        for fn in root.findall(".//footnote")
    }

    return {
        "issuer_cik": first("issuerCik"),
        "issuer_name": first("issuerName"),
        "issuer_ticker": first("issuerTradingSymbol"),
        "owner_cik": first("rptOwnerCik"),
        "owner_name": first("rptOwnerName"),
        "is_director": first("isDirector"),
        "is_officer": first("isOfficer"),
        "officer_title": first("officerTitle"),
        "transaction_date": first("transactionDate/value"),
        "transaction_code": first("transactionCode"),
        "security_title": first("securityTitle/value"),
        "shares": first("transactionShares/value"),
        "price_per_share": first("transactionPricePerShare/value"),
        "footnotes": footnotes,
    }


# %%
# Assume datamule wrote the filing under data/raw/<cik>/<accession>/ as XML.
xml_files = sorted(RAW.rglob("*.xml"))
print(f"Found {len(xml_files)} XML files under {RAW}")

if xml_files:
    sample = parse_form4(xml_files[0])
    print(json.dumps(sample, indent=2, default=str))

# %% [markdown]
# ## As a polars frame
#
# When we scale up in Phase 1, the parser writes one row per transaction to a
# parquet shard. Here we just round-trip a single record to confirm polars is
# wired up.

# %%
if xml_files:
    df = pl.DataFrame([{k: v for k, v in sample.items() if k != "footnotes"}])
    print(df)

# %% [markdown]
# ## Next
#
# * Pin down the exact datamule API surface and replace the TODO sketch above.
# * Identify accession numbers for each of the 9 case-study tickers and
#   confirm the parser handles them (some Form 4s have multiple non-derivative
#   *and* derivative transactions — we'll need to flatten both tables).
# * Build the LLM extractor for footnote text (Phase 1).
