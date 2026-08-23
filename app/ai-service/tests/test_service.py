import time
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


def _images(root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    pre = np.full((64, 64, 3), 210, dtype=np.uint8)
    post = pre.copy()
    post[16:48, 12:52] = np.array([30, 60, 170], dtype=np.uint8)
    pre_path = root / "灾前.png"
    post_path = root / "灾后.png"
    Image.fromarray(pre).save(pre_path)
    Image.fromarray(post).save(post_path)
    return pre_path, post_path


def test_health_and_model_info() -> None:
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["production_checkpoint_loaded"] is False
    assert client.get("/model/info").status_code == 200


def test_inference_job_with_chinese_paths(tmp_path: Path) -> None:
    client = TestClient(app)
    pre, post = _images(tmp_path / "中文样本")
    output = tmp_path / "中文输出"
    response = client.post("/inference/flood", json={
        "pre_image_path": str(pre),
        "post_image_path": str(post),
        "output_dir": str(output),
    })
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    for _ in range(100):
        payload = client.get(f"/jobs/{job_id}").json()
        if payload["status"] in {"completed", "failed"}:
            break
        time.sleep(0.02)
    assert payload["status"] == "completed", payload.get("error")
    result = payload["result"]
    assert Path(result["mask_path"]).is_file()
    assert Path(result["preview_path"]).is_file()
    assert result["statistics"]["flood_pixels"] > 0


def test_rejects_missing_input(tmp_path: Path) -> None:
    client = TestClient(app)
    response = client.post("/inference/flood", json={
        "pre_image_path": str(tmp_path / "missing-pre.png"),
        "post_image_path": str(tmp_path / "missing-post.png"),
        "output_dir": str(tmp_path / "out"),
    })
    assert response.status_code == 422
