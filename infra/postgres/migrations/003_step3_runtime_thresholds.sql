BEGIN;

ALTER TABLE features.message_nlp_signal
    ADD COLUMN IF NOT EXISTS thresholds JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS active_labels TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    ADD COLUMN IF NOT EXISTS model_device TEXT NOT NULL DEFAULT 'unknown';

COMMENT ON COLUMN features.message_nlp_signal.thresholds IS
'Validation-tuned per-label operating thresholds used by the runtime predictor.';
COMMENT ON COLUMN features.message_nlp_signal.active_labels IS
'Operational labels activated from probabilities using validation-tuned thresholds.';
COMMENT ON COLUMN features.message_nlp_signal.model_device IS
'Inference device reported by the runtime predictor, e.g. cuda or cpu.';

INSERT INTO core.app_metadata (key, value)
VALUES ('schema_version', 'step3.2-v1')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();

COMMIT;
