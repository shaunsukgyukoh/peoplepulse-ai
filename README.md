# PeoplePulse — Production HR Operations

`main` is the production-oriented branch. The original portfolio / model-evaluation experience is preserved on the `portfolio` branch.

## Purpose

PeoplePulse helps HR managers review:

- the active employee directory with real names, department, and job title;
- a **manual** key-staff marker (`★`) for business-critical roles;
- voluntary employee self-report status (`good`, `okay`, `needs_support`, `prefer_not_to_say`);
- organization-level Slack-derived work-communication trends;
- monthly report ingestion status.

The production dashboard intentionally hides portfolio-only information such as model benchmark tables, SHAP plots, synthetic attrition evaluation, tool-call evaluation, and other engineering metrics.

## Important HR boundary

PeoplePulse production does **not** expose employee-level inferred psychological or mental-health states.

- Slack NLP remains organization/cohort-level on the dashboard.
- Individual status shown in the employee roster must come from **voluntary self-report** only.
- `is_key_staff` is a manager-entered field and must never be generated from NLP, attrition-risk, browsing, or inferred behavioral scores.
- The system must not be used to automate hiring, firing, discipline, promotion, compensation, or similar employment decisions.
- Raw Slack text is not durably stored by the PeoplePulse pipeline.

## Branches

```text
main
└─ production HR dashboard
   ├─ employee real-name directory
   ├─ voluntary self-report view
   ├─ manual key-staff stars
   ├─ employee filters / sorting
   ├─ aggregate Slack work signals
   └─ monthly report operations

portfolio
└─ portfolio / interview branch
   ├─ NLP benchmark comparison
   ├─ synthetic attrition ML
   ├─ SHAP
   ├─ MLflow / Evidently / Grafana
   ├─ Ollama / LangGraph agent
   └─ evaluation artifacts
```

## First-time production setup

Activate the existing environment:

```powershell
cd "C:\Users\a\Documents\Agentic-AI project\peoplepulse-ai"
.\.venv\Scripts\Activate.ps1
```

Make sure the existing `.env` contains the same `EMPLOYEE_HASH_KEY` that is already used by Slack ingestion, plus a strong `ACTIVITY_ADMIN_TOKEN`.

Start the production dashboard:

```powershell
.\scripts\run_production_main.ps1
```

Dashboard:

```text
http://localhost:3000
```

API docs:

```text
http://localhost:8000/docs
```

## Employee directory

Apply the schema manually if needed:

```powershell
python scripts/apply_production_main_migration.py
```

Create a local employee directory from the template:

```powershell
Copy-Item data\templates\employee_directory.csv.example data\employee_directory.csv
```

Required CSV columns:

```text
slack_user_id,employee_name,department
```

Optional columns:

```text
job_title,is_key_staff,is_active,self_report_status
```

Allowed self-report values:

```text
good
okay
needs_support
prefer_not_to_say
```

Then load it:

```powershell
python scripts/load_employee_directory.py data\employee_directory.csv
```

`slack_user_id` is converted with the same `EMPLOYEE_HASH_KEY` / `employee` HMAC namespace used by the Slack pipeline, so the directory can be matched to existing derived records without storing the raw Slack ID in the directory table.

**Never commit the real CSV.** `.gitignore` excludes production employee-directory files.

## Dashboard features

### Employee roster

Managers can:

- view employee names, department, and job title;
- filter by department and self-report status;
- search by name / department / job title;
- show starred key staff only;
- sort by key staff, name, department, or self-report status;
- toggle a `★` key-staff marker using the administrator token.

### Self-report visualization

The dashboard visualizes voluntary status distribution only. It does not convert Slack messages into individual psychological diagnoses.

### Organization work-communication signals

Slack-derived NLP is shown only in aggregate, including work-strain / positive-expression / overload-expression trends. These signals are intended to identify organization-level patterns that may justify workload or process review, not to score individuals.

### Monthly report operations

The existing three-report upload flow remains available for authorized administrators.

## Production tables

```text
core.employee_directory
features.message_nlp_signal
features.department_monthly_activity
features.department_monthly_fusion
```

`core.employee_directory` contains manager-visible identity data and voluntary status. It does not store individual Slack NLP scores.

## Key-staff semantics

`is_key_staff` is deliberately independent of all AI outputs.

Correct examples:

- sole maintainer of a critical subsystem;
- formally designated technical lead;
- business-critical license / certification holder;
- explicitly designated succession-critical role.

Do not automatically assign stars based on:

- emotion / sentiment;
- inferred engagement;
- attrition score;
- browser or search history;
- protected or sensitive information.

## Portfolio branch

To return to the full AI/ML portfolio experience:

```powershell
git fetch origin
git switch portfolio
```

To use the production branch:

```powershell
git switch main
git pull origin main
```
