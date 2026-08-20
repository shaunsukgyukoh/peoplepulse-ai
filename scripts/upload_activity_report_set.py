from __future__ import annotations

import argparse
from pathlib import Path

from peoplepulse.activity.processor import MonthlyActivityReportSetProcessor, ReportUpload
from peoplepulse.config import get_settings

parser = argparse.ArgumentParser(
    description="Upload the three actual-format month-end reports"
)
parser.add_argument("--month", required=True, help="YYYY-MM")
parser.add_argument("files", nargs=3, help="Exactly three .xls/.xlsx reports; order does not matter")
args = parser.parse_args()

uploads = []
for value in args.files:
    path = Path(value)
    uploads.append(ReportUpload(filename=path.name, content=path.read_bytes()))

processed = MonthlyActivityReportSetProcessor(get_settings()).process_and_persist(
    uploads=uploads,
    report_month_value=args.month,
)
print(processed.result.model_dump_json(indent=2))
