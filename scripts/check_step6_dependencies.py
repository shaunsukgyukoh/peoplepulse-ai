from __future__ import annotations

import importlib
import sys

REQUIRED = {
    "joblib": "joblib",
    "numpy": "numpy",
    "pandas": "pandas",
    "scikit-learn": "sklearn",
    "xgboost": "xgboost",
    "lightgbm": "lightgbm",
    "catboost": "catboost",
    "shap": "shap",
    "matplotlib": "matplotlib",
}


def _major_minor(version: str) -> tuple[int, int]:
    parts = version.split(".")
    try:
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 0, 0


def main() -> int:
    missing: list[str] = []
    versions: dict[str, str] = {}

    print(
        f"[INFO] Python={sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )

    for package_name, module_name in REQUIRED.items():
        try:
            module = importlib.import_module(module_name)
            versions[package_name] = str(getattr(module, "__version__", "installed"))
        except Exception as exc:  # pragma: no cover - diagnostic path
            missing.append(f"{package_name} ({type(exc).__name__}: {exc})")

    if missing:
        print("[ERROR] STEP 6 ML dependencies are incomplete in the active Python environment.")
        for item in missing:
            print(f"  - {item}")
        print()
        print('Run from the project root with .venv activated:')
        print('  python -m pip install -e ".[ml,dev]"')
        print()
        print("Compatibility note:")
        print("  Python 3.11 -> XGBoost 3.2.x")
        print("  Python 3.12 -> XGBoost 3.3+")
        return 1

    xgb_version = versions.get("xgboost", "0.0")
    xgb_major_minor = _major_minor(xgb_version)
    if sys.version_info < (3, 12) and xgb_major_minor >= (3, 3):
        print(
            "[ERROR] XGBoost >=3.3 requires Python >=3.12. "
            f"Current Python={sys.version_info.major}.{sys.version_info.minor}, "
            f"xgboost={xgb_version}"
        )
        print('Run: python -m pip install -e ".[ml,dev]"')
        return 1

    print("[OK] STEP 6 ML dependencies")
    for package_name in REQUIRED:
        print(f"  {package_name}={versions[package_name]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
