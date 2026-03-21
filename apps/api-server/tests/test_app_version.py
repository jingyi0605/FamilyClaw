import tempfile
import unittest
from pathlib import Path

from app.core.app_version import DEVELOPMENT_FALLBACK_APP_VERSION, load_repo_app_version


class AppVersionTests(unittest.TestCase):
    def test_load_repo_app_version_reads_root_version_file(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            version_file = Path(tempdir) / "VERSION"
            version_file.write_text("1.2.3\n", encoding="utf-8")

            self.assertEqual("1.2.3", load_repo_app_version(version_file=version_file))

    def test_load_repo_app_version_falls_back_when_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            version_file = Path(tempdir) / "VERSION"

            self.assertEqual(
                DEVELOPMENT_FALLBACK_APP_VERSION,
                load_repo_app_version(version_file=version_file),
            )

    def test_load_repo_app_version_falls_back_when_file_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            version_file = Path(tempdir) / "VERSION"
            version_file.write_text("\n", encoding="utf-8")

            self.assertEqual(
                DEVELOPMENT_FALLBACK_APP_VERSION,
                load_repo_app_version(version_file=version_file),
            )
