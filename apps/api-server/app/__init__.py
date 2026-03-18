"""FamilyClaw API application package."""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_official_plugin_import_path() -> None:
    official_root = Path(__file__).resolve().parents[1] / "data" / "plugins" / "official"
    if not official_root.is_dir():
        return

    resolved = str(official_root.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)


_bootstrap_official_plugin_import_path()

