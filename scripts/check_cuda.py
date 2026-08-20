from __future__ import annotations

import torch


def main() -> None:
    print(f"torch={torch.__version__}")
    print(f"torch_cuda_runtime={torch.version.cuda}")
    print(f"cuda_available={torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"gpu={torch.cuda.get_device_name(0)}")
        print(f"device_count={torch.cuda.device_count()}")
    else:
        raise SystemExit(
            "CUDA is not available in this Python environment. Reinstall the project CUDA wheel "
            "before running the Transformer evaluation."
        )


if __name__ == "__main__":
    main()
