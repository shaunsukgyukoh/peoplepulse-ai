# PeoplePulse Workplace Signal Classifier — Model Card

## Intended use
Message-level linguistic signal extraction for a portfolio/demo organizational-analytics system. Outputs are descriptive model scores and must not be used as sole evidence for hiring, firing, promotion, discipline, compensation, or mental-health assessment.

## Labels
`satisfied`, `neutral`, `frustrated`, `angry`, `dissatisfied`, `overloaded`, `conflict`, `disengaged`.

## Data
Record dataset version, provenance, annotation method, consent/governance, train/val/test split strategy, class frequencies, and known gaps.

## Evaluation
Report Macro-F1, Micro-F1, per-label F1, precision/recall, Hamming loss, subset accuracy, and mean/p95 latency on the deployment device.

## Limitations
Text can be sarcastic, context-dependent, multilingual, culturally specific, or misinterpreted. Message-level language is not equivalent to a person's psychological state or intent to resign.

## Privacy and governance
PII masking occurs before NLP; original Slack IDs are HMAC-pseudonymized; raw message text is not durably persisted by the STEP 3 architecture.
