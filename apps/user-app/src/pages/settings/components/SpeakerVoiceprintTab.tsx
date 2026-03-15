import { ToggleSwitch } from '../../family/base';
import type {
  Device,
  HouseholdVoiceprintSummaryRead,
} from '../settingsTypes';
import {
  formatVoiceprintTime,
  getVoiceprintConversationCopy,
  getVoiceprintMemberStatusMeta,
} from './speakerVoiceprintHelpers';

function formatMemberRole(role: string) {
  switch (role) {
    case 'admin':
      return '管理员';
    case 'elder':
      return '长辈';
    case 'child':
      return '儿童';
    case 'guest':
      return '访客';
    default:
      return '家庭成员';
  }
}

export function SpeakerVoiceprintTab(props: {
  device: Device;
  canManage: boolean;
  summary: HouseholdVoiceprintSummaryRead | null;
  loading: boolean;
  error: string;
  switchSaving: boolean;
  onRetry: () => void;
  onToggleVoiceprintEnabled: (nextValue: boolean) => void;
  onStartEnrollment: (memberId?: string) => void;
  onUpdateVoiceprint: (memberId: string) => void;
  onResumeEnrollment: (enrollmentId: string, memberId: string) => void;
}) {
  const voiceprintEnabled = props.summary?.voiceprint_identity_enabled ?? props.device.voiceprint_identity_enabled;
  const conversationCopy = getVoiceprintConversationCopy(voiceprintEnabled);
  const pendingEnrollment = props.summary?.pending_enrollment ?? null;
  const canOpenWizard = props.canManage && !props.loading && !props.error && Boolean(props.summary) && (props.summary?.members.length ?? 0) > 0;
  const headerActionLabel = pendingEnrollment ? '查看进行中任务' : '开始录入';

  return (
    <div className="speaker-voiceprint-tab">
      <div className="speaker-device-detail-dialog__panel">
        <div className="speaker-device-detail-dialog__panel-header">
          <h4>设备级身份策略</h4>
          <p>这一块决定这台设备是按公开对话处理，还是优先按声纹识别成员并路由到对应成员对话。</p>
        </div>
        <div className="speaker-device-detail-dialog__toggle-card">
          <ToggleSwitch
            checked={voiceprintEnabled}
            label="开启声纹识别"
            description={props.canManage ? '打开后，这台设备会优先按声纹识别成员；关闭后按公开对话处理。' : '你当前只有查看权限，不能修改这台设备的声纹策略。'}
            onChange={props.onToggleVoiceprintEnabled}
            disabled={props.switchSaving || !props.canManage}
          />
        </div>
        <div className="speaker-voiceprint-tab__strategy-card">
          <span className={`badge badge--${conversationCopy.mode === 'voiceprint_member' ? 'success' : 'secondary'}`}>
            {conversationCopy.title}
          </span>
          <ul className="speaker-voiceprint-tab__strategy-list">
            {conversationCopy.lines.map((line) => <li key={line}>{line}</li>)}
          </ul>
        </div>
      </div>

      <div className="speaker-device-detail-dialog__panel">
        <div className="speaker-device-detail-dialog__panel-header">
          <h4>家庭成员声纹状态</h4>
          <p>先看清谁还没建档、谁在处理中、谁已经可用，再决定要不要发起首次录入或更新。</p>
        </div>
        <div className="speaker-voiceprint-tab__header-actions">
          <button
            className="btn btn--outline btn--sm"
            type="button"
            onClick={() => (pendingEnrollment ? props.onResumeEnrollment(pendingEnrollment.enrollment_id, pendingEnrollment.target_member_id) : props.onStartEnrollment())}
            disabled={!props.canManage || (!pendingEnrollment && !canOpenWizard)}
          >
            {props.canManage ? headerActionLabel : '仅管理员可录入'}
          </button>
        </div>

        {props.loading ? <div className="speaker-voiceprint-tab__empty">正在加载声纹状态…</div> : null}
        {!props.loading && props.error ? (
          <div className="speaker-voiceprint-tab__error-card">
            <strong>声纹区域加载失败</strong>
            <p>{props.error}</p>
            <button className="btn btn--outline btn--sm" type="button" onClick={props.onRetry}>重试</button>
          </div>
        ) : null}

        {!props.loading && !props.error && props.summary?.pending_enrollment ? (
          <div className="speaker-voiceprint-tab__pending-banner">
            <span className="badge badge--info">有进行中的录入任务</span>
            <p>当前设备还有一条未完成的建档任务，样本进度 {props.summary.pending_enrollment.sample_count} / {props.summary.pending_enrollment.sample_goal}。</p>
            {props.canManage ? (
              <div className="speaker-voiceprint-tab__pending-actions">
                <button
                  className="btn btn--outline btn--sm"
                  type="button"
                  onClick={() => props.onResumeEnrollment(props.summary!.pending_enrollment!.enrollment_id, props.summary!.pending_enrollment!.target_member_id)}
                >
                  继续查看进度
                </button>
              </div>
            ) : null}
          </div>
        ) : null}

        {!props.loading && !props.error ? (
          <div className="speaker-voiceprint-tab__member-list">
            {props.summary?.members.map((member) => {
              const meta = getVoiceprintMemberStatusMeta(member);
              return (
                <div key={member.member_id} className="speaker-voiceprint-tab__member-card">
                  <div className="speaker-voiceprint-tab__member-header">
                    <div>
                      <strong>{member.member_name}</strong>
                      <span>{formatMemberRole(member.member_role)}</span>
                    </div>
                    <span className={`badge badge--${meta.tone}`}>{meta.label}</span>
                  </div>
                  <p className="speaker-voiceprint-tab__member-desc">{meta.description}</p>
                  <div className="speaker-voiceprint-tab__member-meta">
                    <span>最近更新：{formatVoiceprintTime(member.updated_at)}</span>
                    <span>样本轮数：{member.sample_count}</span>
                  </div>
                  <div className="speaker-voiceprint-tab__member-actions">
                    <button
                      className="btn btn--outline btn--sm"
                      type="button"
                      onClick={() => {
                        if (member.status === 'pending' && member.pending_enrollment_id) {
                          props.onResumeEnrollment(member.pending_enrollment_id, member.member_id);
                          return;
                        }
                        if (member.status === 'active') {
                          props.onUpdateVoiceprint(member.member_id);
                          return;
                        }
                        props.onStartEnrollment(member.member_id);
                      }}
                      disabled={!props.canManage || (member.status === 'pending' ? !member.pending_enrollment_id : meta.disabled)}
                    >
                      {props.canManage ? meta.actionLabel : '仅管理员可操作'}
                    </button>
                    {member.error_message ? <span className="speaker-voiceprint-tab__member-error">{member.error_message}</span> : null}
                  </div>
                </div>
              );
            })}
          </div>
        ) : null}

        {!props.loading && !props.error && props.summary && props.summary.members.length === 0 ? (
          <div className="speaker-voiceprint-tab__empty">当前家庭还没有可展示的成员。</div>
        ) : null}
      </div>
    </div>
  );
}
