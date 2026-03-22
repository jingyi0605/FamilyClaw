from __future__ import annotations

import importlib
import sys
from pathlib import Path

from app.modules.plugin.import_path import plugin_runtime_import_path


def test_plugin_runtime_import_path_supports_flattened_package_root(tmp_path: Path) -> None:
    plugin_root = tmp_path / "0.1.1"
    plugin_root.mkdir()
    (plugin_root / "__init__.py").write_text("", encoding="utf-8")
    (plugin_root / "integration.py").write_text("VALUE = 'integration-ok'\n", encoding="utf-8")
    (plugin_root / "models.py").write_text("VALUE = 'model-ok'\n", encoding="utf-8")

    with plugin_runtime_import_path(plugin_root, package_names=["fc_flat_demo"]):
        integration_module = importlib.import_module("fc_flat_demo.integration")
        models_module = importlib.import_module("fc_flat_demo.models")

    assert integration_module.VALUE == "integration-ok"
    assert models_module.VALUE == "model-ok"

    sys.modules.pop("fc_flat_demo", None)
    sys.modules.pop("fc_flat_demo.integration", None)
    sys.modules.pop("fc_flat_demo.models", None)
