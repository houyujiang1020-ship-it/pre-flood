"""Match the installed official launcher without changing licensing state."""
import ctypes
import os


def require_administrator():
    if os.name != 'nt' or not ctypes.windll.shell32.IsUserAnAdmin():
        raise RuntimeError(
            'MapGIS official desktop requires an elevated Windows session. '
            'Open PowerShell as administrator using the licensed Windows account, '
            'then rerun the script. No authorization test was attempted.')


def host_environment(program):
    environment = os.environ.copy()
    environment['PATH'] = str(program) + os.pathsep + environment.get('PATH', '')
    return environment
