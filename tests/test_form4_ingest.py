"""Unit tests for ``dark_arts.ingest.form4``.

We don't hit the network here — :func:`download_form4` is a thin wrapper
around datamule and is exercised in the smoke notebook plus step 3
(case-study verification). The tests below cover:

  * the :data:`CASE_STUDIES` registry shape,
  * :func:`iter_form4_rows` against a fake duck-typed portfolio so we can
    assert the accession / filed_at enrichment without a real download.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dark_arts.ingest.form4 import (
    CASE_STUDIES,
    CaseStudy,
    iter_form4_rows,
    portfolio_dir_for_cik,
)

FIXTURE = Path(__file__).parent / "fixtures" / "form4_sample.xml"


# --- Fakes -----------------------------------------------------------------
# The real datamule Submission yields Documents on iteration; we mimic just
# enough of that surface (.type, .extension, .content, .accession,
# .filing_date) to drive iter_form4_rows offline.


@dataclass
class FakeDoc:
    type: str
    extension: str
    content: bytes
    accession: str
    filing_date: str


@dataclass
class FakeSubmission:
    docs: list[FakeDoc]

    def __iter__(self):
        return iter(self.docs)


@dataclass
class FakePortfolio:
    subs: list[FakeSubmission]

    def __iter__(self):
        return iter(self.subs)


# --- iter_form4_rows -------------------------------------------------------


def _fixture_doc(accession: str, filing_date: str) -> FakeDoc:
    return FakeDoc(
        type="4",
        extension=".xml",
        content=FIXTURE.read_bytes(),
        accession=accession,
        filing_date=filing_date,
    )


def test_iter_form4_rows_enriches_with_accession_and_filing_date() -> None:
    portfolio = FakePortfolio(subs=[
        FakeSubmission(docs=[_fixture_doc("0001549084-25-000123", "2025-11-17")]),
    ])
    rows = list(iter_form4_rows(portfolio))
    # Fixture has 1 non-derivative + 1 derivative transaction.
    assert len(rows) == 2
    for r in rows:
        assert r["accession_number"] == "0001549084-25-000123"
        assert r["filed_at"] == "2025-11-17"
        # Parser fields still present.
        assert r["issuer_ticker"] == "EKSO"


def test_iter_form4_rows_skips_non_xml_and_non_form4_documents() -> None:
    """A real Form 4 submission ships index/cover-page docs alongside the
    structured XML. Only the type==4, .xml document should be parsed."""
    xml_body = FIXTURE.read_bytes()
    portfolio = FakePortfolio(subs=[
        FakeSubmission(docs=[
            FakeDoc("submission_metadata", ".json", b"{}", "acc1", "2025-11-17"),
            FakeDoc("4", ".htm", b"<html>cover</html>", "acc1", "2025-11-17"),
            FakeDoc("EX-24", ".xml", b"<powerOfAttorney/>", "acc1", "2025-11-17"),
            FakeDoc("4", ".xml", xml_body, "acc1", "2025-11-17"),
        ]),
    ])
    rows = list(iter_form4_rows(portfolio))
    assert len(rows) == 2  # only the type=4 .xml contributed
    assert {r["accession_number"] for r in rows} == {"acc1"}


def test_iter_form4_rows_walks_multiple_submissions() -> None:
    portfolio = FakePortfolio(subs=[
        FakeSubmission(docs=[_fixture_doc("acc-A", "2025-11-17")]),
        FakeSubmission(docs=[_fixture_doc("acc-B", "2025-12-01")]),
        FakeSubmission(docs=[]),  # malformed / filtered submission
    ])
    rows = list(iter_form4_rows(portfolio))
    assert len(rows) == 4
    accs = {r["accession_number"] for r in rows}
    assert accs == {"acc-A", "acc-B"}


def test_iter_form4_rows_handles_empty_portfolio() -> None:
    assert list(iter_form4_rows(FakePortfolio(subs=[]))) == []


# --- CASE_STUDIES registry -------------------------------------------------


def test_case_studies_has_all_nine_phase1_tickers() -> None:
    expected = {"GME", "EKSO", "VAC", "RPD", "KODK", "STMP", "LHCG", "TWTR", "GSKY"}
    assert {cs.ticker for cs in CASE_STUDIES} == expected


def test_case_studies_are_unique_and_well_formed() -> None:
    tickers = [cs.ticker for cs in CASE_STUDIES]
    ciks = [cs.cik for cs in CASE_STUDIES]
    assert len(set(tickers)) == len(tickers), "duplicate ticker"
    assert len(set(ciks)) == len(ciks), "duplicate CIK"
    for cs in CASE_STUDIES:
        assert isinstance(cs, CaseStudy)
        assert len(cs.cik) == 10 and cs.cik.isdigit(), f"{cs.ticker}: CIK not 10-digit zero-padded"
        start, end = cs.filing_date_window
        assert start < end, f"{cs.ticker}: filing window is empty"
        # Date strings must be parseable YYYY-MM-DD.
        import datetime
        datetime.date.fromisoformat(start)
        datetime.date.fromisoformat(end)


def test_portfolio_dir_for_cik_isolates_issuers(tmp_path: Path) -> None:
    """Per-CIK Portfolio dirs are what keep ``iter_form4_rows`` from seeing
    other issuers' tars. The function should create the per-CIK subdir and
    return distinct paths per CIK under the same base."""
    a = portfolio_dir_for_cik("0001549084", base_dir=tmp_path)
    b = portfolio_dir_for_cik("0001326380", base_dir=tmp_path)
    assert a != b
    assert a.exists() and a.is_dir()
    assert b.exists() and b.is_dir()
    assert a.name == "0001549084"
    assert b.name == "0001326380"
    # Same call twice is idempotent (no exists_ok=False errors).
    assert portfolio_dir_for_cik("0001549084", base_dir=tmp_path) == a


def test_case_studies_are_immutable() -> None:
    """``CaseStudy`` is frozen so tests / callers can't mutate the registry
    by accident."""
    import dataclasses
    cs = CASE_STUDIES[0]
    try:
        cs.ticker = "MUTATED"  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("CaseStudy should be frozen")
