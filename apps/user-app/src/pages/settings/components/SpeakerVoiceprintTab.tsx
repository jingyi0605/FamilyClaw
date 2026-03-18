import { useI18n } from '../../../runtime/h5-shell/i18n/I18nProvider';
import type {
  Device,
  HouseholdVoiceprintSummaryRead,
} from '../settingsTypes';
import {
  formatVoiceprintTime,
  getVoiceprintConversationCopy,
  getVoiceprintMemberStatusMeta,
} from './speakerVoiceprintHelpers';
import { VoiceprintEmptyState, VoiceprintToggleSwitch } from './VoiceprintSharedBlocks';

function formatMemberRole(role: string) {
  switch (role) {
    case 'admin':
      return 'voiceprint.wizard.member.admin';
    case 'elder':
      return 'voiceprint.wizard.member.elder';
    case 'child':
      return 'voiceprint.wizard.member.child';
    case 'guest':
      return 'voiceprint.memberRole.guest';
    default:
      return 'voiceprint.wizard.member.default';
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
  const { t, locale } = useI18n();
  const voiceprintEnabled = props.summary?.voiceprint_identity_enabled ?? props.device.voiceprint_identity_enabled;
  const conversationCopy = getVoiceprintConversationCopy(voiceprintEnabled, t);
  const pendingEnrollment = props.summary?.pending_enrollment ?? null;
  const canOpenWizard = props.canManage && !props.loading && !props.error && Boolean(props.summary) && (props.summary?.members.length ?? 0) > 0;
  const headerActionLabel = pendingEnrollment ? t('voiceprint.tab.headerAction.pending') : t('voiceprint.tab.headerAction.start');

  return (
    <div className="speaker-voiceprint-tab">
      <div className="speaker-device-detail-dialog__panel">
        <div className="speaker-device-detail-dialog__panel-header">
          <h4>{t('voiceprint.tab.strategyTitle')}</h4>
          <p>{t('voiceprint.tab.strategyDesc')}</p>
        </div>
        <div className="speaker-device-detail-dialog__toggle-card">
          <VoiceprintToggleSwitch
            checked={voiceprintEnabled}
            label={t('voiceprint.tab.toggleLabel')}
            description={props.canManage ? t('voiceprint.tab.toggleDescEnabled') : t('voiceprint.tab.toggleDescReadonly')}
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
          <h4>{t('voiceprint.tab.memberTitle')}</h4>
          <p>{t('voiceprint.tab.memberDesc')}</p>
        </div>
        <div className="speaker-voiceprint-tab__header-actions">
          <button
            className="btn btn--outline btn--sm"
            type="button"
            onClick={() => (pendingEnrollment ? props.onResumeEnrollment(pendingEnrollment.enrollment_id, pendingEnrollment.target_member_id) : props.onStartEnrollment())}
            disabled={!props.canManage || (!pendingEnrollment && !canOpenWizard)}
          >
            {props.canManage ? headerActionLabel : t('voiceprint.tab.onlyAdminEnroll')}
          </button>
        </div>

        {props.loading ? <div className="speaker-voiceprint-tab__empty">{t('voiceprint.tab.loading')}</div> : null}
        {!props.loading && props.error ? (
          <VoiceprintEmptyState
            className="speaker-voiceprint-tab__error-card"
            icon="⚠️"
            title={t('voiceprint.tab.loadFailed')}
            description={props.error}
            action={<button className="btn btn--outline btn--sm" type="button" onClick={props.onRetry}>{t('voiceprint.tab.retry')}</button>}
          />
        ) : null}

        {!props.loading && !props.error && props.summary?.pending_enrollment ? (
          <div className="speaker-voiceprint-tab__pending-banner">
            <span className="badge badge--info">{t('voiceprint.tab.pendingTitle')}</span>
            <p>{t('voiceprint.tab.pendingProgress', {
              count: props.summary.pending_enrollment.sample_count,
              goal: props.summary.pending_enrollment.sample_goal,
            })}</p>
            {props.canManage ? (
              <div className="speaker-voiceprint-tab__pending-actions">
                <button
                  className="btn btn--outline btn--sm"
                  type="button"
                  onClick={() => props.onResumeEnrollment(props.summary!.pending_enrollment!.enrollment_id, props.summary!.pending_enrollment!.target_member_id)}
                >
                  {t('voiceprint.tab.pendingAction')}
                </button>
              </div>
            ) : null}
          </div>
        ) : null}

        {!props.loading && !props.error ? (
          <div className="speaker-voiceprint-tab__member-list">
            {props.summary?.members.map((member) => {
              const meta = getVoiceprintMemberStatusMeta(member, t);
              return (
                <div key={member.member_id} className="speaker-voiceprint-tab__member-card">
                  <div className="speaker-voiceprint-tab__member-header">
                    <div>
                      <strong>{member.member_name}</strong>
                      <span>{t(formatMemberRole(member.member_role))}</span>
                    </div>
                    <span className={`badge badge--${meta.tone}`}>{meta.label}</span>
                  </div>
                  <p className="speaker-voiceprint-tab__member-desc">{meta.description}</p>
                  <div className="speaker-voiceprint-tab__member-meta">
                    <span>{t('voiceprint.tab.recentUpdated', { time: formatVoiceprintTime(member.updated_at, locale, t) })}</span>
                    <span>{t('voiceprint.tab.sampleCount', { count: member.sample_count })}</span>
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
                      {props.canManage ? meta.actionLabel : t('voiceprint.tab.onlyAdminAction')}
                    </button>
                    {member.error_message ? <span className="speaker-voiceprint-tab__member-error">{member.error_message}</span> : null}
                  </div>
                </div>
              );
            })}
          </div>
        ) : null}

        {!props.loading && !props.error && props.summary && props.summary.members.length === 0 ? (
          <VoiceprintEmptyState
            icon="🎙️"
            title={t('voiceprint.tab.memberTitle')}
            description={t('voiceprint.tab.empty')}
          />
        ) : null}
      </div>
    </div>
  );
}
