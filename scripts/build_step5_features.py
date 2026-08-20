from __future__ import annotations

import argparse
from datetime import date

from peoplepulse.config import get_settings
from peoplepulse.features.builder import build_step5_features


def parse_month(value: str) -> date:
    year, month = value.split("-", maxsplit=1)
    return date(int(year), int(month), 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--mode", choices=["aggregate", "synthetic_demo"], required=True)
    args = parser.parse_args()

    result = build_step5_features(
        get_settings(), report_month=parse_month(args.month), mode=args.mode
    )
    print(
        f"[OK] STEP 5 features built mode={result.mode} month={result.report_month} "
        f"slack_rows={result.slack_rows} fused_rows={result.fused_rows}"
    )


if __name__ == "__main__":
    main()
