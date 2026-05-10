"""Form 4 ingest: download via datamule, walk the portfolio, emit enriched rows.

The XML parser (:func:`dark_arts.parse.form4.parse_form4_xml`) is pure — it
only sees the bytes of one document. The submission-level fields we need for
the grants frame (``accession_number``, ``filed_at``) live on the datamule
``Document`` instance, so this layer is what threads them in.

The download itself is idempotent: ``Portfolio.download_submissions`` defaults
to ``skip_existing=True``, which checks the portfolio directory for existing
submission tars and only fetches what's missing. Re-running an ingest call is
safe and cheap (parse only, no network).

Phase 1 targets the nine case-study issuers in :data:`CASE_STUDIES`. The
Russell-3000-wide pull (Phase 2 onward) will reuse :func:`download_form4` /
:func:`iter_form4_rows` over a longer list — no new code needed at that point,
just a different driver loop.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import datamule

from dark_arts.parse.form4 import Form4Row, parse_form4_xml
from dark_arts.paths import RAW

if TYPE_CHECKING:
    # `Portfolio` is duck-typed in iter_form4_rows so the helper also works
    # against the in-memory fakes our tests use; the real type only matters
    # for type-checkers reading the public API.
    from datamule.portfolio.portfolio import Portfolio


@dataclass(frozen=True)
class CaseStudy:
    """One Phase-1 target issuer plus the filing window we expect to capture
    its grant of interest.

    ``filing_date_window`` is intentionally wider than the grant date itself —
    the EKSO smoke test (Nov-Dec 2025 only) caught 10b5-1 sales but missed
    the headline PSU grant, so windows here pad ~2 months on either side.
    Step 3 (case-study verification) is what tightens these up once we've
    confirmed each grant's exact filing date.
    """

    ticker: str
    cik: str           # zero-padded to 10 digits, matching datamule / EDGAR
    issuer_name: str   # for cross-checking parsed Form 4 issuerName
    filing_date_window: tuple[str, str]  # (YYYY-MM-DD, YYYY-MM-DD)
    note: str


# Phase-1 case studies. CIKs verified via SEC EDGAR ticker→CIK index; issuer
# names come from Form 4 ``<issuerName>`` and so should match exactly once
# parsed. If a parsed filing's issuer_name disagrees with what's here, treat
# that as a CIK lookup error and surface it in the Phase 1.3 verification.
CASE_STUDIES: tuple[CaseStudy, ...] = (
    CaseStudy(
        ticker="EKSO",
        cik="0001549084",
        issuer_name="EKSO BIONICS HOLDINGS, INC.",
        filing_date_window=("2025-09-01", "2025-12-31"),
        note="PSU grant ~Nov 2025 — original Mike Puangmalai case",
    ),
    CaseStudy(
        ticker="STMP",
        cik="0001082923",
        issuer_name="STAMPS.COM INC",
        filing_date_window=("2019-01-01", "2019-12-31"),
        note="Options 2019 — pre-merger leak case",
    ),
    CaseStudy(
        ticker="KODK",
        cik="0000031235",
        issuer_name="EASTMAN KODAK CO",
        filing_date_window=("2020-06-01", "2020-08-31"),
        note="Options Jul 2020 — DFC loan announcement leak",
    ),
    CaseStudy(
        ticker="LHCG",
        cik="0001303313",
        issuer_name="LHC GROUP, INC",
        filing_date_window=("2022-02-01", "2022-04-30"),
        note="RSUs Mar 2022 — pre UNH-LHCG announcement",
    ),
    CaseStudy(
        ticker="TWTR",
        cik="0001418091",
        issuer_name="TWITTER, INC.",
        filing_date_window=("2022-03-01", "2022-05-31"),
        note="RSUs Apr 2022 — pre Musk acquisition close",
    ),
    CaseStudy(
        ticker="RPD",
        cik="0001560327",
        issuer_name="RAPID7, INC",
        filing_date_window=("2026-01-01", "2026-04-30"),
        note="PSUs Mar 2026 — Phase 1 forward case",
    ),
    CaseStudy(
        ticker="GME",
        cik="0001326380",
        issuer_name="GAMESTOP CORP.",
        filing_date_window=("2020-01-01", "2025-12-31"),
        note="Wide pull — meme-era insider activity, dates TBD in step 3",
    ),
    CaseStudy(
        ticker="VAC",
        cik="0001524358",
        issuer_name="MARRIOTT VACATIONS WORLDWIDE CORP",
        filing_date_window=("2020-01-01", "2025-12-31"),
        note="Wide pull — dates TBD in step 3",
    ),
    CaseStudy(
        ticker="GSKY",
        cik="0001712923",
        issuer_name="GREENSKY, INC.",
        filing_date_window=("2018-01-01", "2022-03-31"),
        note="Wide pull — pre Goldman acquisition close",
    ),
)


def portfolio_dir_for_cik(cik: str, base_dir: str | Path | None = None) -> Path:
    """Per-CIK Portfolio directory under ``data/raw/form4/<cik>/``.

    Each CIK gets an isolated Portfolio so that
    :func:`iter_form4_rows` only sees that CIK's filings, ``skip_existing``
    checks the right tars, and the layout extends to the Russell-3000 case
    by just having more peers under ``data/raw/form4/``.
    """
    root = Path(base_dir) if base_dir is not None else (RAW / "form4")
    d = root / cik
    d.mkdir(parents=True, exist_ok=True)
    return d


def download_form4(
    cik: str,
    filing_date: tuple[str, str] | str,
    base_dir: str | Path | None = None,
    *,
    quiet: bool = True,
) -> Portfolio:
    """Download Form 4 submissions for *cik* into a datamule Portfolio.

    The Portfolio is rooted at a per-CIK subdirectory
    (:func:`portfolio_dir_for_cik`) so issues' tars don't co-mingle. Idempotent:
    ``download_submissions`` defaults to ``skip_existing=True``, so already-
    downloaded submissions are not re-fetched. Returns the loaded Portfolio so
    callers can chain into :func:`iter_form4_rows`.
    """
    pdir = portfolio_dir_for_cik(cik, base_dir=base_dir)
    p = datamule.Portfolio(str(pdir))
    p.download_submissions(
        cik=cik,
        submission_type="4",
        filing_date=filing_date,
        quiet=quiet,
    )
    return p


def iter_form4_rows(portfolio: Portfolio) -> Iterator[Form4Row]:
    """Walk *portfolio*, parse every Form 4 XML, and yield rows enriched with
    ``accession_number`` and ``filed_at`` from the document metadata.

    Filters to ``doc.type == '4'`` AND ``doc.extension == '.xml'`` — Form 4
    submissions ship multiple documents (cover-page index, attachments) and
    we only want the structured XML body.
    """
    for sub in portfolio:
        for doc in sub:
            if doc.type == "4" and doc.extension == ".xml":
                for row in parse_form4_xml(doc.content):
                    yield {
                        **row,
                        "accession_number": doc.accession,
                        "filed_at": doc.filing_date,
                    }


def ingest_form4(
    cik: str,
    filing_date: tuple[str, str] | str,
    base_dir: str | Path | None = None,
) -> list[Form4Row]:
    """End-to-end: download + parse Form 4 filings for one issuer/window.

    Returns one row per transaction. Safe to re-run — both the download and
    the parse are pure functions of the inputs (the download is idempotent;
    the parse has no side effects).
    """
    p = download_form4(cik, filing_date, base_dir)
    return list(iter_form4_rows(p))


def ingest_case_study(study: CaseStudy, base_dir: str | Path | None = None) -> list[Form4Row]:
    """Convenience: run :func:`ingest_form4` for one :class:`CaseStudy`."""
    return ingest_form4(study.cik, study.filing_date_window, base_dir)


__all__ = [
    "CASE_STUDIES",
    "CaseStudy",
    "download_form4",
    "ingest_case_study",
    "ingest_form4",
    "iter_form4_rows",
    "portfolio_dir_for_cik",
]
