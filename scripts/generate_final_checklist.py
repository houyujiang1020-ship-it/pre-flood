"""Produce submission checklists from persisted evidence, never from claimed progress."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / "submission"
REQUIRED_IMAGES = (
    "01_main_window.png", "02_flood_layer.png", "03_damage_analysis.png",
    "04_risk_analysis.png", "05_route_planning.png", "06_resource_dispatch.png",
    "07_final_report.png",
)


def read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def latest(directory: Path, pattern: str) -> Path | None:
    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime if p.exists() else 0)
    return files[-1] if files else None


def valid_screenshots() -> tuple[bool, str]:
    folder = latest(SUBMISSION / "screenshots", "demo-*")
    if folder is None or not folder.is_dir():
        return False, "尚无真实 MapGIS 宿主截图"
    manifest = read(folder / "screenshots-manifest.json").get("captures", {})
    for filename in REQUIRED_IMAGES:
        path = folder / filename
        if not path.is_file():
            return False, f"缺少 {filename}"
        matches = [x for x in manifest.values() if x.get("filename") == filename]
        if len(matches) != 1 or hashlib.sha256(path.read_bytes()).hexdigest() != matches[0].get("sha256"):
            return False, f"截图清单与文件不一致：{filename}"
    return True, f"7 张文件及哈希齐备：{folder}；地图内容仍需人工查看"


def release_valid() -> bool:
    folder = ROOT / "MapGIS-FloodGuard-Final"
    data = read(folder / "release-manifest.json")
    files = data.get("files", [])
    if not files:
        return False
    for item in files:
        path = folder / item.get("path", "")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item.get("sha256"):
            return False
    return True


def main() -> None:
    SUBMISSION.mkdir(parents=True, exist_ok=True)
    environment = read(SUBMISSION / "final_environment_report.json")
    validation = read(SUBMISSION / "validation_result.json")
    run_path = latest(ROOT / "outputs" / "demo-runs", "demo-*/demo-progress.json")
    run = read(run_path) if run_path else {}
    evidence = run.get("evidence", {})
    screenshots, screenshot_note = valid_screenshots()
    report_path = Path(evidence.get("FINAL_REPORT", "")) if evidence.get("FINAL_REPORT") else None
    checks = [
        ("MapGIS正常启动", environment.get("all_pass") is True, "SDK、DLL、许可证、MapControl 和插件均需真实 PASS"),
        ("地图正常渲染", False, "截图即使齐备，仍须人工确认地图内容与坐标；" + screenshot_note),
        ("数据加载成功", run.get("status") == "COMPLETE" and "LOAD_DATA" in evidence, "完整演练账本与数据加载证据"),
        ("洪水专题显示", screenshots and "AI_DETECTION" in evidence, "洪水截图及演练账本"),
        ("风险计算成功", validation.get("checks", {}).get("risk_arithmetic") == "PASS", "风险报告内部计算一致性"),
        ("路径规划成功", validation.get("checks", {}).get("route_arithmetic") == "PASS", "原生路线报告内部计算一致性"),
        ("资源调度成功", "RESOURCE_MATCHING" in evidence and run.get("status") == "COMPLETE", "资源推荐结果证据"),
        ("报告生成成功", bool(report_path and report_path.is_file()), "完整演练生成的 HTML 文件"),
        ("截图完整", screenshots, screenshot_note),
        ("发布包完整", release_valid(), "发布清单全部 SHA-256 一致；不代表比赛验收通过"),
    ]
    lines = ["# MapGIS-FloodGuard 最终检查清单", "", "此清单由本机证据自动生成；未采集或尚需人工视觉复核的项目保持未勾选。", ""]
    for label, passed, note in checks:
        lines.append(f"- [{'x' if passed else ' '}] {label} — {note}")
    (ROOT / "Final_Checklist.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    build_log = ROOT / "docs" / "final-stage-build-20261004.log"
    build_text = build_log.read_text(encoding="utf-8", errors="replace") if build_log.is_file() else ""
    stage7_log = ROOT / "docs" / "stage7-build-20261004.log"
    if stage7_log.is_file():
        build_text = stage7_log.read_text(encoding="utf-8", errors="replace")
    counts = re.findall(r"Tests run: (\d+), Failures: 0, Errors: 0, Skipped: 0", build_text)
    tests = (f"构建通过，{counts[-1]} 项 JUnit 测试通过，SDK 注册探针通过"
             if counts and "BUILD SUCCESS" in build_text and "PASS: installed SDK" in build_text
             else "当前构建证据不足")
    all_pass = all(flag for _, flag, _ in checks)
    sections = [
        "# MapGIS-FloodGuard 最终验收报告", "",
        f"验收结论：**{'全部自动检查通过，仍须比赛方复核' if all_pass else '尚未完成真实环境最终验收'}**。", "",
        "## 1. 项目简介", "面向洪涝场景的遥感感知、MapGIS 灾损与风险分析、原生路网应急决策桌面系统。", "",
        "## 2. 系统架构", "FastAPI/PyTorch 提供检测；Java + MapGIS SDK 承担地图、空间叠加、专题图、网络与空间资源。", "",
        "## 3. MapGIS 二次开发内容", "MapControl、HDF 要素类、GeometryOperator、NetCls/NetAnalyse、资源点图层与插件命令。", "",
        "## 4. AI 模块", "当前完整演练使用明确标注的对象预测回放；实时掩膜到对象预测的桥接尚未闭合。", "",
        "## 5. GIS 空间分析", "建筑/道路对象分类、人口格网与洪水面叠加；缺真实洪水面时人口风险不计算。", "",
        "## 6. 风险评估方法", "0.4 建筑 + 0.3 人口 + 0.2 道路 + 0.1 资源距离；资源距离由行政区字段提供。", "",
        "## 7. 应急决策流程", "道路状态映射到 MapGIS 原生边，计算封路前后路线并推荐可达资源。", "",
        "## 8. 测试结果", tests + "。环境完整性与宿主演练见下表。", "",
        "| 项目 | 结果 |", "|---|---|",
    ]
    sections.extend(f"| {label} | {'通过' if passed else '未通过或未核验'} |" for label, passed, _ in checks)
    sections += ["", "## 9. 运行截图", screenshot_note + "。截图文件存在也不能代替人工视觉检查。", "",
                 "## 10. 不足与改进", "当前会话尚无管理员权限下的官方 MapGIS 宿主运行、许可证验证、真实案例原生转换与独立空间复核。",
                 "下一步需在授权宿主完成全流程、保存七张真实截图和报告，并由人员核对地图内容及指标。", ""]
    (ROOT / "Final_Acceptance_Report.md").write_text("\n".join(sections), encoding="utf-8")
    print(f"checked={sum(passed for _, passed, _ in checks)}/{len(checks)} screenshots={screenshots} all_pass={all_pass}")


if __name__ == "__main__":
    main()
