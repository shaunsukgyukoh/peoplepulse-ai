"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import type { EChartsOption } from "echarts";

import EChart from "@/components/EChart";
import {
  apiBase,
  getJson,
  patchJson,
  type EmployeeRow,
  type EmployeesResponse,
  type Overview,
  type OrganizationSupportTimelineResponse,
  type OrganizationTimelineScope,
  type SlackLive,
  type SlackTrendPoint,
  type TrendGranularity,
} from "@/lib/api";

const SIGNAL_LABEL: Record<string, string> = {
  satisfied: "긍정적 업무 표현",
  neutral: "중립적 표현",
  frustrated: "업무 답답함 표현",
  angry: "강한 부정 표현",
  dissatisfied: "업무 불만 표현",
  overloaded: "과부하 표현",
  conflict: "갈등 표현",
  disengaged: "몰입 저하 표현",
};

const SELF_REPORT_LABEL: Record<string, string> = {
  good: "좋음",
  okay: "보통",
  needs_support: "지원 필요",
  prefer_not_to_say: "응답 안 함",
  not_reported: "미입력",
};

const TREND_GRANULARITY_OPTIONS: Array<{
  value: TrendGranularity;
  label: string;
  detail: string;
}> = [
  { value: "hour", label: "시간", detail: "최근 24시간" },
  { value: "day", label: "일", detail: "최근 30일" },
  { value: "week", label: "주", detail: "최근 12주" },
  { value: "month", label: "월", detail: "최근 12개월" },
];

type TimelineMetric = "work_strain" | "self_report";

function pct(value: number | undefined | null): string {
  return typeof value === "number" && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "—";
}

function signalChart(points: SlackTrendPoint[]): EChartsOption {
  return {
    backgroundColor: "transparent",
    tooltip: { trigger: "axis", valueFormatter: (value) => `${(Number(value) * 100).toFixed(1)}%` },
    legend: { data: ["업무 긴장 신호", "긍정 표현", "과부하 표현"], textStyle: { color: "#9bb5ad" } },
    grid: { left: 42, right: 22, top: 42, bottom: 30 },
    xAxis: {
      type: "category",
      data: points.map((p) => new Date(p.bucket).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })),
      boundaryGap: false,
      axisLine: { lineStyle: { color: "rgba(184,216,207,.14)" } },
      axisLabel: { color: "#78958c", hideOverlap: true },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 1,
      axisLabel: { color: "#78958c", formatter: (value: number) => `${Math.round(value * 100)}%` },
      splitLine: { lineStyle: { color: "rgba(184,216,207,.08)" } },
    },
    series: [
      { name: "업무 긴장 신호", type: "line", smooth: true, showSymbol: false, data: points.map((p) => p.work_strain) },
      { name: "긍정 표현", type: "line", smooth: true, showSymbol: false, data: points.map((p) => p.satisfied) },
      { name: "과부하 표현", type: "line", smooth: true, showSymbol: false, data: points.map((p) => p.overloaded) },
    ],
  };
}

function trendBucketLabel(bucket: string, granularity: TrendGranularity): string {
  const date = new Date(bucket);
  if (granularity === "hour") {
    return date.toLocaleString("ko-KR", {
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
    });
  }
  if (granularity === "month") {
    return date.toLocaleDateString("ko-KR", { year: "numeric", month: "short" });
  }
  return date.toLocaleDateString("ko-KR", { month: "numeric", day: "numeric" });
}

function timelineBucketAxis(
  result: OrganizationSupportTimelineResponse,
  metric: TimelineMetric,
): string[] {
  const buckets = Object.values(result.scopes).flatMap((scope) => (
    metric === "work_strain"
      ? scope.work_signal_points.map((point) => point.bucket)
      : scope.self_report_points.map((point) => point.bucket)
  ));
  return Array.from(new Set(buckets)).sort();
}

function overallTimelineChart(
  scope: OrganizationTimelineScope,
  granularity: TrendGranularity,
  metric: TimelineMetric,
  buckets: string[],
): EChartsOption {
  const points = metric === "work_strain"
    ? scope.work_signal_points.map((point) => ({
        bucket: point.bucket,
        value: point.work_strain,
      }))
    : scope.self_report_points.map((point) => ({
        bucket: point.bucket,
        value: point.status_rates.needs_support,
      }));
  const values = new Map(points.map((point) => [point.bucket, point.value]));
  const label = metric === "work_strain" ? "업무 커뮤니케이션 긴장" : "자발적 지원 필요 응답";
  return {
    tooltip: { trigger: "axis", valueFormatter: (value) => `${(Number(value) * 100).toFixed(1)}%` },
    grid: { left: 46, right: 22, top: 26, bottom: 42 },
    xAxis: {
      type: "category",
      data: buckets.map((bucket) => trendBucketLabel(bucket, granularity)),
      boundaryGap: false,
      axisLine: { lineStyle: { color: "rgba(184,216,207,.14)" } },
      axisLabel: { color: "#78958c", hideOverlap: true, rotate: granularity === "hour" ? 25 : 0 },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 1,
      axisLabel: { color: "#78958c", formatter: (value: number) => `${Math.round(value * 100)}%` },
      splitLine: { lineStyle: { color: "rgba(184,216,207,.08)" } },
    },
    series: [
      {
        name: label,
        type: "line",
        smooth: true,
        showSymbol: false,
        areaStyle: { color: "rgba(101,230,180,.08)" },
        lineStyle: { width: 3, color: "#65e6b4" },
        itemStyle: { color: "#65e6b4" },
        data: buckets.map((bucket) => values.get(bucket) ?? null),
      },
    ],
  };
}

function groupedTimelineHeatmap(
  scope: OrganizationTimelineScope,
  granularity: TrendGranularity,
  metric: TimelineMetric,
  buckets: string[],
): EChartsOption {
  const groups = scope.groups.filter((group) => group.eligible).map((group) => group.label);
  const sourcePoints = metric === "work_strain"
    ? scope.work_signal_points.map((point) => ({
        group: point.group,
        bucket: point.bucket,
        value: point.work_strain,
      }))
    : scope.self_report_points.map((point) => ({
        group: point.group,
        bucket: point.bucket,
        value: point.status_rates.needs_support,
      }));
  const data: Array<[number, number, number]> = sourcePoints
    .filter((point) => groups.includes(point.group))
    .map((point) => [buckets.indexOf(point.bucket), groups.indexOf(point.group), point.value]);
  return {
    tooltip: { position: "top" },
    grid: { left: 104, right: 24, top: 18, bottom: 64 },
    xAxis: {
      type: "category",
      data: buckets.map((bucket) => trendBucketLabel(bucket, granularity)),
      splitArea: { show: true },
      axisLine: { lineStyle: { color: "rgba(184,216,207,.14)" } },
      axisLabel: { color: "#78958c", hideOverlap: true, rotate: granularity === "hour" ? 25 : 0 },
    },
    yAxis: {
      type: "category",
      data: groups,
      splitArea: { show: true },
      axisLabel: { color: "#9bb5ad", width: 92, overflow: "truncate" },
    },
    visualMap: {
      min: 0,
      max: 1,
      calculable: false,
      orient: "horizontal",
      left: "center",
      bottom: 4,
      text: ["높음", "낮음"],
      textStyle: { color: "#78958c" },
      inRange: { color: ["#17362e", "#65e6b4", "#f5c76b", "#ff8e8e"] },
    },
    series: [
      {
        name: metric === "work_strain" ? "업무 커뮤니케이션 긴장" : "자발적 지원 필요 응답",
        type: "heatmap",
        data,
        label: { show: false },
        emphasis: { itemStyle: { shadowBlur: 12, shadowColor: "rgba(0,0,0,.45)" } },
      },
    ],
  };
}

function timelinePointCount(scope: OrganizationTimelineScope, metric: TimelineMetric): number {
  return metric === "work_strain"
    ? scope.work_signal_points.length
    : scope.self_report_points.length;
}

function timelineHeatmapHeight(scope: OrganizationTimelineScope): number {
  const eligibleGroups = scope.groups.filter((group) => group.eligible).length;
  return Math.max(260, Math.min(620, eligibleGroups * 30 + 100));
}

function selfReportChart(summary: EmployeesResponse | null): EChartsOption {
  const rows = summary?.summary.self_report ?? {};
  return {
    tooltip: { trigger: "item" },
    legend: { bottom: 0, textStyle: { color: "#9bb5ad" } },
    series: [
      {
        type: "pie",
        radius: ["42%", "68%"],
        center: ["50%", "43%"],
        label: { color: "#eef8f4", formatter: "{b}\n{c}명" },
        data: ["good", "okay", "needs_support", "prefer_not_to_say", "not_reported"].map((key) => ({
          name: SELF_REPORT_LABEL[key],
          value: Number(rows[key] ?? 0),
        })),
      },
    ],
  };
}

export default function DashboardPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [employeesData, setEmployeesData] = useState<EmployeesResponse | null>(null);
  const [live, setLive] = useState<SlackLive | null>(null);
  const [trend, setTrend] = useState<SlackTrendPoint[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [signalRevision, setSignalRevision] = useState(0);

  const [query, setQuery] = useState("");
  const [department, setDepartment] = useState("all");
  const [status, setStatus] = useState("all");
  const [starredOnly, setStarredOnly] = useState(false);
  const [sortBy, setSortBy] = useState("starred");
  const [adminToken, setAdminToken] = useState("");
  const [savingStar, setSavingStar] = useState<string | null>(null);
  const [trendGranularity, setTrendGranularity] = useState<TrendGranularity>("week");
  const [timelineMetric, setTimelineMetric] = useState<TimelineMetric>("self_report");
  const [timelineData, setTimelineData] = useState<OrganizationSupportTimelineResponse | null>(null);
  const [timelineError, setTimelineError] = useState<string | null>(null);

  const [reportMonth, setReportMonth] = useState("2026-07");
  const [jobFile, setJobFile] = useState<File | null>(null);
  const [searchFile, setSearchFile] = useState<File | null>(null);
  const [docFile, setDocFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState("");

  const load = useCallback(async () => {
    try {
      const [overviewData, employeeRows, trendData] = await Promise.all([
        getJson<Overview>("/api/v1/dashboard/overview"),
        getJson<EmployeesResponse>("/api/v1/dashboard/employees"),
        getJson<{ points: SlackTrendPoint[] }>("/api/v1/dashboard/slack/trend?minutes=60"),
      ]);
      setOverview(overviewData);
      setEmployeesData(employeeRows);
      setLive(overviewData.slack);
      setTrend(trendData.points);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 30_000);
    return () => window.clearInterval(timer);
  }, [load]);

  useEffect(() => {
    const source = new EventSource(`${apiBase()}/api/v1/dashboard/slack/stream`);
    source.addEventListener("slack_signal", (event) => {
      const message = event as MessageEvent<string>;
      setLive(JSON.parse(message.data) as SlackLive);
      setConnected(true);
      setSignalRevision((revision) => revision + 1);
      void getJson<{ points: SlackTrendPoint[] }>("/api/v1/dashboard/slack/trend?minutes=60")
        .then((data) => setTrend(data.points))
        .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
    });
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    return () => source.close();
  }, []);

  const departments = useMemo(
    () => Array.from(new Set((employeesData?.employees ?? []).map((row) => row.department))).sort(),
    [employeesData],
  );

  useEffect(() => {
    let cancelled = false;
    const path = `/api/v1/dashboard/organization/support-timeline?granularity=${trendGranularity}`;
    void getJson<OrganizationSupportTimelineResponse>(path)
      .then((result) => {
        if (!cancelled) {
          setTimelineData(result);
          setTimelineError(null);
        }
      })
      .catch((reason) => {
        if (!cancelled) {
          setTimelineData(null);
          setTimelineError(reason instanceof Error ? reason.message : String(reason));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [signalRevision, trendGranularity]);

  const filteredEmployees = useMemo(() => {
    const rows = [...(employeesData?.employees ?? [])].filter((row) => {
      const q = query.trim().toLowerCase();
      const matchesQuery = !q || [row.employee_name, row.department, row.job_title ?? ""].some((value) => value.toLowerCase().includes(q));
      const matchesDepartment = department === "all" || row.department === department;
      const rowStatus = row.self_report_status ?? "not_reported";
      const matchesStatus = status === "all" || rowStatus === status;
      const matchesStar = !starredOnly || row.is_key_staff;
      return matchesQuery && matchesDepartment && matchesStatus && matchesStar;
    });

    rows.sort((a, b) => {
      if (sortBy === "name") return a.employee_name.localeCompare(b.employee_name, "ko");
      if (sortBy === "department") return a.department.localeCompare(b.department, "ko") || a.employee_name.localeCompare(b.employee_name, "ko");
      if (sortBy === "status") return (a.self_report_status ?? "zz").localeCompare(b.self_report_status ?? "zz") || a.employee_name.localeCompare(b.employee_name, "ko");
      return Number(b.is_key_staff) - Number(a.is_key_staff) || a.employee_name.localeCompare(b.employee_name, "ko");
    });
    return rows;
  }, [employeesData, query, department, status, starredOnly, sortBy]);

  async function toggleKeyStaff(row: EmployeeRow) {
    if (!adminToken) {
      setError("핵심인력 별표를 변경하려면 관리자 토큰을 입력하세요.");
      return;
    }
    setSavingStar(row.employee_id_hash);
    try {
      await patchJson(`/api/v1/dashboard/employees/${row.employee_id_hash}/key-staff`, { is_key_staff: !row.is_key_staff }, adminToken);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setSavingStar(null);
    }
  }

  async function uploadReports(event: FormEvent) {
    event.preventDefault();
    if (!jobFile || !searchFile || !docFile || !adminToken) return;
    setUploading(true);
    setUploadResult("Processing three monthly reports...");
    try {
      const data = new FormData();
      data.append("admin_token", adminToken);
      data.append("report_month", reportMonth);
      data.append("files", jobFile);
      data.append("files", searchFile);
      data.append("files", docFile);
      const response = await fetch(`${apiBase()}/api/v1/activity/report-sets`, { method: "POST", body: data });
      const body = await response.json();
      if (!response.ok) throw new Error(JSON.stringify(body, null, 2));
      setUploadResult(JSON.stringify(body, null, 2));
      await load();
    } catch (reason) {
      setUploadResult(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setUploading(false);
    }
  }

  const workforce = employeesData?.summary ?? overview?.workforce;
  const currentLive = live ?? overview?.slack;
  const needsSupport = workforce?.self_report?.needs_support ?? 0;
  const timelineScopes = timelineData?.scopes;
  const timelineSourceTitle = timelineMetric === "work_strain"
    ? "업무 커뮤니케이션 긴장"
    : "자발적 지원 필요 응답";
  const timelineSourceDetail = timelineMetric === "work_strain"
    ? "Slack 업무 표현을 직원별로 먼저 평균한 뒤 조직도상 부서별로만 재집계합니다. 심리 상태나 정신건강 진단이 아닙니다."
    : "직원이 직접 제출한 self-report 중 ‘지원 필요’ 응답 비율입니다. 개인 응답은 표시하지 않습니다.";
  const timelineAxisBuckets = timelineData ? timelineBucketAxis(timelineData, timelineMetric) : [];

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark">P</div><div>PeoplePulse</div></div>
        <div className="brand-sub">HR workforce support dashboard</div>
        <nav className="nav">
          <a href="#overview">운영 요약</a>
          <a href="#state-trends">조직 타임라인</a>
          <a href="#employees">직원 현황</a>
          <a href="#signals">조직 업무 신호</a>
          <a href="#reports">월말 데이터 업데이트</a>
        </nav>
        <div className="sidebar-note">
          <strong>운영 원칙</strong><br />직원별 상태는 자발적 self-report만 표시합니다. Slack NLP는 조직 수준 업무 커뮤니케이션 추세로만 사용하며 심리·정신건강 진단이나 인사 의사결정에 사용하지 않습니다.
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <div className="eyebrow">PRODUCTION HR OPERATIONS</div>
            <h1>조직의 흐름을 먼저 보고,<br />지원이 필요한 곳을 찾습니다.</h1>
            <p>전체·조직도상 부서·직책의 시계열을 같은 화면에서 비교하고, 자발적 상태 공유와 업무 커뮤니케이션 신호의 출처를 분리해 보여줍니다. 개인 심리 추론이나 인사 판단 점수는 제공하지 않습니다.</p>
          </div>
          <div className="status-cluster">
            <span className={`badge ${connected ? "badge-live" : ""}`}><span className="dot" />{connected ? "Live" : "Reconnecting"}</span>
            <span className="badge">Production main</span>
          </div>
        </header>

        {error && <div className="notice error">{error}</div>}

        <section id="overview" className="section-shell">
          <div className="section-head"><div><div className="eyebrow">Overview</div><h2>운영 요약</h2><p>HR 운영에 필요한 현재 상태만 보여줍니다.</p></div></div>
          <div className="grid-5">
            <div className="metric-card metric-card-accent"><div className="metric-label">재직 직원</div><div className="metric-value">{workforce?.employee_count ?? 0}</div><div className="metric-detail">Employee Directory 기준</div></div>
            <div className="metric-card"><div className="metric-label">핵심인력</div><div className="metric-value">★ {workforce?.key_staff_count ?? 0}</div><div className="metric-detail">관리자가 수동 지정</div></div>
            <div className="metric-card"><div className="metric-label">Self-report 지원 필요</div><div className="metric-value">{needsSupport}</div><div className="metric-detail">자발적 상태 공유 기준</div></div>
            <div className="metric-card"><div className="metric-label">조직 업무 긴장 신호</div><div className="metric-value">{pct(currentLive?.work_strain)}</div><div className="metric-detail">최근 15분 조직 전체 집계</div></div>
            <div className="metric-card"><div className="metric-label">최근 월말 데이터</div><div className="metric-value">{overview?.latest_report?.report_month ?? "—"}</div><div className="metric-detail">3종 보고서 처리 현황</div></div>
          </div>
        </section>

        <section id="state-trends" className="section-shell">
          <div className="section-head trend-section-head">
            <div>
              <div className="eyebrow">Organization Support Timeline</div>
              <h2>전체·부서·직책을 한 시간축에서</h2>
              <p>전체 조직의 흐름을 먼저 보고, 같은 기간의 조직도상 부서와 직책별 차이를 히트맵으로 함께 비교합니다. 모든 그룹은 최소 인원 기준을 통과한 구간만 표시합니다.</p>
            </div>
            <div className="timeline-control-stack">
              <div className="source-tabs" aria-label="타임라인 데이터 출처">
                <button type="button" className={timelineMetric === "work_strain" ? "active" : ""} onClick={() => setTimelineMetric("work_strain")}>업무 커뮤니케이션 · 부서</button>
                <button type="button" className={timelineMetric === "self_report" ? "active" : ""} onClick={() => setTimelineMetric("self_report")}>Self-report · 전체/부서/직책</button>
              </div>
              <div className="range-tabs" aria-label="추세 집계 단위">
                {TREND_GRANULARITY_OPTIONS.map((option) => (
                  <button
                    type="button"
                    key={option.value}
                    className={trendGranularity === option.value ? "active" : ""}
                    onClick={() => setTrendGranularity(option.value)}
                    title={option.detail}
                  >
                    {option.label}<small>{option.detail}</small>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="timeline-source-note">
            <div><span className="timeline-source-dot" />{timelineSourceTitle}</div>
            <p>{timelineSourceDetail}</p>
            <span>구간별 최소 {timelineData?.minimum_cohort_size ?? 5}명</span>
          </div>
          {timelineError && <div className="notice error">{timelineError}</div>}

          <div className="timeline-overview-grid">
            <div className="panel timeline-overall-panel">
              <div className="panel-title">
                <span>전체 조직 타임라인</span>
                <span className="panel-subtitle">{timelineScopes?.overall.groups[0]?.active_employee_count ?? 0}명 · organization-wide</span>
              </div>
              {timelineMetric === "work_strain" ? (
                <div className="timeline-empty">업무 커뮤니케이션 신호는 조직도상 부서 집계에서만 제공합니다. 전체 조직 추세는 자발적 Self-report 보기에서 확인할 수 있습니다.</div>
              ) : timelineScopes?.overall && timelinePointCount(timelineScopes.overall, timelineMetric) > 0 ? (
                <EChart option={overallTimelineChart(timelineScopes.overall, trendGranularity, timelineMetric, timelineAxisBuckets)} height={310} />
              ) : <div className="timeline-empty">선택한 기간에 최소 인원 기준을 충족한 전체 조직 데이터가 없습니다.</div>}
            </div>
            <div className="timeline-reading-guide">
              <div className="eyebrow">HOW TO READ</div>
              <strong>{timelineMetric === "self_report" ? <>전체 흐름에서 시작해<br />그룹 차이로 내려갑니다.</> : <>부서 간 업무 표현의<br />변화만 비교합니다.</>}</strong>
              {timelineMetric === "self_report" ? (
                <ol>
                  <li>전체 조직 선으로 변화 시점을 확인</li>
                  <li>부서 히트맵에서 같은 시점의 차이 확인</li>
                  <li>직책 히트맵으로 역할군의 공통 패턴 확인</li>
                </ol>
              ) : (
                <ol>
                  <li>부서 히트맵에서 변화 시점 확인</li>
                  <li>업무환경 개선 논의의 시작점으로만 활용</li>
                  <li>개인이나 직책 단위로 역추적하지 않음</li>
                </ol>
              )}
              <p>색이 진해도 개인 심리 진단이나 인사 판단 근거로 사용할 수 없습니다.</p>
            </div>
          </div>

          <div className="timeline-heatmap-grid">
            <div className="panel timeline-heatmap-panel">
              <div className="panel-title">
                <span>조직도상 부서별</span>
                <span className="panel-subtitle">{timelineScopes?.department.groups.filter((group) => group.eligible).length ?? 0}개 부서 표시</span>
              </div>
              {timelineScopes?.department && timelinePointCount(timelineScopes.department, timelineMetric) > 0 ? (
                <EChart option={groupedTimelineHeatmap(timelineScopes.department, trendGranularity, timelineMetric, timelineAxisBuckets)} height={timelineHeatmapHeight(timelineScopes.department)} />
              ) : <div className="timeline-empty">이 기간에는 최소 인원 기준을 통과한 부서별 구간이 없습니다.</div>}
              <div className="trend-policy">employee_directory.department 기준 · 직원별 선집계 → 부서 평균</div>
            </div>

            <div className="panel timeline-heatmap-panel">
              <div className="panel-title">
                <span>직책별</span>
                <span className="panel-subtitle">{timelineScopes?.job_title.groups.filter((group) => group.eligible).length ?? 0}개 직책 표시</span>
              </div>
              {timelineMetric === "work_strain" ? (
                <div className="timeline-empty">Slack 파생 업무 신호는 직책별로 제공하지 않습니다. 직책 타임라인은 자발적 Self-report 보기에서만 표시합니다.</div>
              ) : timelineScopes?.job_title && timelinePointCount(timelineScopes.job_title, timelineMetric) > 0 ? (
                <EChart option={groupedTimelineHeatmap(timelineScopes.job_title, trendGranularity, timelineMetric, timelineAxisBuckets)} height={timelineHeatmapHeight(timelineScopes.job_title)} />
              ) : <div className="timeline-empty">이 기간에는 최소 인원 기준을 통과한 직책별 구간이 없습니다.</div>}
              <div className="trend-policy">employee_directory.job_title 기준 · 직책 미입력은 별도 그룹</div>
            </div>
          </div>

          <div className="timeline-policy-strip">
            <span>{timelineMetric === "self_report" ? "전체 · 부서 · 직책 동시 비교" : "조직도상 부서만 제공"}</span>
            <span>개인 식별값 0건</span>
            <span>원문 비저장</span>
            <span>심리·정신건강 진단 아님</span>
          </div>
        </section>

        <section id="employees" className="section-shell">
          <div className="section-head">
            <div><div className="eyebrow">Employee Directory</div><h2>직원 현황</h2><p>실명·부서·직책과 자발적 self-report 상태를 확인합니다. 별표는 업무 중요도 판단을 위한 수동 메타데이터이며 AI 신호로 자동 지정되지 않습니다.</p></div>
          </div>

          <div className="grid-4 employee-filters">
            <input className="field" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="이름 / 부서 / 직책 검색" />
            <select className="field" value={department} onChange={(e) => setDepartment(e.target.value)}>
              <option value="all">전체 부서</option>{departments.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            <select className="field" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="all">전체 상태</option>
              <option value="good">좋음</option><option value="okay">보통</option><option value="needs_support">지원 필요</option><option value="prefer_not_to_say">응답 안 함</option><option value="not_reported">미입력</option>
            </select>
            <select className="field" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
              <option value="starred">핵심인력 우선</option><option value="name">이름순</option><option value="department">부서순</option><option value="status">상태순</option>
            </select>
          </div>
          <div className="employee-toolbar">
            <label className="star-filter"><input type="checkbox" checked={starredOnly} onChange={(e) => setStarredOnly(e.target.checked)} /> 핵심인력만 보기</label>
            <input className="field admin-token-field" type="password" value={adminToken} onChange={(e) => setAdminToken(e.target.value)} placeholder="관리자 토큰 — 별표/업로드 변경용" />
            <span className="badge">{filteredEmployees.length}명 표시</span>
          </div>

          <div className="table-wrap employee-table-wrap">
            <table>
              <thead><tr><th>핵심</th><th>이름</th><th>부서</th><th>직책</th><th>Self-report</th><th>최근 상태 공유</th></tr></thead>
              <tbody>
                {filteredEmployees.map((row) => {
                  const state = row.self_report_status ?? "not_reported";
                  return (
                    <tr key={row.employee_id_hash}>
                      <td><button className={`star-button ${row.is_key_staff ? "active" : ""}`} disabled={savingStar === row.employee_id_hash} onClick={() => toggleKeyStaff(row)} aria-label={`${row.employee_name} 핵심인력 표시 변경`}>{row.is_key_staff ? "★" : "☆"}</button></td>
                      <td><strong>{row.employee_name}</strong></td>
                      <td>{row.department}</td>
                      <td>{row.job_title ?? "—"}</td>
                      <td><span className={`state-badge state-${state}`}>{SELF_REPORT_LABEL[state]}</span></td>
                      <td>{row.self_report_updated_at ? new Date(row.self_report_updated_at).toLocaleString("ko-KR") : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {!filteredEmployees.length && <div className="notice">조건에 맞는 직원이 없습니다. Employee Directory가 비어 있다면 `scripts/load_employee_directory.py`로 먼저 등록하세요.</div>}
        </section>

        <section id="signals" className="section-shell">
          <div className="section-head"><div><div className="eyebrow">Work Communication Signals</div><h2>조직 업무 신호</h2><p>Slack 원문은 저장하지 않으며 개인별 점수는 표시하지 않습니다. 이 지표는 조직 수준의 업무 커뮤니케이션 추세를 파악해 지원·업무환경 개선 논의를 시작하기 위한 참고값입니다.</p></div></div>
          <div className="grid-2">
            <div className="panel"><div className="panel-title">최근 60분 추세<span className="panel-subtitle">aggregate only</span></div><EChart option={signalChart(trend)} height={330} /></div>
            <div className="panel"><div className="panel-title">자발적 Self-report 분포<span className="panel-subtitle">employee-provided</span></div><EChart option={selfReportChart(employeesData)} height={330} /></div>
          </div>
          <div className="signal-grid">
            {Object.entries(currentLive?.signals ?? {}).map(([key, value]) => <div className="signal" key={key}><div className="signal-name">{SIGNAL_LABEL[key] ?? key}</div><div className="signal-score">{pct(value)}</div><div className="progress"><span style={{ width: `${Math.max(0, Math.min(100, value * 100))}%` }} /></div></div>)}
          </div>
        </section>

        <section id="reports" className="section-shell">
          <div className="section-head"><div><div className="eyebrow">Data Operations</div><h2>월말 데이터 업데이트</h2><p>관리자가 3종 보고서를 한 번에 업로드합니다. 운영 Dashboard에는 모델 성능/실험 지표를 노출하지 않습니다.</p></div></div>
          <form onSubmit={uploadReports}>
            <div className="upload-grid">
              <label>Report month</label><input className="field" type="month" value={reportMonth} onChange={(e) => setReportMonth(e.target.value)} />
              <label>취업사이트 접속내역</label><input className="field" type="file" accept=".xls,.xlsx" onChange={(e) => setJobFile(e.target.files?.[0] ?? null)} />
              <label>웹 검색 내역</label><input className="field" type="file" accept=".xls,.xlsx" onChange={(e) => setSearchFile(e.target.files?.[0] ?? null)} />
              <label>문서활용 내역</label><input className="field" type="file" accept=".xls,.xlsx" onChange={(e) => setDocFile(e.target.files?.[0] ?? null)} />
            </div>
            <div style={{ marginTop: 14 }}><button className="primary-button" disabled={!adminToken || !jobFile || !searchFile || !docFile || uploading}>{uploading ? "처리 중..." : "3개 보고서 검증 및 처리"}</button></div>
          </form>
          {uploadResult && <pre className="upload-result" style={{ marginTop: 14 }}>{uploadResult}</pre>}
        </section>

        <div className="footer">PeoplePulse production main · 개인별 Slack NLP/정신건강 추론/퇴사 위험 순위는 운영 Dashboard에 제공하지 않습니다. 핵심인력 별표는 관리자의 독립적인 수동 지정 값입니다.</div>
      </main>
    </div>
  );
}
