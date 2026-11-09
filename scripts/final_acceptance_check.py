"""Stage 8 evidence audit and submission staging. Never turns missing evidence into PASS."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "FloodGuard_Final_Submission"
EVIDENCE = ROOT / "Final_Evidence"
IMAGE_NAMES = ["01_main.png", "01a_map_data.png", "02_flood.png", "03_damage.png", "04_risk.png",
               "05_blockroad.png", "06_route.png", "07_resource.png", "08_report.png"]


def read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def latest(folder: Path, pattern: str) -> Path | None:
    paths = list(folder.glob(pattern)) if folder.exists() else []
    return max(paths, key=lambda p: p.stat().st_mtime) if paths else None


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def screenshot_audit() -> tuple[bool, str, Path | None]:
    folder = latest(EVIDENCE, "demo-*")
    if folder is None:
        return False, "尚无官方宿主运行截图", None
    captures = read(folder / "screenshots-manifest.json").get("captures", {})
    for name in IMAGE_NAMES:
        path = folder / name
        records = [x for x in captures.values() if isinstance(x, dict) and x.get("filename") == name]
        if not path.is_file() or len(records) != 1:
            return False, f"缺少截图或元数据：{name}", folder
        record = records[0]
        if sha(path) != record.get("sha256") or not all(record.get(k) for k in ("captured_at", "function", "operation_step")):
            return False, f"截图哈希或操作记录不完整：{name}", folder
    if read(folder / "visual_review.json").get("approved") is not True:
        return False, "要求的八张截图及地图数据补充图、元数据完整，尚缺人工地图内容视觉复核", folder
    return True, "要求的八张截图、地图数据补充图及人工视觉复核完整", folder


def official_case() -> tuple[bool, str, Path | None]:
    manifest = ROOT / "OfficialDemoScenario" / "official_scenario.json"
    data = read(manifest)
    if data.get("ready") is not True or data.get("data_type") not in ("REAL", "FORMALLY_PREPARED"):
        return False, "尚无已核验正式案例清单", manifest
    sources = data.get("sources", {})
    names = {"flood": "flood_prediction.json", "resources": "resources.json"}
    for key in ("flood", "buildings", "roads", "population", "resources"):
        source = sources.get(key, {})
        path = Path(str(source.get("path") or "missing"))
        if not path.is_absolute():
            path = manifest.parent / path
        valid_name = path.name.lower() == names[key] if key in names else path.name.lower().startswith(key + ".")
        if not valid_name or not path.is_file() or len(source.get("sha256", "")) != 64 or not source.get("provenance"):
            return False, f"正式案例缺少有效来源：{key}", manifest
        if sha(path).lower() != source["sha256"].lower():
            return False, f"正式案例文件哈希不符：{key}", manifest
    scenario = data.get("scenario", {})
    for field in ("administrativeUrl", "populationUrl", "floodExtentUrl", "networkUrl", "sourceRoadsUrl"):
        if not scenario.get(field, "").startswith("gdbp://"):
            return False, f"正式案例缺少 MapGIS 图层：{field}", manifest
    if scenario.get("simulated") is not False:
        return False, "正式案例仍标记为模拟数据", manifest
    return True, "正式案例源文件、哈希与 MapGIS 图层引用已核对", manifest


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()
    host_log = ROOT / "docs" / "stage8-host-20261004.log"
    startup_path = ROOT / "startup_log.json"
    if not startup_path.exists():
        host_text = host_log.read_text(encoding="utf-8", errors="replace") if host_log.exists() else ""
        write(startup_path, {"checked_at": now, "startup_time": None, "sdk": "UNVERIFIED",
                             "plugin": "UNVERIFIED", "map": "UNVERIFIED",
                             "status": "HOST_NOT_STARTED", "exceptions": ["需要管理员会话；尚未执行授权测试"]
                             if "requires an elevated Windows session" in host_text else ["尚无官方宿主启动记录"],
                             "source": str(host_log) if host_log.exists() else None})
    startup = read(startup_path)
    env = read(ROOT / "submission" / "final_environment_report.json")
    valid_case, case_note, case_path = official_case()
    valid_images, image_note, image_folder = screenshot_audit()
    run_path = latest(ROOT / "outputs" / "demo-runs", "demo-*/demo-progress.json")
    run = read(run_path) if run_path else {}
    validation_path = ROOT / "final_validation.json"
    validation = read(validation_path)
    if not validation:
        source = read(ROOT / "submission" / "validation_result.json")
        validation = {"checked_at": now, "final_acceptance": "NOT_VERIFIED",
                      "source": str(ROOT / "submission" / "validation_result.json"),
                      "checks": source.get("checks", {}), "metrics": source.get("metrics", {}),
                      "reason": "尚无正式案例的 MapGIS 宿主灾损、风险、路线结果"}
        write(validation_path, validation)
    checks = {
        "mapgis_license": env.get("license") == "PASS" and env.get("all_pass") is True,
        "mapcontrol": env.get("mapcontrol") == "PASS" and startup.get("map") == "WINDOW_SHOWN",
        "map_rendered": valid_images,
        "official_data": valid_case,
        "flood_analysis": run.get("status") == "COMPLETE" and "AI_DETECTION" in run.get("evidence", {}),
        "risk_analysis": validation.get("checks", {}).get("risk_arithmetic") == "PASS" and valid_case,
        "route_planning": validation.get("checks", {}).get("route_arithmetic") == "PASS" and valid_case,
        "resource_dispatch": "RESOURCE_MATCHING" in run.get("evidence", {}) and valid_case,
        "report_generated": "FINAL_REPORT" in run.get("evidence", {}) and valid_case,
        "screenshots_complete": valid_images,
        "submission_sources": (ROOT / "app/mapgis-flood-desktop/target/mapgis-floodguard-plugin.jar").is_file()
                              and (ROOT / "MapGIS-FloodGuard-Final/application/FloodGuard.jar").is_file(),
    }
    status = "FINAL READY" if all(checks.values()) and validation.get("final_acceptance") == "VERIFIED" else "NOT_READY"
    audit = {"checked_at": now, "status": status, "checks": checks,
             "notes": {"official_case": case_note, "screenshots": image_note,
                       "host": "宿主未启动；管理员权限预检停止，未测试许可证" if startup.get("status") == "HOST_NOT_STARTED" else "查看 startup_log.json"},
             "evidence": {"startup": str(startup_path), "environment": str(ROOT / "submission" / "final_environment_report.json"),
                          "scenario": str(case_path), "demo": str(run_path) if run_path else None,
                          "screenshots": str(image_folder) if image_folder else None,
                          "validation": str(validation_path)}}
    write(ROOT / "FinalAcceptanceCheck.json", audit)
    lines = ["# MapGIS-FloodGuard 第八阶段最终验收报告", "", f"当前状态：**{status}**。", "",
             "## 1. 项目简介", "面向城市洪涝灾害的智能分析与应急决策桌面系统。", "",
             "## 2. 系统架构", "Java + MapGIS SDK 桌面工作台经 FastAPI/PyTorch 接入 AI 检测，串联灾损、风险、路网与资源调度。", "",
             "## 3. MapGIS 二次开发内容", "地图使用官方 MapControl；空间对象、叠加、网络分析和专题显示由 MapGIS SDK 提供。", "",
             "## 4. AI 模块", "AI 对象预测通过 flood_prediction.json 进入灾损分析。正式案例推理或回放仍需在官方宿主记录。", "",
             "## 5. GIS 空间分析与风险评估", "风险公式为 0.4 建筑 + 0.3 人口 + 0.2 道路 + 0.1 资源距离。人口项须使用真实洪水面和 MapGIS 人口格网叠加。", "",
             "## 6. 应急决策流程", "道路封闭状态进入 MapGIS 原生路网阻抗，再计算绕行路线和资源匹配。", "",
             "## 7. 真实运行环境", f"启动记录：`{startup_path.name}`；环境报告：`submission/final_environment_report.json`。",
             "本次官方宿主探针在管理员权限预检处停止，未进入许可证、MapControl 与地图渲染验证。", "",
             "## 8. 正式案例说明", case_note, "", "## 9. 测试与指标结果",
             "本轮 SDK 插件构建成功；静态注册探针通过。正式案例指标需要宿主实际运行后由 FinalValidator 复核。", "",
             "| 验收项 | 状态 |", "|---|---|"]
    lines.extend(f"| {key} | {'通过' if value else '未核验/未通过'} |" for key, value in checks.items())
    lines += ["", "## 10. 运行截图", image_note, "", "## 11. 问题记录与后续验收",
              "1. 在管理员权限且有授权的 MapGIS 宿主运行插件，留存许可证状态与真实地图渲染记录。",
              "2. 补齐 `OfficialDemoScenario/official_scenario.json` 及全部正式数据的来源、SHA-256 和 MapGIS 原生图层 URL。",
              "3. 执行完整演练并人工检查八张必需截图及地图数据补充图、人口叠加结果、路线和报告；更新独立复核结果。", ""]
    (ROOT / "Final_Acceptance_Report.md").write_text("\n".join(lines), encoding="utf-8")
    # Stage a reviewable package without representing absent data or screenshots as completed evidence.
    for name in ("app", "plugin", "data", "screenshots", "reports", "logs"):
        (OUT / name).mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    copies = [
        (ROOT / "app/mapgis-flood-desktop/target/mapgis-floodguard-plugin.jar", OUT / "plugin/mapgis-floodguard-plugin.jar"),
        (ROOT / "MapGIS-FloodGuard-Final/application/FloodGuard.jar", OUT / "app/FloodGuard.jar"),
        (ROOT / "Final_Acceptance_Report.md", OUT / "reports/Final_Acceptance_Report.md"),
        (ROOT / "final_validation.json", OUT / "reports/final_validation.json"),
        (ROOT / "FinalAcceptanceCheck.json", OUT / "reports/FinalAcceptanceCheck.json"),
        (startup_path, OUT / "logs/startup_log.json"),
        (host_log, OUT / "logs/stage8-host-20261004.log"),
        (ROOT / "docs/stage8-build-20261004.log", OUT / "logs/stage8-build-20261004.log"),
    ]
    if valid_case and case_path:
        copies.append((case_path, OUT / "data/official_scenario.json"))
    if valid_images and image_folder:
        copies.extend((p, OUT / "screenshots" / p.name) for p in image_folder.iterdir() if p.is_file())
    manifest = []
    for source, target in copies:
        if source.is_file():
            shutil.copy2(source, target)
            manifest.append({"path": target.relative_to(OUT).as_posix(), "sha256": sha(target)})
    write(OUT / "submission-manifest.json", {"status": status, "created_at": now, "files": manifest})
    (OUT / "README.md").write_text("# MapGIS-FloodGuard 正式提交暂存包\n\n当前状态：" + status +
                                     "。查看 reports/Final_Acceptance_Report.md 和 reports/FinalAcceptanceCheck.json。\n"
                                     "data/ 与 screenshots/ 只有真实验收证据通过后才会填充。\n", encoding="utf-8")
    (OUT / "Demo说明.md").write_text("# 比赛演示\n\n在授权 MapGIS 宿主加载 OfficialDemoScenario 的正式清单，"
                                    "点击“加载真实案例”和“比赛演示”，逐步核查洪水、灾损、风险、封路、路线、资源及报告。"
                                    "完整演练后复核 Final_Evidence 八张必需截图、地图数据补充图及各阶段日志。\n", encoding="utf-8")
    print(f"status={status} checks={sum(checks.values())}/{len(checks)} package={OUT}")


if __name__ == "__main__":
    main()
