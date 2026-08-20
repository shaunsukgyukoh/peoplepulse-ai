BEGIN;

CREATE TABLE IF NOT EXISTS audit.activity_report_set_batch (
    batch_id UUID PRIMARY KEY,
    report_month DATE NOT NULL,
    privacy_mode TEXT NOT NULL CHECK (privacy_mode IN ('aggregate', 'synthetic_demo')),
    report_set_sha256 CHAR(64) NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completed', 'superseded', 'failed')),
    policy_version TEXT NOT NULL,
    input_rows INTEGER NOT NULL CHECK (input_rows >= 0),
    duplicate_rows_removed INTEGER NOT NULL CHECK (duplicate_rows_removed >= 0),
    privacy_excluded_rows INTEGER NOT NULL CHECK (privacy_excluded_rows >= 0),
    department_feature_rows INTEGER NOT NULL CHECK (department_feature_rows >= 0),
    synthetic_employee_feature_rows INTEGER NOT NULL CHECK (synthetic_employee_feature_rows >= 0),
    suppressed_departments INTEGER NOT NULL CHECK (suppressed_departments >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_activity_report_set_month_hash UNIQUE (report_month, privacy_mode, report_set_sha256)
);

CREATE TABLE IF NOT EXISTS audit.activity_report_file (
    batch_id UUID NOT NULL REFERENCES audit.activity_report_set_batch(batch_id) ON DELETE CASCADE,
    report_type TEXT NOT NULL CHECK (report_type IN ('job_site_access', 'web_search', 'document_usage')),
    filename_sha256 CHAR(64) NOT NULL,
    file_sha256 CHAR(64) NOT NULL,
    input_rows INTEGER NOT NULL CHECK (input_rows >= 0),
    duplicate_rows_removed INTEGER NOT NULL CHECK (duplicate_rows_removed >= 0),
    privacy_excluded_rows INTEGER NOT NULL CHECK (privacy_excluded_rows >= 0),
    rows_after_privacy INTEGER NOT NULL CHECK (rows_after_privacy >= 0),
    PRIMARY KEY (batch_id, report_type)
);

CREATE TABLE IF NOT EXISTS audit.activity_report_exclusion_summary (
    batch_id UUID NOT NULL REFERENCES audit.activity_report_set_batch(batch_id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    PRIMARY KEY (batch_id, category)
);

CREATE TABLE IF NOT EXISTS features.department_monthly_activity (
    department_id_hash CHAR(32) NOT NULL,
    report_month DATE NOT NULL,
    source_batch_id UUID NOT NULL REFERENCES audit.activity_report_set_batch(batch_id),
    cohort_employee_count INTEGER NOT NULL CHECK (cohort_employee_count >= 1),
    job_site_events INTEGER NOT NULL CHECK (job_site_events >= 0),
    job_site_seconds DOUBLE PRECISION NOT NULL CHECK (job_site_seconds >= 0),
    job_site_active_days INTEGER NOT NULL CHECK (job_site_active_days BETWEEN 0 AND 31),
    web_search_events INTEGER NOT NULL CHECK (web_search_events >= 0),
    web_search_active_days INTEGER NOT NULL CHECK (web_search_active_days BETWEEN 0 AND 31),
    document_usage_events INTEGER NOT NULL CHECK (document_usage_events >= 0),
    document_active_days INTEGER NOT NULL CHECK (document_active_days BETWEEN 0 AND 31),
    document_create_events INTEGER NOT NULL CHECK (document_create_events >= 0),
    document_modify_events INTEGER NOT NULL CHECK (document_modify_events >= 0),
    document_view_events INTEGER NOT NULL CHECK (document_view_events >= 0),
    after_hours_search_ratio DOUBLE PRECISION NOT NULL CHECK (after_hours_search_ratio BETWEEN 0 AND 1),
    after_hours_document_ratio DOUBLE PRECISION NOT NULL CHECK (after_hours_document_ratio BETWEEN 0 AND 1),
    weekend_search_ratio DOUBLE PRECISION NOT NULL CHECK (weekend_search_ratio BETWEEN 0 AND 1),
    weekend_document_ratio DOUBLE PRECISION NOT NULL CHECK (weekend_document_ratio BETWEEN 0 AND 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (department_id_hash, report_month)
);

CREATE TABLE IF NOT EXISTS features.synthetic_employee_monthly_activity (
    employee_id_hash CHAR(32) NOT NULL,
    department_id_hash CHAR(32) NOT NULL,
    report_month DATE NOT NULL,
    source_batch_id UUID NOT NULL REFERENCES audit.activity_report_set_batch(batch_id),
    job_site_events INTEGER NOT NULL CHECK (job_site_events >= 0),
    job_site_seconds DOUBLE PRECISION NOT NULL CHECK (job_site_seconds >= 0),
    job_site_active_days INTEGER NOT NULL CHECK (job_site_active_days BETWEEN 0 AND 31),
    web_search_events INTEGER NOT NULL CHECK (web_search_events >= 0),
    web_search_active_days INTEGER NOT NULL CHECK (web_search_active_days BETWEEN 0 AND 31),
    document_usage_events INTEGER NOT NULL CHECK (document_usage_events >= 0),
    document_active_days INTEGER NOT NULL CHECK (document_active_days BETWEEN 0 AND 31),
    document_create_events INTEGER NOT NULL CHECK (document_create_events >= 0),
    document_modify_events INTEGER NOT NULL CHECK (document_modify_events >= 0),
    document_view_events INTEGER NOT NULL CHECK (document_view_events >= 0),
    after_hours_search_ratio DOUBLE PRECISION NOT NULL CHECK (after_hours_search_ratio BETWEEN 0 AND 1),
    after_hours_document_ratio DOUBLE PRECISION NOT NULL CHECK (after_hours_document_ratio BETWEEN 0 AND 1),
    weekend_search_ratio DOUBLE PRECISION NOT NULL CHECK (weekend_search_ratio BETWEEN 0 AND 1),
    weekend_document_ratio DOUBLE PRECISION NOT NULL CHECK (weekend_document_ratio BETWEEN 0 AND 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (employee_id_hash, report_month)
);

COMMENT ON TABLE features.department_monthly_activity IS
'Production-safe cohort features from the three monthly activity reports. Raw names, search text, titles, filenames and sites are not persisted. Departments below the configured minimum cohort size are suppressed.';

COMMENT ON TABLE features.synthetic_employee_monthly_activity IS
'Employee-level feature table reserved for synthetic portfolio data only. Runtime code blocks real filenames from entering this table.';

COMMENT ON TABLE audit.activity_report_exclusion_summary IS
'Batch-level counts for privacy-filtered sensitive categories only; no employee identifier or raw text is retained.';

INSERT INTO core.app_metadata (key, value)
VALUES ('schema_version', 'step4-actual-reports-v1')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();

COMMIT;
