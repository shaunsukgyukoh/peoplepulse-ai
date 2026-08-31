# PeoplePulse AI

**Privacy-Aware Employee Retention Intelligence Platform**

Slack 기반 업무 커뮤니케이션과 월간 운영 데이터를 분석하는 과정에서 개인정보와 인사 의사결정 위험을 최소화하면서, realtime NLP, feature engineering, temporal ML, MLOps, local Agent를 하나의 시스템으로 통합한 AI/Data engineering portfolio project입니다.

> Employee-level attrition modeling과 성능 수치는 synthetic portfolio data에만 적용됩니다. 실제 직원에 대한 채용, 해고, 승진, 보상, 징계 자동화 용도로 설계하지 않았습니다.

## 프로젝트 개요

| 항목 | 내용 |
|---|---|
| 문제 영역 | People Analytics, Privacy-aware AI, MLOps |
| 데이터 흐름 | Slack realtime signal, 월간 report, synthetic ML |
| 핵심 기술 | PyTorch, KLUE RoBERTa, Redis, PostgreSQL, FastAPI, Next.js |
| ML/MLOps | scikit-learn, XGBoost, LightGBM, CatBoost, SHAP, MLflow, Evidently |
| Agent | LangGraph, Ollama, allowlisted read-only tools |
| 설계 원칙 | Data minimization, temporal leakage control, policy guard |

## 1. 문제 정의

조직 데이터를 활용해 업무 부담이나 이탈 위험을 분석하는 시스템은 기술적으로는 만들기 쉽지만, 잘못 설계하면 직원 감시 시스템이 될 수 있습니다.

특히 다음 문제를 동시에 해결해야 했습니다.

- Slack raw message를 장기간 저장할 경우 개인정보 노출 위험
- 직원 단위 심리 상태를 추정할 경우 과도한 profiling 위험
- 월간 activity data와 realtime communication signal의 identity 연결 문제
- attrition dataset의 낮은 positive rate와 class imbalance
- 시간 순서를 무시한 random split에서 발생하는 temporal leakage
- 모델 결과와 실제 HR 의사결정의 경계
- LLM Agent가 임의 SQL이나 raw employee data에 접근할 위험
- model experiment, drift, API 상태를 별도 도구에서 관리해야 하는 운영 복잡성

따라서 목표를 "이탈 가능성이 높은 직원을 찾는 모델"이 아니라 "privacy boundary를 시스템 구조 안에 포함한 people analytics platform"으로 정의했습니다.

## 2. 해결 방안

### Realtime Slack pipeline

Slack Events API와 Socket Mode로 message event를 받고 PII masking과 HMAC pseudonymization 후 Redis Streams로 전달합니다.

raw text를 analytics DB에 장기 저장하는 대신 NLP에서 필요한 derived workplace signal만 저장하도록 설계했습니다.

### Production dashboard 상태 추세

운영 Dashboard는 동일한 네 가지 시간 범위를 직원별 자발적 상태 이력과 팀별 업무 커뮤니케이션 집계에 적용합니다.

| 선택 | 집계 단위 | 조회 범위 |
|---|---|---|
| 시간 | 1시간 | 최근 24시간 |
| 일 | 1일 | 최근 30일 |
| 주 | 1주 | 최근 12주 |
| 월 | 1개월 | 최근 12개월 |

- 직원별 차트는 직원이 직접 제출한 `self_report_status` 이력만 사용하며 관리자 토큰이 있어야 조회할 수 있습니다.
- Slack NLP는 개인 점수나 심리·정신건강 진단으로 노출하지 않습니다. 업무 커뮤니케이션 신호만 직원별로 먼저 평균한 뒤 팀 평균으로 집계합니다.
- 각 시간 구간에서 서로 다른 참여 직원이 `ACTIVITY_MIN_COHORT_SIZE` 이상일 때만 팀 점을 반환합니다. 기본값은 5명입니다.
- 모든 구간은 `Asia/Seoul` 기준이며 Dashboard의 Slack SSE revision이 바뀌면 현재 선택한 팀 추세를 다시 조회합니다.

관련 API는 `GET /api/v1/dashboard/employees/{employee_id_hash}/self-report/trend`와 `GET /api/v1/dashboard/teams/work-signals/trend`이며, `granularity`에는 `hour`, `day`, `week`, `month`를 사용할 수 있습니다.

### Monthly data pipeline

서로 다른 월간 report format을 parser가 자동 인식하고 Pandera validation과 privacy filtering을 거쳐 monthly feature로 변환합니다.

### Feature Store

Slack과 monthly report의 identifier를 동일한 HMAC namespace로 연결하고 PostgreSQL에 rolling feature를 저장합니다.

메시지가 많은 사람이 cohort 평균을 지배하지 않도록 employee-first aggregation 후 cohort aggregation을 수행했습니다.

### Temporal ML

7, 30, 90일 rolling feature와 trend delta를 만들고, 미래 target window와 purge gap을 포함한 temporal split을 적용했습니다.

class imbalance 때문에 accuracy보다 Average Precision, PR-AUC, Recall@Top-K, calibration을 중심으로 평가했습니다.

### Responsible Agent

LangGraph와 Ollama 기반 Analyst Agent에는 arbitrary SQL을 제공하지 않고 fixed read-only tool만 허용했습니다.

LLM 앞에 deterministic policy gate를 두어 individual real-employee risk, raw message, employment decision, mental-health inference 요청을 차단하도록 설계했습니다.

### MLOps

MLflow experiment tracking, Evidently drift, Prometheus metrics, Grafana dashboard를 하나의 Docker Compose stack으로 구성했습니다.

## 3. 이해관계자 관점과 협업 방식

개인 portfolio project로 진행했기 때문에 실제 HR 조직이나 직원 데이터를 이용한 공동 개발은 하지 않았습니다.

대신 시스템 요구사항을 다음 stakeholder 관점으로 분리했습니다.

- HR 운영자, 조직 수준의 workload signal과 report 상태 필요
- 직원, raw communication과 개인 민감정보 보호 필요
- Data/ML engineer, 재현 가능한 feature와 model evaluation 필요
- 운영자, drift와 service health monitoring 필요
- AI Agent 사용자, 근거가 있는 read-only analytics만 필요

이 stakeholder 간 요구가 충돌하는 지점을 architecture boundary로 명시했습니다.

## 4. 본인 기여

- Slack realtime ingestion과 Redis Streams pipeline 설계
- PII masking과 HMAC pseudonymization 구현
- KLUE RoBERTa 기반 Korean workplace multi-label NLP pipeline 구축
- 실제 형식의 월간 report ingestion과 Pandera validation 구현
- identity resolution과 PostgreSQL feature store 구축
- 7, 30, 90일 rolling feature와 temporal target pipeline 구현
- Logistic Regression, XGBoost, LightGBM, CatBoost 비교 실험
- probability calibration과 SHAP explainability 적용
- FastAPI backend, Next.js dashboard, SSE realtime view 구현
- MLflow, Evidently, Prometheus, Grafana MLOps stack 구성
- LangGraph, Ollama 기반 local analytics Agent와 tool policy 구현
- deterministic privacy guard와 evaluation harness 구현
- synthetic data와 real-data scope를 분리하는 repository/branch strategy 설계

## 5. 최종 결과와 성과

### NLP benchmark, synthetic portfolio dataset

| Model | Macro-F1 | Macro Precision | Macro Recall | P95 latency |
|---|---:|---:|---:|---:|
| KLUE RoBERTa-base | **0.799** | 0.732 | 0.969 | 7.26 ms |
| TF-IDF + Logistic | 0.557 | 0.593 | 0.767 | **2.61 ms** |
| KcELECTRA-base | 0.476 | 0.353 | 0.948 | 6.66 ms |
| KcELECTRA-small | 0.263 | 0.158 | 0.917 | 7.81 ms |

KLUE RoBERTa-base가 synthetic benchmark에서 가장 높은 Macro-F1을 기록했습니다.

### Synthetic attrition reference

temporal test set에서 privacy-safe Logistic Regression을 기준으로 다음 결과를 얻었습니다.

- Average Precision: **0.1238**
- ROC-AUC: **0.6988**
- Recall@Top10%: **0.2683**
- Calibrated Brier score: **0.0566**
- Test positive rate: **5.76%**

synthetic panel은 650명의 synthetic employee와 36개월 시계열로 구성했습니다.

### Agent evaluation infrastructure

- single-tool, multi-tool, source trace, privacy attack를 포함한 36개 deterministic evaluation case 구성
- policy test가 기준을 만족하지 못하면 portfolio preflight가 실패하도록 검증 단계 구성
- tool selection, citation, unsupported numeric claim, latency를 함께 평가하는 harness 구현

## 6. 인사이트와 러닝

### Responsible AI는 문서가 아니라 architecture constraint여야 합니다

"개인정보를 조심한다"는 원칙만 적는 것으로는 부족했습니다. raw message 비저장, pseudonymization, aggregate-only real-data analytics, read-only tool, policy gate처럼 시스템이 위험한 행동을 구조적으로 하기 어렵게 만드는 것이 중요했습니다.

### 불균형 문제에서는 accuracy가 핵심 metric이 아닙니다

positive rate가 낮은 attrition 문제에서는 ROC-AUC만으로도 운영 성능을 오해할 수 있습니다. AP, Recall@Top-K, calibration을 함께 봐야 실제 screening 성능을 이해할 수 있었습니다.

### ML model과 product decision은 분리해야 합니다

모델 output은 분석 신호일 뿐 인사 의사결정 자체가 아닙니다. 특히 employment domain에서는 model performance와 사용할 수 있는 decision scope를 별도로 정의해야 했습니다.

## 7. Architecture

```text
Slack
 -> Mask/HMAC
 -> Redis Streams
 -> Korean NLP
 -> Derived Signals
                         -> PostgreSQL Feature Store
Monthly Reports
 -> Validation
 -> Monthly Features
                         -> Temporal ML
                         -> FastAPI
                         -> Next.js Dashboard
                         -> MLflow/Evidently/Prometheus/Grafana
                         -> Policy Guard
                         -> LangGraph/Ollama
                         -> Read-only Tools
```

## 8. Branch Strategy

### `main`

Production-oriented HR operations view

- employee directory
- voluntary self-report
- manual key-staff marker
- aggregate Slack work signals
- monthly report operations

### `portfolio`

Full AI/ML engineering demonstration

- NLP benchmark
- synthetic attrition ML
- SHAP
- MLflow and drift monitoring
- LangGraph Agent
- evaluation harness

[Open portfolio branch](https://github.com/shaunsukgyukoh/peoplepulse-ai/tree/portfolio)

## 9. 기술 스택

`Python, PyTorch, Transformers, KLUE RoBERTa, Redis, PostgreSQL, Pandera, scikit-learn, XGBoost, LightGBM, CatBoost, SHAP, FastAPI, Next.js, React, MLflow, Evidently, Prometheus, Grafana, LangGraph, Ollama, Docker Compose`

## 10. 운영 Dashboard 실행 및 업데이트

Docker Compose stack을 실행한 뒤 production-main migration과 직원 directory를 반영합니다.

```powershell
docker compose up -d postgres redis slack-listener nlp-worker api dashboard
python scripts/apply_production_main_migration.py
python scripts/load_employee_directory.py data/employee_directory.csv
```

실제 Slack realtime 연결에는 Socket Mode용 `SLACK_APP_TOKEN`, bot용 `SLACK_BOT_TOKEN`, 서명 검증용 `SLACK_SIGNING_SECRET`가 필요합니다. 직원별 자발적 self-report 이력을 보려면 API와 Dashboard에 동일한 `ACTIVITY_ADMIN_TOKEN`을 설정하고, 팀별 집계 최소 인원은 `ACTIVITY_MIN_COHORT_SIZE`로 조정합니다.

운영 확인 예시는 다음과 같습니다.

```powershell
docker compose ps
curl.exe -sS http://localhost:8000/health
curl.exe -sS -N --max-time 4 http://localhost:8000/api/v1/dashboard/slack/stream
curl.exe -sS "http://localhost:8000/api/v1/dashboard/teams/work-signals/trend?granularity=day"
```

SSE 명령은 연결을 4초 뒤 의도적으로 종료하므로 `curl` timeout exit code가 발생할 수 있습니다. 응답에 `event:`와 `data:`가 수신되면 stream 전달이 동작한 것입니다.

## 11. 한계

- employee-level ML 결과는 synthetic data에만 해당합니다.
- causal attrition prediction을 주장하지 않습니다.
- protected-class fairness evaluation은 public dataset에 해당 demographic label을 포함하지 않아 수행하지 않았습니다.
- Docker Compose는 single-machine reproducible environment이며 HA production infrastructure는 아닙니다.
- deterministic policy guard는 enterprise authorization과 audit system을 대체하지 않습니다.
