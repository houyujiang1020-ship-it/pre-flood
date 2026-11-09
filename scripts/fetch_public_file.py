"""Download a public artifact with resume support and a SHA-256 receipt."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_range(url: str, path: Path, start: int, end: int) -> None:
    expected = end - start + 1
    existing = path.stat().st_size if path.exists() else 0
    if existing > expected:
        raise RuntimeError(f"oversized range file: {path}")
    if existing == expected:
        return
    request_start = start + existing
    request = urllib.request.Request(
        url,
        headers={
            "Range": f"bytes={request_start}-{end}",
            "User-Agent": "mapgos-reproducible-artifact-fetch/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        if response.status != 206:
            raise RuntimeError(f"server ignored Range request for {start}-{end}")
        with path.open("ab") as output:
            while block := response.read(1024 * 1024):
                output.write(block)
    if path.stat().st_size != expected:
        raise RuntimeError(f"range size mismatch for {start}-{end}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--expected-size", type=int)
    parser.add_argument("--parallel", type=int, default=1)
    args = parser.parse_args()

    destination = args.destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    partial = destination.with_suffix(destination.suffix + ".part")
    if args.parallel > 1:
        if args.expected_size is None:
            raise RuntimeError("--parallel requires --expected-size")
        part_dir = destination.with_suffix(destination.suffix + ".parts")
        part_dir.mkdir(parents=True, exist_ok=True)
        chunk_size = (args.expected_size + args.parallel - 1) // args.parallel
        ranges = []
        for index in range(args.parallel):
            start = index * chunk_size
            end = min(args.expected_size - 1, start + chunk_size - 1)
            if start <= end:
                ranges.append((index, start, end))
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallel) as pool:
            futures = [
                pool.submit(
                    download_range,
                    args.url,
                    part_dir / f"part-{index:03d}",
                    start,
                    end,
                )
                for index, start, end in ranges
            ]
            for future in concurrent.futures.as_completed(futures):
                future.result()
        with partial.open("wb") as output:
            for index, _, _ in ranges:
                with (part_dir / f"part-{index:03d}").open("rb") as source:
                    while block := source.read(8 * 1024 * 1024):
                        output.write(block)
        for child in part_dir.iterdir():
            child.unlink()
        part_dir.rmdir()
    else:
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {"User-Agent": "mapgos-reproducible-artifact-fetch/1.0"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = urllib.request.Request(args.url, headers=headers)
        with urllib.request.urlopen(request, timeout=120) as response:
            if offset and response.status != 206:
                raise RuntimeError("server ignored Range request; refusing to append")
            mode = "ab" if offset else "wb"
            with partial.open(mode) as output:
                while block := response.read(8 * 1024 * 1024):
                    output.write(block)

    actual_size = partial.stat().st_size
    if args.expected_size is not None and actual_size != args.expected_size:
        raise RuntimeError(
            f"size mismatch: expected {args.expected_size}, downloaded {actual_size}"
        )
    os.replace(partial, destination)
    receipt = {
        "url": args.url,
        "path": str(destination),
        "size_bytes": actual_size,
        "sha256": sha256(destination),
        "download_seconds": round(time.time() - started, 3),
    }
    receipt_path = destination.with_suffix(destination.suffix + ".receipt.json")
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
