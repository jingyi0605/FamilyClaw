from __future__ import annotations

from pathlib import Path
import unittest


API_SERVER_ROOT = Path(__file__).resolve().parents[1]
DEVICE_SERVICE_PATH = API_SERVER_ROOT / "app" / "modules" / "device" / "service.py"


class DeviceServiceNoWeatherSpecialCaseTests(unittest.TestCase):
    def test_device_service_does_not_keep_weather_specific_branches(self) -> None:
        source = DEVICE_SERVICE_PATH.read_text(encoding="utf-8")
        self.assertNotIn('binding.platform == "weather"', source)
        self.assertNotIn("weather_entity_normalizer", source)
        self.assertNotIn("normalize_weather_capabilities_payload", source)


if __name__ == "__main__":
    unittest.main()
