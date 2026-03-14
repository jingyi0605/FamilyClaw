from dataclasses import dataclass
from hashlib import sha256

CAPABILITY_DESCRIPTOR_VERSION = "20260314-v1"


@dataclass(frozen=True)
class CapabilityDescriptor:
    descriptor_id: str
    primary_text: str
    examples: tuple[str, ...]
    negative_examples: tuple[str, ...] = ()
    lane: str | None = None
    proposal_kind: str | None = None

    def build_document(self) -> str:
        parts = [self.primary_text.strip()]
        if self.examples:
            parts.append("典型表达：" + "；".join(item.strip() for item in self.examples if item.strip()))
        if self.negative_examples:
            parts.append("不要误判成：" + "；".join(item.strip() for item in self.negative_examples if item.strip()))
        return "\n".join(parts)


LANE_DESCRIPTORS: tuple[CapabilityDescriptor, ...] = (
    CapabilityDescriptor(
        descriptor_id="fast_action.device_control",
        lane="fast_action",
        primary_text="用户要求立刻执行带副作用的设备或场景动作，需要快速执行和快速回执。",
        examples=(
            "把客厅灯关掉",
            "打开卧室空调",
            "立刻停止扫地机器人",
            "帮我执行离家模式",
            "把书房窗帘拉开",
            "把门锁锁上",
        ),
        negative_examples=(
            "现在客厅灯亮着吗",
            "我喜欢暖一点的灯光",
            "记住我怕黑",
        ),
    ),
    CapabilityDescriptor(
        descriptor_id="realtime_query.state_query",
        lane="realtime_query",
        primary_text="用户要查询当前家庭状态、设备状态或结构化事实，不要求立刻触发副作用动作。",
        examples=(
            "现在家里有人吗",
            "客厅温度是多少",
            "门锁现在锁了吗",
            "今天谁在家",
            "洗衣机现在什么状态",
            "还有哪些提醒没完成",
        ),
        negative_examples=(
            "帮我把客厅灯打开",
            "以后提醒我时先发消息",
            "记住我不吃香菜",
        ),
    ),
    CapabilityDescriptor(
        descriptor_id="free_chat.normal_chat",
        lane="free_chat",
        primary_text="普通闲聊、陪伴对话、开放式问答和故事请求，不需要实时取数或立即执行动作。",
        examples=(
            "给我讲个睡前故事",
            "你今天心情怎么样",
            "陪我聊会天",
            "我最近有点累",
            "你觉得春天适合去哪玩",
            "讲一个科幻笑话",
        ),
        negative_examples=(
            "把客厅灯关掉",
            "现在家里有人吗",
            "明天早上八点提醒我开会",
        ),
    ),
)

PROPOSAL_DESCRIPTORS: tuple[CapabilityDescriptor, ...] = (
    CapabilityDescriptor(
        descriptor_id="proposal.memory_candidate",
        proposal_kind="memory_write",
        primary_text="用户透露长期稳定偏好、关系、习惯或事实，适合形成长期记忆提案。",
        examples=(
            "记住我早餐只喝无糖豆浆",
            "我对花生过敏",
            "以后买咖啡给我点燕麦奶",
            "我周末通常会带孩子去公园",
            "我最喜欢蓝色的杯子",
        ),
        negative_examples=(
            "把客厅灯关掉",
            "现在门锁锁了吗",
            "明天提醒我交电费",
        ),
    ),
    CapabilityDescriptor(
        descriptor_id="proposal.config_candidate",
        proposal_kind="config_apply",
        primary_text="用户表达系统以后应该怎么工作、怎么称呼、怎么通知，适合形成配置提案。",
        examples=(
            "以后提醒我时先发消息再语音",
            "把我的称呼改成爸爸",
            "晚上十点后别播报提醒",
            "默认先告诉我结论再展开细节",
            "以后设备异常先通知我老婆",
        ),
        negative_examples=(
            "记住我喜欢喝热水",
            "现在空调开着吗",
            "帮我把窗帘拉开",
        ),
    ),
    CapabilityDescriptor(
        descriptor_id="proposal.reminder_candidate",
        proposal_kind="reminder_create",
        primary_text="用户表达未来时间点要做的事，适合先形成提醒草稿提案，而不是抢占主聊天回复。",
        examples=(
            "明天早上八点提醒我开会",
            "周五记得交电费",
            "晚上九点提醒孩子刷牙",
            "下周一提醒我给妈妈打电话",
            "下午三点提醒我收快递",
        ),
        negative_examples=(
            "记住我喜欢早睡",
            "现在谁在家",
            "把客厅灯打开",
        ),
    ),
)


def get_lane_descriptors() -> tuple[CapabilityDescriptor, ...]:
    return LANE_DESCRIPTORS


def get_proposal_descriptors() -> tuple[CapabilityDescriptor, ...]:
    return PROPOSAL_DESCRIPTORS


def get_all_descriptors() -> tuple[CapabilityDescriptor, ...]:
    return (*LANE_DESCRIPTORS, *PROPOSAL_DESCRIPTORS)


def get_descriptor_document_hash(descriptors: tuple[CapabilityDescriptor, ...] | list[CapabilityDescriptor]) -> str:
    payload = "|".join(
        f"{descriptor.descriptor_id}:{descriptor.build_document()}"
        for descriptor in sorted(descriptors, key=lambda item: item.descriptor_id)
    )
    return sha256(f"{CAPABILITY_DESCRIPTOR_VERSION}|{payload}".encode("utf-8")).hexdigest()
