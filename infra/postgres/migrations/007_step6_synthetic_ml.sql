BEGIN;

CREATE TABLE IF NOT EXISTS ml.synthetic_attrition_experiment (
    experiment_id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    feature_set TEXT NOT NULL CHECK (feature_set IN ('privacy_safe', 'synthetic_full')),
    target_name TEXT NOT NULL CHECK (target_name IN ('attrition_30d', 'attrition_60d', 'attrition_90d')),
    selected_model TEXT NOT NULL,
    average_precision DOUBLE PRECISION NOT NULL CHECK (average_precision BETWEEN 0 AND 1),
    pr_auc DOUBLE PRECISION NOT NULL CHECK (pr_auc BETWEEN 0 AND 1),
    roc_auc DOUBLE PRECISION NOT NULL CHECK (roc_auc BETWEEN 0 AND 1),
    brier_score DOUBLE PRECISION NOT NULL CHECK (brier_score BETWEEN 0 AND 1),
    data_scope TEXT NOT NULL DEFAULT 'synthetic_demo' CHECK (data_scope = 'synthetic_demo'),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS ml.synthetic_attrition_prediction (
    experiment_id UUID NOT NULL REFERENCES ml.synthetic_attrition_experiment(experiment_id) ON DELETE CASCADE,
    canonical_employee_id_hash CHAR(32) NOT NULL,
    snapshot_month DATE NOT NULL,
    target_value BOOLEAN NOT NULL,
    calibrated_probability DOUBLE PRECISION NOT NULL CHECK (calibrated_probability BETWEEN 0 AND 1),
    data_scope TEXT NOT NULL DEFAULT 'synthetic_demo' CHECK (data_scope = 'synthetic_demo'),
    PRIMARY KEY (experiment_id, canonical_employee_id_hash, snapshot_month)
);

COMMENT ON TABLE ml.synthetic_attrition_experiment IS
'Synthetic portfolio experiment registry only. It is not a production employee decision table.';
COMMENT ON TABLE ml.synthetic_attrition_prediction IS
'Synthetic-demo predictions only. Real employee-level attrition prediction is intentionally unsupported.';

INSERT INTO core.app_metadata (key, value)
VALUES ('schema_version', 'step6-synthetic-ml-v1')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();

COMMIT;
