import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from roadbook_utils import validate_roadbook, wgs84_to_gcj02  # noqa: E402
from export_excel import safe_excel_value  # noqa: E402


def sample_roadbook():
    base_day = {
        "day": 1,
        "date": "2026-09-25",
        "is_gap_day": False,
        "start": "成都",
        "end": "康定",
        "route_level": "detailed",
        "waypoints": [],
        "route_geometry": [[104.07, 30.67], [103.1, 30.2], [101.96, 30.05]],
        "route_source": {"provider": "高德 MCP", "strategy": "避开高速", "checked_at": "2026-09-10"},
        "start_coords": [104.07, 30.67],
        "end_coords": [101.96, 30.05],
        "distance_km": 260,
        "max_elevation_m": 3000,
        "end_elevation_m": 2560,
        "scenic_spots": [],
        "scenic_routes": [{"name": "测试风景公路", "reason": "测试连续景观"}],
        "fuel_stops": [],
        "alternative_routes": [{"name": "测试备选", "trigger": "主线管制"}],
        "road_closure_risk": "中:测试",
        "weather_typical": "测试",
        "clothing": "测试",
        "schedule": {"am": "出发", "pm": "抵达", "evening": "休息"},
        "meals": {"lunch": "沿途县城", "dinner": "住宿点附近"},
        "crowd_avoidance": {"enabled": True, "plan": "避开午后拥堵"},
        "snow_risk": {"level": "低", "basis": "历史同期测试资料", "checked_at": "2026-09-10", "action": "出发前复核"},
        "plan_b": "原地等待并复核",
        "requires_lodging": True,
    }
    gap_one = {
        **copy.deepcopy(base_day),
        "day": 2,
        "date": None,
        "is_gap_day": True,
        "route_level": "rough",
        "distance_km": 0,
        "requires_lodging": True,
    }
    gap_two = {**copy.deepcopy(gap_one), "day": 3, "requires_lodging": False}
    return {
        "title": "测试</script><script>alert(1)</script>",
        "coordinate_system": "gcj02",
        "crowd_avoidance": {"mode": "avoid", "locations": ["测试地点"]},
        "days": [base_day, gap_one, gap_two],
    }


class CoreTests(unittest.TestCase):
    def test_valid_sample(self):
        self.assertEqual(validate_roadbook(sample_roadbook()), [])

    def test_rejects_missing_coordinate_system(self):
        roadbook = sample_roadbook()
        del roadbook["coordinate_system"]
        self.assertTrue(any("coordinate_system" in item for item in validate_roadbook(roadbook)))

    def test_rejects_high_risk_route_without_safety_fields(self):
        roadbook = sample_roadbook()
        roadbook["days"][0]["technical_difficulty"] = 4
        del roadbook["days"][0]["route_geometry"]
        errors = validate_roadbook(roadbook)
        self.assertTrue(any("route_geometry" in item for item in errors))
        self.assertTrue(any("bailout_points" in item for item in errors))

    def test_rejects_detailed_route_without_real_geometry(self):
        roadbook = sample_roadbook()
        del roadbook["days"][0]["route_geometry"]
        self.assertTrue(any("道路轨迹" in item for item in validate_roadbook(roadbook)))

    def test_rejects_snow_high_without_no_go_conditions(self):
        roadbook = sample_roadbook()
        roadbook["days"][0]["snow_risk"]["level"] = "高"
        self.assertTrue(any("no_go_conditions" in item for item in validate_roadbook(roadbook)))

    def test_wgs84_conversion_changes_sichuan_coordinate(self):
        lng, lat = wgs84_to_gcj02(104.07, 30.67)
        self.assertNotAlmostEqual(lng, 104.07, places=4)
        self.assertNotAlmostEqual(lat, 30.67, places=4)

    def test_excel_formula_text_is_neutralized(self):
        self.assertEqual(safe_excel_value("=1+1"), "'=1+1")
        self.assertEqual(safe_excel_value("普通文本"), "普通文本")

    def test_budget_counts_all_days_and_only_required_nights(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "roadbook.json"
            source.write_text(json.dumps(sample_roadbook(), ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "budget_estimator.py"), str(source), "--tier", "comfort"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("2晚", result.stdout)
            self.assertIn("3天", result.stdout)

    def test_html_neutralizes_script_terminator(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "roadbook.json"
            output = Path(temp_dir) / "roadbook.html"
            source.write_text(json.dumps(sample_roadbook(), ensure_ascii=False), encoding="utf-8")
            subprocess.run(
                [sys.executable, str(SCRIPTS / "export_html.py"), str(source), "-o", str(output)],
                check=True,
                capture_output=True,
                text=True,
            )
            generated = output.read_text(encoding="utf-8")
            self.assertNotIn("</script><script>alert(1)</script>", generated)
            self.assertIn("&lt;/script&gt;", generated)
            self.assertIn("AMapLoader.load", generated)
            self.assertNotIn("leaflet", generated.lower())
            self.assertIn("查看第${d.day}天详情", generated)
            if shutil.which("node"):
                scripts = re.findall(r"<script>(.*?)</script>", generated, re.DOTALL)
                result = subprocess.run(["node", "--check"], input=scripts[-1], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
