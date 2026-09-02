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

const TREND_GRANULARITY_OPTIONS: Array<{
  value: TrendGranularity;
  label: string;
  detail: string;
}> = [
  { value: "hour", label: "60분", detail: "최근 24시간" },
  { value: "day", label: "일별", detail: "최근 30일" },
  { value: "week", label: "주간", detail: "최근 12주" },
  { value: "month", label: "월간", detail: "최근 12개월" },
];

type TimelineSignal = "work_strain" | keyof typeof SIGNAL_LABEL;

const TIMELINE_SIGNAL_OPTIONS: Array<{ value: TimelineSignal; label: string }> = [
  { value: "work_strain", label: "업무 긴장 종합" },
  ...Object.entries(SIGNAL_LABEL).map(([value, label]) => ({
    value: value as TimelineSignal,
    label,
  })),
];

function pct(value: number | undefined | null): string {
  return typeof value === "number" && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "—";
}

function timelineSignalValue(
  point: OrganizationSupportTimelineResponse["points"][number],
  signal: TimelineSignal,
): number {
  return signal === "work_strain" ? point.work_strain : point.signals[signal] ?? 0;
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
): string[] {
  const buckets = result.points.map((point) => point.bucket);
  return Array.from(new Set(buckets)).sort();
}

function departmentTimelineHeatmap(
  result: OrganizationSupportTimelineResponse,
  granularity: TrendGranularity,
  buckets: string[],
  signal: TimelineSignal,
): EChartsOption {
  const groups = result.departments.map((department) => department.department);
  const data: Array<[number, number, number]> = result.points
    .filter((point) => groups.includes(point.department))
    .map((point) => [
      buckets.indexOf(point.bucket),
      groups.indexOf(point.department),
      timelineSignalValue(point, signal),
    ]);
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
        name: TIMELINE_SIGNAL_OPTIONS.find((option) => option.value === signal)?.label,
        type: "heatmap",
        data,
        label: { show: false },
        emphasis: { itemStyle: { shadowBlur: 12, shadowColor: "rgba(0,0,0,.45)" } },
      },
    ],
  };
}

function departmentTimelineLines(
  result: OrganizationSupportTimelineResponse,
  granularity: TrendGranularity,
  buckets: string[],
  signal: TimelineSignal,
): EChartsOption {
  const points = new Map(
    result.points.map((point) => [
      `${point.department}\u0000${point.bucket}`,
      timelineSignalValue(point, signal),
    ]),
  );
  return {
    tooltip: {
      trigger: "axis",
      valueFormatter: (value) => `${(Number(value) * 100).toFixed(1)}%`,
    },
    legend: {
      type: "scroll",
      top: 0,
      textStyle: { color: "#9bb5ad" },
    },
    grid: { left: 46, right: 24, top: 54, bottom: 42 },
    xAxis: {
      type: "category",
      data: buckets.map((bucket) => trendBucketLabel(bucket, granularity)),
      boundaryGap: false,
      axisLine: { lineStyle: { color: "rgba(184,216,207,.14)" } },
      axisLabel: {
        color: "#78958c",
        hideOverlap: true,
        rotate: granularity === "hour" ? 25 : 0,
      },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 1,
      axisLabel: {
        color: "#78958c",
        formatter: (value: number) => `${Math.round(value * 100)}%`,
      },
      splitLine: { lineStyle: { color: "rgba(184,216,207,.08)" } },
    },
    series: result.departments.map((department) => ({
      name: department.department,
      type: "line",
      smooth: true,
      connectNulls: false,
      showSymbol: false,
      data: buckets.map(
        (bucket) => points.get(`${department.department}\u0000${bucket}`) ?? null,
      ),
    })),
  };
}

function timelineHeatmapHeight(result: OrganizationSupportTimelineResponse): number {
  return Math.max(300, Math.min(620, result.departments.length * 30 + 100));
}

export default function DashboardPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [employeesData, setEmployeesData] = useState<EmployeesResponse | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [signalRevision, setSignalRevision] = useState(0);

  const [query, setQuery] = useState("");
  const [department, setDepartment] = useState("all");
  const [starredOnly, setStarredOnly] = useState(false);
  const [sortBy, setSortBy] = useState("starred");
  const [adminToken, setAdminToken] = useState("");
  const [savingStar, setSavingStar] = useState<string | null>(null);
  const [trendGranularity, setTrendGranularity] = useState<TrendGranularity>("week");
  const [timelineSignal, setTimelineSignal] = useState<TimelineSignal>("work_strain");
  const [timelineData, setTimelineData] = useState<OrganizationSupportTimelineResponse | null>(null);
  const [timelineError, setTimelineError] = useState<string | null>(null);

  const [jobFile, setJobFile] = useState<File | null>(null);
  const [searchFile, setSearchFile] = useState<File | null>(null);
  const [docFile, setDocFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState("");

  const load = useCallback(async () => {
    try {
      const [overviewData, employeeRows] = await Promise.all([
        getJson<Overview>("/api/v1/dashboard/overview"),
        getJson<EmployeesResponse>("/api/v1/dashboard/employees"),
      ]);
      setOverview(overviewData);
      setEmployeesData(employeeRows);
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
    source.addEventListener("slack_signal", () => {
      setConnected(true);
      setSignalRevision((revision) => revision + 1);
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
      const matchesStar = !starredOnly || row.is_key_staff;
      return matchesQuery && matchesDepartment && matchesStar;
    });

    rows.sort((a, b) => {
      if (sortBy === "name") return a.employee_name.localeCompare(b.employee_name, "ko");
      if (sortBy === "department") return a.department.localeCompare(b.department, "ko") || a.employee_name.localeCompare(b.employee_name, "ko");
      return Number(b.is_key_staff) - Number(a.is_key_staff) || a.employee_name.localeCompare(b.employee_name, "ko");
    });
    return rows;
  }, [employeesData, query, department, starredOnly, sortBy]);

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
    const missingRequirements = [
      !adminToken.trim() && "관리자 토큰",
      !jobFile && "취업사이트 접속내역",
      !searchFile && "웹 검색 내역",
      !docFile && "문서활용 내역",
    ].filter(Boolean);
    if (!adminToken.trim() || !jobFile || !searchFile || !docFile) {
      setUploadResult(`필수 항목을 확인하세요: ${missingRequirements.join(", ")}`);
      return;
    }
    setUploading(true);
    setUploadResult("3개 활동 보고서의 표시 기간과 내용을 검증하고 있습니다...");
    try {
      const data = new FormData();
      data.append("admin_token", adminToken.trim());
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
  const latestReportPeriod = overview?.latest_report?.period_start && overview.latest_report.period_end
    ? `${overview.latest_report.period_start} – ${overview.latest_report.period_end}`
    : overview?.latest_report?.report_month ?? "—";
  const timelineAxisBuckets = timelineData ? timelineBucketAxis(timelineData) : [];
  const timelineSignalLabel = TIMELINE_SIGNAL_OPTIONS.find(
    (option) => option.value === timelineSignal,
  )?.label;
  const latestDepartmentPoints = timelineData?.departments.map((department) => {
    const points = timelineData.points
      .filter((point) => point.department === department.department)
      .sort((a, b) => b.bucket.localeCompare(a.bucket));
    return { ...department, point: points[0] ?? null };
  }) ?? [];

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark">P</div><div>PeoplePulse</div></div>
        <div className="brand-sub">HR workforce support dashboard</div>
        <nav className="nav">
          <a href="#overview">운영 요약</a>
          <a href="#signals">부서 업무 신호</a>
          <a href="#employees">직원 현황</a>
          <a href="#reports">월말 데이터 업데이트</a>
        </nav>
        <div className="sidebar-note">
          <strong>운영 원칙</strong><br />Slack 업무 신호는 조직도상 부서 단위로만 집계합니다. 개인 점수나 심리·정신건강 진단, 인사 의사결정 지표는 제공하지 않습니다.
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <div className="eyebrow">PRODUCTION HR OPERATIONS</div>
            <h1>부서의 업무 흐름을 보고,<br />환경 개선 시점을 찾습니다.</h1>
            <p>조직도상 부서별 업무 커뮤니케이션 흐름을 동일한 시간축에서 비교합니다. 직원별 상태나 개인 심리 추론, 인사 판단 점수는 제공하지 않습니다.</p>
          </div>
          <div className="status-cluster">
            <span className={`badge ${connected ? "badge-live" : ""}`}><span className="dot" />{connected ? "Live" : "Reconnecting"}</span>
            <span className="badge">Production main</span>
          </div>
        </header>

        {error && <div className="notice error">{error}</div>}

        <section id="overview" className="section-shell">
          <div className="section-head"><div><div className="eyebrow">Overview</div><h2>운영 요약</h2><p>HR 운영에 필요한 현재 상태만 보여줍니다.</p></div></div>
          <div className="grid-3">
            <div className="metric-card metric-card-accent"><div className="metric-label">재직 직원</div><div className="metric-value">{workforce?.employee_count ?? 0}</div><div className="metric-detail">Employee Directory 기준</div></div>
            <div className="metric-card"><div className="metric-label">핵심인력</div><div className="metric-value">★ {workforce?.key_staff_count ?? 0}</div><div className="metric-detail">관리자가 수동 지정</div></div>
            <div className="metric-card"><div className="metric-label">최근 분석 기간</div><div className="metric-value metric-value-period">{latestReportPeriod}</div><div className="metric-detail">엑셀 표시 기간 자동 인식</div></div>
          </div>
        </section>

        <section id="signals" className="section-shell">
          <div className="section-head trend-section-head">
            <div>
              <div className="eyebrow">Department Work Signal Timeline</div>
              <h2>조직도상 부서별 업무 흐름</h2>
              <p>같은 시간축에서 부서별 업무 커뮤니케이션 변화를 비교합니다. 모든 값은 직원별로 먼저 집계하며 최소 인원 기준을 통과한 부서·시간 구간만 표시합니다.</p>
            </div>
            <div className="timeline-control-stack">
              <select
                className="field timeline-signal-select"
                value={timelineSignal}
                onChange={(event) => setTimelineSignal(event.target.value as TimelineSignal)}
                aria-label="업무 신호 선택"
              >
                {TIMELINE_SIGNAL_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
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
            <div><span className="timeline-source-dot" />{timelineSignalLabel}</div>
            <p>Slack 업무 표현을 직원별로 먼저 평균한 뒤 조직도상 부서별로만 재집계합니다. 심리 상태나 정신건강 진단이 아닙니다.</p>
            <span>구간별 최소 {timelineData?.minimum_cohort_size ?? 5}명</span>
          </div>
          {timelineError && <div className="notice error">{timelineError}</div>}

          <div className="timeline-overview-grid">
            <div className="panel timeline-heatmap-panel">
              <div className="panel-title">
                <span>조직도상 부서별</span>
                <span className="panel-subtitle">{timelineData?.departments.length ?? 0}개 부서 표시</span>
              </div>
              {timelineData && timelineData.points.length > 0 ? (
                <EChart option={departmentTimelineHeatmap(timelineData, trendGranularity, timelineAxisBuckets, timelineSignal)} height={timelineHeatmapHeight(timelineData)} />
              ) : <div className="timeline-empty">이 기간에는 최소 인원 기준을 통과한 부서별 구간이 없습니다.</div>}
              <div className="trend-policy">employee_directory.department 기준 · 직원별 선집계 → 부서 평균</div>
            </div>
            <div className="timeline-reading-guide">
              <div className="eyebrow">HOW TO READ</div>
              <strong>부서 간 업무 표현의<br />변화만 비교합니다.</strong>
              <ol>
                <li>히트맵에서 변화 시점을 확인</li>
                <li>업무환경 개선 논의의 시작점으로만 활용</li>
                <li>개인이나 직책 단위로 역추적하지 않음</li>
              </ol>
              <p>색이 진해도 개인 심리 진단이나 인사 판단 근거로 사용할 수 없습니다.</p>
            </div>
          </div>

          <div className="panel department-lines-panel">
            <div className="panel-title">
              <span>전체 표시 가능 부서 비교</span>
              <span className="panel-subtitle">조직 전체 평균이 아닌 부서별 선 비교</span>
            </div>
            {timelineData && timelineData.points.length > 0 ? (
              <EChart option={departmentTimelineLines(timelineData, trendGranularity, timelineAxisBuckets, timelineSignal)} height={360} />
            ) : <div className="timeline-empty">선택한 기간에 비교 가능한 부서 시계열이 없습니다.</div>}
          </div>

          <div className="department-signal-grid">
            {latestDepartmentPoints.map((departmentRow) => (
              <article className="department-signal-card" key={departmentRow.department}>
                <div className="department-signal-head">
                  <strong>{departmentRow.department}</strong>
                  <span>{departmentRow.active_employee_count}명</span>
                </div>
                <div className="department-signal-value">
                  {departmentRow.point ? pct(timelineSignalValue(departmentRow.point, timelineSignal)) : "—"}
                </div>
                <div className="department-signal-meta">
                  {departmentRow.point
                    ? `${trendBucketLabel(departmentRow.point.bucket, trendGranularity)} · 참여 ${departmentRow.point.cohort_employee_count}명 · 메시지 ${departmentRow.point.message_count}건`
                    : "선택 기간에 최소 인원 기준을 충족한 구간 없음"}
                </div>
              </article>
            ))}
          </div>

          <div className="timeline-policy-strip">
            <span>표시 가능 {timelineData?.departments.length ?? 0}개 부서</span>
            <span>최소 인원 미달 {timelineData?.suppressed_department_count ?? 0}개 부서 비공개</span>
            <span>개인 식별값 0건</span>
            <span>원문 비저장</span>
            <span>심리·정신건강 진단 아님</span>
          </div>
        </section>

        <section id="employees" className="section-shell">
          <div className="section-head">
            <div><div className="eyebrow">Employee Directory</div><h2>직원 현황</h2><p>실명·부서·직책과 관리자가 수동 지정한 핵심인력 여부를 확인합니다. 별표는 AI 신호로 자동 지정되지 않습니다.</p></div>
          </div>

          <div className="grid-3 employee-filters">
            <input className="field" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="이름 / 부서 / 직책 검색" />
            <select className="field" value={department} onChange={(e) => setDepartment(e.target.value)}>
              <option value="all">전체 부서</option>{departments.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            <select className="field" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
              <option value="starred">핵심인력 우선</option><option value="name">이름순</option><option value="department">부서순</option>
            </select>
          </div>
          <div className="employee-toolbar">
            <label className="star-filter"><input type="checkbox" checked={starredOnly} onChange={(e) => setStarredOnly(e.target.checked)} /> 핵심인력만 보기</label>
            <input className="field admin-token-field" type="password" value={adminToken} onChange={(e) => setAdminToken(e.target.value)} placeholder="관리자 토큰 — 별표/업로드 변경용" />
            <span className="badge">{filteredEmployees.length}명 표시</span>
          </div>

          <div className="table-wrap employee-table-wrap">
            <table>
              <thead><tr><th>핵심</th><th>이름</th><th>부서</th><th>직책</th></tr></thead>
              <tbody>
                {filteredEmployees.map((row) => (
                  <tr key={row.employee_id_hash}>
                    <td><button className={`star-button ${row.is_key_staff ? "active" : ""}`} disabled={savingStar === row.employee_id_hash} onClick={() => toggleKeyStaff(row)} aria-label={`${row.employee_name} 핵심인력 표시 변경`}>{row.is_key_staff ? "★" : "☆"}</button></td>
                    <td><strong>{row.employee_name}</strong></td>
                    <td>{row.department}</td>
                    <td>{row.job_title ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!filteredEmployees.length && <div className="notice">조건에 맞는 직원이 없습니다. Employee Directory가 비어 있다면 `scripts/load_employee_directory.py`로 먼저 등록하세요.</div>}
        </section>

        <section id="reports" className="section-shell">
          <div className="section-head"><div><div className="eyebrow">Data Operations</div><h2>월말 데이터 업데이트</h2><p>관리자가 같은 기간으로 내보낸 3종 보고서를 한 번에 업로드합니다. 분석 기간은 엑셀 상단의 표시 기간에서 자동으로 읽으며 여러 달이면 월별 feature로 나눠 처리합니다.</p></div></div>
          <form onSubmit={uploadReports}>
            <div className="upload-grid">
              <label htmlFor="report-admin-token">관리자 토큰</label><input id="report-admin-token" className="field" type="password" autoComplete="off" required value={adminToken} onChange={(e) => setAdminToken(e.target.value)} placeholder="ACTIVITY_ADMIN_TOKEN 값" />
              <label htmlFor="job-report">취업사이트 접속내역</label><input id="job-report" className="field" type="file" accept=".xls,.xlsx" required onChange={(e) => setJobFile(e.target.files?.[0] ?? null)} />
              <label htmlFor="search-report">웹 검색 내역</label><input id="search-report" className="field" type="file" accept=".xls,.xlsx" required onChange={(e) => setSearchFile(e.target.files?.[0] ?? null)} />
              <label htmlFor="document-report">문서활용 내역</label><input id="document-report" className="field" type="file" accept=".xls,.xlsx" required onChange={(e) => setDocFile(e.target.files?.[0] ?? null)} />
            </div>
            <p className="upload-auth-note">API 서버의 <code>ACTIVITY_ADMIN_TOKEN</code>과 같은 값을 입력하세요. 토큰은 브라우저에 저장하지 않습니다. 보고 월은 입력하지 않으며 세 엑셀의 표시 기간이 같아야 합니다.</p>
            <div style={{ marginTop: 14 }}><button type="submit" className="primary-button" disabled={uploading}>{uploading ? "처리 중..." : "3개 보고서 검증 및 처리"}</button></div>
          </form>
          {uploadResult && <pre className="upload-result" style={{ marginTop: 14 }}>{uploadResult}</pre>}
        </section>

        <div className="footer">PeoplePulse production main · 개인별 Slack NLP/정신건강 추론/퇴사 위험 순위는 운영 Dashboard에 제공하지 않습니다. 핵심인력 별표는 관리자의 독립적인 수동 지정 값입니다.</div>
      </main>
    </div>
  );
}
