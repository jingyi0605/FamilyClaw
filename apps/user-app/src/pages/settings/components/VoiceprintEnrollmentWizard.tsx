import type {
  HouseholdVoiceprintMemberSummaryRead,
  VoiceprintEnrollmentRead,
} from '../settingsTypes';
import {
  formatVoiceprintTime,
  type VoiceprintWizardState,
} from './speakerVoiceprintHelpers';

function getWizardTitle(mode: VoiceprintWizardState['mode'], step: VoiceprintWizardState['step']) {
  if (step === 'success') {
    return mode === 'update' ? '声纹更新完成' : '声纹录入完成';
  }
  if (step === 'failed') {
    return mode === 'update' ? '声纹更新失败' : '声纹录入失败';
  }
  if (step === 'waiting') {
    return '声纹录入进行中';
  }
  return mode === 'update' ? '更新声纹' : '开始录入';
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
  onBack: () => void;
  onSelectMember: (memberId: string) => void;
  onContinue: () => void;
  onStart: () => void;
}) {
  const selectedMember = getSelectedMember(props.members, props.wizard.memberId);
  const isWaiting = props.wizard.step === 'waiting';
  const progressCount = props.enrollment?.sample_count ?? 0;
  const progressGoal = props.enrollment?.sample_goal ?? 3;

  return (
    <div className="member-modal-overlay" onClick={props.busy || isWaiting ? undefined : props.onClose}>
      <div className="member-modal speaker-voiceprint-wizard" onClick={(event) => event.stopPropagation()}>
        <div className="member-modal__header">
          <div>
            <h3>{getWizardTitle(props.wizard.mode, props.wizard.step)}</h3>
            <p>首版默认按多轮样本处理，默认 3 轮。首次录入和更新声纹共用同一套向导，不再维护两套分叉流程。</p>
          </div>
        </div>

        {props.wizard.step === 'select_member' ? (
          <div className="speaker-voiceprint-wizard__body">
            <div className="speaker-voiceprint-wizard__steps">
              <span className="badge badge--info">步骤 1 / 2</span>
              <strong>选择要录入声纹的成员</strong>
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
                  <span>{member.member_role === 'admin' ? '管理员' : member.member_role === 'elder' ? '长辈' : member.member_role === 'child' ? '儿童' : '家庭成员'}</span>
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {props.wizard.step === 'confirm' ? (
          <div className="speaker-voiceprint-wizard__body">
            <div className="speaker-voiceprint-wizard__steps">
              <span className="badge badge--info">步骤 2 / 2</span>
              <strong>确认设备和录入说明</strong>
            </div>
            <div className="speaker-voiceprint-wizard__confirm-card">
              <div>
                <span className="speaker-voiceprint-wizard__label">目标成员</span>
                <strong>{selectedMember?.member_name ?? '未选择成员'}</strong>
              </div>
              <div>
                <span className="speaker-voiceprint-wizard__label">目标设备</span>
                <strong>{props.deviceName}</strong>
              </div>
            </div>
            <ul className="speaker-voiceprint-wizard__tips">
              <li>请让目标成员本人站在这台设备附近说话。</li>
              <li>首版默认采 3 轮样本，每轮完成后页面会自动刷新进度。</li>
              <li>识别失败不会打断现有语音主链，这里只影响声纹能力本身。</li>
            </ul>
          </div>
        ) : null}

        {props.wizard.step === 'creating' ? (
          <div className="speaker-voiceprint-wizard__body speaker-voiceprint-wizard__body--center">
            <span className="badge badge--info">正在创建建档任务</span>
            <strong>正在为 {selectedMember?.member_name ?? '目标成员'} 创建声纹建档任务</strong>
            <p>任务创建成功后会自动进入多轮样本进度页。</p>
          </div>
        ) : null}

        {props.wizard.step === 'waiting' ? (
          <div className="speaker-voiceprint-wizard__body">
            <div className="speaker-voiceprint-wizard__steps">
              <span className="badge badge--info">采样进行中</span>
              <strong>{selectedMember?.member_name ?? '目标成员'} 正在录入声纹</strong>
            </div>
            <div className="speaker-voiceprint-wizard__progress-card">
              <div>
                <span className="speaker-voiceprint-wizard__label">当前进度</span>
                <strong>{progressCount} / {progressGoal} 轮样本</strong>
              </div>
              <div>
                <span className="speaker-voiceprint-wizard__label">任务状态</span>
                <strong>{props.enrollment?.status === 'recording' ? '等待下一轮样本' : props.enrollment?.status === 'processing' ? '正在处理样本' : '准备中'}</strong>
              </div>
              <div>
                <span className="speaker-voiceprint-wizard__label">最近更新时间</span>
                <strong>{formatVoiceprintTime(props.enrollment?.updated_at ?? null)}</strong>
              </div>
            </div>
            <p className="speaker-voiceprint-wizard__hint">请继续在 {props.deviceName} 附近让目标成员说话。页面会自动轮询，不需要手动刷新。</p>
          </div>
        ) : null}

        {props.wizard.step === 'success' ? (
          <div className="speaker-voiceprint-wizard__body speaker-voiceprint-wizard__body--center">
            <span className="badge badge--success">已完成</span>
            <strong>{props.wizard.mode === 'update' ? '成员声纹已经更新' : '成员声纹已经绑定完成'}</strong>
            <p>{selectedMember?.member_name ?? '目标成员'} 的状态列表已经刷新，现在可以回到声纹管理页继续操作。</p>
          </div>
        ) : null}

        {props.wizard.step === 'failed' ? (
          <div className="speaker-voiceprint-wizard__body speaker-voiceprint-wizard__body--center">
            <span className="badge badge--danger">未完成</span>
            <strong>{props.wizard.mode === 'update' ? '这次更新没有成功' : '这次录入没有成功'}</strong>
            <p>{props.wizard.error || '可以重新开始，现有设备页其他功能不会受到影响。'}</p>
          </div>
        ) : null}

        <div className="member-modal__actions">
          {props.wizard.step === 'select_member' ? (
            <>
              <button className="btn btn--outline btn--sm" type="button" onClick={props.onClose} disabled={props.busy}>取消</button>
              <button className="btn btn--outline btn--sm" type="button" onClick={props.onContinue} disabled={!props.wizard.memberId || props.busy}>下一步</button>
            </>
          ) : null}
          {props.wizard.step === 'confirm' ? (
            <>
              <button className="btn btn--outline btn--sm" type="button" onClick={props.onBack} disabled={props.busy || Boolean(props.wizard.lockedMemberId)}>上一步</button>
              <button className="btn btn--outline btn--sm" type="button" onClick={() => void props.onStart()} disabled={props.busy || !props.wizard.memberId}>
                {props.busy ? '创建中...' : (props.wizard.mode === 'update' ? '开始更新' : '创建建档任务')}
              </button>
            </>
          ) : null}
          {props.wizard.step === 'creating' || props.wizard.step === 'waiting' ? (
            <button className="btn btn--outline btn--sm" type="button" disabled>
              请等待
            </button>
          ) : null}
          {props.wizard.step === 'success' ? (
            <button className="btn btn--outline btn--sm" type="button" onClick={props.onClose}>完成</button>
          ) : null}
          {props.wizard.step === 'failed' ? (
            <>
              <button className="btn btn--outline btn--sm" type="button" onClick={props.onClose}>关闭</button>
              <button className="btn btn--outline btn--sm" type="button" onClick={props.onStart} disabled={props.busy || !props.wizard.memberId}>
                {props.busy ? '重试中...' : '重新开始'}
              </button>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
