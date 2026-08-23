import argparse
import json
from pathlib import Path

from .inference import predict


def main() -> int:
    parser = argparse.ArgumentParser(prog="mapgis-flood-ai")
    subparsers = parser.add_subparsers(dest="command", required=True)
    predict_parser = subparsers.add_parser("predict")
    predict_parser.add_argument("--pre", type=Path, required=True)
    predict_parser.add_argument("--post", type=Path, required=True)
    predict_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = predict(args.pre.expanduser().resolve(), args.post.expanduser().resolve(), args.output.expanduser().resolve())
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
