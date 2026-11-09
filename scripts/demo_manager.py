"""Project-owned service/desktop lifecycle. No license bypass and no unscoped process termination."""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from prepare_desktop import current_plugin, extend_ui
from verify_mapgis_host import authorization_failed
from mapgis_runtime import require_administrator, host_environment
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXPOSURE_PRE = ROOT / 'data/processed/exposure-0_41_59/pre.tif'
EXPOSURE_POST = ROOT / 'data/processed/exposure-0_41_59/post-aligned.tif'
MODEL_CONFIGS = {'e4-research': ROOT / 'config/application.e4-research.yaml',
                 'siamunet-smoke': ROOT / 'config/application.smoke.yaml'}
MODEL_CHECKPOINTS = {'e4-research': ROOT / 'models/experiments/germany-louisiana-foundation-initialized-four-class-20260926/best_model.pth',
                     'siamunet-smoke': ROOT / 'models/checkpoints/spacenet8-smoke/smoke_model.pth'}


def install_pending_plugin(root):
    pending = root / 'runtime/pending-plugin/mapgis-floodguard-plugin.jar'
    if not pending.is_file():
        return False
    with zipfile.ZipFile(pending) as archive:
        if archive.testzip() is not None or 'com/zondy/mapgis/floodguard/plugin/FloodInferenceCommand.class' not in archive.namelist():
            raise ValueError('Pending MapGIS plugin JAR is invalid')
    installed = root / 'app/mapgis-flood-desktop/target/mapgis-floodguard-plugin.jar'
    installed.parent.mkdir(parents=True, exist_ok=True)
    temporary = installed.with_name('mapgis-floodguard-plugin.pending.jar')
    try:
        shutil.copy2(pending, temporary)
        os.replace(temporary, installed)
    finally:
        temporary.unlink(missing_ok=True)
    pending.unlink()
    return True
STATE = ROOT / 'runtime/demo-state.json'
LOGS = ROOT / 'logs'


def inspect_process(pid):
    # The PID is converted to int, never interpolated from an arbitrary shell fragment.
    command = f'Get-CimInstance Win32_Process -Filter "ProcessId={int(pid)}" | Select-Object ProcessId,CommandLine,CreationDate | ConvertTo-Json -Compress'
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command], capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError('Cannot safely inspect process identity')
    return json.loads(result.stdout) if result.stdout.strip() else None


def record(process):
    identity = inspect_process(process.pid)
    if not identity:
        raise RuntimeError('Launched process exited before identity was recorded')
    return identity


def terminate_owned(identity):
    current = inspect_process(identity['ProcessId'])
    if current is None:
        return
    if current.get('CreationDate') != identity.get('CreationDate'):
        # The recorded process has exited and Windows reused its PID.  The new
        # process is unrelated, so leave it untouched and treat the owned
        # process as already stopped.
        return
    if current.get('CommandLine') is None:
        raise RuntimeError('Cannot read the recorded process command line. Run stop_demo.ps1 in an administrator PowerShell to verify its identity safely.')
    if current.get('CommandLine') != identity.get('CommandLine'):
        raise RuntimeError('Process command line changed; refusing to terminate unrelated process')
    subprocess.run(['taskkill.exe', '/PID', str(identity['ProcessId']), '/T', '/F'], check=True,
                   stdout=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)


def inspect_project_listener(port):
    command = (
        f'$p=(Get-NetTCPConnection -State Listen -LocalPort {int(port)} -ErrorAction SilentlyContinue '
        '| Select-Object -First 1 -ExpandProperty OwningProcess); '
        'if($p){Get-CimInstance Win32_Process -Filter "ProcessId=$p" '
        '| Select-Object ProcessId,CommandLine,CreationDate | ConvertTo-Json -Compress}'
    )
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command], capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode or not result.stdout.strip():
        return None
    identity = json.loads(result.stdout)
    line = identity.get('CommandLine') or ''
    if str(ROOT).lower() not in line.lower() or 'uvicorn' not in line.lower() or f'--port {int(port)}' not in line:
        return None
    return identity


def stop():
    if not STATE.is_file():
        print('No project-owned demo processes recorded.')
        return
    state = json.loads(STATE.read_text(encoding='utf-8'))
    for identity in reversed(state['processes']):
        terminate_owned(identity)
    listener = inspect_project_listener(state.get('port', 8765))
    if listener:
        terminate_owned(listener)
    state['status'] = 'stopped'
    state['processes'] = []
    STATE.write_text(json.dumps(state, indent=2), encoding='utf-8')
    print('Stopped only recorded, identity-checked demo process trees.')


def host_args(program, ui, port):
    exports = [
        'javafx.base/com.sun.javafx.collections', 'javafx.base/com.sun.javafx.event',
        'javafx.graphics/com.sun.glass.ui', 'javafx.graphics/com.sun.javafx.application',
        'javafx.graphics/com.sun.javafx.scene.input', 'javafx.graphics/com.sun.javafx.util',
        'javafx.controls/com.sun.javafx.scene.control', 'javafx.controls/com.sun.javafx.scene.control.behavior',
        'javafx.controls/com.sun.javafx.scene.control.skin', 'javafx.controls/com.sun.javafx.scene.control.skin.resources',
        'javafx.web/com.sun.javafx.webkit', 'javafx.web/com.sun.webkit']
    args = [str(program / 'java/jre21/bin/desktopjava.exe'), '--add-opens', 'java.base/java.net=ALL-UNNAMED']
    for export in exports:
        args += ['--add-exports', export + '=ALL-UNNAMED']
    args += ['-Dmapgis.console.encoding=GBK', '-Dfloodguard.auto.open=true', '-Dfloodguard.auto.acceptance=true',
             f'-Dfloodguard.pre={EXPOSURE_PRE}',
             f'-Dfloodguard.post={EXPOSURE_POST}',
             f'-Dfloodguard.output={ROOT / "outputs/desktop-acceptance"}',
             f'-Dfloodguard.evidence={ROOT / "runtime/desktop-evidence"}',
             f'-Dfloodguard.ai.url=http://127.0.0.1:{port}/',
             '-cp', '*;lib/*', 'com.zondy.mapgis.ribbonapploader.DesktopLauncher', '--developer', f'--custom-ui={ui}']
    return args


def start(program, port, ai_only, model='e4-research'):
    if not ai_only:
        require_administrator()
        if not (program / 'java/jre21/bin/desktopjava.exe').is_file():
            raise FileNotFoundError('Official MapGIS desktopjava.exe is missing')
        if not EXPOSURE_PRE.is_file() or not EXPOSURE_POST.is_file():
            raise FileNotFoundError('Prepare the matching 0_41_59 image pair with .venv-training/Scripts/python.exe scripts/prepare_exposure_04159.py')
    if STATE.is_file() and json.loads(STATE.read_text(encoding='utf-8')).get('processes'):
        raise RuntimeError('Demo state already exists. Run stop_demo.ps1 to inspect/stop it first.')
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', port)) == 0:
            raise RuntimeError(f'Port {port} already in use; no existing process was changed')
    if not MODEL_CHECKPOINTS[model].is_file():
        raise FileNotFoundError(f'Missing configured {model} model checkpoint: {MODEL_CHECKPOINTS[model]}')
    if not ai_only and install_pending_plugin(ROOT):
        print('Installed the pending rebuilt FloodGuard plugin before MapGIS startup.')
    ui = ROOT / 'runtime/desktop/application.xml'
    if not ai_only:
        plugin = current_plugin(ROOT)
        with zipfile.ZipFile(program / 'mapgis_ribbonapploader.jar') as archive:
            tree = extend_ui(archive.read('application.xml'), program, plugin)
        ui.parent.mkdir(parents=True, exist_ok=True)
        tree.write(ui, encoding='utf-8', xml_declaration=True)
    LOGS.mkdir(exist_ok=True)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    processes = []
    state = {'status': 'starting', 'processes': processes, 'port': port, 'gis_verified': False}
    def persist():
        STATE.write_text(json.dumps(state, indent=2), encoding='utf-8')
    try:
        environment = os.environ.copy()
        environment['FLOODGUARD_CONFIG'] = str(MODEL_CONFIGS[model])
        environment['PYTHONUTF8'] = '1'
        with (LOGS / 'ai-service.log').open('ab') as log:
            ai = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--app-dir', str(ROOT / 'app/ai-service'),
                                   '--host', '127.0.0.1', '--port', str(port)], cwd=ROOT, env=environment,
                                  stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(record(ai)); persist()
        deadline = time.monotonic() + 60
        health = None
        while time.monotonic() < deadline:
            if ai.poll() is not None:
                raise RuntimeError('AI service exited; inspect logs/ai-service.log')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=3) as response:
                    health = json.load(response)
                if health.get('backend') == model and health.get('model_loaded') is True:
                    break
            except OSError:
                pass
            time.sleep(.25)
        if not health or health.get('backend') != model or health.get('model_loaded') is not True:
            raise RuntimeError('AI model readiness failed; inspect logs/ai-service.log')
        if not ai_only:
            log_path = LOGS / 'desktop.log'
            with log_path.open('wb') as log:
                host = subprocess.Popen(host_args(program, ui, port), cwd=program, stdout=log, stderr=log,
                                        env=host_environment(program),
                                        creationflags=subprocess.CREATE_NO_WINDOW)
            processes.append(record(host)); persist()
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if authorization_failed(log_path.read_bytes()):
                    raise RuntimeError('MapGIS authorization failed in this launch; compare logs with the working official developer desktop')
                if host.poll() is not None:
                    raise RuntimeError('MapGIS host exited; inspect logs/desktop.log')
                time.sleep(.25)
        state['status'] = 'ai_only' if ai_only else 'launched_pending_manual_gis_verification'
        state['health'] = health; persist()
        print(json.dumps(state, ensure_ascii=True, indent=2))
    except BaseException:
        for identity in reversed(processes):
            terminate_owned(identity)
        state['status'] = 'failed'; state['processes'] = []; persist()
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'stop'])
    parser.add_argument('--program', type=Path)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--ai-only', action='store_true')
    parser.add_argument('--model', choices=MODEL_CONFIGS, default='e4-research')
    args = parser.parse_args()
    if args.action == 'stop':
        stop()
    else:
        if not 1024 <= args.port <= 65535:
            parser.error('Port must be between 1024 and 65535')
        if not args.ai_only and args.program is None:
            parser.error('--program is required for the desktop')
        start(args.program, args.port, args.ai_only, args.model)


if __name__ == '__main__':
    main()
