import unittest

from app.modules.plugin.versioning import (
    MarketplaceVersionFact,
    compare_plugin_versions,
    resolve_host_compatibility,
    resolve_marketplace_version_governance,
    resolve_non_market_version_governance,
)


class PluginVersioningTests(unittest.TestCase):
    def test_compare_plugin_versions_supports_numeric_and_prerelease(self) -> None:
        self.assertLess(compare_plugin_versions("1.0.0", "1.1.0"), 0)
        self.assertGreater(compare_plugin_versions("1.2.0", "1.1.9"), 0)
        self.assertLess(compare_plugin_versions("1.0.0rc1", "1.0.0"), 0)

    def test_resolve_host_compatibility_blocks_when_host_too_old(self) -> None:
        result = resolve_host_compatibility(
            host_version="0.1.0",
            min_app_version="0.2.0",
            target_version="1.0.0",
        )
        self.assertEqual("host_too_old", result.status)
        self.assertIn("0.2.0", result.blocked_reason or "")

    def test_resolve_marketplace_version_governance_uses_latest_compatible_version(self) -> None:
        result = resolve_marketplace_version_governance(
            host_version="0.1.0",
            declared_version="1.0.0",
            installed_version="1.0.0",
            latest_version="2.0.0",
            versions=[
                MarketplaceVersionFact(version="1.0.0", min_app_version="0.1.0"),
                MarketplaceVersionFact(version="1.5.0", min_app_version="0.1.0"),
                MarketplaceVersionFact(version="2.0.0", min_app_version="9.9.9"),
            ],
        )
        self.assertEqual("1.5.0", result.latest_compatible_version)
        self.assertEqual("upgrade_available", result.update_state)
        self.assertEqual("host_too_old", result.compatibility_status)

    def test_resolve_marketplace_version_governance_marks_non_catalog_install_as_newer(self) -> None:
        result = resolve_marketplace_version_governance(
            host_version="0.1.0",
            declared_version="9.9.9",
            installed_version="9.9.9",
            latest_version="1.0.0",
            versions=[MarketplaceVersionFact(version="1.0.0", min_app_version="0.1.0")],
        )
        self.assertEqual("installed_newer_than_market", result.update_state)

    def test_resolve_non_market_version_governance_returns_stable_state(self) -> None:
        result = resolve_non_market_version_governance(
            source_type="local",
            declared_version="1.0.0",
            installed_version="1.0.0",
        )
        self.assertEqual("not_market_managed", result.update_state)
        self.assertEqual("local", result.source_type)


if __name__ == "__main__":
    unittest.main()
