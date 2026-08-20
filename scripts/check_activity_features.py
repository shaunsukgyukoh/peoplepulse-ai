import json

import psycopg

from peoplepulse.config import get_settings

settings = get_settings()
with psycopg.connect(settings.postgres_dsn) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM audit.activity_report_set_batch")
        batches = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM features.department_monthly_activity")
        department_features = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM features.synthetic_employee_monthly_activity")
        synthetic_features = cur.fetchone()[0]
        cur.execute(
            """
            SELECT report_month, privacy_mode, status,
                   input_rows, privacy_excluded_rows,
                   department_feature_rows, synthetic_employee_feature_rows,
                   suppressed_departments
            FROM audit.activity_report_set_batch
            ORDER BY created_at DESC LIMIT 6
            """
        )
        rows = cur.fetchall()
print(
    json.dumps(
        {
            "batches": batches,
            "department_feature_rows": department_features,
            "synthetic_employee_feature_rows": synthetic_features,
            "recent_batches": rows,
        },
        default=str,
        indent=2,
        ensure_ascii=False,
    )
)
