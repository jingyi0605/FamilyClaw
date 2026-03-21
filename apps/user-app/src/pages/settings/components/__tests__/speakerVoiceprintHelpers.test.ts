import test from 'node:test';
import assert from 'node:assert/strict';
import type {
  HouseholdVoiceprintMemberSummaryRead,
  VoiceprintEnrollmentRead,
} from '../../settingsTypes';
import {
  createVoiceprintWaitingWizardState,
  createVoiceprintWizardState,
  getNextWizardStateFromEnrollment,
  getVoiceprintConversationCopy,
  getVoiceprintEnrollmentProgressMeta,
  getVoiceprintMemberStatusMeta,
} from '../speakerVoiceprintHelpers';

function createMemberSummary(
  overrides: Partial<HouseholdVoiceprintMemberSummaryRead> = {},
): HouseholdVoiceprintMemberSummaryRead {
  return {
    member_id: 'member-1',
    member_name: '妈妈',
    member_role: 'adult',
    status: 'not_enrolled',
    sample_count: 0,
    updated_at: null,
    pending_enrollment_id: null,
    active_profile_id: null,
    error_message: null,
    ...overrides,
  };
}

function createEnrollment(
  overrides: Partial<VoiceprintEnrollmentRead> = {},
): VoiceprintEnrollmentRead {
  return {
    id: 'enrollment-1',
    household_id: 'household-1',
    member_id: 'member-1',
    terminal_id: 'device-1',
    status: 'pending',
    expected_phrase: '我是妈妈',
    sample_goal: 3,
    sample_count: 1,
    expires_at: '2026-03-16T12:00:00+08:00',
    error_code: null,
    error_message: null,
    created_at: '2026-03-16T11:00:00+08:00',
    updated_at: '2026-03-16T11:10:00+08:00',
    ...overrides,
  };
}

test('设备级文案能区分公开对话和成员路由', () => {
  const publicCopy = getVoiceprintConversationCopy(false);
  const memberCopy = getVoiceprintConversationCopy(true);

  assert.equal(publicCopy.mode, 'public');
  assert.match(publicCopy.title, /公开对话/);
  assert.ok(publicCopy.lines.some((line) => line.includes('所有家庭成员都可以看到')));

  assert.equal(memberCopy.mode, 'voiceprint_member');
  assert.match(memberCopy.title, /成员路由/);
  assert.ok(memberCopy.lines.some((line) => line.includes('识别失败时会按后端既有降级规则继续处理')));
});

test('成员状态元数据覆盖建档中、可用、失败、已停用、未建档', () => {
  assert.equal(getVoiceprintMemberStatusMeta(createMemberSummary({ status: 'pending', sample_count: 2 })).actionLabel, '查看进度');
  assert.equal(getVoiceprintMemberStatusMeta(createMemberSummary({ status: 'active', sample_count: 3 })).actionLabel, '更新声纹');
  assert.equal(getVoiceprintMemberStatusMeta(createMemberSummary({ status: 'failed', error_message: 'provider down' })).description, 'provider down');
  assert.equal(getVoiceprintMemberStatusMeta(createMemberSummary({ status: 'disabled' })).label, '已停用');
  assert.equal(getVoiceprintMemberStatusMeta(createMemberSummary({ status: 'not_enrolled' })).label, '未建档');
});

test('向导状态工厂同时支持首次录入、更新和继续查看进度', () => {
  const createWizard = createVoiceprintWizardState('create');
  const updateWizard = createVoiceprintWizardState('update', 'member-2');
  const waitingWizard = createVoiceprintWaitingWizardState('member-3', 'enrollment-3');

  assert.equal(createWizard.step, 'select_member');
  assert.equal(createWizard.lockedMemberId, null);

  assert.equal(updateWizard.step, 'confirm');
  assert.equal(updateWizard.memberId, 'member-2');
  assert.equal(updateWizard.lockedMemberId, 'member-2');

  assert.equal(waitingWizard.step, 'waiting');
  assert.equal(waitingWizard.memberId, 'member-3');
  assert.equal(waitingWizard.enrollmentId, 'enrollment-3');
});

test('等待页的当前轮次和当前进度必须使用同一套口径', () => {
  const recordingMeta = getVoiceprintEnrollmentProgressMeta(
    createEnrollment({ status: 'recording', sample_count: 2, sample_goal: 3 }),
  );
  assert.equal(recordingMeta.currentRound, 3);
  assert.equal(recordingMeta.progressCount, 3);

  const processingMeta = getVoiceprintEnrollmentProgressMeta(
    createEnrollment({ status: 'processing', sample_count: 3, sample_goal: 3 }),
  );
  assert.equal(processingMeta.currentRound, 3);
  assert.equal(processingMeta.progressCount, 3);

  const pendingMeta = getVoiceprintEnrollmentProgressMeta(
    createEnrollment({ status: 'pending', sample_count: 0, sample_goal: 3 }),
  );
  assert.equal(pendingMeta.currentRound, 1);
  assert.equal(pendingMeta.progressCount, 1);
});

test('向导状态机会把进行中、成功、失败结果映射到对应页面', () => {
  const baseState = createVoiceprintWaitingWizardState('member-1', 'enrollment-1');

  const waitingState = getNextWizardStateFromEnrollment(baseState, createEnrollment({ status: 'processing' }));
  assert.equal(waitingState.step, 'waiting');

  const successState = getNextWizardStateFromEnrollment(baseState, createEnrollment({ status: 'completed' }));
  assert.equal(successState.step, 'success');
  assert.equal(successState.error, '');

  const failedState = getNextWizardStateFromEnrollment(
    baseState,
    createEnrollment({ status: 'failed', error_message: '采样超时' }),
  );
  assert.equal(failedState.step, 'failed');
  assert.equal(failedState.error, '采样超时');
});
