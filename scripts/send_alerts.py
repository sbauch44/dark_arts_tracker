"""Send alerts for newly high-scoring filings.

Reads today's scores, applies the alert rules from ``docs/plan.md`` §11,
and dispatches an email digest plus Slack-webhook urgent pings.

Phase 8+.
"""

from __future__ import annotations

import sys


def main() -> int:
    print("send_alerts: not implemented yet (Phase 8).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
