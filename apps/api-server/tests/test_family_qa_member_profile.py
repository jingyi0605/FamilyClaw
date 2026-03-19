import unittest
from datetime import date

from app.modules.context.schemas import ContextOverviewDeviceSummary
from app.modules.family_qa.schemas import (
    QaFactMemberProfile,
    QaFactMemberRelationship,
    QaFactViewRead,
    QaMemorySummary,
    QaPermissionScope,
    QaReminderSummary,
    QaSceneSummary,
)
from app.modules.family_qa.service import _answer_from_fact_view


class FamilyQaMemberProfileTests(unittest.TestCase):
    def test_answer_from_fact_view_returns_member_age(self) -> None:
        fact_view = self._build_fact_view()
        expected_age = date.today().year - 2018
        if (date.today().month, date.today().day) < (3, 20):
            expected_age -= 1

        answer_type, answer_text, confidence, facts, suggestions = _answer_from_fact_view(
            fact_view,
            "朵朵现在多大了？",
        )

        self.assertEqual("member_profile", answer_type)
        self.assertIn(f"{expected_age} 岁", answer_text)
        self.assertIn("2018-03-20", answer_text)
        self.assertGreaterEqual(confidence, 0.95)
        self.assertEqual("member_profile", facts[0].type)
        self.assertIn("查看家庭成员", suggestions)

    def test_answer_from_fact_view_returns_member_relationship(self) -> None:
        fact_view = self._build_fact_view()

        answer_type, answer_text, confidence, facts, suggestions = _answer_from_fact_view(
            fact_view,
            "你知道朵朵和我什么关系吗？",
        )

        self.assertEqual("member_relationship", answer_type)
        self.assertIn("朵朵是你的女儿", answer_text)
        self.assertGreaterEqual(confidence, 0.95)
        self.assertEqual("member_relationship", facts[0].type)
        self.assertIn("查看家庭关系", suggestions)

    def _build_fact_view(self) -> QaFactViewRead:
        return QaFactViewRead(
            household_id="household-1",
            generated_at="2026-03-19T17:00:00Z",
            requester_member_id="member-owner",
            active_member=None,
            member_states=[],
            member_profiles=[
                QaFactMemberProfile(
                    member_id="member-owner",
                    name="杰哥",
                    aliases=["杰哥", "张杰"],
                    role="admin",
                    gender="male",
                    age_group="adult",
                    age_group_label="成人",
                    birthday="1990-01-01",
                    age_years=36,
                    preferred_name="杰哥",
                    guardian_member_id=None,
                    guardian_name=None,
                    relationships=[
                        QaFactMemberRelationship(
                            target_member_id="member-duoduo",
                            target_member_name="朵朵",
                            relation_type="father",
                            relation_label="爸爸",
                        )
                    ],
                ),
                QaFactMemberProfile(
                    member_id="member-duoduo",
                    name="朵朵",
                    aliases=["朵朵"],
                    role="child",
                    gender="female",
                    age_group="child",
                    age_group_label="儿童",
                    birthday="2018-03-20",
                    age_years=self._expected_child_age(),
                    preferred_name="朵朵",
                    guardian_member_id="member-owner",
                    guardian_name="杰哥",
                    relationships=[
                        QaFactMemberRelationship(
                            target_member_id="member-owner",
                            target_member_name="杰哥",
                            relation_type="daughter",
                            relation_label="女儿",
                        )
                    ],
                ),
            ],
            room_occupancy=[],
            device_summary=ContextOverviewDeviceSummary(
                total=0,
                active=0,
                offline=0,
                inactive=0,
                controllable=0,
                controllable_active=0,
                controllable_offline=0,
            ),
            device_states=[],
            reminder_summary=QaReminderSummary(total_tasks=0, enabled_tasks=0, pending_runs=0, recent_items=[]),
            scene_summary=QaSceneSummary(total_templates=0, enabled_templates=0, running_executions=0, recent_items=[]),
            memory_summary=QaMemorySummary(),
            permission_scope=QaPermissionScope(
                requester_member_id="member-owner",
                requester_role="admin",
                can_view_member_details=True,
                visible_member_ids=["member-owner", "member-duoduo"],
                visible_room_ids=[],
            ),
        )

    def _expected_child_age(self) -> int:
        today = date.today()
        age_years = today.year - 2018
        if (today.month, today.day) < (3, 20):
            age_years -= 1
        return age_years


if __name__ == "__main__":
    unittest.main()
