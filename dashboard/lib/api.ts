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

export type TrendGranularity = "hour" | "day" | "week" | "month";

export type SelfReportTrendPoint = {
  bucket: string;
  status: "good" | "okay" | "needs_support" | "prefer_not_to_say";
  recorded_at: string;
};

export type SelfReportTrendResponse = {
  granularity: TrendGranularity;
  window: string;
  timezone: string;
  source: "voluntary_self_report_only";
  employee: {
    employee_id_hash: string;
    employee_name: string;
    department: string;
  };
  points: SelfReportTrendPoint[];
};

export type DepartmentSignalTrendPoint = {
  department: string;
  bucket: string;
  cohort_employee_count: number;
  message_count: number;
  work_strain: number;
  signals: SignalMap;
};

export type DepartmentSignalTrendResponse = {
  granularity: TrendGranularity;
  window: string;
  timezone: string;
  minimum_cohort_size: number;
  aggregation: string;
  source: "aggregate_work_communication_signals_only";
  departments: Array<{
    department: string;
    active_employee_count: number;
    eligible: boolean;
  }>;
  points: DepartmentSignalTrendPoint[];
};

export type TimelineGrouping = "overall" | "department" | "job_title";

export type TimelineGroup = {
  label: string;
  active_employee_count: number;
  eligible: boolean;
};

export type WorkSignalTimelinePoint = {
  group: string;
  bucket: string;
  cohort_employee_count: number;
  message_count: number;
  work_strain: number;
  signals: SignalMap;
};

export type SelfReportTimelinePoint = {
  group: string;
  bucket: string;
  reporting_employee_count: number;
  status_rates: {
    good: number;
    okay: number;
    needs_support: number;
    prefer_not_to_say: number;
  };
};

export type OrganizationTimelineScope = {
  group_by: TimelineGrouping;
  groups: TimelineGroup[];
  work_signal_points: WorkSignalTimelinePoint[];
  self_report_points: SelfReportTimelinePoint[];
};

export type OrganizationSupportTimelineResponse = {
  granularity: TrendGranularity;
  window: string;
  timezone: string;
  minimum_cohort_size: number;
  groupings: TimelineGrouping[];
  sources: {
    self_report: "voluntary_employee_self_report_only";
    work_signals: "aggregate_work_communication_signals_only";
  };
  source_groupings: {
    self_report: TimelineGrouping[];
    work_signals: TimelineGrouping[];
  };
  privacy: {
    employee_first_aggregation: boolean;
    individual_identifiers_returned: false;
    psychological_diagnosis: false;
  };
  scopes: Record<TimelineGrouping, OrganizationTimelineScope>;
};

export type EmployeeRow = {
  employee_id_hash: string;
  employee_name: string;
  department: string;
  job_title: string | null;
  is_key_staff: boolean;
  self_report_status: "good" | "okay" | "needs_support" | "prefer_not_to_say" | null;
  self_report_updated_at: string | null;
  last_activity_at: string | null;
  message_count_7d: number;
};

export type WorkforceSummary = {
  employee_count: number;
  key_staff_count: number;
  departments: Record<string, number>;
  self_report: Record<string, number>;
};

export type EmployeesResponse = {
  employees: EmployeeRow[];
  summary: WorkforceSummary;
  signal_policy: {
    individual_slack_nlp_visible: boolean;
    individual_state_source: string;
    key_staff_source: string;
    department_minimum_cohort_size: number;
    timeline_groupings: TimelineGrouping[];
  };
};

export type Overview = {
  generated_at: string;
  slack: SlackLive;
  workforce: WorkforceSummary;
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
  privacy: Record<string, string | boolean>;
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
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json() as Promise<T>;
}

export async function getAdminJson<T>(path: string, adminToken: string): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, {
    cache: "no-store",
    headers: { "X-Admin-Token": adminToken },
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.detail ?? `${response.status} ${response.statusText}`);
  return payload as T;
}

export async function patchJson<T>(path: string, body: unknown, adminToken: string): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Token": adminToken,
    },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.detail ?? `${response.status} ${response.statusText}`);
  return payload as T;
}
