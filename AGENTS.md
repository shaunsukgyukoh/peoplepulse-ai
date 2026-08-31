# Repository working agreements

## Completion workflow

- For every user-requested repository change, verify the affected behavior against the actually running application after tests pass. Do not describe realtime behavior as working based only on unit tests or static inspection.
- Update `README.md` in the same change whenever behavior, configuration, setup, operations, or public API usage changes.
- Inspect the complete diff and the remote branch before publishing. Preserve unrelated user changes and integrate remote work without destructive Git operations.
- For repository-changing tasks, create a detailed commit message that explains behavior, operational impact, privacy boundaries, and verification, then push the verified commit to the current tracked branch. If a task is read-only or produces no repository change, report that no commit or push was needed.

## Employee-data boundaries

- Never expose employee-level Slack NLP scores or infer or display an employee's psychological or mental-health state from workplace communications.
- An employee-level state view may use only a voluntary employee-provided self-report, must require administrative authorization, and must identify that source clearly.
- Slack-derived workplace signals may be shown only as employee-first aggregates grouped by the organizational-chart `department` in `core.employee_directory`. Suppress every department/time bucket below `ACTIVITY_MIN_COHORT_SIZE`, which defaults to 5, and never return employee identifiers or raw messages in that aggregate response.
