import test from 'node:test';
import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import type {
  Device,
  HouseholdVoiceprintMemberSummaryRead,
  HouseholdVoiceprintSummaryRead,
  VoiceprintEnrollmentRead,
} from '../../settingsTypes';
import { I18nProvider } from '../../../../runtime/h5-shell/i18n/I18nProvider';
import { SpeakerVoiceprintTab } from '../SpeakerVoiceprintTab';
import { VoiceprintEnrollmentWizard } from '../VoiceprintEnrollmentWizard';
import { createVoiceprintWaitingWizardState, createVoiceprintWizardState } from '../speakerVoiceprintHelpers';

function renderWithI18n(element: JSX.Element) {
  return renderToStaticMarkup(<I18nProvider>{element}</I18nProvider>);
}

function createDevice(overrides: Partial<Device> = {}): Device {
  return {
    id: 'device-1',
    household_id: 'household-1',
    room_id: 'room-1',
    name: '客厅小爱',
    device_type: 'speaker',
    vendor: 'xiaomi',
    status: 'active',
    controllable: true,
    voice_auto_takeover_enabled: true,
    voiceprint_identity_enabled: false,
    voice_takeover_prefixes: ['请'],
    created_at: '2026-03-16T10:00:00+08:00',
    updated_at: '2026-03-16T10:00:00+08:00',
    ...overrides,
  };
}

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

function createSummary(
  overrides: Partial<HouseholdVoiceprintSummaryRead> = {},
): HouseholdVoiceprintSummaryRead {
  return {
    household_id: 'household-1',
    terminal_id: 'device-1',
    voiceprint_identity_enabled: false,
    conversation_mode: 'public',
    pending_enrollment: null,
    members: [createMemberSummary()],
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
    status: 'processing',
    expected_phrase: '我是妈妈',
    sample_goal: 3,
    sample_count: 2,
    expires_at: '2026-03-16T12:00:00+08:00',
    error_code: null,
    error_message: null,
    created_at: '2026-03-16T11:00:00+08:00',
    updated_at: '2026-03-16T11:10:00+08:00',
    ...overrides,
  };
}

test('声纹标签页会展示公开对话文案、进行中任务入口和成员状态操作', () => {
  const markup = renderWithI18n(
    <SpeakerVoiceprintTab
      device={createDevice()}
      canManage
      summary={createSummary({
        pending_enrollment: {
          enrollment_id: 'enrollment-1',
          target_member_id: 'member-2',
          expected_phrase: '我是爸爸',
          sample_goal: 3,
          sample_count: 2,
          expires_at: '2026-03-16T12:00:00+08:00',
        },
        members: [
          createMemberSummary({
            member_id: 'member-2',
            member_name: '爸爸',
            status: 'pending',
            sample_count: 2,
            pending_enrollment_id: 'enrollment-1',
          }),
          createMemberSummary({
            member_id: 'member-1',
            status: 'active',
            sample_count: 3,
          }),
        ],
      })}
      loading={false}
      error=""
      switchSaving={false}
      onRetry={() => {}}
      onToggleVoiceprintEnabled={() => {}}
      onStartEnrollment={() => {}}
      onUpdateVoiceprint={() => {}}
      onResumeEnrollment={() => {}}
    />,
  );

  assert.match(markup, /当前按公开对话处理/);
  assert.match(markup, /所有家庭成员都可以看到这台设备的对话内容/);
  assert.match(markup, /查看进行中任务/);
  assert.match(markup, /继续查看进度/);
  assert.match(markup, /查看进度/);
  assert.match(markup, /更新声纹/);
});

test('声纹标签页在非管理员和局部失败时只保留只读与重试提示', () => {
  const markup = renderWithI18n(
    <SpeakerVoiceprintTab
      device={createDevice()}
      canManage={false}
      summary={null}
      loading={false}
      error="summary failed"
      switchSaving={false}
      onRetry={() => {}}
      onToggleVoiceprintEnabled={() => {}}
      onStartEnrollment={() => {}}
      onUpdateVoiceprint={() => {}}
      onResumeEnrollment={() => {}}
    />,
  );

  assert.match(markup, /你当前只有查看权限/);
  assert.match(markup, /仅管理员可录入/);
  assert.match(markup, /声纹区域加载失败/);
  assert.match(markup, /重试/);
});

test('向导会展示等待进度与更新成功文案', () => {
  const waitingMarkup = renderWithI18n(
    <VoiceprintEnrollmentWizard
      wizard={createVoiceprintWaitingWizardState('member-1', 'enrollment-1')}
      members={[createMemberSummary()]}
      deviceName="客厅小爱"
      enrollment={createEnrollment()}
      busy={false}
      onClose={() => {}}
      onCancelEnrollment={() => {}}
      onBack={() => {}}
      onSelectMember={() => {}}
      onContinue={() => {}}
      onStart={() => {}}
    />,
  );

  assert.match(waitingMarkup, /声纹录入进行中/);
  assert.match(waitingMarkup, /当前朗读内容/);
  assert.match(waitingMarkup, /我是妈妈/);
  assert.match(waitingMarkup, /第 2 \/ 3 轮/);
  assert.match(waitingMarkup, /2 \/ 3 轮样本/);
  assert.match(waitingMarkup, /音响会先倒计时，再发出滴的一声提示音/);
  assert.match(waitingMarkup, /结束本次录入/);

  const successMarkup = renderWithI18n(
    <VoiceprintEnrollmentWizard
      wizard={{ ...createVoiceprintWizardState('update', 'member-1'), step: 'success' }}
      members={[createMemberSummary()]}
      deviceName="客厅小爱"
      enrollment={null}
      busy={false}
      onClose={() => {}}
      onCancelEnrollment={() => {}}
      onBack={() => {}}
      onSelectMember={() => {}}
      onContinue={() => {}}
      onStart={() => {}}
    />,
  );

  assert.match(successMarkup, /声纹更新完成/);
  assert.match(successMarkup, /成员声纹已经更新/);
});
