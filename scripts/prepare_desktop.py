"""Extend the installed host's UI into a project-owned config; never modify its binaries/config/license."""
import argparse
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

PACKAGE = 'com.mapgis.floodguard.mapgis.'


def extend_ui(raw: bytes, program: Path, plugin: Path) -> ET.ElementTree:
    root = ET.fromstring(raw)
    packages = root.find('packages')
    pages = root.find('ribboncontrol/ribbonpages')
    if root.tag != 'application' or packages is None or pages is None:
        raise ValueError('Unsupported MapGIS host application.xml schema')
    for package in packages.findall('package'):
        if package.text and not Path(package.text).is_absolute():
            package.text = str((program / package.text).resolve())
    if not any(p.text == str(plugin.resolve()) for p in packages):
        ET.SubElement(packages, 'package').text = str(plugin.resolve())
    for page in pages.findall('ribbonpage'):
        if page.get('name') == PACKAGE + 'FloodRibbonPage':
            pages.remove(page)
    page = ET.SubElement(pages, 'ribbonpage', name=PACKAGE + 'FloodRibbonPage', text='洪涝应急', isselected='true')
    group = ET.SubElement(page, 'ribbonpagegroup', name=PACKAGE + 'FloodRibbonGroup', text='智能解译')
    ET.SubElement(group, 'item', name=PACKAGE + 'FloodInferenceCommand', caption='洪涝智能识别',
                  hint='选择影像、调用模型并检查结果', type='command', begingroup='false')
    main = root.find('mainapp')
    if main is not None:
        main.set('caption', 'MapGIS-FloodGuard 洪涝应急决策 · 开发验证版')
    return ET.ElementTree(root)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--program', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    plugin = root / 'app/mapgis-flood-desktop/target/mapgis-floodguard-plugin.jar'
    if not plugin.is_file():
        raise FileNotFoundError('Build the MapGIS plugin first')
    with zipfile.ZipFile(args.program / 'mapgis_ribbonapploader.jar') as archive:
        tree = extend_ui(archive.read('application.xml'), args.program, plugin)
    destination = root / 'runtime/desktop/application.xml'
    destination.parent.mkdir(parents=True, exist_ok=True)
    tree.write(destination, encoding='utf-8', xml_declaration=True)
    print(destination)


if __name__ == '__main__':
    main()
