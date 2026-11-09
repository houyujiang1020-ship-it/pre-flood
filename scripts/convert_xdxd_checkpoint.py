"""Convert an audited legacy XD_XD SpaceNet-5 model pickle to a safe state_dict."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import types
import warnings
from datetime import datetime, timezone
from pathlib import Path

import torch


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def install_legacy_module(source: Path) -> None:
    module_name = "aa.pytorch.models.senet"
    spec = importlib.util.spec_from_file_location(module_name, source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import compatibility source: {source}")
    module = importlib.util.module_from_spec(spec)
    for name in ("aa", "aa.pytorch", "aa.pytorch.models"):
        sys.modules[name] = types.ModuleType(name)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    sys.modules["aa"].pytorch = sys.modules["aa.pytorch"]
    sys.modules["aa.pytorch"].models = sys.modules["aa.pytorch.models"]
    sys.modules["aa.pytorch.models"].senet = module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-url", required=True)
    args = parser.parse_args()

    input_path = args.input.resolve()
    source = args.source.resolve()
    actual_input_sha = sha256(input_path)
    if actual_input_sha != args.expected_sha256.lower():
        raise RuntimeError(f"input SHA-256 mismatch: {actual_input_sha}")
    install_legacy_module(source)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", torch.serialization.SourceChangeWarning)
        # The legacy artifact is a pickle. It is loaded only after matching the exact
        # SHA-256 recorded from the official public SpaceNet bucket.
        model = torch.load(input_path, map_location="cpu", weights_only=False)
    state_dict = model.state_dict()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(state_dict, output)
    receipt = {
        "schema": "xdxd-spacenet5-state-dict-v1",
        "source_url": args.source_url,
        "source_artifact": str(input_path),
        "source_sha256": actual_input_sha,
        "compatibility_source": str(source),
        "compatibility_source_sha256": sha256(source),
        "output": str(output),
        "output_sha256": sha256(output),
        "parameter_tensors": len(state_dict),
        "parameters": sum(value.numel() for value in state_dict.values()),
        "converted_at": datetime.now(timezone.utc).isoformat(),
        "warning": "External road-foundation research weight; not a four-class flood model.",
        "production_ready": False,
    }
    receipt_path = output.with_suffix(output.suffix + ".receipt.json")
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
