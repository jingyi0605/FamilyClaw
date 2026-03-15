import { FeaturePlaceholder } from '../../components/FeaturePlaceholder';

export default function FamilyPage() {
  return (
    <FeaturePlaceholder
      title="家庭页"
      description="H5 已按 user-web 正式迁移旧家庭页；当前这个文件只保留 RN / 非 H5 的安全构建页。"
      parityStatus="h5_ready"
      blockingReason="本轮按要求优先保证 H5 / PC 端 1:1 还原，RN 样式与交互后续再单独适配。"
    />
  );
}
