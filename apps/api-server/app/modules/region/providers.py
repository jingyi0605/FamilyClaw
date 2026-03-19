from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.utils import load_json
from app.modules.region.models import RegionNode
from app.modules.region.schemas import RegionNodeRead

logger = logging.getLogger(__name__)

BUILTIN_CN_MAINLAND_PROVIDER = "builtin.cn-mainland"
BUILTIN_CN_MAINLAND_COUNTRY = "CN"
BUILTIN_CN_MAINLAND_DATA_FILE = Path(__file__).parent / "data" / "cn_regions.json"


class RegionProvider(ABC):
    provider_code: str
    country_code: str
    source_type: str = "builtin"
    plugin_id: str | None = None
    plugin_name: str | None = None

    @abstractmethod
    def list_children(
        self,
        db: Session,
        *,
        parent_region_code: str | None = None,
        admin_level: str | None = None,
    ) -> list[RegionNodeRead]:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        db: Session,
        *,
        keyword: str,
        admin_level: str | None = None,
        parent_region_code: str | None = None,
    ) -> list[RegionNodeRead]:
        raise NotImplementedError

    @abstractmethod
    def resolve(self, db: Session, *, region_code: str) -> RegionNodeRead | None:
        raise NotImplementedError

    @abstractmethod
    def build_snapshot(self, node: RegionNodeRead) -> dict[str, object]:
        raise NotImplementedError


@dataclass(slots=True)
class RegionProviderRegistryEntry:
    provider: RegionProvider
    household_id: str | None = None


class RegionProviderExecutionError(RuntimeError):
    pass


class RegionProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[tuple[str | None, str], RegionProviderRegistryEntry] = {}

    def register(self, provider: RegionProvider, *, household_id: str | None = None) -> RegionProvider:
        self._providers[(household_id, provider.provider_code)] = RegionProviderRegistryEntry(
            provider=provider,
            household_id=household_id,
        )
        return provider

    def get(self, provider_code: str, *, household_id: str | None = None) -> RegionProvider | None:
        scoped = self._providers.get((household_id, provider_code))
        if scoped is not None:
            return scoped.provider
        global_provider = self._providers.get((None, provider_code))
        if global_provider is not None:
            return global_provider.provider
        return None

    def unregister(self, provider_code: str, *, household_id: str | None = None) -> None:
        self._providers.pop((household_id, provider_code), None)

    def clear_scope(self, household_id: str) -> None:
        stale_keys = [key for key in self._providers if key[0] == household_id]
        for key in stale_keys:
            self._providers.pop(key, None)

    def list(self, *, household_id: str | None = None) -> list[RegionProvider]:
        global_items = [entry.provider for key, entry in self._providers.items() if key[0] is None]
        if household_id is None:
            return sorted(global_items, key=lambda item: item.provider_code)

        scoped_map = {item.provider_code: item for item in global_items}
        for key, entry in self._providers.items():
            if key[0] == household_id:
                scoped_map[entry.provider.provider_code] = entry.provider
        return sorted(scoped_map.values(), key=lambda item: item.provider_code)


class CnMainlandRegionProvider(RegionProvider):
    provider_code = BUILTIN_CN_MAINLAND_PROVIDER
    country_code = BUILTIN_CN_MAINLAND_COUNTRY
    plugin_name = "中国大陆"

    def list_children(
        self,
        db: Session,
        *,
        parent_region_code: str | None = None,
        admin_level: str | None = None,
    ) -> list[RegionNodeRead]:
        statement = select(RegionNode).where(
            RegionNode.provider_code == self.provider_code,
            RegionNode.country_code == self.country_code,
            RegionNode.enabled.is_(True),
        )
        if parent_region_code is None:
            statement = statement.where(RegionNode.parent_region_code.is_(None))
        else:
            statement = statement.where(RegionNode.parent_region_code == parent_region_code)
        if admin_level:
            statement = statement.where(RegionNode.admin_level == admin_level)
        rows = db.scalars(statement.order_by(RegionNode.region_code.asc())).all()
        return [_to_region_node_read(row) for row in rows]

    def search(
        self,
        db: Session,
        *,
        keyword: str,
        admin_level: str | None = None,
        parent_region_code: str | None = None,
    ) -> list[RegionNodeRead]:
        normalized_keyword = keyword.strip()
        like_value = f"%{normalized_keyword.lower()}%"
        statement = select(RegionNode).where(
            RegionNode.provider_code == self.provider_code,
            RegionNode.country_code == self.country_code,
            RegionNode.enabled.is_(True),
            or_(
                func.lower(RegionNode.name).like(like_value),
                func.lower(RegionNode.full_name).like(like_value),
            ),
        )
        if admin_level:
            statement = statement.where(RegionNode.admin_level == admin_level)
        if parent_region_code:
            statement = statement.where(RegionNode.parent_region_code == parent_region_code)
        rows = db.scalars(statement.order_by(RegionNode.region_code.asc()).limit(50)).all()
        return [_to_region_node_read(row) for row in rows]

    def resolve(self, db: Session, *, region_code: str) -> RegionNodeRead | None:
        row = db.scalar(
            select(RegionNode).where(
                RegionNode.provider_code == self.provider_code,
                RegionNode.country_code == self.country_code,
                RegionNode.region_code == region_code,
                RegionNode.enabled.is_(True),
            )
        )
        if row is None:
            return None
        return _to_region_node_read(row)

    def build_snapshot(self, node: RegionNodeRead) -> dict[str, object]:
        path_codes = node.path_codes
        path_names = node.path_names
        snapshot = {
            "provider_code": node.provider_code,
            "country_code": node.country_code,
            "region_code": node.region_code,
            "admin_level": node.admin_level,
            "province": {"code": path_codes[0], "name": path_names[0]},
            "city": {"code": path_codes[1], "name": path_names[1]},
            "district": {"code": path_codes[2], "name": path_names[2]},
            "display_name": f"{path_names[0]} {path_names[2]}",
            "timezone": node.timezone,
        }
        representative_coordinate = _build_snapshot_coordinate(node)
        if representative_coordinate is not None:
            snapshot["representative_coordinate"] = representative_coordinate
        return snapshot


def _to_region_node_read(row: RegionNode) -> RegionNodeRead:
    return RegionNodeRead(
        provider_code=row.provider_code,
        country_code=row.country_code,
        region_code=row.region_code,
        parent_region_code=row.parent_region_code,
        admin_level=cast(Any, row.admin_level),
        name=row.name,
        full_name=row.full_name,
        path_codes=load_json(row.path_codes) or [],
        path_names=load_json(row.path_names) or [],
        timezone=row.timezone,
        source_version=row.source_version,
        latitude=row.latitude,
        longitude=row.longitude,
        coordinate_precision=cast(Any, row.coordinate_precision),
        coordinate_source=cast(Any, row.coordinate_source),
        coordinate_updated_at=row.coordinate_updated_at,
    )


class JsonFileCnMainlandRegionProvider(RegionProvider):
    """基于JSON文件的中国大陆地区数据提供者，不依赖数据库。"""

    provider_code = BUILTIN_CN_MAINLAND_PROVIDER
    country_code = BUILTIN_CN_MAINLAND_COUNTRY
    source_type = "json_file"
    plugin_name = "中国大陆"

    def __init__(self) -> None:
        self._data: list[RegionNodeRead] | None = None
        self._by_code: dict[str, RegionNodeRead] | None = None

    def _ensure_loaded(self) -> None:
        """延迟加载数据到内存。"""
        if self._data is not None:
            return

        if not BUILTIN_CN_MAINLAND_DATA_FILE.exists():
            logger.warning("地区数据文件不存在: %s", BUILTIN_CN_MAINLAND_DATA_FILE)
            self._data = []
            self._by_code = {}
            return

        try:
            with open(BUILTIN_CN_MAINLAND_DATA_FILE, encoding="utf-8") as f:
                raw_items = json.load(f)

            self._data = [
                RegionNodeRead(
                    provider_code=item["provider_code"],
                    country_code=item["country_code"],
                    region_code=item["region_code"],
                    parent_region_code=item.get("parent_region_code"),
                    admin_level=cast(Any, item.get("admin_level")),
                    name=item["name"],
                    full_name=item.get("full_name", item["name"]),
                    path_codes=item.get("path_codes", []),
                    path_names=item.get("path_names", []),
                    timezone=item.get("timezone"),
                    source_version=item.get("source_version"),
                    latitude=item.get("latitude"),
                    longitude=item.get("longitude"),
                    coordinate_precision=cast(Any, item.get("coordinate_precision")),
                    coordinate_source=cast(Any, item.get("coordinate_source")),
                    coordinate_updated_at=item.get("coordinate_updated_at"),
                )
                for item in raw_items
                if item.get("enabled", True)
            ]
            self._by_code = {node.region_code: node for node in self._data}
            logger.info("已从JSON文件加载 %d 条地区数据", len(self._data))
        except Exception as e:
            logger.error("加载地区数据文件失败: %s", e)
            self._data = []
            self._by_code = {}

    def list_children(
        self,
        db: Session,  # noqa: ARG002 - 保持接口一致，但不需要数据库
        *,
        parent_region_code: str | None = None,
        admin_level: str | None = None,
    ) -> list[RegionNodeRead]:
        self._ensure_loaded()
        if self._data is None:
            return []

        result = []
        for node in self._data:
            if parent_region_code is None:
                if node.parent_region_code is not None:
                    continue
            elif node.parent_region_code != parent_region_code:
                continue

            if admin_level and node.admin_level != admin_level:
                continue

            result.append(node)

        return sorted(result, key=lambda n: n.region_code)

    def search(
        self,
        db: Session,  # noqa: ARG002 - 保持接口一致，但不需要数据库
        *,
        keyword: str,
        admin_level: str | None = None,
        parent_region_code: str | None = None,
    ) -> list[RegionNodeRead]:
        self._ensure_loaded()
        if self._data is None:
            return []

        normalized_keyword = keyword.strip().lower()
        result = []

        for node in self._data:
            if normalized_keyword not in node.name.lower() and normalized_keyword not in node.full_name.lower():
                continue

            if admin_level and node.admin_level != admin_level:
                continue

            if parent_region_code and node.parent_region_code != parent_region_code:
                continue

            result.append(node)
            if len(result) >= 50:
                break

        return sorted(result, key=lambda n: n.region_code)

    def resolve(
        self,
        db: Session,  # noqa: ARG002 - 保持接口一致，但不需要数据库
        *,
        region_code: str,
    ) -> RegionNodeRead | None:
        self._ensure_loaded()
        if self._by_code is None:
            return None
        return self._by_code.get(region_code)

    def build_snapshot(self, node: RegionNodeRead) -> dict[str, object]:
        path_codes = node.path_codes
        path_names = node.path_names
        snapshot = {
            "provider_code": node.provider_code,
            "country_code": node.country_code,
            "region_code": node.region_code,
            "admin_level": node.admin_level,
            "province": {"code": path_codes[0], "name": path_names[0]},
            "city": {"code": path_codes[1], "name": path_names[1]},
            "district": {"code": path_codes[2], "name": path_names[2]},
            "display_name": f"{path_names[0]} {path_names[2]}",
            "timezone": node.timezone,
        }
        representative_coordinate = _build_snapshot_coordinate(node)
        if representative_coordinate is not None:
            snapshot["representative_coordinate"] = representative_coordinate
        return snapshot


def _build_snapshot_coordinate(node: RegionNodeRead) -> dict[str, object] | None:
    if node.latitude is None or node.longitude is None:
        return None
    return {
        "latitude": node.latitude,
        "longitude": node.longitude,
        "coordinate_precision": node.coordinate_precision,
        "coordinate_source": node.coordinate_source,
        "coordinate_updated_at": node.coordinate_updated_at,
    }


region_provider_registry = RegionProviderRegistry()
# 使用基于JSON文件的Provider，不依赖数据库
region_provider_registry.register(JsonFileCnMainlandRegionProvider())
