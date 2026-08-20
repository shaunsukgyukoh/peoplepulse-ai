export type SignalMap = Record<string, number>;

export type SlackLive = {
  message_count: number;
  avg_inference_ms: number;
  work_strain: number;
  signals: SignalMap;
  model_name: string | null;
  model_device: string | null;
  last_message_at: string | null;
};

export type Overview = {
  generated_at: string;
  slack: SlackLive;
  latest_report: null | {
    batch_id: string;
    report_month: string;
    privacy_mode: string;
    status: string;
    input_rows: number;
    duplicate_rows_removed: number;
    privacy_excluded_rows: number;
    department_feature_rows: number;
    synthetic_employee_feature_rows: number;
    suppressed_departments: number;
    created_at: string;
  };
  activity: {
    department_rows: number;
    synthetic_employee_rows: number;
    latest_month: string | null;
  };
  nlp_model: Record<string, number | string | null>;
  attrition_model: Record<string, number | string | null>;
  privacy: {
    production_scope: string;
    employee_level_attrition_scope: string;
    raw_slack_text_persisted: boolean;
    raw_activity_text_persisted: boolean;
  };
};

export type SlackTrendPoint = {
  bucket: string;
  message_count: number;
  satisfied: number;
  frustrated: number;
  overloaded: number;
  disengaged: number;
  work_strain: number;
  avg_inference_ms: number;
};

export type AttritionMetrics = {
  source: string;
  scope: string;
  feature_sets: Array<Record<string, number | string>>;
  selected_model: string | null;
  privacy_safe: Record<string, number>;
  privacy_safe_raw: Record<string, number>;
  split: Record<string, unknown>;
  calibration: Record<string, unknown>;
};

export type NlpModel = {
  model: string;
  family: string;
  evaluation?: string;
  macro_f1: number;
  micro_f1: number;
  macro_precision: number;
  macro_recall: number;
  latency_ms_mean: number;
  latency_ms_p95: number;
  device: string;
};

export type ShapResult = {
  source: string;
  features: Array<{
    feature: string;
    mean_abs_shap: number | null;
    rank?: number;
  }>;
};

export function apiBase(): string {
  if (process.env.NEXT_PUBLIC_PEOPLEPULSE_API_URL) {
    return process.env.NEXT_PUBLIC_PEOPLEPULSE_API_URL;
  }
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
}

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}
