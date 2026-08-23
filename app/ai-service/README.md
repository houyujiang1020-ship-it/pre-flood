# AI Service

```powershell
Set-Location -LiteralPath 'C:\Users\33076\Desktop\高级开发\app\ai-service'
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

CLI:

```powershell
..\..\.venv\Scripts\python.exe -m app.cli predict --pre PRE.png --post POST.png --output OUTPUT_DIR
```

当前 `spectral-change-fallback` 后端执行真实的影像变化计算，但不是训练好的 SpaceNet8 checkpoint。API 会明确返回该状态，防止演示时误报模型能力。
