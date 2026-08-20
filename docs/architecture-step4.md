# STEP 4 — Actual 3-Report Monthly Activity Pipeline

## Input contracts

The production upload is one month represented by exactly three `.xls` or `.xlsx` exports. Their order and filenames are not trusted; the header row is detected from its signature.

```text
취업사이트 접속내역
  이름 | 부서 | 총 접속 시간 | 접속 사이트 | 타이틀 | 접속 시간 ↓ | 접속일

웹 검색 내역
  이름 | 부서 | 검색 키워드 ↓ | 키워드 | 검색어 | 검색 사이트 | 검색일

문서활용 내역
  이름 | 부서 | 활용 키워드 ↓ | 키워드 | 문서명 | 구분 | 시각
```

The real export layout places a period/department summary above the header and uses blank identity cells for subsequent rows belonging to the same employee. The normalization layer therefore forward-fills `이름` and `부서` after extracting the detail table.

## Flow

```text
3 files in one multipart request
          ↓
.xls / .xlsx + size validation
          ↓
pandas.read_excel(engine="calamine", header=None)
          ↓
scan first rows for header signature
          ↓
exactly one of each report type?
          ↓
forward-fill 이름 / 부서
          ↓
normalize "회사 > 부서" -> leaf department
          ↓
report-specific Pandera DataFrameModel
          ↓
report-month validation
          ↓
duplicate removal
          ↓
in-memory sensitive-content filtering
          ↓
         privacy mode
   ┌──────────┴─────────────┐
   │                        │
aggregate                synthetic_demo
(real default)            (portfolio only)
   │                        │
min cohort size             require every filename
(k-anonymity)                starts with Synthetic_
   │                        │
HMAC department ID          HMAC employee/department IDs
   │                        │
features.department_        features.synthetic_employee_
monthly_activity            monthly_activity
   └──────────┬─────────────┘
              ↓
       PostgreSQL transaction
```

## Privacy boundary

The three reports contain employee browsing/search/document information that can expose highly personal intent. STEP 4 therefore separates the production and synthetic portfolio paths.

### `aggregate` (default)

- no employee-level feature row is persisted;
- raw name, site, title, search query, search category, document name and document keyword are never persisted;
- department identifiers are HMAC-pseudonymized;
- a department with fewer than `ACTIVITY_MIN_COHORT_SIZE` distinct employees is suppressed;
- sensitive rows are excluded before aggregation and retained only as batch-level counts.

### `synthetic_demo`

- employee-level derived features can be persisted for model development;
- all 3 uploaded filenames must begin with `ACTIVITY_DEMO_FILENAME_PREFIX` (default `Synthetic_`);
- this mode is intended only for the synthetic actual-format files shipped under `data/synthetic/activity/actual-format/`.

## Stored features

Both feature families are behavioral volume/timing aggregates rather than raw content:

- job-site event count / seconds / active days
- web-search event count / active days
- document event count / active days
- document create / modify / view counts
- after-hours search/document ratios
- weekend search/document ratios

No raw keyword category such as resignation/union/health is saved as an employee feature.

## Identity note for STEP 5

The actual reports identify people by name while Slack identifies people by Slack user ID. These should **not** be joined by guessing display names. STEP 5 must introduce an explicit controlled identity mapping (canonical employee key) before synthetic Slack and activity features can be joined for the portfolio ML dataset.
