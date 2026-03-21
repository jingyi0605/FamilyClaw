from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

from app.modules.integration import service as integration_service
from app.modules.plugin import service as plugin_service
from app.modules.region.providers import RegionProvider, region_provider_registry
from app.modules.region.schemas import RegionNodeRead


@contextmanager
def force_weather_plugin_in_process() -> Iterator[None]:
    """天气插件业务测试统一走同进程，保证 provider patch 在当前进程可见。"""

    original_run_plugin_sync_pipeline = plugin_service.run_plugin_sync_pipeline

    def _run_plugin_sync_pipeline_in_process(
        db,
        *,
        household_id: str,
        request,
        actor=None,
        root_dir=None,
        state_file=None,
        source_type="builtin",
        execution_backend=None,
        runner_config=None,
    ):
        if request.plugin_id == "official-weather" and request.plugin_type == "integration":
            execution_backend = "in_process"
        return original_run_plugin_sync_pipeline(
            db,
            household_id=household_id,
            request=request,
            actor=actor,
            root_dir=root_dir,
            state_file=state_file,
            source_type=source_type,
            execution_backend=execution_backend,
            runner_config=runner_config,
        )

    with patch.object(
        integration_service,
        "run_plugin_sync_pipeline",
        side_effect=_run_plugin_sync_pipeline_in_process,
    ):
        yield


class StaticRegionProvider(RegionProvider):
    """测试专用静态地区 provider，避免天气测试依赖真实目录数据。"""

    def __init__(
        self,
        *,
        provider_code: str,
        country_code: str,
        plugin_name: str,
        nodes: list[RegionNodeRead],
    ) -> None:
        self.provider_code = provider_code
        self.country_code = country_code
        self.plugin_name = plugin_name
        self._nodes = nodes
        self._nodes_by_code = {node.region_code: node for node in nodes}

    def list_children(
        self,
        db,  # noqa: ANN001
        *,
        parent_region_code: str | None = None,
        admin_level: str | None = None,
    ) -> list[RegionNodeRead]:
        items: list[RegionNodeRead] = []
        for node in self._nodes:
            if parent_region_code is None:
                if node.parent_region_code is not None:
                    continue
            elif node.parent_region_code != parent_region_code:
                continue
            if admin_level is not None and node.admin_level != admin_level:
                continue
            items.append(node)
        return sorted(items, key=lambda item: item.region_code)

    def search(
        self,
        db,  # noqa: ANN001
        *,
        keyword: str,
        admin_level: str | None = None,
        parent_region_code: str | None = None,
    ) -> list[RegionNodeRead]:
        normalized_keyword = keyword.strip().lower()
        items: list[RegionNodeRead] = []
        for node in self.list_children(db, parent_region_code=parent_region_code, admin_level=admin_level):
            if normalized_keyword in node.name.lower() or normalized_keyword in node.full_name.lower():
                items.append(node)
        return items

    def resolve(self, db, *, region_code: str) -> RegionNodeRead | None:  # noqa: ANN001
        return self._nodes_by_code.get(region_code)

    def build_snapshot(self, node: RegionNodeRead) -> dict[str, object]:
        path_codes = list(node.path_codes)
        path_names = list(node.path_names)
        return {
            "provider_code": node.provider_code,
            "country_code": node.country_code,
            "region_code": node.region_code,
            "admin_level": node.admin_level,
            "province": {
                "code": path_codes[0] if len(path_codes) >= 1 else node.region_code,
                "name": path_names[0] if len(path_names) >= 1 else node.name,
            },
            "city": {
                "code": path_codes[1] if len(path_codes) >= 2 else node.region_code,
                "name": path_names[1] if len(path_names) >= 2 else node.name,
            },
            "district": {
                "code": path_codes[2] if len(path_codes) >= 3 else node.region_code,
                "name": path_names[2] if len(path_names) >= 3 else node.name,
            },
            "display_name": node.full_name,
            "timezone": node.timezone,
        }


def build_region_node(
    *,
    provider_code: str,
    region_code: str,
    name: str,
    full_name: str,
    admin_level: str,
    path_codes: list[str],
    path_names: list[str],
    parent_region_code: str | None,
    latitude: float | None,
    longitude: float | None,
) -> RegionNodeRead:
    return RegionNodeRead(
        provider_code=provider_code,
        country_code="CN",
        region_code=region_code,
        parent_region_code=parent_region_code,
        admin_level=admin_level,
        name=name,
        full_name=full_name,
        path_codes=path_codes,
        path_names=path_names,
        timezone="Asia/Shanghai",
        source_version="test",
        latitude=latitude,
        longitude=longitude,
        coordinate_precision="district" if latitude is not None and longitude is not None else None,
        coordinate_source="provider_builtin" if latitude is not None and longitude is not None else None,
        coordinate_updated_at="2026-03-18T03:00:00Z" if latitude is not None and longitude is not None else None,
    )


def build_weather_test_region_provider() -> StaticRegionProvider:
    provider_code = "test.cn-weather"
    nodes = [
        build_region_node(
            provider_code=provider_code,
            region_code="310000",
            name="上海市",
            full_name="上海市",
            admin_level="province",
            path_codes=["310000"],
            path_names=["上海市"],
            parent_region_code=None,
            latitude=31.2304,
            longitude=121.4737,
        ),
        build_region_node(
            provider_code=provider_code,
            region_code="310100",
            name="上海市",
            full_name="上海市 / 上海市",
            admin_level="city",
            path_codes=["310000", "310100"],
            path_names=["上海市", "上海市"],
            parent_region_code="310000",
            latitude=31.2304,
            longitude=121.4737,
        ),
        build_region_node(
            provider_code=provider_code,
            region_code="310115",
            name="浦东新区",
            full_name="中国 上海市",
            admin_level="district",
            path_codes=["310000", "310100", "310115"],
            path_names=["上海市", "上海市", "浦东新区"],
            parent_region_code="310100",
            latitude=31.2304,
            longitude=121.4737,
        ),
        build_region_node(
            provider_code=provider_code,
            region_code="320000",
            name="江苏省",
            full_name="江苏省",
            admin_level="province",
            path_codes=["320000"],
            path_names=["江苏省"],
            parent_region_code=None,
            latitude=31.2989,
            longitude=120.5853,
        ),
        build_region_node(
            provider_code=provider_code,
            region_code="320500",
            name="苏州市",
            full_name="江苏省 / 苏州市",
            admin_level="city",
            path_codes=["320000", "320500"],
            path_names=["江苏省", "苏州市"],
            parent_region_code="320000",
            latitude=31.2989,
            longitude=120.5853,
        ),
        build_region_node(
            provider_code=provider_code,
            region_code="320505",
            name="虎丘区",
            full_name="中国 江苏省 苏州市",
            admin_level="district",
            path_codes=["320000", "320500", "320505"],
            path_names=["江苏省", "苏州市", "虎丘区"],
            parent_region_code="320500",
            latitude=31.2989,
            longitude=120.5853,
        ),
        build_region_node(
            provider_code=provider_code,
            region_code="330000",
            name="浙江省",
            full_name="浙江省",
            admin_level="province",
            path_codes=["330000"],
            path_names=["浙江省"],
            parent_region_code=None,
            latitude=30.2741,
            longitude=120.1551,
        ),
        build_region_node(
            provider_code=provider_code,
            region_code="330100",
            name="杭州市",
            full_name="浙江省 / 杭州市",
            admin_level="city",
            path_codes=["330000", "330100"],
            path_names=["浙江省", "杭州市"],
            parent_region_code="330000",
            latitude=30.2741,
            longitude=120.1551,
        ),
        build_region_node(
            provider_code=provider_code,
            region_code="330106",
            name="西湖区",
            full_name="中国 浙江省 杭州市",
            admin_level="district",
            path_codes=["330000", "330100", "330106"],
            path_names=["浙江省", "杭州市", "西湖区"],
            parent_region_code="330100",
            latitude=30.2741,
            longitude=120.1551,
        ),
        build_region_node(
            provider_code=provider_code,
            region_code="990000",
            name="测试省",
            full_name="测试省",
            admin_level="province",
            path_codes=["990000"],
            path_names=["测试省"],
            parent_region_code=None,
            latitude=None,
            longitude=None,
        ),
        build_region_node(
            provider_code=provider_code,
            region_code="990100",
            name="测试市",
            full_name="测试省 / 测试市",
            admin_level="city",
            path_codes=["990000", "990100"],
            path_names=["测试省", "测试市"],
            parent_region_code="990000",
            latitude=None,
            longitude=None,
        ),
        build_region_node(
            provider_code=provider_code,
            region_code="990101",
            name="无坐标地区",
            full_name="中国 无坐标地区",
            admin_level="district",
            path_codes=["990000", "990100", "990101"],
            path_names=["测试省", "测试市", "无坐标地区"],
            parent_region_code="990100",
            latitude=None,
            longitude=None,
        ),
    ]
    return StaticRegionProvider(
        provider_code=provider_code,
        country_code="CN",
        plugin_name="测试地区",
        nodes=nodes,
    )


@contextmanager
def register_region_provider(provider: RegionProvider) -> Iterator[None]:
    region_provider_registry.register(provider)
    try:
        yield
    finally:
        region_provider_registry.unregister(provider.provider_code)
