import { FeaturePlaceholder } from '../../components/FeaturePlaceholder';

export default function FamilyPage() {
  return (
    <FeaturePlaceholder
      title="家庭页壳"
      description="家庭页会在共享状态和 API 继续抽干净之后迁入。"
      parityStatus="not_started"
      blockingReason="当前只完成了路由壳，家庭列表、房间、成员关系都还在 user-web。"
    />
  );
}
