import { useI18n } from '../../../runtime/h5-shell/i18n/I18nProvider';
import type {
  HouseholdVoiceprintMemberSummaryRead,
  VoiceprintEnrollmentRead,
} from '../settingsTypes';
import {
  formatVoiceprintTime,
  getVoiceprintEnrollmentProgressMeta,
  type VoiceprintWizardState,
} from './speakerVoiceprintHelpers';
import { VoiceprintDialog } from './VoiceprintSharedBlocks';

function getWizardTitle(
  mode: VoiceprintWizardState['mode'],
  step: VoiceprintWizardState['step'],
  t: (key: string, params?: Record<string, string | number>) => string,
) {
  if (step === 'success') {
    return mode === 'update'
      ? t('voiceprint.wizard.title.successUpdate')
      : t('voiceprint.wizard.title.successEnroll');
  }
  if (step === 'failed') {
    return mode === 'update'
      ? t('voiceprint.wizard.title.failedUpdate')
      : t('voiceprint.wizard.title.failedEnroll');
  }
  if (step === 'waiting') {
    return t('voiceprint.wizard.title.waiting');
  }
  return mode === 'update'
    ? t('voiceprint.wizard.title.update')
    : t('voiceprint.wizard.title.start');
}

function getSelectedMember(
  members: HouseholdVoiceprintMemberSummaryRead[],
  memberId: string | null,
) {
  return members.find((member) => member.member_id === memberId) ?? null;
}

export function VoiceprintEnrollmentWizard(props: {
  wizard: VoiceprintWizardState;
  members: HouseholdVoiceprintMemberSummaryRead[];
  deviceName: string;
  enrollment: VoiceprintEnrollmentRead | null;
  busy: boolean;
  onClose: () => void;
  onCancelEnrollment: () => void;
  onBack: () => void;
  onSelectMember: (memberId: string) => void;
  onContinue: () => void;
  onStart: () => void;
}) {
  const { t, locale } = useI18n();
  const selectedMember = getSelectedMember(props.members, props.wizard.memberId);
  const isWaiting = props.wizard.step === 'waiting';
  const progressMeta = getVoiceprintEnrollmentProgressMeta(props.enrollment);
  const phraseText = (props.enrollment?.expected_phrase ?? '').trim() || t('voiceprint.wizard.promptFallback');
  const memberName = selectedMember?.member_name ?? t('voiceprint.wizard.noMember');

  return (
    <VoiceprintDialog
      title={getWizardTitle(props.wizard.mode, props.wizard.step, t)}
      description={t('voiceprint.wizard.intro')}
      className="speaker-voiceprint-wizard"
      closeDisabled={props.busy || isWaiting}
      onClose={props.onClose}
      actions={(
        <>
          {props.wizard.step === 'select_member' ? (
            <>
              <button className="btn btn--outline btn--sm" type="button" onClick={props.onClose} disabled={props.busy}>{t('voiceprint.wizard.cancel')}</button>
              <button className="btn btn--outline btn--sm" type="button" onClick={props.onContinue} disabled={!props.wizard.memberId || props.busy}>{t('voiceprint.wizard.next')}</button>
            </>
          ) : null}
          {props.wizard.step === 'confirm' ? (
            <>
              <button className="btn btn--outline btn--sm" type="button" onClick={props.onBack} disabled={props.busy || Boolean(props.wizard.lockedMemberId)}>{t('voiceprint.wizard.back')}</button>
              <button className="btn btn--outline btn--sm" type="button" onClick={() => void props.onStart()} disabled={props.busy || !props.wizard.memberId}>
                {props.busy ? t('voiceprint.wizard.creating') : (props.wizard.mode === 'update' ? t('voiceprint.wizard.startUpdate') : t('voiceprint.wizard.createTask'))}
              </button>
            </>
          ) : null}
          {props.wizard.step === 'creating' ? (
            <button className="btn btn--outline btn--sm" type="button" disabled>
              {t('voiceprint.wizard.pleaseWait')}
            </button>
          ) : null}
          {props.wizard.step === 'waiting' ? (
            <>
              <button className="btn btn--outline btn--sm" type="button" onClick={props.onCancelEnrollment} disabled={props.busy}>
                {props.busy ? t('voiceprint.wizard.cancelling') : t('voiceprint.wizard.cancelEnrollment')}
              </button>
              <button className="btn btn--outline btn--sm" type="button" disabled>
                {t('voiceprint.wizard.pleaseWait')}
              </button>
            </>
          ) : null}
          {props.wizard.step === 'success' ? (
            <button className="btn btn--outline btn--sm" type="button" onClick={props.onClose}>{t('voiceprint.wizard.done')}</button>
          ) : null}
          {props.wizard.step === 'failed' ? (
            <>
              <button className="btn btn--outline btn--sm" type="button" onClick={props.onClose}>{t('voiceprint.wizard.close')}</button>
              <button className="btn btn--outline btn--sm" type="button" onClick={props.onStart} disabled={props.busy || !props.wizard.memberId}>
                {props.busy ? t('voiceprint.wizard.retrying') : t('voiceprint.wizard.restart')}
              </button>
            </>
          ) : null}
        </>
      )}
    >
        {props.wizard.step === 'select_member' ? (
          <div className="speaker-voiceprint-wizard__body">
            <div className="speaker-voiceprint-wizard__steps">
              <span className="badge badge--info">{t('voiceprint.wizard.stepSelect')}</span>
              <strong>{t('voiceprint.wizard.selectMemberTitle')}</strong>
            </div>
            <div className="speaker-voiceprint-wizard__member-list">
              {props.members.map((member) => (
                <button
                  key={member.member_id}
                  type="button"
                  className={`speaker-voiceprint-wizard__member-item ${props.wizard.memberId === member.member_id ? 'speaker-voiceprint-wizard__member-item--active' : ''}`}
                  onClick={() => props.onSelectMember(member.member_id)}
                >
                  <strong>{member.member_name}</strong>
                  <span>{member.member_role === 'admin'
                    ? t('voiceprint.wizard.member.admin')
                    : member.member_role === 'elder'
                      ? t('voiceprint.wizard.member.elder')
                      : member.member_role === 'child'
                        ? t('voiceprint.wizard.member.child')
                        : t('voiceprint.wizard.member.default')}</span>
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {props.wizard.step === 'confirm' ? (
          <div className="speaker-voiceprint-wizard__body">
            <div className="speaker-voiceprint-wizard__steps">
              <span className="badge badge--info">{t('voiceprint.wizard.stepConfirm')}</span>
              <strong>{t('voiceprint.wizard.confirmTitle')}</strong>
            </div>
            <div className="speaker-voiceprint-wizard__confirm-card">
              <div>
                <span className="speaker-voiceprint-wizard__label">{t('voiceprint.wizard.targetMember')}</span>
                <strong>{memberName}</strong>
              </div>
              <div>
                <span className="speaker-voiceprint-wizard__label">{t('voiceprint.wizard.targetDevice')}</span>
                <strong>{props.deviceName}</strong>
              </div>
            </div>
            <ul className="speaker-voiceprint-wizard__tips">
              <li>{t('voiceprint.wizard.tip.nearDevice')}</li>
              <li>{t('voiceprint.wizard.tip.samples')}</li>
              <li>{t('voiceprint.wizard.tip.safe')}</li>
            </ul>
          </div>
        ) : null}

        {props.wizard.step === 'creating' ? (
          <div className="speaker-voiceprint-wizard__body speaker-voiceprint-wizard__body--center">
            <span className="badge badge--info">{t('voiceprint.wizard.creatingBadge')}</span>
            <strong>{t('voiceprint.wizard.creatingTitle', { memberName })}</strong>
            <p>{t('voiceprint.wizard.creatingHint')}</p>
          </div>
        ) : null}

        {props.wizard.step === 'waiting' ? (
          <div className="speaker-voiceprint-wizard__body">
            <div className="speaker-voiceprint-wizard__steps">
              <span className="badge badge--info">{t('voiceprint.wizard.waitingBadge')}</span>
              <strong>{t('voiceprint.wizard.waitingTitle', { memberName })}</strong>
            </div>
            <div className="speaker-voiceprint-wizard__prompt-card">
              <div className="speaker-voiceprint-wizard__prompt-meta">
                <span className="speaker-voiceprint-wizard__label">{t('voiceprint.wizard.roundLabel')}</span>
                <strong>{t('voiceprint.wizard.roundValue', { current: progressMeta.currentRound, goal: progressMeta.progressGoal })}</strong>
              </div>
              <div className="speaker-voiceprint-wizard__prompt-meta">
                <span className="speaker-voiceprint-wizard__label">{t('voiceprint.wizard.promptLabel')}</span>
                <strong className="speaker-voiceprint-wizard__prompt-text">{phraseText}</strong>
              </div>
            </div>
            <div className="speaker-voiceprint-wizard__progress-card">
              <div>
                <span className="speaker-voiceprint-wizard__label">{t('voiceprint.wizard.progress')}</span>
                <strong>{t('voiceprint.wizard.progressValue', { count: progressMeta.progressCount, goal: progressMeta.progressGoal })}</strong>
              </div>
              <div>
                <span className="speaker-voiceprint-wizard__label">{t('voiceprint.wizard.taskStatus')}</span>
                <strong>{props.enrollment?.status === 'recording'
                  ? t('voiceprint.wizard.taskStatus.recording')
                  : props.enrollment?.status === 'processing'
                    ? t('voiceprint.wizard.taskStatus.processing')
                    : t('voiceprint.wizard.taskStatus.preparing')}</strong>
              </div>
              <div>
                <span className="speaker-voiceprint-wizard__label">{t('voiceprint.wizard.lastUpdated')}</span>
                <strong>{formatVoiceprintTime(props.enrollment?.updated_at ?? null, locale, t)}</strong>
              </div>
            </div>
            <ul className="speaker-voiceprint-wizard__guide-list">
              <li>{t('voiceprint.wizard.guide.step1')}</li>
              <li>{t('voiceprint.wizard.guide.step2')}</li>
              <li>{t('voiceprint.wizard.guide.step3')}</li>
            </ul>
            <p className="speaker-voiceprint-wizard__hint">{t('voiceprint.wizard.waitingHint', { deviceName: props.deviceName })}</p>
          </div>
        ) : null}

        {props.wizard.step === 'success' ? (
          <div className="speaker-voiceprint-wizard__body speaker-voiceprint-wizard__body--center">
            <span className="badge badge--success">{t('voiceprint.wizard.successBadge')}</span>
            <strong>{props.wizard.mode === 'update'
              ? t('voiceprint.wizard.successTitle.update')
              : t('voiceprint.wizard.successTitle.enroll')}</strong>
            <p>{t('voiceprint.wizard.successHint', { memberName })}</p>
          </div>
        ) : null}

        {props.wizard.step === 'failed' ? (
          <div className="speaker-voiceprint-wizard__body speaker-voiceprint-wizard__body--center">
            <span className="badge badge--danger">{t('voiceprint.wizard.failedBadge')}</span>
            <strong>{props.wizard.mode === 'update'
              ? t('voiceprint.wizard.failedTitle.update')
              : t('voiceprint.wizard.failedTitle.enroll')}</strong>
            <p>{props.wizard.error || t('voiceprint.wizard.failedHint')}</p>
          </div>
        ) : null}
    </VoiceprintDialog>
  );
}
