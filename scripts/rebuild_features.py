"""Rebuild the per-grant feature frame and per-company governance frame.

Reads ``data/parquet/grants.parquet`` and friends, recomputes features per
``docs/plan.md`` §7, and writes ``data/parquet/grant_features.parquet`` and
``data/parquet/company_governance.parquet``.

Phase 3+.
"""

from __future__ import annotations

import sys


def main() -> int:
    print("rebuild_features: not implemented yet (Phase 3).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
