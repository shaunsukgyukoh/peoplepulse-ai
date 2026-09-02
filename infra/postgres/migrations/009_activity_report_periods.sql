BEGIN;

ALTER TABLE audit.activity_report_set_batch
    ADD COLUMN IF NOT EXISTS period_start DATE,
    ADD COLUMN IF NOT EXISTS period_end DATE;

UPDATE audit.activity_report_set_batch
SET period_start = COALESCE(period_start, report_month),
    period_end = COALESCE(
        period_end,
        (report_month + INTERVAL '1 month - 1 day')::date
    )
WHERE period_start IS NULL OR period_end IS NULL;

ALTER TABLE audit.activity_report_set_batch
    ALTER COLUMN period_start SET NOT NULL,
    ALTER COLUMN period_end SET NOT NULL;

ALTER TABLE audit.activity_report_set_batch
    DROP CONSTRAINT IF EXISTS uq_activity_report_set_month_hash;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_activity_report_set_period'
          AND conrelid = 'audit.activity_report_set_batch'::regclass
    ) THEN
        ALTER TABLE audit.activity_report_set_batch
            ADD CONSTRAINT ck_activity_report_set_period
            CHECK (period_end >= period_start);
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_activity_report_set_period_hash'
          AND conrelid = 'audit.activity_report_set_batch'::regclass
    ) THEN
        ALTER TABLE audit.activity_report_set_batch
            ADD CONSTRAINT uq_activity_report_set_period_hash
            UNIQUE (period_start, period_end, privacy_mode, report_set_sha256);
    END IF;
END $$;

COMMENT ON COLUMN audit.activity_report_set_batch.period_start IS
'Start date automatically read from the workbook period metadata, or inferred from event dates.';

COMMENT ON COLUMN audit.activity_report_set_batch.period_end IS
'End date automatically read from the workbook period metadata, or inferred from event dates.';

INSERT INTO core.app_metadata (key, value)
VALUES ('activity_report_period_schema', 'v1')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();

COMMIT;
