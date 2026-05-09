"""SEC filing ingestion.

Datamule wrappers and scheduling for Form 4, DEF 14A / DEFM14A / S-4,
8-K (Items 5.02, 8.01, 1.01), and SC 13D / 13D-A.

Each submodule writes raw filing metadata + blobs to ``data/raw/``;
parsing is the responsibility of :mod:`dark_arts.parse`.
"""
