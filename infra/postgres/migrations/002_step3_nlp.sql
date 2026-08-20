BEGIN;

CREATE TABLE IF NOT EXISTS features.message_nlp_signal (
    event_id TEXT PRIMARY KEY,
    employee_id_hash CHAR(32) NOT NULL,
    channel_id_hash CHAR(32) NOT NULL,
    channel_type TEXT NOT NULL,
    message_ts TIMESTAMPTZ,
    received_at TIMESTAMPTZ NOT NULL,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    threshold REAL NOT NULL CHECK (threshold >= 0 AND threshold <= 1),
    inference_ms REAL NOT NULL CHECK (inference_ms >= 0),
    satisfied REAL NOT NULL CHECK (satisfied BETWEEN 0 AND 1),
    neutral REAL NOT NULL CHECK (neutral BETWEEN 0 AND 1),
    frustrated REAL NOT NULL CHECK (frustrated BETWEEN 0 AND 1),
    angry REAL NOT NULL CHECK (angry BETWEEN 0 AND 1),
    dissatisfied REAL NOT NULL CHECK (dissatisfied BETWEEN 0 AND 1),
    overloaded REAL NOT NULL CHECK (overloaded BETWEEN 0 AND 1),
    conflict REAL NOT NULL CHECK (conflict BETWEEN 0 AND 1),
    disengaged REAL NOT NULL CHECK (disengaged BETWEEN 0 AND 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_message_nlp_signal_employee_ts
    ON features.message_nlp_signal (employee_id_hash, message_ts DESC);
CREATE INDEX IF NOT EXISTS idx_message_nlp_signal_channel_ts
    ON features.message_nlp_signal (channel_id_hash, message_ts DESC);

COMMENT ON TABLE features.message_nlp_signal IS
'Derived message-level linguistic signals. No raw Slack message text is stored here.';

INSERT INTO core.app_metadata (key, value)
VALUES ('schema_version', 'step3-v1')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();

COMMIT;
