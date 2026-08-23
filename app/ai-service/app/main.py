from fastapi import FastAPI, HTTPException, status

from . import __version__
from .inference import MODEL_NAME, MODEL_VERSION
from .jobs import jobs
from .schemas import InferenceRequest, JobResponse

app = FastAPI(title="MapGIS-FloodGuard AI Service", version=__version__)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "model_loaded": True,
        "device": "cpu",
        "backend": MODEL_NAME,
        "production_checkpoint_loaded": False,
    }


@app.get("/model/info")
def model_info() -> dict[str, object]:
    return {
        "name": MODEL_NAME,
        "version": MODEL_VERSION,
        "device": "cpu",
        "classes": [
            "Flood Mask", "Flooded Building", "Non-Flooded Building",
            "Flooded Road", "Non-Flooded Road",
        ],
        "is_spacenet8_checkpoint": False,
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
