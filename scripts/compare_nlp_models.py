from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="artifacts/models")
    parser.add_argument("--output", default="artifacts/reports")
    args = parser.parse_args()

    rows = []
    for model_dir in Path(args.root).iterdir():
        if not model_dir.is_dir() or model_dir.name == "selected":
            continue
        tuned = model_dir / "metrics_tuned.json"
        raw = model_dir / "metrics.json"
        path = tuned if tuned.exists() else raw
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        rows.append({
            "model": data.get("model_name", model_dir.name),
            "family": data.get("model_family", "unknown"),
            "evaluation": "val-tuned thresholds" if tuned.exists() else "fixed threshold",
            "macro_f1": data.get("macro_f1"),
            "micro_f1": data.get("micro_f1"),
            "macro_precision": data.get("macro_precision"),
            "macro_recall": data.get("macro_recall"),
            "latency_ms_mean": data.get("latency_ms_mean"),
            "latency_ms_p95": data.get("latency_ms_p95"),
            "device": data.get("device", "cpu"),
            "metrics_path": str(path),
        })
    if not rows:
        raise SystemExit("No model metrics found. Train/evaluate models first.")
    df = pd.DataFrame(rows).sort_values(["macro_f1", "latency_ms_mean"], ascending=[False, True])
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "nlp_model_comparison.csv", index=False)
    (out / "nlp_model_comparison.json").write_text(
        df.to_json(orient="records", force_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(df.to_string(index=False))
    print(
        "\nSelection rule: compare validation-tuned test Macro-F1, then verify synchronized "
        "p95 latency on the actual deployment device."
    )


if __name__ == "__main__":
    main()
