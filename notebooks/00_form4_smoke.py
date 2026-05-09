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

import xml.etree.ElementTree as ET
from typing import Any

import datamule
import polars as pl

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
# Form 4 ships as XML with a stable schema. We extract a flat record per
# transaction matching the columns we want in `grants.parquet`. Footnotes
# come back as a dict keyed by `<footnote id="F1">` and are joined back into
# the relevant transaction row via `<footnoteId>` references — but for the
# smoke test we just attach the full footnotes blob to every row.
#
# datamule's own `Document.parse()` doesn't have a Form 4 mapping, so we
# parse the raw bytes (`Document.content`) with stdlib ElementTree.

# %%
def _text(parent: ET.Element, path: str) -> str | None:
    """Find one text leaf at `path` under `parent`. Tolerates `<x><value>foo</value></x>`."""
    el = parent.find(path)
    if el is None:
        return None
    # Many Form 4 leaves wrap their value in <value>.
    val = el.find("value")
    if val is not None and val.text:
        return val.text.strip()
    return el.text.strip() if el.text else None


def _bool_int(parent: ET.Element, path: str) -> bool | None:
    raw = _text(parent, path)
    if raw is None:
        return None
    return raw.strip() in ("1", "true", "True")


def parse_form4_xml(xml_bytes: bytes) -> list[dict[str, Any]]:
    """Return one row per non-derivative + derivative transaction in the Form 4."""
    root = ET.fromstring(xml_bytes)

    issuer_cik = _text(root, "issuer/issuerCik")
    issuer_name = _text(root, "issuer/issuerName")
    ticker = _text(root, "issuer/issuerTradingSymbol")
    period = _text(root, "periodOfReport")

    # Reporting owner block (one Form 4 = one insider).
    owner = root.find("reportingOwner") or ET.Element("none")
    owner_cik = _text(owner, "reportingOwnerId/rptOwnerCik")
    owner_name = _text(owner, "reportingOwnerId/rptOwnerName")
    is_director = _bool_int(owner, "reportingOwnerRelationship/isDirector")
    is_officer = _bool_int(owner, "reportingOwnerRelationship/isOfficer")
    is_ten_pct_owner = _bool_int(owner, "reportingOwnerRelationship/isTenPercentOwner")
    officer_title = _text(owner, "reportingOwnerRelationship/officerTitle")

    footnotes = {
        fn.get("id"): (fn.text or "").strip()
        for fn in root.findall("footnotes/footnote")
    }

    rows: list[dict[str, Any]] = []
    for tx_path, table_kind in (
        ("nonDerivativeTable/nonDerivativeTransaction", "non_derivative"),
        ("derivativeTable/derivativeTransaction", "derivative"),
    ):
        for tx in root.findall(tx_path):
            rows.append({
                "issuer_cik": issuer_cik,
                "issuer_name": issuer_name,
                "issuer_ticker": ticker,
                "period_of_report": period,
                "owner_cik": owner_cik,
                "owner_name": owner_name,
                "is_director": is_director,
                "is_officer": is_officer,
                "is_ten_pct_owner": is_ten_pct_owner,
                "officer_title": officer_title,
                "table_kind": table_kind,
                "security_title": _text(tx, "securityTitle"),
                "transaction_date": _text(tx, "transactionDate"),
                "transaction_code": _text(tx, "transactionCoding/transactionCode"),
                "shares": _text(tx, "transactionAmounts/transactionShares"),
                "price_per_share": _text(tx, "transactionAmounts/transactionPricePerShare"),
                "acquired_disposed": _text(
                    tx, "transactionAmounts/transactionAcquiredDisposedCode"
                ),
                "shares_owned_after": _text(
                    tx, "postTransactionAmounts/sharesOwnedFollowingTransaction"
                ),
                "ownership_form": _text(tx, "ownershipNature/directOrIndirectOwnership"),
                # Derivative-only fields (will be None for non-derivative rows).
                "conversion_or_exercise_price": _text(tx, "conversionOrExercisePrice"),
                "exercise_date": _text(tx, "exerciseDate"),
                "expiration_date": _text(tx, "expirationDate"),
                "underlying_security_title": _text(
                    tx, "underlyingSecurity/underlyingSecurityTitle"
                ),
                "underlying_shares": _text(tx, "underlyingSecurity/underlyingSecurityShares"),
                # All footnotes attached as JSON-able dict; footnote-resolution is a
                # later phase (the LLM extractor consumes the joined text).
                "footnotes": footnotes,
            })
    return rows


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
# * Lift `parse_form4_xml` into `src/dark_arts/parse/form4.py` once we lock
#   in the canonical column set.
# * Pull the full case-study set (the 9 named tickers) and confirm we get
#   what we expect for KODK Jul 2020, STMP 2019, LHCG Mar 2022, etc.
# * Build the LLM extractor for footnote text (Phase 1).
