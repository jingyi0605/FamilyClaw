import unittest

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.account.schemas import HouseholdAccountCreateRequest
from app.modules.account.service import (
    AuthenticatedActor,
    create_household_account_with_binding,
    ensure_pending_household_bootstrap_accounts,
)
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.plugin import set_household_plugin_enabled
from app.modules.plugin.schemas import PluginStateUpdateRequest
from app.modules.scheduler.dispatchers import dispatch_task_run
from app.modules.scheduler.schemas import ScheduledTaskDefinitionCreate, ScheduledTaskDefinitionUpdate
from app.modules.scheduler.service import (
    create_task_definition,
    process_due_schedule_tick,
    update_task_definition,
)


class SchedulerPluginStateTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()

        ensure_pending_household_bootstrap_accounts(self.db)
        self.household = create_household(
            self.db,
            HouseholdCreate(
                name="Scheduler Plugin Home",
                city="Shenzhen",
                timezone="Asia/Shanghai",
                locale="zh-CN",
            ),
        )
        self.admin_member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="调度管理员", role="admin"),
        )
        self.db.flush()
        self.admin_account, _ = create_household_account_with_binding(
            self.db,
            HouseholdAccountCreateRequest(
                household_id=self.household.id,
                member_id=self.admin_member.id,
                username=f"sp_{self.id().split('.')[-1][:24]}",
                password="admin123",
                must_change_password=False,
            ),
        )
        self.db.commit()

        self.admin_actor = AuthenticatedActor(
            account_id=self.admin_account.id,
            username=self.admin_account.username,
            account_type=self.admin_account.account_type,
            account_status=self.admin_account.status,
            household_id=self.household.id,
            member_id=self.admin_member.id,
            member_role=self.admin_member.role,
            must_change_password=False,
        )

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()

    def test_create_task_definition_rejects_disabled_plugin_target(self) -> None:
        self._disable_plugin("homeassistant")

        with self.assertRaises(HTTPException) as ctx:
            create_task_definition(
                self.db,
                actor=self.admin_actor,
                payload=ScheduledTaskDefinitionCreate(
                    household_id=self.household.id,
                    owner_scope="household",
                    code="disabled-plugin-create",
                    name="禁用插件任务",
                    trigger_type="schedule",
                    schedule_type="interval",
                    schedule_expr="60",
                    target_type="plugin_job",
                    target_ref_id="homeassistant",
                ),
                now_iso="2026-03-17T10:00:00Z",
            )

        self.assertEqual(409, ctx.exception.status_code)
        self.assertIsInstance(ctx.exception.detail, dict)
        assert isinstance(ctx.exception.detail, dict)
        self.assertEqual("plugin_disabled", ctx.exception.detail["error_code"])
        self.assertEqual("plugin_id", ctx.exception.detail["field"])

    def test_update_task_definition_rejects_disabled_plugin_target(self) -> None:
        task = create_task_definition(
            self.db,
            actor=self.admin_actor,
            payload=ScheduledTaskDefinitionCreate(
                household_id=self.household.id,
                owner_scope="household",
                code="disabled-plugin-update",
                name="待更新插件任务",
                trigger_type="schedule",
                schedule_type="interval",
                schedule_expr="60",
                target_type="plugin_job",
                target_ref_id="homeassistant",
            ),
            now_iso="2026-03-17T10:00:00Z",
        )
        self.db.commit()
        self._disable_plugin("homeassistant")

        with self.assertRaises(HTTPException) as ctx:
            update_task_definition(
                self.db,
                actor=self.admin_actor,
                task_id=task.id,
                payload=ScheduledTaskDefinitionUpdate(name="已禁用后的更新"),
                now_iso="2026-03-17T10:01:00Z",
            )

        self.assertEqual(409, ctx.exception.status_code)
        self.assertIsInstance(ctx.exception.detail, dict)
        assert isinstance(ctx.exception.detail, dict)
        self.assertEqual("plugin_disabled", ctx.exception.detail["error_code"])

    def test_dispatch_run_preserves_plugin_disabled_error_code(self) -> None:
        task = create_task_definition(
            self.db,
            actor=self.admin_actor,
            payload=ScheduledTaskDefinitionCreate(
                household_id=self.household.id,
                owner_scope="household",
                code="disabled-plugin-dispatch",
                name="运行前禁用插件",
                trigger_type="schedule",
                schedule_type="interval",
                schedule_expr="60",
                target_type="plugin_job",
                target_ref_id="homeassistant",
            ),
            now_iso="2026-03-17T10:00:00Z",
        )
        self.db.commit()

        runs = process_due_schedule_tick(self.db, now_iso="2026-03-17T10:01:00Z")
        self.db.commit()
        self.assertEqual(1, len(runs))

        self._disable_plugin("homeassistant")
        dispatched = dispatch_task_run(self.db, task_run_id=runs[0].id)
        self.db.commit()

        self.assertEqual(task.id, dispatched.task_definition_id)
        self.assertEqual("failed", dispatched.status)
        self.assertEqual("plugin_disabled", dispatched.error_code)

    def _disable_plugin(self, plugin_id: str) -> None:
        set_household_plugin_enabled(
            self.db,
            household_id=self.household.id,
            plugin_id=plugin_id,
            payload=PluginStateUpdateRequest(enabled=False),
            updated_by="test-suite",
        )
        self.db.flush()


if __name__ == "__main__":
    unittest.main()
