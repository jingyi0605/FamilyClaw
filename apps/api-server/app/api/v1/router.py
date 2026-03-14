from fastapi import APIRouter

from app.api.v1.endpoints.accounts import router as accounts_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.ai_config import router as ai_config_router
from app.api.v1.endpoints.ai_admin import router as ai_admin_router
from app.api.v1.endpoints.audit_logs import router as audit_logs_router
from app.api.v1.endpoints.context import router as context_router
from app.api.v1.endpoints.conversations import router as conversations_router
from app.api.v1.endpoints.device_actions import router as device_actions_router
from app.api.v1.endpoints.devices import router as devices_router
from app.api.v1.endpoints.family_qa import router as family_qa_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.households import router as households_router
from app.api.v1.endpoints.member_permissions import router as member_permissions_router
from app.api.v1.endpoints.member_preferences import router as member_preferences_router
from app.api.v1.endpoints.member_relationships import router as member_relationships_router
from app.api.v1.endpoints.members import router as members_router
from app.api.v1.endpoints.memories import router as memories_router
from app.api.v1.endpoints.reminders import router as reminders_router
from app.api.v1.endpoints.reminders import run_router as reminder_runs_router
from app.api.v1.endpoints.realtime import router as realtime_router
from app.api.v1.endpoints.regions import router as regions_router
from app.api.v1.endpoints.rooms import router as rooms_router
from app.api.v1.endpoints.scenes import router as scenes_router

router = APIRouter()
router.include_router(accounts_router)
router.include_router(auth_router)
router.include_router(ai_config_router)
router.include_router(ai_admin_router)
router.include_router(audit_logs_router)
router.include_router(context_router)
router.include_router(conversations_router)
router.include_router(device_actions_router)
router.include_router(devices_router)
router.include_router(family_qa_router)
router.include_router(health_router)
router.include_router(households_router)
router.include_router(member_relationships_router)
router.include_router(member_preferences_router)
router.include_router(member_permissions_router)
router.include_router(members_router)
router.include_router(memories_router)
router.include_router(reminders_router)
router.include_router(reminder_runs_router)
router.include_router(realtime_router)
router.include_router(regions_router)
router.include_router(rooms_router)
router.include_router(scenes_router)
