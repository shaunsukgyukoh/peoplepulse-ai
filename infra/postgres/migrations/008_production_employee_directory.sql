BEGIN;

CREATE TABLE IF NOT EXISTS core.employee_directory (
    employee_id_hash CHAR(32) PRIMARY KEY,
    employee_name TEXT NOT NULL,
    department TEXT NOT NULL,
    job_title TEXT,
    is_key_staff BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_employee_directory_department
    ON core.employee_directory (department, employee_name);
CREATE INDEX IF NOT EXISTS idx_employee_directory_key_staff
    ON core.employee_directory (is_key_staff DESC, department, employee_name);

COMMENT ON TABLE core.employee_directory IS
'Production HR directory. Stores manager-visible identity and organizational placement. Slack-derived NLP scores are not stored here.';

COMMENT ON COLUMN core.employee_directory.is_key_staff IS
'Manual manager designation only. Must not be automatically derived from NLP, retention-risk, or other inferred behavioral scores.';

INSERT INTO core.app_metadata (key, value)
VALUES ('schema_version', 'production-main-v1')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();

COMMIT;
