"""Remind us to re-check the WhatsApp limits."""

import re
import sys
from datetime import date
from pathlib import Path

MAX_AGE_DAYS = 90
DOC = Path(__file__).resolve().parents[1] / "docs" / "whatsapp-constraints.md"


def main() -> int:
    """Return 1 when the limits were not verified recently."""
    match = re.search(r"Last verified: (\d{4}-\d{2}-\d{2})", DOC.read_text())
    if match is None:
        print("WhatsApp limits have never been verified.")
        return 1
    age = (date.today() - date.fromisoformat(match.group(1))).days
    if age > MAX_AGE_DAYS:
        print(f"WhatsApp limits were last verified {age} days ago.")
        return 1
    print(f"WhatsApp limits verified {age} days ago.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
