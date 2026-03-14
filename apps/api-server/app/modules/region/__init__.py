from app.modules.region.models import HouseholdRegionBinding, RegionNode
from app.modules.region.providers import (
    BUILTIN_CN_MAINLAND_COUNTRY,
    BUILTIN_CN_MAINLAND_PROVIDER,
    CnMainlandRegionProvider,
    RegionProvider,
    RegionProviderExecutionError,
    RegionProviderRegistry,
    region_provider_registry,
)

# NOTE: sync_household_plugin_region_providers 已移除顶层导出
# 请直接使用: from app.modules.region.plugin_runtime import sync_household_plugin_region_providers
# 这样可以避免循环导入 (region -> plugin -> memory -> household -> region)

__all__ = [
    "RegionNode",
    "HouseholdRegionBinding",
    "BUILTIN_CN_MAINLAND_COUNTRY",
    "BUILTIN_CN_MAINLAND_PROVIDER",
    "CnMainlandRegionProvider",
    "RegionProvider",
    "RegionProviderExecutionError",
    "RegionProviderRegistry",
    "region_provider_registry",
]
