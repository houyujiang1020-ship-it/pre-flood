import threading
import traceback
import uuid

from .inference import predict
from .contract import write_contract
from .schemas import InferenceRequest, JobResponse


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobResponse] = {}
        self._lock = threading.Lock()

    def create(self, request: InferenceRequest) -> JobResponse:
        job_id = uuid.uuid4().hex
        job = JobResponse(job_id=job_id, status="queued", progress=0)
        with self._lock:
            self._jobs[job_id] = job
        threading.Thread(target=self._run, args=(job_id, request), daemon=True).start()
        return job

    def get(self, job_id: str) -> JobResponse | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _run(self, job_id: str, request: InferenceRequest) -> None:
        with self._lock:
            self._jobs[job_id] = JobResponse(job_id=job_id, status="running", progress=10)
        try:
            result = predict(request.pre_image_path, request.post_image_path, request.output_dir / job_id)
            result = write_contract(job_id, request.pre_image_path, request.post_image_path, result)
            completed = JobResponse(job_id=job_id, status="completed", progress=100, result=result)
            with self._lock:
                self._jobs[job_id] = completed
        except Exception as exc:  # surfaced through the job API and logged by the caller
            failed = JobResponse(
                job_id=job_id,
                status="failed",
                progress=100,
                error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
            )
            with self._lock:
                self._jobs[job_id] = failed


jobs = JobStore()
