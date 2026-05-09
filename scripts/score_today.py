"""Score newly arrived filings.

Loads the latest scoring model (heuristic/logistic/bayesian per config),
applies it to filings ingested in the last N days, and writes
``data/parquet/scores/<run_date>.parquet``.

Phase 4+.
"""

from __future__ import annotations

import sys


def main() -> int:
    print("score_today: not implemented yet (Phase 4).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
