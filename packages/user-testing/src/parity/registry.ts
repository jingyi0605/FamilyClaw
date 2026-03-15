import { FeatureParityItem } from '@familyclaw/user-core';

export type FeatureParityRegistry = {
  generatedAt: string;
  freezeRule: string;
  items: FeatureParityItem[];
};

export function countParityItems(registry: FeatureParityRegistry) {
  return registry.items.reduce<Record<FeatureParityItem['status'], number>>(
    (summary, item) => {
      summary[item.status] += 1;
      return summary;
    },
    {
      blocked: 0,
      dropped: 0,
      in_progress: 0,
      not_started: 0,
      ready: 0,
    },
  );
}
