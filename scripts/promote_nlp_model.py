from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath


def _metrics_parent(raw: str) -> Path:
    # Comparison files are often generated on Windows. Resolve their relative
    # metrics path correctly even if this script is inspected elsewhere.
    p = PureWindowsPath(raw)
    return Path(*p.parts[:-1])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--comparison", default="artifacts/reports/nlp_model_comparison.json"
    )
    parser.add_argument("--destination", default="artifacts/models/selected")
    parser.add_argument("--min-macro-f1", type=float, default=0.70)
    parser.add_argument("--max-p95-ms", type=float, default=20.0)
    parser.add_argument("--family", default="transformer")
    args = parser.parse_args()

    records = json.loads(Path(args.comparison).read_text(encoding="utf-8"))
    eligible = [
        row for row in records
        if row.get("family") == args.family
        and float(row.get("macro_f1", 0.0)) >= args.min_macro_f1
        and float(row.get("latency_ms_p95", float("inf"))) <= args.max_p95_ms
    ]
    if not eligible:
        raise SystemExit("No model meets the promotion constraints")
    best = max(eligible, key=lambda row: float(row["macro_f1"]))
    src = _metrics_parent(best["metrics_path"])
    if not (src / "config.json").exists():
        raise SystemExit(f"Checkpoint not found for selected model: {src}")
    if not (src / "thresholds.json").exists():
        raise SystemExit(f"Validation thresholds not found: {src / 'thresholds.json'}")

    dst = Path(args.destination)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    manifest = {
        "promoted_at": datetime.now(UTC).isoformat(),
        "source_model": best["model"],
        "source_checkpoint": str(src),
        "selection": {
            "primary_metric": "macro_f1",
            "min_macro_f1": args.min_macro_f1,
            "max_p95_ms": args.max_p95_ms,
            "family": args.family,
        },
        "observed_metrics": best,
        "portfolio_note": (
            "Metrics are from the synthetic STEP 3 dataset and are not evidence of "
            "performance on real employees or a basis for automated employment decisions."
        ),
    }
    (dst / "deployment_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"[OK] promoted {best['model']} macro_f1={best['macro_f1']:.4f} "
        f"p95={best['latency_ms_p95']:.2f}ms -> {dst}"
    )


if __name__ == "__main__":
    main()
