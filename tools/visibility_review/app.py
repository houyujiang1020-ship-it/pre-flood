import logging
import secrets
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .manifest import Manifest, DEFAULT
from .review_store import Store, FLAGS
from .preview import Previews, LAYERS


def create_app(manifest_path=DEFAULT / 'visibility_manifest.json', store_dir=DEFAULT, root=None):
    manifest = Manifest(manifest_path, **({'root': root} if root else {}))
    store = Store(manifest, store_dir)
    previews = Previews(manifest, manifest.path.parent / 'previews')
    token = secrets.token_urlsafe(32)
    app = FastAPI(title='Germany Visibility Review', docs_url=None, redoc_url=None)
    app.state.store, app.state.previews = store, previews
    app.mount('/static', StaticFiles(directory=Path(__file__).parent / 'static'), name='static')

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        if request.url.hostname not in ('127.0.0.1', 'localhost', 'testserver'):
            return JSONResponse({'detail': 'Local host only'}, 403)
        if request.method == 'POST' and request.headers.get('x-review-token') != token:
            return JSONResponse({'detail': 'Refresh the review page before saving'}, 403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        if request.url.path.startswith('/api'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/')
    def home():
        return FileResponse(Path(__file__).parent / 'static/index.html')

    @app.get('/health')
    def health():
        return {'service': 'germany-visibility-review', 'store': str(store.directory),
                'manifest_sha256': manifest.sha256}

    @app.get('/api/bootstrap')
    def bootstrap():
        with store.lock():
            store.reload()
            return {'token': token, 'flags': FLAGS, 'summary': store.summary(), 'resume': store.resume(),
                    'sandbox': store.directory != manifest.path.parent, 'store': str(store.directory)}

    @app.get('/api/samples')
    def samples(kind: str = 'all', search: str = '', risk: bool = False):
        with store.lock():
            store.reload()
            return {'ids': store.query(kind, search, risk), 'summary': store.summary(), 'resume': store.resume()}

    @app.get('/api/sample/{sid}')
    def sample(sid: str):
        if sid not in manifest.samples:
            raise HTTPException(404, 'Unknown sample')
        with store.lock():
            store.reload()
            record = store.states[sid].copy()
        images = {slot: previews.get(sid, slot) for slot in ('pre', 'post1', 'post2')}
        return {'sample': manifest.samples[sid], 'record': record, 'images': images}

    @app.get('/preview/{sid}/{slot}/{name}')
    def preview(sid: str, slot: str, name: str):
        if sid not in manifest.samples or slot not in ('pre', 'post1', 'post2') or name not in ('rgb.png', *(k + '.png' for k in LAYERS)):
            raise HTTPException(404)
        path = previews.directory / sid / slot / name
        if not path.is_file():
            raise HTTPException(404, 'Preview unavailable')
        return FileResponse(path, headers={'Cache-Control': 'no-cache'})

    @app.post('/api/review/{sid}')
    def save(sid: str, payload: dict):
        try:
            result = store.save(sid, payload)
            return {'record': result, 'summary': store.summary(), 'next': store.resume()}
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(422, str(exc)) from exc
        except OSError as exc:
            logging.exception('Durability error')
            raise HTTPException(503, 'Save interrupted; reload to check durable journal before retrying') from exc

    @app.post('/api/shutdown')
    def shutdown():
        if not hasattr(app.state, 'shutdown'):
            raise HTTPException(503, 'Not managed by the local launcher')
        app.state.shutdown()
        return {'stopping': True}
    return app
