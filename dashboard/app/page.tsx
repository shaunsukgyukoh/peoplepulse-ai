"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import type { EChartsOption } from "echarts";

import EChart from "@/components/EChart";
import {
  apiBase,
  getAdminJson,
  getJson,
  patchJson,
  type EmployeeRow,
  type EmployeesResponse,
  type Overview,
  type SlackLive,
  type SlackTrendPoint,
  type SelfReportTrendResponse,
  type TeamSignalTrendResponse,
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

function employeeSelfReportTrendChart(
  result: SelfReportTrendResponse | null,
  granularity: TrendGranularity,
): EChartsOption {
  const points = result?.points ?? [];
  const statusOrder = ["지원 필요", "보통", "좋음", "응답 안 함"];
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 72, right: 22, top: 24, bottom: 42 },
    xAxis: {
      type: "category",
      data: points.map((point) => trendBucketLabel(point.bucket, granularity)),
      boundaryGap: false,
      axisLine: { lineStyle: { color: "rgba(184,216,207,.14)" } },
      axisLabel: { color: "#78958c", hideOverlap: true, rotate: granularity === "hour" ? 25 : 0 },
    },
    yAxis: {
      type: "category",
      data: statusOrder,
      axisLabel: { color: "#9bb5ad" },
      axisLine: { lineStyle: { color: "rgba(184,216,207,.14)" } },
      splitLine: { show: true, lineStyle: { color: "rgba(184,216,207,.07)" } },
    },
    series: [
      {
        name: "자발적 Self-report",
        type: "line",
        step: "end",
        symbolSize: 8,
        lineStyle: { width: 3, color: "#8ab9ff" },
        itemStyle: { color: "#8ab9ff" },
        data: points.map((point) => SELF_REPORT_LABEL[point.status] ?? point.status),
      },
    ],
  };
}

function teamSignalTrendChart(
  result: TeamSignalTrendResponse | null,
  granularity: TrendGranularity,
): EChartsOption {
  const points = result?.points ?? [];
  return {
    tooltip: { trigger: "axis", valueFormatter: (value) => `${(Number(value) * 100).toFixed(1)}%` },
    legend: { data: ["업무 긴장", "긍정 표현", "과부하 표현"], textStyle: { color: "#9bb5ad" } },
    grid: { left: 44, right: 22, top: 44, bottom: 42 },
    xAxis: {
      type: "category",
      data: points.map((point) => trendBucketLabel(point.bucket, granularity)),
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
      { name: "업무 긴장", type: "line", smooth: true, data: points.map((point) => point.work_strain) },
      { name: "긍정 표현", type: "line", smooth: true, data: points.map((point) => point.signals.satisfied ?? 0) },
      { name: "과부하 표현", type: "line", smooth: true, data: points.map((point) => point.signals.overloaded ?? 0) },
    ],
  };
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
  const [trendGranularity, setTrendGranularity] = useState<TrendGranularity>("day");
  const [selectedEmployeeId, setSelectedEmployeeId] = useState("");
  const [selectedTeam, setSelectedTeam] = useState("");
  const [employeeTrend, setEmployeeTrend] = useState<SelfReportTrendResponse | null>(null);
  const [teamTrend, setTeamTrend] = useState<TeamSignalTrendResponse | null>(null);
  const [employeeTrendError, setEmployeeTrendError] = useState<string | null>(null);
  const [teamTrendError, setTeamTrendError] = useState<string | null>(null);

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
    const employees = employeesData?.employees ?? [];
    if (!selectedEmployeeId && employees.length) {
      setSelectedEmployeeId(employees[0].employee_id_hash);
    }
    if (!selectedTeam && departments.length) {
      const minimumCohort = employeesData?.signal_policy.team_minimum_cohort_size ?? 5;
      const counts = employeesData?.summary.departments ?? {};
      const eligibleTeams = departments.filter(
        (item) => item !== "미지정" && (counts[item] ?? 0) >= minimumCohort,
      );
      eligibleTeams.sort((a, b) => (counts[b] ?? 0) - (counts[a] ?? 0));
      setSelectedTeam(eligibleTeams[0] ?? departments[0]);
    }
  }, [departments, employeesData, selectedEmployeeId, selectedTeam]);

  useEffect(() => {
    if (!selectedEmployeeId || !adminToken) {
      setEmployeeTrend(null);
      setEmployeeTrendError(null);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      const path = `/api/v1/dashboard/employees/${selectedEmployeeId}/self-report/trend?granularity=${trendGranularity}`;
      void getAdminJson<SelfReportTrendResponse>(path, adminToken)
        .then((result) => {
          if (!cancelled) {
            setEmployeeTrend(result);
            setEmployeeTrendError(null);
          }
        })
        .catch((reason) => {
          if (!cancelled) {
            setEmployeeTrend(null);
            setEmployeeTrendError(reason instanceof Error ? reason.message : String(reason));
          }
        });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [adminToken, employeesData, selectedEmployeeId, trendGranularity]);

  useEffect(() => {
    if (!selectedTeam) {
      setTeamTrend(null);
      return;
    }
    let cancelled = false;
    const path = `/api/v1/dashboard/teams/work-signals/trend?granularity=${trendGranularity}&department=${encodeURIComponent(selectedTeam)}`;
    void getJson<TeamSignalTrendResponse>(path)
      .then((result) => {
        if (!cancelled) {
          setTeamTrend(result);
          setTeamTrendError(null);
        }
      })
      .catch((reason) => {
        if (!cancelled) {
          setTeamTrend(null);
          setTeamTrendError(reason instanceof Error ? reason.message : String(reason));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedTeam, signalRevision, trendGranularity]);

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

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark">P</div><div>PeoplePulse</div></div>
        <div className="brand-sub">HR workforce support dashboard</div>
        <nav className="nav">
          <a href="#overview">운영 요약</a>
          <a href="#employees">직원 현황</a>
          <a href="#state-trends">상태 추세</a>
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
            <h1>직원 지원에 필요한 정보만,<br />한 화면에서.</h1>
            <p>실명 직원 디렉터리, 자발적 상태 공유, 수동 핵심인력 표시, 조직 수준 업무 커뮤니케이션 신호를 제공합니다. 모델 성능·SHAP·Synthetic 평가 정보는 운영 화면에서 제외했습니다.</p>
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

        <section id="state-trends" className="section-shell">
          <div className="section-head trend-section-head">
            <div>
              <div className="eyebrow">Time-series Support View</div>
              <h2>시간·일·주·월 상태 추세</h2>
              <p>직원별 차트는 자발적으로 제출된 self-report 이력만 사용합니다. 팀 차트는 개인별 Slack 점수를 노출하지 않고, 구간별 참여자가 최소 기준을 충족할 때만 직원 우선 집계된 업무 커뮤니케이션 신호를 표시합니다.</p>
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

          <div className="grid-2">
            <div className="panel trend-panel">
              <div className="panel-title">직원별 자발적 Self-report<span className="panel-subtitle">admin · employee-provided</span></div>
              <div className="trend-controls">
                <select className="field" value={selectedEmployeeId} onChange={(event) => setSelectedEmployeeId(event.target.value)}>
                  {(employeesData?.employees ?? []).map((employee) => (
                    <option key={employee.employee_id_hash} value={employee.employee_id_hash}>
                      {employee.employee_name} · {employee.department}
                    </option>
                  ))}
                </select>
                <input className="field" type="password" value={adminToken} onChange={(event) => setAdminToken(event.target.value)} placeholder="관리자 토큰 입력" />
              </div>
              {!adminToken && <div className="notice">민감한 self-report 이력을 조회하려면 관리자 토큰을 입력하세요.</div>}
              {employeeTrendError && <div className="notice error">{employeeTrendError}</div>}
              {adminToken && employeeTrend && !employeeTrend.points.length && <div className="notice">선택한 기간에 자발적 self-report 이력이 없습니다.</div>}
              {employeeTrend?.points.length ? <EChart option={employeeSelfReportTrendChart(employeeTrend, trendGranularity)} height={330} /> : null}
            </div>

            <div className="panel trend-panel">
              <div className="panel-title">팀별 업무 커뮤니케이션 추세<span className="panel-subtitle">anonymous aggregate</span></div>
              <div className="trend-controls single">
                <select className="field" value={selectedTeam} onChange={(event) => setSelectedTeam(event.target.value)}>
                  {departments.map((item) => {
                    const count = employeesData?.summary.departments[item] ?? 0;
                    const minimumCohort = employeesData?.signal_policy.team_minimum_cohort_size ?? 5;
                    return (
                      <option key={item} value={item} disabled={count < minimumCohort}>
                        {item} · {count}명{count < minimumCohort ? " (집계 기준 미달)" : ""}
                      </option>
                    );
                  })}
                </select>
              </div>
              {teamTrendError && <div className="notice error">{teamTrendError}</div>}
              {teamTrend && !teamTrend.points.length && (
                <div className="notice">해당 기간에 최소 {teamTrend.minimum_cohort_size}명 집계 기준을 충족한 구간이 없습니다.</div>
              )}
              {teamTrend?.points.length ? <EChart option={teamSignalTrendChart(teamTrend, trendGranularity)} height={330} /> : null}
              {teamTrend && <div className="trend-policy">직원별 선집계 → 팀 평균 · 최소 {teamTrend.minimum_cohort_size}명 · 원문/개인 점수 비노출</div>}
            </div>
          </div>
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
