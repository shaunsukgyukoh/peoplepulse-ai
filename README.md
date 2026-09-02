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

### Production dashboard 부서 업무 신호 타임라인

운영 Dashboard의 핵심 화면은 조직도상 부서의 업무 커뮤니케이션 신호를 동일한 시간축에서 비교합니다. heatmap으로 변화 시점과 부서 차이를 찾고, 전체 표시 가능 부서 line chart와 부서별 최신 구간 카드로 각 부서를 함께 확인합니다. 여기서 “전체”는 조직 전체 평균이 아니라 개인정보 기준을 통과한 모든 부서의 동시 비교를 뜻합니다.

| 선택 | 집계 단위 | 조회 범위 |
|---|---|---|
| 60분 | 1시간 | 최근 24시간 |
| 일별 | 1일 | 최근 30일 |
| 주간 | 1주 | 최근 12주 |
| 월간 | 1개월 | 최근 12개월 |

- Production Dashboard와 직원 directory CSV 입력은 self-report를 사용하지 않습니다. 과거 DB 컬럼이나 이력 테이블은 자동 삭제하지 않지만 API, UI, loader에서는 읽거나 쓰지 않습니다.
- Slack derived signal은 직원별로 먼저 평균한 뒤 `core.employee_directory.department`별로만 집계합니다. 전체·직책 단위 Slack 신호, Slack workspace team ID, 프로젝트 팀은 제공하지 않습니다.
- 부서·시간 구간마다 서로 다른 직원이 `ACTIVITY_MIN_COHORT_SIZE` 이상일 때만 반환하며, 5명 미만 부서는 명칭과 인원 메타데이터도 응답에서 제외합니다. 기본값은 5명입니다.
- 업무 긴장 종합, 긍정·중립·답답함·강한 부정·불만·과부하·갈등·몰입 저하 표현을 선택해 같은 heatmap, line chart, 부서 카드에 적용할 수 있습니다.
- 최소 인원 기준은 Dashboard에서 해제할 수 없습니다. API는 미달 부서 이름 대신 `suppressed_department_count`만 반환해 비공개 부서 수를 안내합니다.
- 모든 구간은 `Asia/Seoul` 기준이며 Slack SSE revision이 바뀌면 현재 부서 타임라인을 다시 조회합니다.
- Slack 신호는 심리 상태나 정신건강 진단이 아니라 업무 표현의 집계입니다. 개인별 Slack NLP 점수는 API와 Dashboard 모두에서 노출하지 않습니다.

통합 API는 `GET /api/v1/dashboard/organization/support-timeline`이며 `grouping=department`, 최소 인원 기준을 통과한 `departments`, 부서별 `points`, `suppressed_department_count`, 개인정보 비노출 정책을 반환합니다. `granularity`에는 `hour`, `day`, `week`, `month`를 사용할 수 있습니다. 기존 `GET /api/v1/dashboard/departments/work-signals/trend`도 호환성을 위해 유지합니다.

### Synthetic individual activity demo

개인 portfolio용 `synthetic_demo`에서는 `김가람`, `이도윤`, `박서진`이라는 기존 가상 이름을 유지한 별도 개인 활동 화면을 제공합니다. 이 화면은 `APP_ENV=development`이면서 `ACTIVITY_PRIVACY_MODE=synthetic_demo`일 때만 활성화되고, production 또는 aggregate 모드의 `GET /api/v1/dashboard/synthetic-demo/individual-activity`는 이름이나 개인 행 없이 `enabled=false`를 반환합니다.

- 활동 시계열은 `Synthetic_` 파일명 검사를 통과한 배치의 `features.synthetic_employee_monthly_activity`에서만 읽습니다.
- 개인 화면에는 문서 활동, privacy filter를 거친 업무 웹 검색 횟수·활동일, 시간외/주말 비율만 제공합니다. 개인별 Slack feature와 구직 사이트 활동은 반환하지 않습니다.
- 메시지 예시는 Slack 수집 데이터가 아닌 `data/synthetic/dashboard/individual_activity_messages.csv`의 오프라인 가상 fixture입니다. API는 원문을 반환하지 않고 메시지 수, 공백 제외 글자 수, 표면 토큰 수, 질문/감탄부호 수, 존댓말 종결 비율, 빈출 토큰만 계산합니다.
- 긍정/부정/중립 점수, Sentiment Ratio, 부드러움/강경함 같은 어조 라벨, 감정·심리·정신건강 상태는 개인별로 계산하거나 표시하지 않습니다.

전체 synthetic seed와 Dashboard를 실행하려면 다음 portfolio 명령을 사용합니다.

```powershell
.\scripts\portfolio_up.ps1 -Scope synthetic_demo
```

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

실제 Slack realtime 연결에는 Socket Mode용 `SLACK_APP_TOKEN`, bot용 `SLACK_BOT_TOKEN`, 서명 검증용 `SLACK_SIGNING_SECRET`가 필요합니다. 핵심인력 변경과 보고서 업로드에는 API 서버의 `ACTIVITY_ADMIN_TOKEN`과 같은 값을 Dashboard의 해당 관리자 토큰 입력란에 입력합니다. 월말 데이터 업데이트 폼에도 별도 입력란이 있으며 토큰은 브라우저에 저장하지 않습니다. 보고 월은 사용자가 입력하지 않습니다. 서버가 세 Excel 상단의 `기간선택` 범위를 읽고, 표시 기간이 없을 때만 실제 이벤트의 최소·최대 날짜를 사용합니다. 세 파일에 표시된 기간은 서로 같아야 하며 여러 달 범위는 기존 feature store 호환성을 위해 월별 행으로 자동 분할해 전 기간을 처리합니다. 부서 타임라인의 집계 최소 인원은 `ACTIVITY_MIN_COHORT_SIZE`로 조정합니다.

운영 확인 예시는 다음과 같습니다.

```powershell
docker compose ps
curl.exe -sS http://localhost:8000/health
curl.exe -sS -N --max-time 4 http://localhost:8000/api/v1/dashboard/slack/stream
curl.exe -sS "http://localhost:8000/api/v1/dashboard/organization/support-timeline?granularity=week"
```

SSE 명령은 연결을 4초 뒤 의도적으로 종료하므로 `curl` timeout exit code가 발생할 수 있습니다. 응답에 `event:`와 `data:`가 수신되면 stream 전달이 동작한 것입니다. 이 stream은 조직 전체 추론 점수를 보내지 않고 최신 메시지 시각만 갱신 신호로 전달하며, Dashboard는 이를 받으면 최소 코호트 기준이 적용된 부서 타임라인을 다시 조회합니다.

## 11. 한계

- employee-level ML 결과는 synthetic data에만 해당합니다.
- causal attrition prediction을 주장하지 않습니다.
- protected-class fairness evaluation은 public dataset에 해당 demographic label을 포함하지 않아 수행하지 않았습니다.
- Docker Compose는 single-machine reproducible environment이며 HA production infrastructure는 아닙니다.
- deterministic policy guard는 enterprise authorization과 audit system을 대체하지 않습니다.
