from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select

import app.db.models
from app.db.session import SessionLocal
from app.db.utils import dump_json, new_uuid, utc_now_iso
from app.modules.audit.models import AuditLog
from app.modules.device.models import Device, DeviceBinding
from app.modules.household.models import Household
from app.modules.member.models import Member, MemberPreference
from app.modules.permission.models import MemberPermission
from app.modules.relationship.models import MemberRelationship
from app.modules.room.models import Room

SIM_PREFIX = "[模拟数据]"
SIM_NOTE = "该记录由 T024 演示种子脚本生成，仅用于本地演示与联调。"


@dataclass
class SeedSummary:
    household_id: str
    member_count: int
    relationship_count: int
    preference_count: int
    permission_count: int
    room_count: int
    device_count: int
    binding_count: int


def main() -> None:
    with SessionLocal() as db:
        existing_demo_households = list(
            db.scalars(
                select(Household).where(Household.name.like(f"{SIM_PREFIX}%"))
            ).all()
        )
        for household in existing_demo_households:
            db.delete(household)
        db.flush()

        summary = seed_mock_demo_data(db)
        db.commit()

    print(
        json.dumps(
            {
                "simulated": True,
                "note": SIM_NOTE,
                "household_id": summary.household_id,
                "member_count": summary.member_count,
                "relationship_count": summary.relationship_count,
                "preference_count": summary.preference_count,
                "permission_count": summary.permission_count,
                "room_count": summary.room_count,
                "device_count": summary.device_count,
                "binding_count": summary.binding_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def seed_mock_demo_data(db) -> SeedSummary:
    household = Household(
        id=new_uuid(),
        name=f"{SIM_PREFIX} FamilyClaw 演示家庭",
        timezone="Asia/Shanghai",
        locale="zh-CN",
        status="active",
    )
    db.add(household)
    db.flush()

    members = {
        "admin": Member(
            id=new_uuid(),
            household_id=household.id,
            name=f"{SIM_PREFIX} Alex 家庭管理员",
            nickname=f"{SIM_PREFIX} Alex",
            role="admin",
            age_group="adult",
            phone="SIM-ADMIN-0001",
            status="active",
            guardian_member_id=None,
        ),
        "parent": Member(
            id=new_uuid(),
            household_id=household.id,
            name=f"{SIM_PREFIX} Jamie 家长",
            nickname=f"{SIM_PREFIX} Jamie",
            role="adult",
            age_group="adult",
            phone="SIM-PARENT-0001",
            status="active",
            guardian_member_id=None,
        ),
        "child": Member(
            id=new_uuid(),
            household_id=household.id,
            name=f"{SIM_PREFIX} Coco 儿童",
            nickname=f"{SIM_PREFIX} Coco",
            role="child",
            age_group="child",
            phone="SIM-CHILD-0001",
            status="active",
            guardian_member_id=None,
        ),
        "elder": Member(
            id=new_uuid(),
            household_id=household.id,
            name=f"{SIM_PREFIX} Morgan 长辈",
            nickname=f"{SIM_PREFIX} Morgan",
            role="elder",
            age_group="elder",
            phone="SIM-ELDER-0001",
            status="active",
            guardian_member_id=None,
        ),
        "guest": Member(
            id=new_uuid(),
            household_id=household.id,
            name=f"{SIM_PREFIX} Taylor 访客",
            nickname=f"{SIM_PREFIX} Taylor",
            role="guest",
            age_group="adult",
            phone="SIM-GUEST-0001",
            status="inactive",
            guardian_member_id=None,
        ),
    }
    members["child"].guardian_member_id = members["parent"].id
    db.add_all(list(members.values()))
    db.flush()

    relationships = [
        MemberRelationship(
            id=new_uuid(),
            household_id=household.id,
            source_member_id=members["admin"].id,
            target_member_id=members["parent"].id,
            relation_type="spouse",
            visibility_scope="family",
            delegation_scope="device",
        ),
        MemberRelationship(
            id=new_uuid(),
            household_id=household.id,
            source_member_id=members["parent"].id,
            target_member_id=members["child"].id,
            relation_type="parent",
            visibility_scope="family",
            delegation_scope="reminder",
        ),
        MemberRelationship(
            id=new_uuid(),
            household_id=household.id,
            source_member_id=members["admin"].id,
            target_member_id=members["child"].id,
            relation_type="guardian",
            visibility_scope="family",
            delegation_scope="device",
        ),
        MemberRelationship(
            id=new_uuid(),
            household_id=household.id,
            source_member_id=members["parent"].id,
            target_member_id=members["elder"].id,
            relation_type="caregiver",
            visibility_scope="private",
            delegation_scope="health",
        ),
    ]
    db.add_all(relationships)

    preferences = [
        MemberPreference(
            member_id=members["admin"].id,
            preferred_name=f"{SIM_PREFIX} 管理员",
            light_preference=dump_json({"brightness": 80, "mode": "warm"}),
            climate_preference=dump_json({"target_temperature": 25, "mode": "cool"}),
            content_preference=dump_json({"news_topics": ["科技", "家庭自动化"]}),
            reminder_channel_preference=dump_json(["mobile", "speaker"]),
            sleep_schedule=dump_json({"weekday": "23:00", "weekend": "23:30"}),
        ),
        MemberPreference(
            member_id=members["child"].id,
            preferred_name=f"{SIM_PREFIX} 小朋友",
            light_preference=dump_json({"brightness": 35, "mode": "soft"}),
            climate_preference=dump_json({"target_temperature": 26, "mode": "auto"}),
            content_preference=dump_json({"favorites": ["故事", "儿歌"]}),
            reminder_channel_preference=dump_json(["speaker", "screen"]),
            sleep_schedule=dump_json({"weekday": "21:00", "weekend": "21:30"}),
        ),
        MemberPreference(
            member_id=members["elder"].id,
            preferred_name=f"{SIM_PREFIX} 长辈",
            light_preference=dump_json({"brightness": 60, "mode": "natural"}),
            climate_preference=dump_json({"target_temperature": 27, "mode": "auto"}),
            content_preference=dump_json({"favorites": ["天气", "健康提醒"]}),
            reminder_channel_preference=dump_json(["speaker"]),
            sleep_schedule=dump_json({"weekday": "22:00", "weekend": "22:00"}),
        ),
    ]
    db.add_all(preferences)

    permissions = [
        MemberPermission(
            id=new_uuid(),
            household_id=household.id,
            member_id=members["admin"].id,
            resource_type="device",
            resource_scope="family",
            action="manage",
            effect="allow",
        ),
        MemberPermission(
            id=new_uuid(),
            household_id=household.id,
            member_id=members["admin"].id,
            resource_type="scenario",
            resource_scope="family",
            action="manage",
            effect="allow",
        ),
        MemberPermission(
            id=new_uuid(),
            household_id=household.id,
            member_id=members["child"].id,
            resource_type="device",
            resource_scope="self",
            action="read",
            effect="allow",
        ),
        MemberPermission(
            id=new_uuid(),
            household_id=household.id,
            member_id=members["child"].id,
            resource_type="photo",
            resource_scope="family",
            action="read",
            effect="deny",
        ),
        MemberPermission(
            id=new_uuid(),
            household_id=household.id,
            member_id=members["elder"].id,
            resource_type="health",
            resource_scope="self",
            action="read",
            effect="allow",
        ),
        MemberPermission(
            id=new_uuid(),
            household_id=household.id,
            member_id=members["guest"].id,
            resource_type="device",
            resource_scope="public",
            action="read",
            effect="allow",
        ),
    ]
    db.add_all(permissions)

    rooms = {
        "living_room": Room(
            id=new_uuid(),
            household_id=household.id,
            name=f"{SIM_PREFIX} 客厅",
            room_type="living_room",
            privacy_level="public",
        ),
        "bedroom": Room(
            id=new_uuid(),
            household_id=household.id,
            name=f"{SIM_PREFIX} 主卧",
            room_type="bedroom",
            privacy_level="private",
        ),
        "study": Room(
            id=new_uuid(),
            household_id=household.id,
            name=f"{SIM_PREFIX} 书房",
            room_type="study",
            privacy_level="private",
        ),
        "entrance": Room(
            id=new_uuid(),
            household_id=household.id,
            name=f"{SIM_PREFIX} 玄关",
            room_type="entrance",
            privacy_level="sensitive",
        ),
    }
    db.add_all(list(rooms.values()))
    db.flush()

    devices = {
        "living_light": Device(
            id=new_uuid(),
            household_id=household.id,
            room_id=rooms["living_room"].id,
            name=f"{SIM_PREFIX} 客厅主灯",
            device_type="light",
            vendor="ha",
            status="active",
            controllable=1,
        ),
        "bedroom_ac": Device(
            id=new_uuid(),
            household_id=household.id,
            room_id=rooms["bedroom"].id,
            name=f"{SIM_PREFIX} 主卧空调",
            device_type="ac",
            vendor="ha",
            status="active",
            controllable=1,
        ),
        "study_curtain": Device(
            id=new_uuid(),
            household_id=household.id,
            room_id=rooms["study"].id,
            name=f"{SIM_PREFIX} 书房窗帘",
            device_type="curtain",
            vendor="ha",
            status="active",
            controllable=1,
        ),
        "entrance_lock": Device(
            id=new_uuid(),
            household_id=household.id,
            room_id=rooms["entrance"].id,
            name=f"{SIM_PREFIX} 玄关门锁",
            device_type="lock",
            vendor="xiaomi",
            status="active",
            controllable=1,
        ),
        "living_sensor": Device(
            id=new_uuid(),
            household_id=household.id,
            room_id=rooms["living_room"].id,
            name=f"{SIM_PREFIX} 客厅温湿度传感器",
            device_type="sensor",
            vendor="xiaomi",
            status="active",
            controllable=0,
        ),
        "living_speaker": Device(
            id=new_uuid(),
            household_id=household.id,
            room_id=rooms["living_room"].id,
            name=f"{SIM_PREFIX} 家庭音箱",
            device_type="speaker",
            vendor="xiaomi",
            status="active",
            controllable=1,
        ),
    }
    db.add_all(list(devices.values()))
    db.flush()

    bindings = [
        DeviceBinding(
            id=new_uuid(),
            device_id=devices["living_light"].id,
            platform="home_assistant",
            external_entity_id="mock.light.demo_living_room_main",
            external_device_id="mock-ha-device-001",
            capabilities=dump_json({"simulated": True, "note": SIM_NOTE, "domain": "light"}),
            last_sync_at=utc_now_iso(),
        ),
        DeviceBinding(
            id=new_uuid(),
            device_id=devices["bedroom_ac"].id,
            platform="home_assistant",
            external_entity_id="mock.climate.demo_bedroom_ac",
            external_device_id="mock-ha-device-002",
            capabilities=dump_json({"simulated": True, "note": SIM_NOTE, "domain": "climate"}),
            last_sync_at=utc_now_iso(),
        ),
        DeviceBinding(
            id=new_uuid(),
            device_id=devices["entrance_lock"].id,
            platform="xiaomi",
            external_entity_id="mock.lock.demo_entrance_lock",
            external_device_id="mock-mi-device-001",
            capabilities=dump_json({"simulated": True, "note": SIM_NOTE, "domain": "lock"}),
            last_sync_at=utc_now_iso(),
        ),
    ]
    db.add_all(bindings)

    audit_log = AuditLog(
        id=new_uuid(),
        household_id=household.id,
        actor_type="system",
        actor_id=None,
        action="seed.mock_data",
        target_type="household",
        target_id=household.id,
        result="success",
        details=dump_json(
            {
                "simulated": True,
                "note": SIM_NOTE,
                "generated_at": utc_now_iso(),
                "seed_version": "t024-v1",
            }
        ),
    )
    db.add(audit_log)

    return SeedSummary(
        household_id=household.id,
        member_count=len(members),
        relationship_count=len(relationships),
        preference_count=len(preferences),
        permission_count=len(permissions),
        room_count=len(rooms),
        device_count=len(devices),
        binding_count=len(bindings),
    )


if __name__ == "__main__":
    main()

