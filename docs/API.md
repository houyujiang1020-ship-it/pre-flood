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

两个后端均返回 production_checkpoint_loaded=false。默认fallback的is_spacenet8_checkpoint=false；显式选择siamunet-smoke时为true（官方架构自行训练的烟测权重，不是官方预训练权重），device按实际CUDA/CPU返回。模型/配置不可用时health返回503，不静默回退。模型结果没有经验证的生产精度。

掩膜为像素输出；烟测后端flood_mask只是受淹建筑/道路并集，不代表完整水面。两期影像须预先在MapGIS对齐空间网格；尺寸不等时任务失败。job状态内存保存，服务重启后不可恢复。API默认只绑定localhost，不适合直接暴露公网。
