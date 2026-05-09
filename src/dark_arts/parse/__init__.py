"""Filing-specific parsers.

Form 4 XML → structured grants frame, Form 4 footnotes → LLM-extracted
PSU vesting/hurdle terms, CD&A → comp-committee composition, merger
backgrounds → deal timelines, cooperation agreements → activist cap raises.
Outputs land in ``data/parquet/`` as parquet via polars.
"""
