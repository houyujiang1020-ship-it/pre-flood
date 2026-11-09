"""Create a curated review package; never invent successful GIS evidence."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "MapGIS-FloodGuard-Final"


def copy(source: Path, target: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def main() -> None:
    if DEST.exists():
        raise RuntimeError(f"Destination already exists; refusing to mix an older package: {DEST}")
    for folder in ("application", "plugins", "config", "dataset", "reports", "screenshots"):
        (DEST / folder).mkdir(parents=True, exist_ok=True)
    jar = ROOT / "app/mapgis-flood-desktop/target/mapgis-floodguard-plugin.jar"
    copy(jar, DEST / "application/FloodGuard.jar")
    copy(jar, DEST / "plugins/mapgis-floodguard-plugin.jar")
    for path in (ROOT / "DemoDataset_Final").iterdir():
        if path.is_file():
            copy(path, DEST / "dataset" / path.name)
    for name in ("README.md", "DemoScript.md", "Final_Checklist.md", "Final_Acceptance_Report.md"):
        copy(ROOT / name, DEST / ("reports" if name.startswith("Final_") else "") / name)
    copy(ROOT / "FloodGuard-Release/LICENSE", DEST / "LICENSE")
    for name in ("environment_check.json",):
        source = ROOT / "outputs" / name
        if source.is_file():
            copy(source, DEST / "config" / name)
    for name in ("final_environment_report.json", "validation_result.json"):
        source = ROOT / "submission" / name
        if source.is_file():
            copy(source, DEST / "config" / name)
    # Only copy rendered screenshots from an app-generated manifest with matching hashes.
    screenshot_dirs = sorted((ROOT / "submission/screenshots").glob("demo-*"))
    screenshots_complete = False
    if screenshot_dirs:
        latest = screenshot_dirs[-1]
        manifest = latest / "screenshots-manifest.json"
        if manifest.is_file():
            captures = json.loads(manifest.read_text(encoding="utf-8")).get("captures", {})
            required = {"HOME", "FLOOD", "DAMAGE", "RISK", "ROUTE", "RESOURCES", "REPORT"}
            if required.issubset(captures):
                screenshots_complete = True
                for key in required:
                    item = captures[key]
                    path = latest / item["filename"]
                    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                        screenshots_complete = False
                        break
                if screenshots_complete:
                    for key in required:
                        path = latest / captures[key]["filename"]
                        copy(path, DEST / "screenshots" / path.name)
                    copy(manifest, DEST / "screenshots/screenshots-manifest.json")
    report_file = None
    progress_files = sorted((ROOT / "outputs/demo-runs").glob("demo-*/demo-progress.json"))
    if progress_files:
        progress = json.loads(progress_files[-1].read_text(encoding="utf-8"))
        candidate = Path(progress.get("evidence", {}).get("FINAL_REPORT", ""))
        if progress.get("status") == "COMPLETE" and candidate.is_file():
            report_file = candidate
            copy(candidate, DEST / "reports/FloodGuard_Final_Report.html")
    (DEST / "run.bat").write_text(
        '@echo off\r\n'
        'set "MAPGIS_PROGRAM=C:\\Program Files\\MapGIS 10\\Program"\r\n'
        'if not exist "%MAPGIS_PROGRAM%\\MapGIS Desktop(Ribbon).exe" (echo MapGIS official host is missing. & exit /b 2)\r\n'
        'echo Ensure this plugin is registered with the official MapGIS plugin manager and a licensed administrator session is active.\r\n'
        'start "" "%MAPGIS_PROGRAM%\\MapGIS Desktop(Ribbon).exe"\r\n', encoding="ascii")
    files = []
    for path in sorted(DEST.rglob("*")):
        if path.is_file() and path.name != "release-manifest.json":
            files.append({"path": path.relative_to(DEST).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                          "bytes": path.stat().st_size})
    environment = json.loads((ROOT / "submission/final_environment_report.json").read_text(encoding="utf-8"))
    validation = json.loads((ROOT / "submission/validation_result.json").read_text(encoding="utf-8"))
    ready = (environment.get("all_pass") is True and screenshots_complete and report_file is not None
             and validation.get("final_acceptance") == "PASS")
    (DEST / "release-manifest.json").write_text(json.dumps({"schema_version": 1,
            "competition_acceptance_passed": ready, "screenshots_complete": screenshots_complete,
            "files": files}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"package={DEST} files={len(files)} submission_ready={ready}")


if __name__ == "__main__":
    main()
