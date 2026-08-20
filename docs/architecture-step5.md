# STEP 5 — Identity Resolution + 7/30/90d Slack Rollups + Feature Store

## Goal

Create a reproducible feature layer that combines privacy-reduced Slack NLP signals with the
three monthly activity reports without performing fuzzy name matching.

## Two runtime paths

### Production / aggregate

```text
Explicit local Slack-user -> department mapping
  -> HMAC at ingest; raw identifiers are not persisted
  -> message_nlp_signal
  -> employee-first 7/30/90d rollups
  -> department average / cohort suppression
  -> department_monthly_slack_signal
  + department_monthly_activity
  -> department_monthly_fusion
```

No employee-level fused production table is created.

### Portfolio / synthetic_demo

```text
canonical_employee_map.csv
  Slack demo ID -> canonical demo employee <- synthetic report name
                  |
                  -> HMAC-only core.synthetic_identity_map

message_nlp_signal -> 7/30/90d employee Slack features
synthetic_employee_monthly_activity -> monthly activity features
                      |
                      -> synthetic_employee_retention_feature
```

The employee-level table is reserved for synthetic portfolio experiments and is blocked from the
production mode by the surrounding STEP 4/5 controls.

## Why explicit identity resolution

The Slack source identifies people by Slack user ID while monthly reports identify people by name.
PeoplePulse does not fuzzy-match names or guess identities. An authorized mapping file is supplied
locally, transformed to HMAC identifiers, and only the hashes are persisted.

## Slack window features

For 7, 30 and 90 day windows ending on the report month's last day:

- message count
- active days
- message rate/day
- mean of each of the 8 NLP signals
- mean work-strain signal = average of frustrated/angry/dissatisfied/overloaded/conflict/disengaged

Trend features compare 7-day values against 30-day values.

For production department rollups, signal means are calculated per employee first and then averaged
across employees. This prevents a single high-volume Slack user from dominating the department score.

## Output tables

- `core.slack_department_map`
- `core.synthetic_identity_map`
- `features.department_monthly_slack_signal`
- `features.department_monthly_fusion`
- `features.synthetic_employee_monthly_slack_signal`
- `features.synthetic_employee_retention_feature`
