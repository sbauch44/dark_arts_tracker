"""Unit tests for ``dark_arts.parse.form4``.

The fixture at ``tests/fixtures/form4_sample.xml`` is a hand-rolled, namespace-
free Form 4 modeled on a real EKSO Bionics PSU grant: one common-stock open-
market acquisition (non-derivative) plus one PSU grant (derivative) whose
exercise price is footnote-only — the pattern we expect to see all over the
nine Phase-1 case studies.
"""
from __future__ import annotations

import datetime
from pathlib import Path

import polars as pl
import pytest

from dark_arts.parse.form4 import Form4Row, form4_rows_to_frame, parse_form4_xml

FIXTURE = Path(__file__).parent / "fixtures" / "form4_sample.xml"


@pytest.fixture(scope="module")
def sample_xml() -> bytes:
    return FIXTURE.read_bytes()


@pytest.fixture(scope="module")
def rows(sample_xml: bytes) -> list[Form4Row]:
    return parse_form4_xml(sample_xml)


def test_one_row_per_transaction(rows: list[Form4Row]) -> None:
    assert len(rows) == 2
    assert {r["table_kind"] for r in rows} == {"non_derivative", "derivative"}


def test_issuer_and_owner_extracted(rows: list[Form4Row]) -> None:
    r = rows[0]
    assert r["issuer_cik"] == "0001549084"
    assert r["issuer_name"] == "EKSO BIONICS HOLDINGS, INC."
    assert r["issuer_ticker"] == "EKSO"
    assert r["owner_cik"] == "0001234567"
    assert r["owner_name"] == "SMITH JANE"
    assert r["officer_title"] == "Chief Executive Officer"
    assert r["period_of_report"] == "2025-11-15"


def test_relationship_flags_are_booleans(rows: list[Form4Row]) -> None:
    r = rows[0]
    assert r["is_director"] is False
    assert r["is_officer"] is True
    assert r["is_ten_pct_owner"] is False


def test_non_derivative_transaction_fields(rows: list[Form4Row]) -> None:
    nd = next(r for r in rows if r["table_kind"] == "non_derivative")
    assert nd["security_title"] == "Common Stock"
    assert nd["transaction_date"] == "2025-11-15"
    assert nd["transaction_code"] == "A"
    assert nd["shares"] == "10000"
    assert nd["price_per_share"] == "0"
    assert nd["acquired_disposed"] == "A"
    assert nd["shares_owned_after"] == "50000"
    assert nd["ownership_form"] == "D"
    # Derivative-only fields stay None on non-derivative rows.
    assert nd["underlying_security_title"] is None
    assert nd["underlying_shares"] is None
    assert nd["conversion_or_exercise_price"] is None


def test_derivative_transaction_fields(rows: list[Form4Row]) -> None:
    d = next(r for r in rows if r["table_kind"] == "derivative")
    assert d["security_title"] == "Performance Stock Unit"
    assert d["shares"] == "25000"
    assert d["underlying_security_title"] == "Common Stock"
    assert d["underlying_shares"] == "25000"


def test_footnote_only_field_returns_none(rows: list[Form4Row]) -> None:
    """PSU grants commonly carry ``<conversionOrExercisePrice><footnoteId/></...>``
    with no ``<value>`` — should parse as None, not as the empty/whitespace text."""
    d = next(r for r in rows if r["table_kind"] == "derivative")
    assert d["conversion_or_exercise_price"] is None
    assert d["exercise_date"] is None
    assert d["expiration_date"] is None


def test_footnotes_attached_to_every_row(rows: list[Form4Row]) -> None:
    for r in rows:
        fns = r["footnotes"]
        assert set(fns.keys()) == {"F1", "F2"}
        assert "stock price hurdles" in fns["F1"].lower()
        assert "continued service" in fns["F2"].lower()


def test_to_frame_dtypes(rows: list[Form4Row]) -> None:
    df = form4_rows_to_frame(rows)
    schema = df.schema
    assert schema["accession_number"] == pl.Utf8
    assert schema["filed_at"] == pl.Date
    assert schema["period_of_report"] == pl.Date
    assert schema["transaction_date"] == pl.Date
    assert schema["exercise_date"] == pl.Date
    assert schema["expiration_date"] == pl.Date
    assert schema["shares"] == pl.Float64
    assert schema["price_per_share"] == pl.Float64
    assert schema["shares_owned_after"] == pl.Float64
    assert schema["underlying_shares"] == pl.Float64
    assert schema["conversion_or_exercise_price"] == pl.Float64
    assert schema["is_director"] == pl.Boolean
    assert schema["is_officer"] == pl.Boolean
    assert schema["is_ten_pct_owner"] == pl.Boolean
    assert schema["footnotes_json"] == pl.Utf8


def test_to_frame_null_pads_submission_fields(rows: list[Form4Row]) -> None:
    """parse_form4_xml never sets accession_number / filed_at — those come
    from the ingest layer. The frame should still carry them as typed-null
    columns so the schema is stable regardless of caller path."""
    df = form4_rows_to_frame(rows)
    assert df["accession_number"].null_count() == df.height
    assert df["filed_at"].null_count() == df.height


def test_to_frame_preserves_submission_fields_when_present() -> None:
    """When the ingest layer enriches rows with accession_number / filed_at,
    form4_rows_to_frame should pass them through with the right dtypes."""
    enriched: list[Form4Row] = [{
        "accession_number": "0001549084-25-000123",
        "filed_at": "2025-11-17",
        "issuer_cik": "0001549084",
        "issuer_ticker": "EKSO",
        "table_kind": "non_derivative",
        "transaction_date": "2025-11-15",
        "shares": "1000",
        "price_per_share": "5.25",
        "is_director": False,
        "is_officer": True,
        "is_ten_pct_owner": False,
        "footnotes": {},
    }]
    df = form4_rows_to_frame(enriched)
    row = df.row(0, named=True)
    assert row["accession_number"] == "0001549084-25-000123"
    assert row["filed_at"] == datetime.date(2025, 11, 17)
    assert row["shares"] == 1000.0
    assert row["price_per_share"] == 5.25


def test_to_frame_values(rows: list[Form4Row]) -> None:
    df = form4_rows_to_frame(rows)
    assert df.height == 2

    nd = df.filter(pl.col("table_kind") == "non_derivative").row(0, named=True)
    assert nd["shares"] == 10_000.0
    assert nd["price_per_share"] == 0.0
    assert nd["transaction_date"] == datetime.date(2025, 11, 15)
    assert nd["period_of_report"] == datetime.date(2025, 11, 15)
    assert nd["is_officer"] is True
    assert nd["is_director"] is False

    d = df.filter(pl.col("table_kind") == "derivative").row(0, named=True)
    assert d["underlying_shares"] == 25_000.0
    # PSU footnote-only price → null after coercion.
    assert d["conversion_or_exercise_price"] is None


def test_to_frame_footnotes_json_is_round_trippable(rows: list[Form4Row]) -> None:
    import json

    df = form4_rows_to_frame(rows)
    blob = df["footnotes_json"][0]
    decoded = json.loads(blob)
    assert set(decoded.keys()) == {"F1", "F2"}
    assert "$5" in decoded["F1"]


def test_to_frame_empty_returns_typed_empty_frame() -> None:
    df = form4_rows_to_frame([])
    assert df.height == 0
    assert df.schema["transaction_date"] == pl.Date
    assert df.schema["shares"] == pl.Float64
    assert df.schema["is_officer"] == pl.Boolean
    assert df.schema["footnotes_json"] == pl.Utf8


def test_missing_reporting_owner_does_not_crash() -> None:
    """Defensive: a stripped Form 4 with no ``<reportingOwner>`` block should
    yield rows with ``owner_*`` fields all None rather than raising."""
    xml = b"""<?xml version="1.0"?>
<ownershipDocument>
    <periodOfReport>2025-11-15</periodOfReport>
    <issuer>
        <issuerCik>0001549084</issuerCik>
        <issuerName>EKSO BIONICS HOLDINGS, INC.</issuerName>
        <issuerTradingSymbol>EKSO</issuerTradingSymbol>
    </issuer>
    <nonDerivativeTable>
        <nonDerivativeTransaction>
            <securityTitle><value>Common Stock</value></securityTitle>
            <transactionDate><value>2025-11-15</value></transactionDate>
            <transactionCoding><transactionCode>A</transactionCode></transactionCoding>
            <transactionAmounts>
                <transactionShares><value>1</value></transactionShares>
            </transactionAmounts>
        </nonDerivativeTransaction>
    </nonDerivativeTable>
</ownershipDocument>
"""
    rows = parse_form4_xml(xml)
    assert len(rows) == 1
    assert rows[0]["owner_name"] is None
    assert rows[0]["is_director"] is None
    assert rows[0]["footnotes"] == {}
