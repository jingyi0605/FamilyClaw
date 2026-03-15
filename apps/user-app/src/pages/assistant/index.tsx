import { FeaturePlaceholder } from '../../components/FeaturePlaceholder';
import { GuardedPage } from '../../runtime';

export default function AssistantPage() {
  return (
    <GuardedPage mode="protected" path="/pages/assistant/index">
      <FeaturePlaceholder
        title="助手页"
        description="H5 已按 user-web 正式迁移；当前文件保留给 RN 安全构建使用，不直接承接网页 DOM 和旧样式。"
        parityStatus="h5_ready"
        blockingReason="H5 已切到旧页面正式 UI，RN 端暂时保留安全壳，后续再补多端原生样式对齐。"
      />
    </GuardedPage>
  );
}
