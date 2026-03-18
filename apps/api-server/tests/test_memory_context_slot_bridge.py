import unittest
from unittest.mock import patch

from app.api.dependencies import ActorContext
from app.modules.memory.context_engine import build_memory_context_bundle
from app.modules.memory.schemas import MemoryContextBundleRead, MemoryContextLiveSummary, MemoryHotSummaryRead, MemoryQueryResponse


class MemoryContextSlotBridgeTests(unittest.TestCase):
    def test_build_memory_context_bundle_routes_through_context_engine_slot(self) -> None:
        actor = ActorContext(
            role="admin",
            actor_type="member",
            actor_id="member-admin-1",
            account_id="account-admin-1",
            account_type="member",
            account_status="active",
            username="admin",
            household_id="household-demo",
            member_id="member-admin-1",
            member_role="admin",
            is_authenticated=True,
        )
        expected_bundle = MemoryContextBundleRead(
            household_id="household-demo",
            requester_member_id="member-admin-1",
            capability="family_qa",
            question="今晚谁在家？",
            generated_at="2026-03-18T12:00:00Z",
            live_summary=MemoryContextLiveSummary(),
            hot_summary=MemoryHotSummaryRead(
                household_id="household-demo",
                requester_member_id="member-admin-1",
                generated_at="2026-03-18T12:00:00Z",
                total_visible_cards=0,
            ),
            query_result=MemoryQueryResponse(
                household_id="household-demo",
                requester_member_id="member-admin-1",
                total=0,
                query="今晚谁在家？",
            ),
            masked_sections=[],
            degraded=False,
        )

        with patch(
            "app.modules.memory.context_engine.invoke_slot_plugin",
            return_value=expected_bundle,
        ) as mocked_invoke:
            bundle = build_memory_context_bundle(
                object(),
                household_id="household-demo",
                actor=actor,
                requester_member_id="member-admin-1",
                question="今晚谁在家？",
            )

        self.assertEqual(expected_bundle, bundle)
        self.assertTrue(mocked_invoke.called)
        self.assertEqual("context_engine", mocked_invoke.call_args.kwargs["slot_name"])
        self.assertEqual("build_context_bundle", mocked_invoke.call_args.kwargs["operation"])
