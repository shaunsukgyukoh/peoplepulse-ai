-- PeoplePulse AI initial database namespaces.
-- Keep raw/private data isolated from derived ML features and audit metadata.

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS ingest;
CREATE SCHEMA IF NOT EXISTS features;
CREATE SCHEMA IF NOT EXISTS ml;
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS core.app_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO core.app_metadata (key, value)
VALUES
    ('project', 'PeoplePulse AI'),
    ('schema_version', 'step1-v1')
ON CONFLICT (key) DO UPDATE
SET value = EXCLUDED.value,
    updated_at = NOW();

COMMENT ON SCHEMA ingest IS
'Ingestion boundary. Raw employee message text must not be persisted here by default.';

COMMENT ON SCHEMA features IS
'Derived privacy-aware employee/team features used by analytics and ML.';

COMMENT ON SCHEMA ml IS
'Model predictions, explanations, model versions, and evaluation outputs.';

COMMENT ON SCHEMA audit IS
'Privacy, access, pipeline, and model decision audit metadata.';
