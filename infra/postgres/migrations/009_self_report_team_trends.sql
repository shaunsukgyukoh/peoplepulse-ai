BEGIN;

CREATE TABLE IF NOT EXISTS core.employee_self_report_history (
    history_id BIGSERIAL PRIMARY KEY,
    employee_id_hash CHAR(32) NOT NULL REFERENCES core.employee_directory(employee_id_hash)
        ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (
        status IN ('good', 'okay', 'needs_support', 'prefer_not_to_say')
    ),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source TEXT NOT NULL DEFAULT 'directory_self_report',
    UNIQUE (employee_id_hash, recorded_at)
);

CREATE INDEX IF NOT EXISTS idx_employee_self_report_history_employee_time
    ON core.employee_self_report_history (employee_id_hash, recorded_at DESC);

COMMENT ON TABLE core.employee_self_report_history IS
'Voluntary employee-provided self-report history. Never populate from Slack NLP or inferred behavioral signals.';

CREATE OR REPLACE FUNCTION core.capture_employee_self_report_history()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.self_report_status IS NULL THEN
        RETURN NEW;
    END IF;

    IF TG_OP = 'INSERT' OR NEW.self_report_status IS DISTINCT FROM OLD.self_report_status THEN
        INSERT INTO core.employee_self_report_history (
            employee_id_hash, status, recorded_at, source
        ) VALUES (
            NEW.employee_id_hash,
            NEW.self_report_status,
            COALESCE(NEW.self_report_updated_at, NOW()),
            'directory_self_report'
        )
        ON CONFLICT (employee_id_hash, recorded_at) DO NOTHING;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_employee_self_report_history ON core.employee_directory;
CREATE TRIGGER trg_employee_self_report_history
AFTER INSERT OR UPDATE OF self_report_status
ON core.employee_directory
FOR EACH ROW
EXECUTE FUNCTION core.capture_employee_self_report_history();

INSERT INTO core.employee_self_report_history (
    employee_id_hash, status, recorded_at, source
)
SELECT
    d.employee_id_hash,
    d.self_report_status,
    COALESCE(d.self_report_updated_at, d.updated_at, d.created_at),
    'migration_backfill'
FROM core.employee_directory d
WHERE d.self_report_status IS NOT NULL
ON CONFLICT (employee_id_hash, recorded_at) DO NOTHING;

INSERT INTO core.app_metadata (key, value)
VALUES ('schema_version', 'production-main-v2-trends')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();

COMMIT;
