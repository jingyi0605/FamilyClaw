import { FeaturePlaceholder } from '../../components/FeaturePlaceholder';
import { GuardedPage } from '../../runtime';

export default function MemoriesPage() {
  return (
    <GuardedPage mode="protected" path="/pages/memories/index">
      <FeaturePlaceholder
        title="记忆页壳"
        description="后面会基于共享类型和视图模型逐步迁移。"
        parityStatus="not_started"
        blockingReason="记忆数据结构已经有共享落点，但列表与纠错交互还没迁。"
      />
    </GuardedPage>
  );
}
