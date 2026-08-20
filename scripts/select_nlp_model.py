from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Fine-tuned Transformer model directory")
    parser.add_argument("--destination", default="artifacts/models/selected")
    args = parser.parse_args()

    src = Path(args.source)
    dst = Path(args.destination)
    if not (src / "config.json").exists():
        raise SystemExit(f"Not a Hugging Face checkpoint directory: {src}")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print(f"[OK] selected model: {src} -> {dst}")


if __name__ == "__main__":
    main()
