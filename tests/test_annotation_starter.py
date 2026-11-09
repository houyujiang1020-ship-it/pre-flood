"""The annotation gate must not treat unfinished or null-status labels as ready."""
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/annotation_starter.py"
SPEC = importlib.util.spec_from_file_location("annotation_starter", SCRIPT)
starter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(starter)


class AnnotationStarterTests(unittest.TestCase):
    def test_pending_and_null_flood_are_not_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            old = starter.DEST
            starter.DEST = Path(temp)
            try:
                folder = starter.DEST / "01_test"
                folder.mkdir()
                starter.write_json(starter.DEST / "manifest.json", {
                    "tiles": [{"tile": "test", "folder": "01_test", "files": {}}]})
                feature = {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [
                    [[0, 0], [1, 0], [1, 1], [0, 0]]]},
                    "properties": {"id": "b1", "building": "yes", "flooded": None,
                                   "annotation_status": "pending"}}
                starter.write_json(folder / "working_buildings.geojson", {
                    "type": "FeatureCollection", "features": [feature]})
                starter.write_json(folder / "working_roads.geojson", {
                    "type": "FeatureCollection", "features": []})
                with contextlib.redirect_stdout(io.StringIO()):
                    starter.validate()
                result = json.loads((starter.DEST / "validation.json").read_text())
                self.assertEqual("in_progress", result["status"])
                self.assertEqual(1, result["remaining_features"])
                feature["properties"]["annotation_status"] = "verified"
                starter.write_json(folder / "working_buildings.geojson", {
                    "type": "FeatureCollection", "features": [feature]})
                with contextlib.redirect_stdout(io.StringIO()):
                    starter.validate()
                result = json.loads((starter.DEST / "validation.json").read_text())
                self.assertEqual("in_progress", result["status"])
                self.assertTrue(any("flooded=yes/no" in issue for issue in result["issues"]))
                feature["properties"]["flooded"] = "no"
                starter.write_json(folder / "working_buildings.geojson", {
                    "type": "FeatureCollection", "features": [feature]})
                with contextlib.redirect_stdout(io.StringIO()):
                    starter.validate()
                result = json.loads((starter.DEST / "validation.json").read_text())
                self.assertEqual("ready_for_human_final_review", result["status"])
            finally:
                starter.DEST = old


if __name__ == "__main__":
    unittest.main()
