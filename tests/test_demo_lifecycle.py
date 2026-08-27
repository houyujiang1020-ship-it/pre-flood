import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

scripts = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location('demo_manager', scripts / 'demo_manager.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def test_refuses_reused_pid():
    import pytest
    recorded = {'ProcessId': 123, 'CreationDate': 'old', 'CommandLine': 'owned'}
    with patch.object(demo, 'inspect_process', return_value={**recorded, 'CreationDate': 'new'}), \
         patch.object(demo.subprocess, 'run') as kill:
        with pytest.raises(RuntimeError, match='identity changed'):
            demo.terminate_owned(recorded)
        kill.assert_not_called()


def test_missing_process_is_not_killed():
    with patch.object(demo, 'inspect_process', return_value=None), patch.object(demo.subprocess, 'run') as kill:
        demo.terminate_owned({'ProcessId': 123})
        kill.assert_not_called()


def test_host_uses_official_developer_and_custom_ui_arguments(tmp_path):
    args = demo.host_args(tmp_path, tmp_path / '应用.xml', 18766)
    assert '--developer' in args
    assert f'--custom-ui={tmp_path / "应用.xml"}' in args
    assert 'com.zondy.mapgis.ribbonapploader.DesktopLauncher' in args
    assert not any('disable-native' in arg for arg in args)
