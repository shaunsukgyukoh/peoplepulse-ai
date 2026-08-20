"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import type { EChartsOption } from "echarts";

import EChart from "@/components/EChart";
import MetricCard from "@/components/MetricCard";
import Section from "@/components/Section";
import {
  apiBase,
  getJson,
  type AttritionMetrics,
  type NlpModel,
  type Overview,
  type ShapResult,
  type SlackLive,
  type SlackTrendPoint,
} from "@/lib/api";

const SIGNAL_ORDER = [
  "satisfied",
  "neutral",
  "frustrated",
  "angry",
  "dissatisfied",
  "overloaded",
  "conflict",
  "disengaged",
];

const SIGNAL_LABEL: Record<string, string> = {
  satisfied: "만족",
  neutral: "중립",
  frustrated: "답답함",
  angry: "분노",
  dissatisfied: "불만",
  overloaded: "과부하",
  conflict: "갈등",
  disengaged: "몰입 저하",
};

const pct = (value: unknown, digits = 1) =>
  typeof value === "number" && Number.isFinite(value) ? `${(value * 100).toFixed(digits)}%` : "—";
const num = (value: unknown, digits = 2) =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "—";
const compact = (value: unknown) =>
  typeof value === "number" && Number.isFinite(value) ? new Intl.NumberFormat("ko-KR", { notation: "compact" }).format(value) : "—";

function signalChart(points: SlackTrendPoint[]): EChartsOption {
  return {
    backgroundColor: "transparent",
    tooltip: { trigger: "axis", valueFormatter: (value) => `${(Number(value) * 100).toFixed(1)}%` },
    legend: { data: ["work strain", "satisfied", "overloaded"], textStyle: { color: "#9bb5ad" } },
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
      {
        name: "work strain",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: points.map((p) => p.work_strain),
        lineStyle: { width: 2.5, color: "#f5c76b" },
        areaStyle: { color: "rgba(245,199,107,.06)" },
      },
      {
        name: "satisfied",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: points.map((p) => p.satisfied),
        lineStyle: { width: 2, color: "#65e6b4" },
      },
      {
        name: "overloaded",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: points.map((p) => p.overloaded),
        lineStyle: { width: 2, color: "#ff8e8e" },
      },
    ],
  };
}

function nlpChart(models: NlpModel[]): EChartsOption {
  const rows = [...models].reverse();
  return {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { left: 155, right: 24, top: 10, bottom: 24 },
    xAxis: {
      type: "value",
      min: 0,
      max: 1,
      axisLabel: { color: "#78958c", formatter: (value: number) => value.toFixed(1) },
      splitLine: { lineStyle: { color: "rgba(184,216,207,.08)" } },
    },
    yAxis: {
      type: "category",
      data: rows.map((m) => m.model.replace("beomi/", "").replace("klue/", "")),
      axisLabel: { color: "#9bb5ad", width: 140, overflow: "truncate" },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        type: "bar",
        data: rows.map((m) => m.macro_f1),
        barWidth: 13,
        itemStyle: { color: "#65e6b4", borderRadius: [0, 7, 7, 0] },
      },
    ],
  };
}

function featureSetChart(metrics: AttritionMetrics | null): EChartsOption {
  const rows = metrics?.feature_sets ?? [];
  return {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    legend: { data: ["Average Precision", "Recall@Top10%"], textStyle: { color: "#9bb5ad" } },
    grid: { left: 55, right: 18, top: 44, bottom: 36 },
    xAxis: {
      type: "category",
      data: rows.map((r) => String(r.feature_set)),
      axisLabel: { color: "#9bb5ad" },
      axisLine: { lineStyle: { color: "rgba(184,216,207,.14)" } },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 0.35,
      axisLabel: { color: "#78958c" },
      splitLine: { lineStyle: { color: "rgba(184,216,207,.08)" } },
    },
    series: [
      {
        name: "Average Precision",
        type: "bar",
        data: rows.map((r) => Number(r.average_precision ?? 0)),
        itemStyle: { color: "#65e6b4", borderRadius: [5, 5, 0, 0] },
      },
      {
        name: "Recall@Top10%",
        type: "bar",
        data: rows.map((r) => Number(r.recall_at_top_10pct ?? 0)),
        itemStyle: { color: "#8ab9ff", borderRadius: [5, 5, 0, 0] },
      },
    ],
  };
}

function shapChart(shap: ShapResult | null): EChartsOption | null {
  const rows = (shap?.features ?? []).filter((row) => typeof row.mean_abs_shap === "number");
  if (!rows.length) return null;
  const ordered = [...rows].reverse();
  return {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { left: 185, right: 20, top: 10, bottom: 25 },
    xAxis: {
      type: "value",
      axisLabel: { color: "#78958c" },
      splitLine: { lineStyle: { color: "rgba(184,216,207,.08)" } },
    },
    yAxis: {
      type: "category",
      data: ordered.map((row) => row.feature),
      axisLabel: { color: "#9bb5ad", width: 175, overflow: "truncate" },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        type: "bar",
        data: ordered.map((row) => row.mean_abs_shap),
        itemStyle: { color: "#93f3cf", borderRadius: [0, 6, 6, 0] },
      },
    ],
  };
}

export default function DashboardPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [live, setLive] = useState<SlackLive | null>(null);
  const [trend, setTrend] = useState<SlackTrendPoint[]>([]);
  const [attrition, setAttrition] = useState<AttritionMetrics | null>(null);
  const [nlp, setNlp] = useState<NlpModel[]>([]);
  const [shap, setShap] = useState<ShapResult | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [reportMonth, setReportMonth] = useState("2026-07");
  const [adminToken, setAdminToken] = useState("");
  const [jobFile, setJobFile] = useState<File | null>(null);
  const [searchFile, setSearchFile] = useState<File | null>(null);
  const [docFile, setDocFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<string>("");

  const load = useCallback(async () => {
    try {
      const [overviewData, trendData, attritionData, nlpData, shapData] = await Promise.all([
        getJson<Overview>("/api/v1/dashboard/overview"),
        getJson<{ points: SlackTrendPoint[] }>("/api/v1/dashboard/slack/trend?minutes=60"),
        getJson<AttritionMetrics>("/api/v1/dashboard/model/attrition"),
        getJson<{ models: NlpModel[] }>("/api/v1/dashboard/model/nlp"),
        getJson<ShapResult>("/api/v1/dashboard/model/shap"),
      ]);
      setOverview(overviewData);
      setLive(overviewData.slack);
      setTrend(trendData.points);
      setAttrition(attritionData);
      setNlp(nlpData.models);
      setShap(shapData);
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
    });
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    return () => source.close();
  }, []);

  const currentLive = live ?? overview?.slack;
  const attr = attrition?.privacy_safe ?? {};
  const selectedNlp = nlp[0];
  const shapOption = useMemo(() => shapChart(shap), [shap]);

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

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark">P</div><div>PeoplePulse AI</div></div>
        <div className="brand-sub">Privacy-aware workforce intelligence<br />portfolio system</div>
        <nav className="nav">
          <a href="#overview">Executive Overview</a>
          <a href="#realtime">Real-time Slack Signal</a>
          <a href="#reports">Monthly Reports</a>
          <a href="#retention">Retention Evaluation</a>
          <a href="#shap">SHAP</a>
          <a href="#performance">Model Performance</a>
        </nav>
        <div className="sidebar-note">
          <strong>Responsible AI boundary</strong><br />실제 운영 화면은 부서/코호트 분석용입니다. 직원 단위 퇴사 예측은 synthetic demo에서만 허용합니다.
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <div className="eyebrow">STEP 7 · PRODUCTIZATION</div>
            <h1>Workforce intelligence,<br />without raw surveillance.</h1>
            <p>Slack의 파생 NLP 신호, 월말 3종 보고서, synthetic retention ML 평가와 설명가능성을 하나의 운영형 대시보드로 연결합니다.</p>
          </div>
          <div className="status-cluster">
            <span className={`badge ${connected ? "badge-live" : ""}`}><span className="dot" />SSE {connected ? "connected" : "reconnecting"}</span>
            <span className="badge">FastAPI + Next.js 16.3</span>
            <span className="badge">Local / self-hosted</span>
          </div>
        </header>

        {error ? <div className="notice error">API connection: {error}. `http://localhost:8000/health`와 Docker API 상태를 확인하세요.</div> : null}

        <Section id="overview" eyebrow="01 · Executive" title="Executive Overview" description="개인 원문이나 실제 개인 퇴사확률 없이 현재 파이프라인 상태와 조직 수준 신호를 요약합니다.">
          <div className="grid-5">
            <MetricCard label="Slack signals · 15m" value={compact(currentLive?.message_count)} detail={`latest ${currentLive?.last_message_at ? new Date(currentLive.last_message_at).toLocaleTimeString("ko-KR") : "—"}`} accent />
            <MetricCard label="Work strain · 15m" value={pct(currentLive?.work_strain)} detail="6개 업무 긴장 신호의 파생 평균" />
            <MetricCard label="NLP Macro-F1" value={num(selectedNlp?.macro_f1, 3)} detail={`${selectedNlp?.model ?? "—"} · ${selectedNlp?.device ?? "—"}`} />
            <MetricCard label="Retention AP" value={num(attr.average_precision, 3)} detail="Synthetic privacy-safe temporal test" />
            <MetricCard label="Latest report" value={overview?.latest_report?.report_month?.slice(0, 7) ?? "—"} detail={overview?.latest_report ? `${overview.latest_report.privacy_mode} · ${overview.latest_report.input_rows} rows` : "No batch yet"} />
          </div>
          <div className="notice">개인별 attrition probability는 이 Executive 화면에 노출하지 않습니다. 모델 성능은 synthetic portfolio experiment 결과이며 실제 직원 성능을 의미하지 않습니다.</div>
        </Section>

        <Section id="realtime" eyebrow="02 · Streaming" title="Real-time Slack Signal" description="Socket Mode → Redis Streams → CUDA Transformer → PostgreSQL 결과를 SSE로 브라우저에 push합니다." aside={<span className="badge badge-live">{currentLive?.model_name ?? "NLP model"} · {currentLive?.model_device ?? "—"}</span>}>
          <div className="grid-2">
            <div className="panel">
              <div className="panel-title">최근 60분 신호 추세 <span className="panel-subtitle">원문 메시지 미표시</span></div>
              {trend.length ? <EChart option={signalChart(trend)} height={330} /> : <div className="notice">아직 최근 60분 NLP signal이 없습니다. Slack 테스트 메시지를 보내면 실시간으로 표시됩니다.</div>}
            </div>
            <div className="panel">
              <div className="panel-title">현재 15분 signal snapshot <span className="panel-subtitle">SSE live</span></div>
              <div className="signal-grid">
                {SIGNAL_ORDER.map((signal) => {
                  const value = currentLive?.signals?.[signal] ?? 0;
                  return <div className="signal" key={signal}><div className="signal-name">{SIGNAL_LABEL[signal]}</div><div className="signal-score">{pct(value, 0)}</div><div className="progress"><span style={{ width: `${Math.max(0, Math.min(100, value * 100))}%` }} /></div></div>;
                })}
              </div>
              <div className="grid-2" style={{ marginTop: 12 }}>
                <MetricCard label="Mean inference" value={`${num(currentLive?.avg_inference_ms, 1)} ms`} detail="최근 15분" />
                <MetricCard label="Analyzed messages" value={compact(currentLive?.message_count)} detail="최근 15분" />
              </div>
            </div>
          </div>
        </Section>

        <Section id="reports" eyebrow="03 · Batch ingestion" title="Monthly Report Upload" description="실제 3개 보고서 형식을 한 번에 업로드합니다. Backend가 헤더 signature로 종류를 자동 판별하고 privacy policy를 적용합니다." aside={<span className="badge">xls / xlsx</span>}>
          <div className="grid-2">
            <div className="panel">
              <form onSubmit={uploadReports} className="upload-grid">
                <label htmlFor="month">Report month</label><input id="month" className="field" value={reportMonth} onChange={(e) => setReportMonth(e.target.value)} pattern="[0-9]{4}-[0-9]{2}" required />
                <label htmlFor="token">Admin token</label><input id="token" className="field" type="password" value={adminToken} onChange={(e) => setAdminToken(e.target.value)} autoComplete="off" required />
                <label htmlFor="job">취업사이트 접속내역</label><input id="job" className="field" type="file" accept=".xls,.xlsx" onChange={(e) => setJobFile(e.target.files?.[0] ?? null)} required />
                <label htmlFor="search">웹 검색 내역</label><input id="search" className="field" type="file" accept=".xls,.xlsx" onChange={(e) => setSearchFile(e.target.files?.[0] ?? null)} required />
                <label htmlFor="doc">문서활용 내역</label><input id="doc" className="field" type="file" accept=".xls,.xlsx" onChange={(e) => setDocFile(e.target.files?.[0] ?? null)} required />
                <div /><button className="primary-button" disabled={uploading}>{uploading ? "Processing..." : "Validate & process 3 reports"}</button>
              </form>
              <div className="notice">실제 데이터 기본 모드는 `aggregate`: 직원별 원문·검색어·문서명은 저장하지 않고 최소 코호트 크기 정책을 적용합니다.</div>
            </div>
            <div className="panel">
              <div className="panel-title">Latest batch <span className="panel-subtitle">PostgreSQL audit</span></div>
              <div className="grid-2">
                <MetricCard label="Report month" value={overview?.latest_report?.report_month?.slice(0, 7) ?? "—"} />
                <MetricCard label="Input rows" value={compact(overview?.latest_report?.input_rows)} />
                <MetricCard label="Privacy excluded" value={compact(overview?.latest_report?.privacy_excluded_rows)} />
                <MetricCard label="Privacy mode" value={overview?.latest_report?.privacy_mode ?? "—"} />
              </div>
              {uploadResult ? <pre className="upload-result" style={{ marginTop: 12 }}>{uploadResult}</pre> : null}
            </div>
          </div>
        </Section>

        <Section id="retention" eyebrow="04 · Synthetic ML" title="Synthetic Retention Model Evaluation" description="90-day synthetic target, purged temporal split, probability calibration, intent-proxy ablation 결과를 표시합니다." aside={<span className="badge">SYNTHETIC DEMO ONLY</span>}>
          <div className="grid-5">
            <MetricCard label="Selected model" value={attrition?.selected_model?.replaceAll("_", " ") ?? "—"} detail="validation Average Precision" accent />
            <MetricCard label="Average Precision" value={num(attr.average_precision, 4)} detail="privacy_safe temporal test" />
            <MetricCard label="ROC-AUC" value={num(attr.roc_auc, 4)} />
            <MetricCard label="Recall@Top10%" value={pct(attr.recall_at_top_10pct)} />
            <MetricCard label="Brier score" value={num(attr.brier_score, 4)} detail="calibrated probability" />
          </div>
          <div className="grid-2" style={{ marginTop: 14 }}>
            <div className="panel"><div className="panel-title">Intent-proxy ablation <span className="panel-subtitle">privacy_safe vs synthetic_full</span></div><EChart option={featureSetChart(attrition)} height={300} /></div>
            <div className="panel">
              <div className="panel-title">Evaluation contract <span className="panel-subtitle">no random split</span></div>
              <div className="rank-list">
                {["90-day future attrition target", "Purged temporal train / validation / test", "Validation-only model selection", "Sigmoid probability calibration", "Untouched temporal test", "No real employee-level inference"].map((item, index) => <div className="rank-row" key={item}><div className="rank-index">{index + 1}</div><div className="rank-feature">{item}</div></div>)}
              </div>
              <div className="notice">Source: {attrition?.source ?? "—"}. Local STEP 6 artifacts가 있으면 우선 사용하고, 없으면 repository reference metrics로 fallback합니다.</div>
            </div>
          </div>
        </Section>

        <Section id="shap" eyebrow="05 · Explainability" title="SHAP Global Importance" description="선택된 synthetic attrition model의 global feature importance를 보여줍니다. 실제 개인 인사결정 설명으로 사용하지 않습니다.">
          <div className="panel">
            {shapOption ? <EChart option={shapOption} height={420} /> : <div><div className="panel-title">Reference feature ranking <span className="panel-subtitle">SHAP magnitude artifact not found</span></div><div className="rank-list">{(shap?.features ?? []).map((row, index) => <div className="rank-row" key={row.feature}><div className="rank-index">{row.rank ?? index + 1}</div><div className="rank-feature">{row.feature}</div></div>)}</div><div className="notice">`artifacts/ml/step6/privacy_safe/shap/shap_feature_importance.csv`를 생성하면 실제 mean |SHAP| bar chart로 자동 전환됩니다.</div></div>}
          </div>
        </Section>

        <Section id="performance" eyebrow="06 · Model observability" title="Model Performance" description="NLP 후보 성능과 latency, synthetic attrition model의 ranking/calibration을 분리해서 확인합니다.">
          <div className="grid-2">
            <div className="panel"><div className="panel-title">Korean NLP candidates <span className="panel-subtitle">Macro-F1</span></div>{nlp.length ? <EChart option={nlpChart(nlp)} height={300} /> : <div className="notice">NLP comparison artifact not found.</div>}</div>
            <div className="panel">
              <div className="panel-title">NLP benchmark detail <span className="panel-subtitle">validation-tuned thresholds</span></div>
              <div className="table-wrap"><table><thead><tr><th>Model</th><th>Macro-F1</th><th>Precision</th><th>Recall</th><th>P95 ms</th></tr></thead><tbody>{nlp.map((model) => <tr key={model.model}><td>{model.model}</td><td>{num(model.macro_f1, 3)}</td><td>{num(model.macro_precision, 3)}</td><td>{num(model.macro_recall, 3)}</td><td>{num(model.latency_ms_p95, 2)}</td></tr>)}</tbody></table></div>
            </div>
          </div>
          <div className="grid-4" style={{ marginTop: 14 }}>
            <MetricCard label="Attrition AP" value={num(attr.average_precision, 4)} />
            <MetricCard label="PR-AUC" value={num(attr.pr_auc_trapezoid, 4)} />
            <MetricCard label="ECE · 10 bin" value={num(attr.ece_10bin, 4)} />
            <MetricCard label="Test positive rate" value={pct(attr.positive_rate)} />
          </div>
        </Section>

        <div className="footer">PeoplePulse AI · STEP 7 · portfolio-only employee-level attrition model · production analytics remains department/cohort scoped.</div>
      </main>
    </div>
  );
}
