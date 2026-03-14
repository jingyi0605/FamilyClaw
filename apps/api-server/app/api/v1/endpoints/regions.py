from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, require_authenticated_actor
from app.db.session import get_db
from app.modules.region.schemas import RegionNodeRead
from app.modules.region.service import list_region_catalog, raise_region_http_error, search_region_catalog, RegionServiceError

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("/catalog", response_model=list[RegionNodeRead])
def list_region_catalog_endpoint(
    provider_code: Annotated[str, Query(min_length=1)],
    country_code: Annotated[str, Query(min_length=1)],
    household_id: Annotated[str | None, Query()] = None,
    parent_region_code: Annotated[str | None, Query()] = None,
    admin_level: Annotated[str | None, Query()] = None,
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_authenticated_actor),
) -> list[RegionNodeRead]:
    try:
        return list_region_catalog(
            db,
            provider_code=provider_code,
            country_code=country_code,
            household_id=household_id,
            parent_region_code=parent_region_code,
            admin_level=admin_level,
        )
    except RegionServiceError as exc:
        raise raise_region_http_error(exc) from exc


@router.get("/search", response_model=list[RegionNodeRead])
def search_region_catalog_endpoint(
    provider_code: Annotated[str, Query(min_length=1)],
    country_code: Annotated[str, Query(min_length=1)],
    keyword: Annotated[str, Query()],
    household_id: Annotated[str | None, Query()] = None,
    admin_level: Annotated[str | None, Query()] = None,
    parent_region_code: Annotated[str | None, Query()] = None,
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_authenticated_actor),
) -> list[RegionNodeRead]:
    try:
        return search_region_catalog(
            db,
            provider_code=provider_code,
            country_code=country_code,
            keyword=keyword,
            household_id=household_id,
            admin_level=admin_level,
            parent_region_code=parent_region_code,
        )
    except RegionServiceError as exc:
        raise raise_region_http_error(exc) from exc
