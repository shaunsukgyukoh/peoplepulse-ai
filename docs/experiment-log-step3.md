# STEP 3 Experiment Log

## 2026-08-20 — First local model comparison

The first local run used the synthetic `workplace_messages_v01.csv` dataset.
These results validate the experiment pipeline only; they are **not evidence of
performance on real employees or real workplace messages**.

| Model | Macro-F1 | Micro-F1 | Macro Precision | Macro Recall | Device | Initial p95 latency |
|---|---:|---:|---:|---:|---|---:|
| `klue/roberta-base` | 0.6764 | 0.6552 | 0.5467 | 0.9688 | CUDA | 9.92 ms* |
| `beomi/KcELECTRA-base` | 0.4203 | 0.4254 | 0.2721 | 0.9479 | CUDA | 6.95 ms* |
| `tfidf-logreg` | 0.2788 | 0.3896 | 0.4167 | 0.2257 | CPU | 3.02 ms |
| `beomi/KcELECTRA-small-v2022` | 0.1566 | 0.2180 | 0.0952 | 0.5417 | CPU | 8.66 ms |

\* The original CUDA benchmark did not explicitly synchronize the GPU before the
wall-clock timer stopped. CUDA kernels are asynchronous, so these GPU latency
values are provisional and must be re-measured with the STEP 3.1 evaluator.

### Interpretation

- `klue/roberta-base` is the provisional accuracy leader by a large Macro-F1 margin.
- Both CUDA Transformer runs show very high macro recall relative to precision,
  suggesting that the global 0.5 decision threshold is over-activating labels on
  this small synthetic dataset.
- `KcELECTRA-small-v2022` was measured on CPU before the local CUDA environment was
  corrected, so its latency is not directly comparable to the CUDA candidates.
- Device changes should not be used as an explanation for large accuracy gaps;
  thresholding, capacity, data size, and optimization behavior must be investigated.

## STEP 3.1 experiment plan

1. Keep the already-trained checkpoints; do not retrain just to benchmark CUDA.
2. Tune **per-label thresholds on validation data only**.
3. Evaluate those frozen thresholds once on the test split.
4. Re-measure single-message GPU latency with explicit `torch.cuda.synchronize()`.
5. Run the same threshold optimization for the TF-IDF baseline for a fair comparison.
6. Select a production candidate using Macro-F1 first, then p95 latency.
7. Copy the selected checkpoint to `artifacts/models/selected` and connect the Redis NLP worker.


## STEP 3.2 promotion decision

Validation-tuned comparison supplied from the local experiment:

- `klue/roberta-base`: Macro-F1 0.7988, P95 7.26 ms, CUDA — promoted.
- `tfidf-logreg`: Macro-F1 0.5565, P95 2.61 ms, CPU.
- `beomi/KcELECTRA-base`: Macro-F1 0.4763, P95 6.66 ms, CUDA.
- `beomi/KcELECTRA-small-v2022`: Macro-F1 0.2628, P95 7.81 ms, CUDA.

Runtime now loads the promoted checkpoint's `thresholds.json`; production behavior therefore matches the validation-tuned experiment rather than reverting to a global 0.5 threshold.
