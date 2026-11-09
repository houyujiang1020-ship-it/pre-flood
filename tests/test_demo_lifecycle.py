import importlib.util
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

scripts = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location('demo_manager', scripts / 'demo_manager.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def test_skips_reused_pid_without_killing_new_process():
    recorded = {'ProcessId': 123, 'CreationDate': 'old', 'CommandLine': 'owned'}
    with patch.object(demo, 'inspect_process', return_value={**recorded, 'CreationDate': 'new'}), \
         patch.object(demo.subprocess, 'run') as kill:
        demo.terminate_owned(recorded)
        kill.assert_not_called()


def test_refuses_command_change_for_same_process_identity():
    import pytest
    recorded = {'ProcessId': 123, 'CreationDate': 'same', 'CommandLine': 'owned'}
    with patch.object(demo, 'inspect_process', return_value={**recorded, 'CommandLine': 'foreign'}), \
         patch.object(demo.subprocess, 'run') as kill:
        with pytest.raises(RuntimeError, match='command line changed'):
            demo.terminate_owned(recorded)
        kill.assert_not_called()


def test_unreadable_command_line_requests_elevation_without_killing():
    import pytest
    recorded = {'ProcessId': 123, 'CreationDate': 'same', 'CommandLine': 'owned'}
    with patch.object(demo, 'inspect_process', return_value={**recorded, 'CommandLine': None}), \
         patch.object(demo.subprocess, 'run') as kill:
        with pytest.raises(RuntimeError, match='administrator PowerShell'):
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
    assert args[0] == str(tmp_path / 'java/jre21/bin/desktopjava.exe')
    assert '-Dmapgis.console.encoding=GBK' in args
    assert '-Dfile.encoding=UTF-8' not in args
    assert f'-Dfloodguard.pre={demo.EXPOSURE_PRE}' in args
    assert f'-Dfloodguard.post={demo.EXPOSURE_POST}' in args
    assert not any('geotiff-test-0_36_68' in arg for arg in args)


def test_non_elevated_start_refuses_before_side_effects(tmp_path):
    import pytest
    with patch.object(demo, 'require_administrator', side_effect=RuntimeError('elevated')), \
         patch.object(demo.subprocess, 'Popen') as launch:
        with pytest.raises(RuntimeError, match='elevated'):
            demo.start(tmp_path, 18766, False)
        launch.assert_not_called()


def test_host_environment_prepends_program_without_mutating_parent(tmp_path):
    import os
    with patch.dict(os.environ, {'PATH': 'original-path'}):
        result = demo.host_environment(tmp_path)
        assert result['PATH'] == str(tmp_path) + os.pathsep + 'original-path'
        assert os.environ['PATH'] == 'original-path'


def test_installs_pending_plugin_only_after_validating_archive(tmp_path):
    pending = tmp_path / 'runtime/pending-plugin/mapgis-floodguard-plugin.jar'
    pending.parent.mkdir(parents=True)
    with zipfile.ZipFile(pending, 'w') as archive:
        archive.writestr('com/zondy/mapgis/floodguard/plugin/FloodInferenceCommand.class', b'new')
    installed = tmp_path / 'app/mapgis-flood-desktop/target/mapgis-floodguard-plugin.jar'
    installed.parent.mkdir(parents=True)
    installed.write_bytes(b'old')
    assert demo.install_pending_plugin(tmp_path)
    assert installed.read_bytes().startswith(b'PK')
    assert not pending.exists()
    assert not demo.install_pending_plugin(tmp_path)
