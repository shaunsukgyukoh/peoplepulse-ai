from __future__ import annotations

import argparse
import json
from pathlib import Path

from peoplepulse.ml.synthetic_panel import SyntheticPanelConfig, generate_synthetic_attrition_panel


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--employees", type=int, default=650)
    parser.add_argument("--months", type=int, default=36)
    parser.add_argument("--start-month", default="2023-09")
    parser.add_argument("--seed", type=int, default=26082026)
    parser.add_argument("--output", default="data/synthetic/ml/step6_attrition_panel.csv")
    args = parser.parse_args()

    frame = generate_synthetic_attrition_panel(
        SyntheticPanelConfig(
            employees=args.employees,
            start_month=args.start_month,
            months=args.months,
            seed=args.seed,
        )
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    summary = {
        "rows": len(frame),
        "employees": int(frame["canonical_employee_id_hash"].nunique()),
        "months": int(frame["snapshot_month"].nunique()),
        "attrition_30d_rate": float(frame["attrition_30d"].mean()),
        "attrition_60d_rate": float(frame["attrition_60d"].mean()),
        "attrition_90d_rate": float(frame["attrition_90d"].mean()),
        "scope": "synthetic_demo_only",
    }
    (output.with_suffix(".summary.json")).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[OK] wrote {output} rows={len(frame)}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
