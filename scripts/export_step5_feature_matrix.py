from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd
import psycopg

from peoplepulse.config import get_settings


def parse_month(value: str) -> date:
    year, month = value.split("-", maxsplit=1)
    return date(int(year), int(month), 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True)
    parser.add_argument("--mode", choices=["aggregate", "synthetic_demo"], required=True)
    parser.add_argument("--output-dir", default="artifacts/features")
    args = parser.parse_args()

    month = parse_month(args.month)
    if args.mode == "aggregate":
        table = "features.department_monthly_fusion"
        id_columns = ["department_id_hash", "report_month"]
    else:
        table = "features.synthetic_employee_retention_feature"
        id_columns = ["canonical_employee_id_hash", "department_id_hash", "report_month"]

    settings = get_settings()
    with psycopg.connect(settings.postgres_dsn) as conn:
        frame = pd.read_sql_query(
            f"SELECT * FROM {table} WHERE report_month=%s ORDER BY 1",
            conn,
            params=(month,),
        )

    if frame.empty:
        raise SystemExit(f"No rows found in {table} for {args.month}")

    technical = {"created_at", "updated_at", "has_activity_data", "has_slack_data"}
    excluded = set(id_columns) | technical
    model_features = [
        column
        for column in frame.columns
        if column not in excluded and pd.api.types.is_numeric_dtype(frame[column])
    ]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"step5_{args.mode}_{args.month}"
    csv_path = output_dir / f"{stem}.csv"
    manifest_path = output_dir / f"{stem}_manifest.json"
    frame.to_csv(csv_path, index=False)
    manifest_path.write_text(
        json.dumps(
            {
                "source_table": table,
                "report_month": args.month,
                "rows": len(frame),
                "identifier_columns_not_for_training": id_columns,
                "technical_columns_not_for_training": sorted(technical & set(frame.columns)),
                "model_feature_columns": model_features,
                "target_columns": [],
                "note": "STEP 5 exports features only. Attrition targets are introduced in STEP 6 synthetic experiments.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[OK] exported {csv_path}")
    print(f"[OK] manifest {manifest_path} model_features={len(model_features)}")


if __name__ == "__main__":
    main()
