import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path

spec = importlib.util.spec_from_file_location('prepare_desktop', Path(__file__).resolve().parents[1] / 'scripts/prepare_desktop.py')
desktop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desktop)


def test_preserves_existing_ui_and_adds_plugin_once(tmp_path):
    raw = b'<application><packages><package>plugin/base.jar</package></packages><mainapp caption="Original"/><ribboncontrol><ribbonpages><ribbonpage name="base"/></ribbonpages></ribboncontrol></application>'
    plugin = tmp_path / '插件.jar'
    first = desktop.extend_ui(raw, tmp_path, plugin)
    second = desktop.extend_ui(ET.tostring(first.getroot()), tmp_path, plugin)
    assert len(second.findall('packages/package')) == 2
    assert len(second.findall('ribboncontrol/ribbonpages/ribbonpage')) == 2
    assert second.find('ribboncontrol/ribbonpages/ribbonpage').get('name') == 'base'
    assert second.find('packages/package').text == str((tmp_path / 'plugin/base.jar').resolve())
    page = second.findall('ribboncontrol/ribbonpages/ribbonpage')[1]
    assert page.get('name') == 'com.zondy.mapgis.floodguard.plugin.FloodRibbonPage'
    assert page.find('ribbonpagegroup/item').get('name') == 'com.zondy.mapgis.floodguard.plugin.FloodInferenceCommand'


def test_migrates_old_unregistered_page(tmp_path):
    raw = b'<application><packages/><ribboncontrol><ribbonpages><ribbonpage name="com.mapgis.floodguard.mapgis.FloodRibbonPage"/></ribbonpages></ribboncontrol></application>'
    tree = desktop.extend_ui(raw, tmp_path, tmp_path / 'plugin.jar')
    pages = tree.findall('ribboncontrol/ribbonpages/ribbonpage')
    assert len(pages) == 1
    assert pages[0].get('name') == desktop.PACKAGE + 'FloodRibbonPage'


def test_rejects_unrecognized_host_config(tmp_path):
    import pytest
    with pytest.raises(ValueError, match='schema'):
        desktop.extend_ui(b'<different/>', tmp_path, tmp_path / 'plugin.jar')


def test_current_plugin_does_not_fall_back_to_stale_runtime_copy(tmp_path):
    import pytest
    stale = tmp_path / 'runtime/plugin-build-next/mapgis-floodguard-plugin.jar'
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b'old')
    with pytest.raises(FileNotFoundError, match='current MapGIS plugin'):
        desktop.current_plugin(tmp_path)
    current = tmp_path / 'app/mapgis-flood-desktop/target/mapgis-floodguard-plugin.jar'
    current.parent.mkdir(parents=True)
    current.write_bytes(b'new')
    assert desktop.current_plugin(tmp_path) == current
