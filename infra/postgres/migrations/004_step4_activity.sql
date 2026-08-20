BEGIN;

CREATE TABLE IF NOT EXISTS audit.activity_upload_batch (
    batch_id UUID PRIMARY KEY,
    report_month DATE NOT NULL,
    filename_sha256 CHAR(64) NOT NULL,
    file_sha256 CHAR(64) NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completed', 'superseded', 'failed')),
    input_rows INTEGER NOT NULL CHECK (input_rows >= 0),
    duplicate_rows_removed INTEGER NOT NULL CHECK (duplicate_rows_removed >= 0),
    feature_source_rows INTEGER NOT NULL CHECK (feature_source_rows >= 0),
    excluded_rows INTEGER NOT NULL CHECK (excluded_rows >= 0),
    employee_feature_rows INTEGER NOT NULL CHECK (employee_feature_rows >= 0),
    policy_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_activity_upload_month_hash UNIQUE (report_month, file_sha256)
);

CREATE TABLE IF NOT EXISTS audit.activity_upload_exclusion_summary (
    batch_id UUID NOT NULL REFERENCES audit.activity_upload_batch(batch_id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    PRIMARY KEY (batch_id, category)
);

CREATE TABLE IF NOT EXISTS features.employee_monthly_activity (
    employee_id_hash CHAR(32) NOT NULL,
    report_month DATE NOT NULL,
    source_batch_id UUID NOT NULL REFERENCES audit.activity_upload_batch(batch_id),
    activity_events INTEGER NOT NULL CHECK (activity_events >= 0),
    active_days INTEGER NOT NULL CHECK (active_days BETWEEN 0 AND 31),
    eligible_seconds DOUBLE PRECISION NOT NULL CHECK (eligible_seconds >= 0),
    after_hours_ratio DOUBLE PRECISION NOT NULL CHECK (after_hours_ratio BETWEEN 0 AND 1),
    weekend_ratio DOUBLE PRECISION NOT NULL CHECK (weekend_ratio BETWEEN 0 AND 1),
    category_diversity INTEGER NOT NULL CHECK (category_diversity >= 0),
    development_ratio DOUBLE PRECISION NOT NULL CHECK (development_ratio BETWEEN 0 AND 1),
    documentation_ratio DOUBLE PRECISION NOT NULL CHECK (documentation_ratio BETWEEN 0 AND 1),
    collaboration_ratio DOUBLE PRECISION NOT NULL CHECK (collaboration_ratio BETWEEN 0 AND 1),
    project_management_ratio DOUBLE PRECISION NOT NULL CHECK (project_management_ratio BETWEEN 0 AND 1),
    business_tools_ratio DOUBLE PRECISION NOT NULL CHECK (business_tools_ratio BETWEEN 0 AND 1),
    internal_ratio DOUBLE PRECISION NOT NULL CHECK (internal_ratio BETWEEN 0 AND 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (employee_id_hash, report_month)
);

CREATE INDEX IF NOT EXISTS idx_employee_monthly_activity_month
    ON features.employee_monthly_activity (report_month DESC);

COMMENT ON TABLE features.employee_monthly_activity IS
'Monthly employee activity features derived only from explicitly allowlisted work-domain categories. Raw URLs/domains are not persisted.';
COMMENT ON TABLE audit.activity_upload_exclusion_summary IS
'Batch-level counts of excluded categories only. No employee identifiers or raw URL values are retained.';

INSERT INTO core.app_metadata (key, value)
VALUES ('schema_version', 'step4-v1')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();

COMMIT;
