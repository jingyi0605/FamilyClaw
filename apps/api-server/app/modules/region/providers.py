from __future__ import annotations

from abc import ABC, abstractmethod

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.utils import load_json
from app.modules.region.models import RegionNode
from app.modules.region.schemas import RegionNodeRead


BUILTIN_CN_MAINLAND_PROVIDER = "builtin.cn-mainland"
BUILTIN_CN_MAINLAND_COUNTRY = "CN"


class RegionProvider(ABC):
    provider_code: str
    country_code: str

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
    def resolve(self, db: Session, *, region_code: str) -> RegionNode | None:
        raise NotImplementedError

    @abstractmethod
    def build_snapshot(self, node: RegionNode) -> dict[str, object]:
        raise NotImplementedError


class RegionProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, RegionProvider] = {}

    def register(self, provider: RegionProvider) -> RegionProvider:
        self._providers[provider.provider_code] = provider
        return provider

    def get(self, provider_code: str) -> RegionProvider | None:
        return self._providers.get(provider_code)


class CnMainlandRegionProvider(RegionProvider):
    provider_code = BUILTIN_CN_MAINLAND_PROVIDER
    country_code = BUILTIN_CN_MAINLAND_COUNTRY

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

    def resolve(self, db: Session, *, region_code: str) -> RegionNode | None:
        return db.scalar(
            select(RegionNode).where(
                RegionNode.provider_code == self.provider_code,
                RegionNode.country_code == self.country_code,
                RegionNode.region_code == region_code,
                RegionNode.enabled.is_(True),
            )
        )

    def build_snapshot(self, node: RegionNode) -> dict[str, object]:
        path_codes = load_json(node.path_codes) or []
        path_names = load_json(node.path_names) or []
        return {
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


def _to_region_node_read(row: RegionNode) -> RegionNodeRead:
    return RegionNodeRead(
        provider_code=row.provider_code,
        country_code=row.country_code,
        region_code=row.region_code,
        parent_region_code=row.parent_region_code,
        admin_level=row.admin_level,
        name=row.name,
        full_name=row.full_name,
        path_codes=load_json(row.path_codes) or [],
        path_names=load_json(row.path_names) or [],
        timezone=row.timezone,
        source_version=row.source_version,
    )


region_provider_registry = RegionProviderRegistry()
region_provider_registry.register(CnMainlandRegionProvider())
