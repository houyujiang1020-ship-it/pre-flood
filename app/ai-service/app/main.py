from fastapi import FastAPI, HTTPException, status

from . import __version__
from .inference import MODEL_NAME, MODEL_VERSION
from .jobs import jobs
from .schemas import InferenceRequest, JobResponse
from .settings import settings

app = FastAPI(title="MapGIS-FloodGuard AI Service", version=__version__)


@app.get("/health")
def health() -> dict[str, object]:
    try:
        config = settings()
        device = 'cpu'
        if config.backend == 'siamunet-smoke':
            from .torch_backend import model_state
            _, device = model_state()
    except Exception as error:
        raise HTTPException(status_code=503, detail=f'Model unavailable: {type(error).__name__}: {error}') from error
    return {
        "status": "ok",
        "model_loaded": True,
        "device": device,
        "backend": config.backend,
        "production_checkpoint_loaded": False,
    }


@app.get("/model/info")
def model_info() -> dict[str, object]:
    state = health()
    return {
        "name": state['backend'],
        "version": MODEL_VERSION,
        "device": state['device'],
        "classes": [
            "Flood Mask", "Flooded Building", "Non-Flooded Building",
            "Flooded Road", "Non-Flooded Road",
        ],
        "is_spacenet8_checkpoint": state['backend'] == 'siamunet-smoke',
        "production_ready": False,
        "warning": "Smoke/fallback backend only; not validated for operational decisions.",
    }


@app.post("/inference/flood", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_inference(request: InferenceRequest) -> JobResponse:
    return jobs.create(request)


@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
