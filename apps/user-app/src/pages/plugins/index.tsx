import { FeaturePlaceholder } from '../../components/FeaturePlaceholder';
import { GuardedPage } from '../../runtime';

export default function PluginsPage() {
  return (
    <GuardedPage mode="protected" path="/pages/plugins/index">
      <FeaturePlaceholder
        title="插件页壳"
        description="插件管理属于低频但重要页面，先给稳定入口，不急着硬搬。"
        parityStatus="not_started"
        blockingReason="插件列表、挂载和任务流还在 user-web，后面等共享 API 扩完再迁。"
      />
    </GuardedPage>
  );
}
