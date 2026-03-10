from fastapi import APIRouter

from app.api.v1.endpoints.audit_logs import router as audit_logs_router
from app.api.v1.endpoints.context import router as context_router
from app.api.v1.endpoints.device_actions import router as device_actions_router
from app.api.v1.endpoints.devices import router as devices_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.households import router as households_router
from app.api.v1.endpoints.member_permissions import router as member_permissions_router
from app.api.v1.endpoints.member_preferences import router as member_preferences_router
from app.api.v1.endpoints.member_relationships import router as member_relationships_router
from app.api.v1.endpoints.members import router as members_router
from app.api.v1.endpoints.rooms import router as rooms_router

router = APIRouter()
router.include_router(audit_logs_router)
router.include_router(context_router)
router.include_router(device_actions_router)
router.include_router(devices_router)
router.include_router(health_router)
router.include_router(households_router)
router.include_router(member_relationships_router)
router.include_router(member_preferences_router)
router.include_router(member_permissions_router)
router.include_router(members_router)
router.include_router(rooms_router)
