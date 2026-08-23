# AI Service API

Base URL: `http://127.0.0.1:8765`

## Endpoints

- `GET /health`：服务、后端和生产 checkpoint 状态。
- `GET /model/info`：版本和五类输出。
- `POST /inference/flood`：提交灾前/灾后影像路径与输出目录，返回异步 `job_id`。
- `GET /jobs/{job_id}`：读取任务进度、结果路径、统计和错误栈。

请求示例：

```json
{
  "pre_image_path": "C:/data/pre.png",
  "post_image_path": "C:/data/post.png",
  "output_dir": "C:/data/output"
}
```

当前后端明确返回 `production_checkpoint_loaded: false` 和 `is_spacenet8_checkpoint: false`，避免把变化检测 fallback 误报为训练完成的 SpaceNet8 模型。
