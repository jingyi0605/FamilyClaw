from app.modules.delivery.schemas import DeliveryPlan, DeliveryTarget
from app.modules.reminder.schemas import ReminderTaskRead


def build_delivery_plan(
    task: ReminderTaskRead,
    *,
    active_member_id: str | None = None,
) -> DeliveryPlan:
    targets: list[DeliveryTarget] = []
    member_ids = list(dict.fromkeys(task.target_member_ids))
    room_ids = list(dict.fromkeys(task.preferred_room_ids))
    channels = task.delivery_channels or ["admin_web"]

    for member_id in member_ids:
        targets.append(
            DeliveryTarget(
                member_id=member_id,
                room_id=None,
                channels=channels,
            )
        )

    if not targets and active_member_id is not None:
        targets.append(
            DeliveryTarget(
                member_id=active_member_id,
                room_id=None,
                channels=channels,
            )
        )

    for room_id in room_ids:
        targets.append(
            DeliveryTarget(
                member_id=None,
                room_id=room_id,
                channels=channels,
            )
        )

    return DeliveryPlan(
        household_id=task.household_id,
        task_id=task.id,
        strategy="members_then_rooms",
        targets=targets,
    )
