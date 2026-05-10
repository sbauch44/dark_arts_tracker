"""Form 4 XML → row dicts (and optionally a typed polars frame).

Form 4 ships as a stable XML schema: one filing = one insider, with one or
more transactions split across a non-derivative table (e.g. open-market buys,
RSU vests landing as common stock) and a derivative table (e.g. PSU/RSU
grants, option exercises). We parse the raw bytes (datamule's
``Document.content``) with stdlib ElementTree and emit one row per
transaction, preserving everything we'll need for the Phase 1 grants frame
plus the raw footnote blob the LLM extractor consumes downstream.

The column shape mirrors the smoke notebook so the two stay in sync — see
``notebooks/00_form4_smoke.py``.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import TypedDict

import polars as pl


class Form4Row(TypedDict, total=False):
    """One transaction row from a Form 4 filing.

    Values are the raw strings as they appear in the XML; coercion to
    numerics/dates happens in :func:`form4_rows_to_frame`. ``footnotes`` is
    the per-filing footnote dict ``{id: text}`` attached verbatim to every row
    so callers can resolve references without re-reading the source XML.
    """

    issuer_cik: str | None
    issuer_name: str | None
    issuer_ticker: str | None
    period_of_report: str | None
    owner_cik: str | None
    owner_name: str | None
    is_director: bool | None
    is_officer: bool | None
    is_ten_pct_owner: bool | None
    officer_title: str | None
    table_kind: str
    security_title: str | None
    transaction_date: str | None
    transaction_code: str | None
    shares: str | None
    price_per_share: str | None
    acquired_disposed: str | None
    shares_owned_after: str | None
    ownership_form: str | None
    conversion_or_exercise_price: str | None
    exercise_date: str | None
    expiration_date: str | None
    underlying_security_title: str | None
    underlying_shares: str | None
    footnotes: dict[str, str]


# Target dtypes for :func:`form4_rows_to_frame`. Order here is the column order
# of the returned frame. ``footnotes`` is replaced by ``footnotes_json`` (Utf8)
# so the frame is parquet-safe.
_SCHEMA: dict[str, type[pl.DataType]] = {
    "issuer_cik": pl.Utf8,
    "issuer_name": pl.Utf8,
    "issuer_ticker": pl.Utf8,
    "period_of_report": pl.Date,
    "owner_cik": pl.Utf8,
    "owner_name": pl.Utf8,
    "is_director": pl.Boolean,
    "is_officer": pl.Boolean,
    "is_ten_pct_owner": pl.Boolean,
    "officer_title": pl.Utf8,
    "table_kind": pl.Utf8,
    "security_title": pl.Utf8,
    "transaction_date": pl.Date,
    "transaction_code": pl.Utf8,
    "shares": pl.Float64,
    "price_per_share": pl.Float64,
    "acquired_disposed": pl.Utf8,
    "shares_owned_after": pl.Float64,
    "ownership_form": pl.Utf8,
    "conversion_or_exercise_price": pl.Float64,
    "exercise_date": pl.Date,
    "expiration_date": pl.Date,
    "underlying_security_title": pl.Utf8,
    "underlying_shares": pl.Float64,
    "footnotes_json": pl.Utf8,
}


def _text(parent: ET.Element, path: str) -> str | None:
    """Find one text leaf at *path* under *parent*.

    Tolerates the common Form 4 idiom of wrapping leaves in ``<value>`` (e.g.
    ``<transactionShares><value>1000</value><footnoteId id="F1"/></transactionShares>``).
    Returns ``None`` when the element is missing or has no text content (e.g.
    a ``conversionOrExercisePrice`` that contains only a ``<footnoteId/>`` —
    common on PSU grants where the price is "see footnote").
    """
    el = parent.find(path)
    if el is None:
        return None
    val = el.find("value")
    if val is not None and val.text:
        return val.text.strip()
    return el.text.strip() if el.text and el.text.strip() else None


def _bool_int(parent: ET.Element, path: str) -> bool | None:
    raw = _text(parent, path)
    if raw is None:
        return None
    return raw.strip() in ("1", "true", "True")


def parse_form4_xml(xml_bytes: bytes) -> list[Form4Row]:
    """Return one row per non-derivative + derivative transaction in *xml_bytes*.

    Joint filings (multiple ``<reportingOwner>`` blocks) currently take the
    first owner only. TODO: surface co-filers when we have a case study that
    needs them — none of the nine Phase-1 case studies do.
    """
    root = ET.fromstring(xml_bytes)

    issuer_cik = _text(root, "issuer/issuerCik")
    issuer_name = _text(root, "issuer/issuerName")
    ticker = _text(root, "issuer/issuerTradingSymbol")
    period = _text(root, "periodOfReport")

    owner = root.find("reportingOwner")
    if owner is None:
        owner = ET.Element("none")
    owner_cik = _text(owner, "reportingOwnerId/rptOwnerCik")
    owner_name = _text(owner, "reportingOwnerId/rptOwnerName")
    is_director = _bool_int(owner, "reportingOwnerRelationship/isDirector")
    is_officer = _bool_int(owner, "reportingOwnerRelationship/isOfficer")
    is_ten_pct_owner = _bool_int(owner, "reportingOwnerRelationship/isTenPercentOwner")
    officer_title = _text(owner, "reportingOwnerRelationship/officerTitle")

    footnotes = {
        fn.get("id", ""): (fn.text or "").strip()
        for fn in root.findall("footnotes/footnote")
    }

    rows: list[Form4Row] = []
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
                # Derivative-only fields stay None for non-derivative rows.
                "conversion_or_exercise_price": _text(tx, "conversionOrExercisePrice"),
                "exercise_date": _text(tx, "exerciseDate"),
                "expiration_date": _text(tx, "expirationDate"),
                "underlying_security_title": _text(
                    tx, "underlyingSecurity/underlyingSecurityTitle"
                ),
                "underlying_shares": _text(tx, "underlyingSecurity/underlyingSecurityShares"),
                "footnotes": footnotes,
            })
    return rows


def form4_rows_to_frame(rows: list[Form4Row]) -> pl.DataFrame:
    """Convert :func:`parse_form4_xml` output to a typed polars DataFrame.

    Numeric/date/boolean columns are coerced to their target dtypes (see
    ``_SCHEMA``). The per-filing ``footnotes`` dict is serialized to a JSON
    string in column ``footnotes_json`` so the frame is parquet-friendly; the
    LLM extractor (Phase 1, item 5) reads it back via ``json.loads`` keyed by
    accession number.
    """
    if not rows:
        return pl.DataFrame(schema=_SCHEMA)

    flat = [
        {
            **{k: v for k, v in r.items() if k != "footnotes"},
            "footnotes_json": json.dumps(r.get("footnotes") or {}),
        }
        for r in rows
    ]
    df = pl.DataFrame(flat, infer_schema_length=None)

    # Date columns arrive as Utf8 from the XML; everything else gets a direct
    # non-strict cast (None passes through, unparseable values become null).
    return df.select([
        pl.col(col).cast(pl.Utf8, strict=False).str.to_date(strict=False).alias(col)
        if dtype is pl.Date
        else pl.col(col).cast(dtype, strict=False).alias(col)
        for col, dtype in _SCHEMA.items()
    ])
