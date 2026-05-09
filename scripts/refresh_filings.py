"""Refresh SEC filings cache.

Pulls new Form 4, DEF 14A, DEFM14A, S-4, 8-K (5.02/8.01/1.01), and
SC 13D/A filings since the last successful run, writes them under
``data/raw/``, and updates a watermark.

Cron entry point. Phase 1+ (see docs/plan.md §6).
"""

from __future__ import annotations

import sys


def main() -> int:
    print("refresh_filings: not implemented yet (Phase 1).", file=sys.stderr)
    print("See docs/plan.md §6 Phase 1.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
