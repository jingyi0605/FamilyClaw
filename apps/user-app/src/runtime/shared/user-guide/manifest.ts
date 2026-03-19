import type { UserGuideManifest } from '@familyclaw/user-core';
import { USER_GUIDE_ANCHOR_IDS } from './constants';

// 阶段 2 开始把共享脚本接到真实页面锚点上，跨端仍然只维护这一份主链路。
export const USER_APP_GUIDE_VERSION = 1;

export const userAppGuideManifestV1: UserGuideManifest = {
  version: USER_APP_GUIDE_VERSION,
  steps: [
    {
      step_id: 'home-overview',
      route: '/pages/home/index',
      anchor_id: USER_GUIDE_ANCHOR_IDS.homeOverview,
      title_key: 'userGuide.home.title',
      content_key: 'userGuide.home.content',
      placement: 'auto',
      required_role: null,
      optional: false,
      runtime_targets: ['h5', 'rn'],
    },
    {
      step_id: 'family-overview',
      route: '/pages/family/index',
      anchor_id: USER_GUIDE_ANCHOR_IDS.familyOverview,
      title_key: 'userGuide.family.title',
      content_key: 'userGuide.family.content',
      placement: 'center',
      required_role: null,
      optional: false,
      runtime_targets: ['h5', 'rn'],
    },
    {
      step_id: 'assistant-overview',
      route: '/pages/assistant/index',
      anchor_id: USER_GUIDE_ANCHOR_IDS.assistantOverview,
      title_key: 'userGuide.assistant.title',
      content_key: 'userGuide.assistant.content',
      placement: 'center',
      required_role: null,
      optional: false,
      runtime_targets: ['h5', 'rn'],
    },
    {
      step_id: 'memories-overview',
      route: '/pages/memories/index',
      anchor_id: USER_GUIDE_ANCHOR_IDS.memoriesOverview,
      title_key: 'userGuide.memories.title',
      content_key: 'userGuide.memories.content',
      placement: 'auto',
      required_role: null,
      optional: false,
      runtime_targets: ['h5', 'rn'],
    },
    {
      step_id: 'settings-overview',
      route: '/pages/settings/index',
      anchor_id: USER_GUIDE_ANCHOR_IDS.settingsReplay,
      title_key: 'userGuide.settings.title',
      content_key: 'userGuide.settings.content',
      placement: 'auto',
      required_role: null,
      optional: false,
      runtime_targets: ['h5', 'rn'],
    },
  ],
};
