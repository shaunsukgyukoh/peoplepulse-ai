from __future__ import annotations

import argparse

from peoplepulse.config import get_settings
from peoplepulse.features.identity import load_identity_mapping


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["aggregate", "synthetic_demo"], required=True)
    parser.add_argument("--path", required=True)
    args = parser.parse_args()

    result = load_identity_mapping(args.path, mode=args.mode, settings=get_settings())
    print(
        f"[OK] identity mapping loaded mode={result.mode} "
        f"rows={result.persisted_rows} path={result.mapping_path}"
    )


if __name__ == "__main__":
    main()
