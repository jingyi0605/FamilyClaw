from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import unittest


API_SERVER_ROOT = Path(__file__).resolve().parents[1]
HOST_CODE_DIRS = (
    API_SERVER_ROOT / "app",
    API_SERVER_ROOT / "migrations",
)


def _resolve_python_executable() -> str:
    candidate = API_SERVER_ROOT / ".venv" / "Scripts" / "python.exe"
    if candidate.exists():
        return str(candidate)
    return sys.executable


class HostImportWithoutOfficialWeatherTests(unittest.TestCase):
    def _run_import_smoke(self, statement: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(API_SERVER_ROOT)
        return subprocess.run(
            [_resolve_python_executable(), "-c", f"{statement}; print('ok')"],
            cwd=API_SERVER_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_app_db_models_can_import_without_official_weather_on_pythonpath(self) -> None:
        result = self._run_import_smoke("import app.db.models")
        self.assertEqual(0, result.returncode, msg=result.stderr)
        self.assertIn("ok", result.stdout)
        self.assertNotIn("official_weather", result.stderr)

    def test_app_main_can_import_without_official_weather_on_pythonpath(self) -> None:
        result = self._run_import_smoke("import app.main")
        self.assertEqual(0, result.returncode, msg=result.stderr)
        self.assertIn("ok", result.stdout)
        self.assertNotIn("official_weather", result.stderr)

    def test_host_code_has_no_static_imports_of_official_weather(self) -> None:
        forbidden_patterns = ("import official_weather", "from official_weather")
        for base_dir in HOST_CODE_DIRS:
            for file_path in base_dir.rglob("*.py"):
                source = file_path.read_text(encoding="utf-8")
                for pattern in forbidden_patterns:
                    self.assertNotIn(
                        pattern,
                        source,
                        msg=f"{file_path} 仍然包含宿主对 official_weather 的静态依赖。",
                    )


if __name__ == "__main__":
    unittest.main()
