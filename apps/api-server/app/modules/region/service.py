from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.household.models import Household
from app.modules.region.plugin_runtime import sync_household_plugin_region_providers
from app.modules.region.models import HouseholdRegionBinding, RegionNode
from app.modules.region.providers import (
    BUILTIN_CN_MAINLAND_COUNTRY,
    BUILTIN_CN_MAINLAND_PROVIDER,
    RegionProvider,
    RegionProviderExecutionError,
    region_provider_registry,
)
from app.modules.region.schemas import (
    HouseholdCoordinateOverrideRead,
    HouseholdRegionErrorRead,
    HouseholdRegionRead,
    RegionCatalogImportItem,
    RegionNodeRead,
    RegionNodeRefRead,
    RegionSelection,
    ResolvedHouseholdCoordinateRead,
)

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
                latitude=item.latitude,
                longitude=item.longitude,
                coordinate_precision=item.coordinate_precision,
                coordinate_source=item.coordinate_source,
                coordinate_updated_at=item.coordinate_updated_at,
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
            existing.latitude = item.latitude
            existing.longitude = item.longitude
            existing.coordinate_precision = item.coordinate_precision
            existing.coordinate_source = item.coordinate_source
            existing.coordinate_updated_at = item.coordinate_updated_at
            existing.enabled = item.enabled
            existing.extra = dump_json(item.extra)
        db.add(existing)


def list_region_catalog(
    db: Session,
    *,
    provider_code: str,
    country_code: str,
    household_id: str | None = None,
    parent_region_code: str | None = None,
    admin_level: str | None = None,
) -> list[RegionNodeRead]:
    provider = _require_provider(
        db,
        provider_code=provider_code,
        country_code=country_code,
        household_id=household_id,
    )
    try:
        return provider.list_children(
            db,
            parent_region_code=parent_region_code,
            admin_level=admin_level,
        )
    except RegionProviderExecutionError as exc:
        raise _raise_provider_runtime_error(provider_code=provider_code, exc=exc) from exc


def search_region_catalog(
    db: Session,
    *,
    provider_code: str,
    country_code: str,
    keyword: str,
    household_id: str | None = None,
    admin_level: str | None = None,
    parent_region_code: str | None = None,
) -> list[RegionNodeRead]:
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        raise RegionServiceError(
            detail="keyword 不能为空",
            error_code="region_keyword_required",
            field="keyword",
        )
    provider = _require_provider(
        db,
        provider_code=provider_code,
        country_code=country_code,
        household_id=household_id,
    )
    try:
        return provider.search(
            db,
            keyword=normalized_keyword,
            admin_level=admin_level,
            parent_region_code=parent_region_code,
        )
    except RegionProviderExecutionError as exc:
        raise _raise_provider_runtime_error(provider_code=provider_code, exc=exc) from exc


def get_household_region_binding(db: Session, household_id: str) -> HouseholdRegionBinding | None:
    return db.get(HouseholdRegionBinding, household_id)


def has_household_region_binding(db: Session, household_id: str) -> bool:
    return get_household_region_binding(db, household_id) is not None


def get_household_coordinate_override(household: Household | None) -> HouseholdCoordinateOverrideRead | None:
    if household is None:
        return None
    if household.latitude is None or household.longitude is None:
        return None
    if household.coordinate_source is None or household.coordinate_precision is None or household.coordinate_updated_at is None:
        return None
    return HouseholdCoordinateOverrideRead(
        latitude=household.latitude,
        longitude=household.longitude,
        coordinate_source=cast(Any, household.coordinate_source),
        coordinate_precision=cast(Any, household.coordinate_precision),
        coordinate_updated_at=household.coordinate_updated_at,
    )


def upsert_household_region(
    db: Session,
    *,
    household: Household,
    selection: RegionSelection,
    source: str,
) -> HouseholdRegionBinding:
    provider = _require_provider(
        db,
        provider_code=selection.provider_code,
        country_code=selection.country_code,
        household_id=household.id,
    )
    region_node = _get_region_node_or_raise(
        db,
        provider_code=provider.provider_code,
        country_code=provider.country_code,
        household_id=household.id,
        region_code=selection.region_code,
    )
    if region_node.admin_level != DISTRICT_LEVEL:
        raise RegionServiceError(
            detail="当前只接受区县级正式地区绑定",
            error_code="region_level_invalid",
            field="region_selection.region_code",
        )

    snapshot = _build_snapshot(provider=provider, node=region_node)
    province = cast(dict[str, str], snapshot["province"])
    city = cast(dict[str, str], snapshot["city"])
    district = cast(dict[str, str], snapshot["district"])
    display_name = cast(str, snapshot["display_name"])
    existing = db.get(HouseholdRegionBinding, household.id)
    if existing is None:
        existing = HouseholdRegionBinding(
            household_id=household.id,
            provider_code=selection.provider_code,
            country_code=selection.country_code,
            region_code=selection.region_code,
            admin_level=DISTRICT_LEVEL,
            province_code=province["code"],
            province_name=province["name"],
            city_code=city["code"],
            city_name=city["name"],
            district_code=district["code"],
            district_name=district["name"],
            display_name=display_name,
            snapshot=dump_json(snapshot) or "{}",
            source=source,
        )
    else:
        existing.provider_code = selection.provider_code
        existing.country_code = selection.country_code
        existing.region_code = selection.region_code
        existing.admin_level = DISTRICT_LEVEL
        existing.province_code = province["code"]
        existing.province_name = province["name"]
        existing.city_code = city["code"]
        existing.city_name = city["name"]
        existing.district_code = district["code"]
        existing.district_name = district["name"]
        existing.display_name = display_name
        existing.snapshot = dump_json(snapshot) or "{}"
        existing.source = source
    household.city = display_name
    db.add(household)
    db.add(existing)
    return existing


def get_household_region_context(
    db: Session,
    household_id: str,
    *,
    household: Household | None = None,
) -> HouseholdRegionRead:
    household = household or db.get(Household, household_id)
    binding = get_household_region_binding(db, household_id)
    if binding is None:
        return HouseholdRegionRead(
            status="unconfigured",
            coordinate=_resolve_household_coordinate(
                db,
                household=household,
                binding=None,
                household_id=household_id,
            ),
        )

    snapshot = load_json(binding.snapshot) or {}
    provider = _find_provider_for_household(db, provider_code=binding.provider_code, household_id=household_id)
    status_value = "configured" if provider is not None else "provider_unavailable"
    return HouseholdRegionRead(
        status=status_value,
        provider_code=binding.provider_code,
        country_code=binding.country_code,
        region_code=binding.region_code,
        admin_level=cast(Any, binding.admin_level),
        province=_to_region_ref(snapshot.get("province")),
        city=_to_region_ref(snapshot.get("city")),
        district=_to_region_ref(snapshot.get("district")),
        display_name=snapshot.get("display_name") or binding.display_name,
        timezone=snapshot.get("timezone"),
        coordinate=_resolve_household_coordinate(
            db,
            household=household,
            binding=binding,
            household_id=household_id,
        ),
    )


def resolve_household_region_context(db: Session, household_id: str) -> HouseholdRegionErrorRead:
    household = db.get(Household, household_id)
    binding = get_household_region_binding(db, household_id)
    context = get_household_region_context(db, household_id, household=household)
    if binding is None:
        return HouseholdRegionErrorRead(
            **context.model_dump(),
            error_code="household_region_unconfigured",
            detail="当前家庭还没有配置正式地区",
        )
    if context.status == "provider_unavailable" and not context.coordinate.available:
        return HouseholdRegionErrorRead(
            **context.model_dump(),
            error_code="region_provider_unavailable",
            detail="当前家庭的地区 provider 暂时不可用，无法解析地区代表坐标",
        )
    return HouseholdRegionErrorRead(**context.model_dump())


def _resolve_household_coordinate(
    db: Session,
    *,
    household: Household | None,
    binding: HouseholdRegionBinding | None,
    household_id: str,
) -> ResolvedHouseholdCoordinateRead:
    exact_coordinate = _build_household_exact_coordinate(household=household, binding=binding)
    if exact_coordinate is not None:
        return exact_coordinate

    if binding is None:
        return ResolvedHouseholdCoordinateRead(
            available=False,
            source_type="unavailable",
        )

    snapshot = load_json(binding.snapshot) or {}
    snapshot_coordinate = _build_region_coordinate_from_snapshot(binding=binding, snapshot=snapshot)
    if snapshot_coordinate is not None:
        return snapshot_coordinate

    provider = _find_provider_for_household(db, provider_code=binding.provider_code, household_id=household_id)
    if provider is None:
        return _build_unavailable_coordinate(binding=binding, snapshot=snapshot)

    try:
        node = provider.resolve(db, region_code=binding.region_code)
    except RegionProviderExecutionError:
        return _build_unavailable_coordinate(binding=binding, snapshot=snapshot)
    if node is None or node.latitude is None or node.longitude is None:
        return _build_unavailable_coordinate(binding=binding, snapshot=snapshot)

    return ResolvedHouseholdCoordinateRead(
        available=True,
        latitude=node.latitude,
        longitude=node.longitude,
        source_type="region_representative",
        precision=node.coordinate_precision,
        provider_code=binding.provider_code,
        region_code=binding.region_code,
        region_path=_extract_region_path(snapshot),
        updated_at=node.coordinate_updated_at,
    )


def _build_household_exact_coordinate(
    *,
    household: Household | None,
    binding: HouseholdRegionBinding | None,
) -> ResolvedHouseholdCoordinateRead | None:
    coordinate = get_household_coordinate_override(household)
    if coordinate is None:
        return None
    return ResolvedHouseholdCoordinateRead(
        available=True,
        latitude=coordinate.latitude,
        longitude=coordinate.longitude,
        source_type="household_exact",
        precision=coordinate.coordinate_precision,
        provider_code=binding.provider_code if binding is not None else None,
        region_code=binding.region_code if binding is not None else None,
        region_path=_extract_region_path(load_json(binding.snapshot) or {}) if binding is not None else [],
        updated_at=coordinate.coordinate_updated_at,
    )


def _build_region_coordinate_from_snapshot(
    *,
    binding: HouseholdRegionBinding,
    snapshot: dict[str, object],
) -> ResolvedHouseholdCoordinateRead | None:
    coordinate = snapshot.get("representative_coordinate")
    if not isinstance(coordinate, dict):
        return None
    latitude = coordinate.get("latitude")
    longitude = coordinate.get("longitude")
    if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
        return None
    precision = coordinate.get("coordinate_precision")
    updated_at = coordinate.get("coordinate_updated_at")
    return ResolvedHouseholdCoordinateRead(
        available=True,
        latitude=float(latitude),
        longitude=float(longitude),
        source_type="region_representative",
        precision=cast(Any, precision) if isinstance(precision, str) else None,
        provider_code=binding.provider_code,
        region_code=binding.region_code,
        region_path=_extract_region_path(snapshot),
        updated_at=updated_at if isinstance(updated_at, str) else None,
    )


def _build_unavailable_coordinate(
    *,
    binding: HouseholdRegionBinding,
    snapshot: dict[str, object],
) -> ResolvedHouseholdCoordinateRead:
    return ResolvedHouseholdCoordinateRead(
        available=False,
        source_type="unavailable",
        provider_code=binding.provider_code,
        region_code=binding.region_code,
        region_path=_extract_region_path(snapshot),
    )


def _require_provider(
    db: Session,
    *,
    provider_code: str,
    country_code: str,
    household_id: str | None = None,
) -> RegionProvider:
    provider = _find_provider_for_household(db, provider_code=provider_code, household_id=household_id)
    if provider is None:
        raise RegionServiceError(
            detail=f"不支持的地区提供方: {provider_code}",
            error_code="region_provider_not_found",
            field="provider_code",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if provider.country_code != country_code:
        raise RegionServiceError(
            detail=f"提供方 {provider_code} 当前只支持 {provider.country_code}",
            error_code="region_country_not_supported",
            field="country_code",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return provider


def _get_region_node_or_raise(
    db: Session,
    *,
    provider_code: str,
    country_code: str,
    household_id: str | None = None,
    region_code: str,
) -> RegionNodeRead:
    provider = _require_provider(
        db,
        provider_code=provider_code,
        country_code=country_code,
        household_id=household_id,
    )
    try:
        row = provider.resolve(db, region_code=region_code)
    except RegionProviderExecutionError as exc:
        raise _raise_provider_runtime_error(provider_code=provider_code, exc=exc) from exc
    if row is None:
        raise RegionServiceError(
            detail=f"地区编码不存在: {region_code}",
            error_code="region_not_found",
            field="region_selection.region_code",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return row


def _build_snapshot(*, provider: RegionProvider, node: RegionNodeRead) -> dict[str, object]:
    path_codes = node.path_codes
    path_names = node.path_names
    if len(path_codes) < 3 or len(path_names) < 3:
        raise RegionServiceError(
            detail=f"地区路径不完整: {node.region_code}",
            error_code="region_parent_mismatch",
            field="region_selection.region_code",
        )
    try:
        return provider.build_snapshot(node)
    except RegionProviderExecutionError as exc:
        raise _raise_provider_runtime_error(provider_code=provider.provider_code, exc=exc) from exc


def _find_provider_for_household(db: Session, *, provider_code: str, household_id: str | None) -> RegionProvider | None:
    if household_id is not None:
        sync_household_plugin_region_providers(db, household_id)
        provider = region_provider_registry.get(provider_code, household_id=household_id)
        if provider is not None:
            return provider
    return region_provider_registry.get(provider_code)


def _raise_provider_runtime_error(*, provider_code: str, exc: Exception) -> RegionServiceError:
    return RegionServiceError(
        detail=f"地区 provider 执行失败: {provider_code}",
        error_code="region_provider_execution_failed",
        field="provider_code",
        status_code=status.HTTP_502_BAD_GATEWAY,
    )


def _to_region_ref(value: object | None) -> RegionNodeRefRead | None:
    if not isinstance(value, dict):
        return None
    code = value.get("code")
    name = value.get("name")
    if not isinstance(code, str) or not isinstance(name, str):
        return None
    return RegionNodeRefRead(code=code, name=name)


def _extract_region_path(snapshot: dict[str, object]) -> list[str]:
    path: list[str] = []
    for key in ("province", "city", "district"):
        node_ref = _to_region_ref(snapshot.get(key))
        if node_ref is None:
            continue
        path.append(node_ref.name)
    return path


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
