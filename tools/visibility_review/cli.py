import argparse
import json
import logging
import os
import socket
import sys
from pathlib import Path
from .manifest import Manifest, DEFAULT, ROOT
from .review_store import Store, atomic_json
from .preview import Previews
from .validation import integrity, report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['check', 'warm', 'report', 'serve'])
    parser.add_argument('--manifest', type=Path, default=DEFAULT / 'visibility_manifest.json')
    parser.add_argument('--store', type=Path, default=DEFAULT)
    parser.add_argument('--port', type=int, default=18766)
    parser.add_argument('--instance', default='manual-cli')
    parser.add_argument('--report', type=Path, default=ROOT / 'docs/VISIBILITY_REVIEW_REPORT.md')
    args = parser.parse_args()
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[logging.FileHandler(logs / 'visibility-review.log', encoding='utf-8'), logging.StreamHandler()])
    m = Manifest(args.manifest)
    if args.command == 'serve':
        import uvicorn
        from .app import create_app
        args.store.mkdir(parents=True, exist_ok=True)
        # Lifetime lock prevents a second service sharing the same review store.
        lockfile = (args.store / '.service.lock').open('a+b')
        if lockfile.tell() == 0:
            lockfile.write(b'0'); lockfile.flush()
        lockfile.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(lockfile.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        app = create_app(args.manifest, args.store)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        for port in range(args.port, min(args.port + 100, 65536)):
            try:
                sock.bind(('127.0.0.1', port))
                break
            except OSError:
                logging.info('Port %s unavailable; trying next local port', port)
        else:
            raise RuntimeError('No free local port')
        sock.listen(128)
        atomic_json(args.store / 'service_ready.json', {'pid': os.getpid(), 'port': port,
                    'instance': args.instance, 'url': f'http://127.0.0.1:{port}', 'store': str(args.store.resolve())})
        logging.info('Germany Visibility Review: http://127.0.0.1:%s ; store=%s', port, args.store.resolve())
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_config=None))
        app.state.shutdown = lambda: setattr(server, 'should_exit', True)
        server.run(sockets=[sock])
        return
    store = Store(m, args.store)
    if args.command == 'check':
        result = integrity(m, store, hashes=True)
        logging.info('Integrity: %s samples, %s hashes, %s issues', result['total_sample_count'], result['hashes_checked'], len(result['issues']))
        print(json.dumps(result, ensure_ascii=True))
        # Duplicates/mapping contradictions make decisions ambiguous. Missing/corrupt assets remain reviewable.
        if any(i['code'] in ('DUPLICATE_SAMPLE_ID', 'INVALID_POST_COLUMN', 'MAPPING_ERROR') for i in result['issues']):
            sys.exit(2)
    elif args.command == 'warm':
        errors = Previews(m, m.path.parent / 'previews').warm()
        logging.info('Preview cache checked: %s samples; %s asset errors', len(m.samples), len(errors))
    elif args.command == 'report':
        print(json.dumps(report(m, store, args.report)))


if __name__ == '__main__':
    main()
