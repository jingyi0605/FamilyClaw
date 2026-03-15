import { FeaturePlaceholder } from '../../components/FeaturePlaceholder';

export default function AssistantPage() {
  return (
    <FeaturePlaceholder
      title="助手页壳"
      description="先把实时能力接口立起来，再迁聊天页面。"
      parityStatus="not_started"
      blockingReason="当前实时连接只做了统一接口占位，没有硬搬浏览器 WebSocket 逻辑。"
    />
  );
}
