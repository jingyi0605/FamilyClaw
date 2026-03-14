from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.household.models import Household
from app.modules.region.models import HouseholdRegionBinding, RegionNode
from app.modules.region.schemas import (
    HouseholdRegionErrorRead,
    HouseholdRegionRead,
    RegionCatalogImportItem,
    RegionNodeRead,
    RegionNodeRefRead,
    RegionSelection,
)

BUILTIN_CN_MAINLAND_PROVIDER = "builtin.cn-mainland"
BUILTIN_CN_MAINLAND_COUNTRY = "CN"
DISTRICT_LEVEL = "district"


@dataclass
class RegionServiceError(Exception):
    detail: str
    error_code: str
    field: str | None = None
    status_code: int = status.HTTP_400_BAD_REQUEST


def raise_region_http_error(exc: RegionServiceError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "detail": exc.detail,
            "error_code": exc.error_code,
            "field": exc.field,
            "timestamp": utc_now_iso(),
        },
    )


def import_region_catalog(
    db: Session,
    *,
    items: list[RegionCatalogImportItem],
    provider_code: str = BUILTIN_CN_MAINLAND_PROVIDER,
    country_code: str = BUILTIN_CN_MAINLAND_COUNTRY,
    source_version: str | None = None,
) -> None:
    imported_at = utc_now_iso()
    seen_codes: set[str] = set()
    for item in items:
        if item.region_code in seen_codes:
            raise RegionServiceError(
                detail=f"重复地区编码: {item.region_code}",
                error_code="region_duplicate_code",
                field="region_code",
            )
        seen_codes.add(item.region_code)
        if not item.path_codes or item.path_codes[-1] != item.region_code:
            raise RegionServiceError(
                detail=f"地区路径和编码不一致: {item.region_code}",
                error_code="region_parent_mismatch",
                field="path_codes",
            )

        existing = db.scalar(
            select(RegionNode).where(
                RegionNode.provider_code == provider_code,
                RegionNode.region_code == item.region_code,
            )
        )
        if existing is None:
            existing = RegionNode(
                id=new_uuid(),
                provider_code=provider_code,
                country_code=country_code,
                region_code=item.region_code,
                parent_region_code=item.parent_region_code,
                admin_level=item.admin_level,
                name=item.name,
                full_name=item.full_name,
                path_codes=dump_json(item.path_codes) or "[]",
                path_names=dump_json(item.path_names) or "[]",
                timezone=item.timezone,
                source_version=source_version,
                imported_at=imported_at,
                enabled=item.enabled,
                extra=dump_json(item.extra),
            )
        else:
            existing.parent_region_code = item.parent_region_code
            existing.admin_level = item.admin_level
            existing.name = item.name
            existing.full_name = item.full_name
            existing.path_codes = dump_json(item.path_codes) or "[]"
            existing.path_names = dump_json(item.path_names) or "[]"
            existing.timezone = item.timezone
            existing.source_version = source_version
            existing.imported_at = imported_at
            existing.enabled = item.enabled
            existing.extra = dump_json(item.extra)
        db.add(existing)


def list_region_catalog(
    db: Session,
    *,
    provider_code: str,
    country_code: str,
    parent_region_code: str | None = None,
    admin_level: str | None = None,
) -> list[RegionNodeRead]:
    _ensure_builtin_cn_supported(provider_code=provider_code, country_code=country_code)
    statement = select(RegionNode).where(
        RegionNode.provider_code == provider_code,
        RegionNode.country_code == country_code,
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


def search_region_catalog(
    db: Session,
    *,
    provider_code: str,
    country_code: str,
    keyword: str,
    admin_level: str | None = None,
    parent_region_code: str | None = None,
) -> list[RegionNodeRead]:
    _ensure_builtin_cn_supported(provider_code=provider_code, country_code=country_code)
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        raise RegionServiceError(
            detail="keyword 不能为空",
            error_code="region_keyword_required",
            field="keyword",
        )
    like_value = f"%{normalized_keyword.lower()}%"
    statement = select(RegionNode).where(
        RegionNode.provider_code == provider_code,
        RegionNode.country_code == country_code,
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


def get_household_region_binding(db: Session, household_id: str) -> HouseholdRegionBinding | None:
    return db.get(HouseholdRegionBinding, household_id)


def has_household_region_binding(db: Session, household_id: str) -> bool:
    return get_household_region_binding(db, household_id) is not None


def upsert_household_region(
    db: Session,
    *,
    household: Household,
    selection: RegionSelection,
    source: str,
) -> HouseholdRegionBinding:
    _ensure_builtin_cn_supported(
        provider_code=selection.provider_code,
        country_code=selection.country_code,
    )
    region_node = _get_region_node_or_raise(
        db,
        provider_code=selection.provider_code,
        country_code=selection.country_code,
        region_code=selection.region_code,
    )
    if region_node.admin_level != DISTRICT_LEVEL:
        raise RegionServiceError(
            detail="当前只接受区县级正式地区绑定",
            error_code="region_level_invalid",
            field="region_selection.region_code",
        )

    snapshot = _build_snapshot_from_node(region_node)
    existing = db.get(HouseholdRegionBinding, household.id)
    if existing is None:
        existing = HouseholdRegionBinding(
            household_id=household.id,
            provider_code=selection.provider_code,
            country_code=selection.country_code,
            region_code=selection.region_code,
            admin_level=DISTRICT_LEVEL,
            province_code=snapshot["province"]["code"],
            province_name=snapshot["province"]["name"],
            city_code=snapshot["city"]["code"],
            city_name=snapshot["city"]["name"],
            district_code=snapshot["district"]["code"],
            district_name=snapshot["district"]["name"],
            display_name=snapshot["display_name"],
            snapshot=dump_json(snapshot) or "{}",
            source=source,
        )
    else:
        existing.provider_code = selection.provider_code
        existing.country_code = selection.country_code
        existing.region_code = selection.region_code
        existing.admin_level = DISTRICT_LEVEL
        existing.province_code = snapshot["province"]["code"]
        existing.province_name = snapshot["province"]["name"]
        existing.city_code = snapshot["city"]["code"]
        existing.city_name = snapshot["city"]["name"]
        existing.district_code = snapshot["district"]["code"]
        existing.district_name = snapshot["district"]["name"]
        existing.display_name = snapshot["display_name"]
        existing.snapshot = dump_json(snapshot) or "{}"
        existing.source = source
    household.city = snapshot["display_name"]
    db.add(household)
    db.add(existing)
    return existing


def get_household_region_context(db: Session, household_id: str) -> HouseholdRegionRead:
    binding = get_household_region_binding(db, household_id)
    if binding is None:
        return HouseholdRegionRead(status="unconfigured")

    snapshot = load_json(binding.snapshot) or {}
    return HouseholdRegionRead(
        status="configured",
        provider_code=binding.provider_code,
        country_code=binding.country_code,
        region_code=binding.region_code,
        admin_level=binding.admin_level,
        province=_to_region_ref(snapshot.get("province")),
        city=_to_region_ref(snapshot.get("city")),
        district=_to_region_ref(snapshot.get("district")),
        display_name=snapshot.get("display_name") or binding.display_name,
        timezone=snapshot.get("timezone"),
    )


def resolve_household_region_context(db: Session, household_id: str) -> HouseholdRegionErrorRead:
    binding = get_household_region_binding(db, household_id)
    if binding is None:
        return HouseholdRegionErrorRead(
            status="unconfigured",
            error_code="household_region_unconfigured",
            detail="当前家庭还没有配置正式地区",
        )
    context = get_household_region_context(db, household_id)
    return HouseholdRegionErrorRead(**context.model_dump())


def _ensure_builtin_cn_supported(*, provider_code: str, country_code: str) -> None:
    if provider_code != BUILTIN_CN_MAINLAND_PROVIDER:
        raise RegionServiceError(
            detail=f"不支持的地区提供方: {provider_code}",
            error_code="region_provider_not_found",
            field="provider_code",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if country_code != BUILTIN_CN_MAINLAND_COUNTRY:
        raise RegionServiceError(
            detail=f"当前只支持 {BUILTIN_CN_MAINLAND_COUNTRY}",
            error_code="region_country_not_supported",
            field="country_code",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


def _get_region_node_or_raise(
    db: Session,
    *,
    provider_code: str,
    country_code: str,
    region_code: str,
) -> RegionNode:
    row = db.scalar(
        select(RegionNode).where(
            RegionNode.provider_code == provider_code,
            RegionNode.country_code == country_code,
            RegionNode.region_code == region_code,
            RegionNode.enabled.is_(True),
        )
    )
    if row is None:
        raise RegionServiceError(
            detail=f"地区编码不存在: {region_code}",
            error_code="region_not_found",
            field="region_selection.region_code",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return row


def _build_snapshot_from_node(node: RegionNode) -> dict[str, object]:
    path_codes = load_json(node.path_codes) or []
    path_names = load_json(node.path_names) or []
    if len(path_codes) < 3 or len(path_names) < 3:
        raise RegionServiceError(
            detail=f"地区路径不完整: {node.region_code}",
            error_code="region_parent_mismatch",
            field="region_selection.region_code",
        )
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


def _to_region_ref(value: object | None) -> RegionNodeRefRead | None:
    if not isinstance(value, dict):
        return None
    code = value.get("code")
    name = value.get("name")
    if not isinstance(code, str) or not isinstance(name, str):
        return None
    return RegionNodeRefRead(code=code, name=name)


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
