"""Read-only host diagnostic. Never alter registry/license files or infer success from liveness."""
import argparse
import json
import subprocess
import time
from pathlib import Path
from mapgis_runtime import require_administrator, host_environment


def authorization_failed(raw: bytes) -> bool:
    markers = ['授权验证失败', '授权验证不成功', 'license verification failed']
    return any(marker.encode(encoding) in raw for marker in markers for encoding in ('utf-8', 'gb18030'))


def authorization_succeeded(raw: bytes) -> bool:
    # A license message is one prerequisite, never full plugin/GIS verification.
    markers = ['授权验证成功', 'license verification succeeded']
    return any(marker.encode(encoding) in raw for marker in markers for encoding in ('utf-8', 'gb18030'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--java', required=True)
    parser.add_argument('--program', required=True)
    parser.add_argument('--stdout', type=Path, required=True)
    parser.add_argument('--stderr', type=Path, required=True)
    parser.add_argument('--keep-open', action='store_true')
    parser.add_argument('java_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    require_administrator()
    java_args = args.java_args[1:] if args.java_args[:1] == ['--'] else args.java_args
    with args.stdout.open('wb') as stdout, args.stderr.open('wb') as stderr:
        process = subprocess.Popen([args.java, *java_args], cwd=args.program, stdout=stdout, stderr=stderr,
                                   env=host_environment(args.program),
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if args.keep_open:
        print(json.dumps({'pid': process.pid, 'verified': False, 'authorization_verified': False,
                          'status': 'manual_verification_required'}))
        return 0
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            output=args.stdout.read_bytes() + args.stderr.read_bytes()
            if authorization_failed(output):
                print(json.dumps({'verified': False, 'authorization_verified': False,
                                  'status': 'authorization_failed'}))
                return 3
            if process.poll() is not None:
                print(json.dumps({'verified': False, 'authorization_verified': authorization_succeeded(output),
                                  'status': 'exited', 'exit_code': process.returncode}))
                return 4
            time.sleep(0.25)
        output=args.stdout.read_bytes() + args.stderr.read_bytes()
        print(json.dumps({'verified': False, 'authorization_verified': authorization_succeeded(output),
                          'status': 'manual_verification_required'}))
        return 2
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == '__main__':
    raise SystemExit(main())
