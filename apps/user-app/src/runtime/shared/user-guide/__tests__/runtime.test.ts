import test from 'node:test';
import assert from 'node:assert/strict';
import type { UserGuideManifest } from '@familyclaw/user-core';
import {
  beginGuideCompletion,
  createGuideSession,
  filterGuideSteps,
  markGuideAnchorResolved,
  moveGuideSession,
  restoreGuideSession,
  shouldAutoStartGuide,
  syncGuideSessionRoute,
} from '../runtime';

const manifest: UserGuideManifest = {
  version: 1,
  steps: [
    {
      step_id: 'home',
      route: '/pages/home/index',
      anchor_id: null,
      title_key: 'home.title',
      content_key: 'home.content',
      placement: 'center',
      required_role: null,
      optional: false,
      runtime_targets: ['h5', 'rn'],
    },
    {
      step_id: 'admin-only',
      route: '/pages/settings/index',
      anchor_id: 'settings-entry',
      title_key: 'settings.title',
      content_key: 'settings.content',
      placement: 'right',
      required_role: 'admin',
      optional: false,
      runtime_targets: ['h5'],
    },
  ],
};

test('filterGuideSteps 会按角色和运行时过滤共享脚本', () => {
  const adminSteps = filterGuideSteps(manifest, {
    memberRole: 'admin',
    runtimeTarget: 'h5',
  });
  assert.equal(adminSteps.length, 2);

  const memberSteps = filterGuideSteps(manifest, {
    memberRole: 'adult',
    runtimeTarget: 'rn',
  });
  assert.deepEqual(memberSteps.map((step) => step.step_id), ['home']);
});

test('createGuideSession 会根据当前路由决定是展示还是导航', () => {
  const session = createGuideSession(manifest, {
    memberRole: 'admin',
    runtimeTarget: 'h5',
    currentRoute: '/pages/home/index',
    source: 'manual',
  });
  assert.ok(session);
  assert.equal(session.status, 'showing');
  assert.equal(session.pendingRoute, null);

  const navigatingSession = createGuideSession(manifest, {
    memberRole: 'admin',
    runtimeTarget: 'h5',
    currentRoute: '/pages/family/index',
    source: 'manual',
  });
  assert.ok(navigatingSession);
  assert.equal(navigatingSession.status, 'navigating');
  assert.equal(navigatingSession.pendingRoute, '/pages/home/index');
});

test('moveGuideSession 和 markGuideAnchorResolved 能表达阶段 1 需要的状态流转', () => {
  const session = createGuideSession(manifest, {
    memberRole: 'admin',
    runtimeTarget: 'h5',
    currentRoute: '/pages/home/index',
    source: 'manual',
  });
  assert.ok(session);

  const nextSession = moveGuideSession(session, 'next', '/pages/home/index');
  assert.equal(nextSession.status, 'navigating');
  assert.equal(nextSession.pendingRoute, '/pages/settings/index');

  const routedSession = syncGuideSessionRoute(nextSession, '/pages/settings/index');
  assert.equal(routedSession.status, 'waiting_anchor');
  assert.equal(routedSession.waitingAnchorId, 'settings-entry');

  const showingSession = markGuideAnchorResolved(routedSession);
  assert.equal(showingSession.status, 'showing');

  const completingSession = beginGuideCompletion(showingSession);
  assert.equal(completingSession.status, 'completing');
});

test('restoreGuideSession 会在刷新后恢复到最近一步', () => {
  const restoredSession = restoreGuideSession(manifest, {
    memberRole: 'admin',
    runtimeTarget: 'h5',
    currentRoute: '/pages/settings/index',
  }, {
    currentStepIndex: 1,
    source: 'auto_after_setup',
  });

  assert.ok(restoredSession);
  assert.equal(restoredSession.currentStepIndex, 1);
  assert.equal(restoredSession.status, 'waiting_anchor');
  assert.equal(restoredSession.waitingAnchorId, 'settings-entry');
});

test('shouldAutoStartGuide 只在刚完成初始化且版本未完成时返回 true', () => {
  assert.equal(
    shouldAutoStartGuide(
      { member_id: 'member-001', user_app_guide_version: null, updated_at: null },
      1,
      { justCompletedSetup: true },
    ),
    true,
  );
  assert.equal(
    shouldAutoStartGuide(
      { member_id: 'member-001', user_app_guide_version: 1, updated_at: '2026-03-19T23:20:00Z' },
      1,
      { justCompletedSetup: true },
    ),
    false,
  );
  assert.equal(
    shouldAutoStartGuide(
      { member_id: 'member-001', user_app_guide_version: null, updated_at: null },
      1,
      { justCompletedSetup: false },
    ),
    false,
  );
});
