from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.version_metadata import get_system_version_info

router = APIRouter(tags=["system"])


class SystemVersionRead(BaseModel):
    current_version: str
    build_channel: Literal["stable", "preview", "development"]
    build_time: str | None = None
    release_notes_url: str | None = None
    update_status: Literal["up_to_date", "update_available", "check_unavailable"]
    latest_version: str | None = None
    latest_release_notes_url: str | None = None
    latest_release_title: str | None = None
    latest_release_summary: str | None = None
    latest_release_published_at: str | None = None


@router.get("/system/version", response_model=SystemVersionRead)
def get_system_version() -> SystemVersionRead:
    version_info = get_system_version_info()
    return SystemVersionRead(
        current_version=version_info.current_version,
        build_channel=version_info.build_channel,
        build_time=version_info.build_time,
        release_notes_url=version_info.release_notes_url,
        update_status=version_info.update_status,
        latest_version=version_info.latest_version,
        latest_release_notes_url=version_info.latest_release_notes_url,
        latest_release_title=version_info.latest_release_title,
        latest_release_summary=version_info.latest_release_summary,
        latest_release_published_at=version_info.latest_release_published_at,
    )
