from __future__ import annotations

import json
from pathlib import Path


REQUIRED = [
    Path("dashboard/package.json"),
    Path("dashboard/app/page.tsx"),
    Path("dashboard/app/globals.css"),
    Path("src/peoplepulse/api/dashboard.py"),
    Path("src/peoplepulse/dashboard/service.py"),
    Path("docs/experiment-results/step6_reference_metrics.json"),
    Path("docs/experiment-results/nlp_model_comparison_step3_1.json"),
]


def main() -> int:
    missing = [str(path) for path in REQUIRED if not path.exists()]
    if missing:
        print("[ERROR] STEP 7 files missing:")
        for path in missing:
            print(f"  - {path}")
        return 1

    package = json.loads(Path("dashboard/package.json").read_text(encoding="utf-8"))
    reference = json.loads(
        Path("docs/experiment-results/step6_reference_metrics.json").read_text(encoding="utf-8")
    )
    nlp = json.loads(
        Path("docs/experiment-results/nlp_model_comparison_step3_1.json").read_text(encoding="utf-8")
    )
    print("[OK] STEP 7 static preflight")
    print(f"  next={package['dependencies']['next']}")
    print(f"  react={package['dependencies']['react']}")
    print(f"  echarts={package['dependencies']['echarts']}")
    print(f"  attrition_scope={reference.get('scope')}")
    print(f"  nlp_models={len(nlp)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
