#!/usr/bin/env python3
"""Export viva-ready evidence pack for comparative privacy firewall."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.privacy_viva import generate_viva_pack


def main() -> int:
    result = generate_viva_pack(dataset_version="v3", report_dir="reports/viva")
    print(f"Wrote {result['artifacts']['json']}")
    print(f"Wrote {result['artifacts']['markdown']}")
    print(f"Wrote {result['artifacts']['leaderboard_csv']}")
    print(f"Wrote {result['artifacts']['adversarial_csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
