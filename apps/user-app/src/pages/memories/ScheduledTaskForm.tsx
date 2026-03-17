import { useEffect, useMemo, useState } from 'react';
import { useAuthContext, useHouseholdContext } from '../../runtime';
import { SettingsDialog } from '../settings/components/SettingsSharedBlocks';
import { api, ApiError } from './api';
import { useMemoriesText } from './copy';
import type {
  Member,
  OwnerScope,
  RuleType,
  ScheduledTaskDefinition,
  ScheduledTaskDefinitionCreate,
  ScheduleType,
  TargetType,
  TriggerType,
} from './types';

type TaskFormMode = 'create' | 'edit' | 'copy';

interface TaskFormData {
  name: string;
  description: string;
  owner_scope: OwnerScope;
  owner_member_id: string | null;
  trigger_type: TriggerType;
  schedule_type: ScheduleType | null;
  schedule_expr: string;
  heartbeat_interval_seconds: number;
  timezone: string;
  target_type: TargetType;
  target_ref_id: string;
  rule_type: RuleType;
  enabled: boolean;
}

const defaultFormData: TaskFormData = {
  name: '',
  description: '',
  owner_scope: 'member',
  owner_member_id: null,
  trigger_type: 'schedule',
  schedule_type: 'daily',
  schedule_expr: '09:00',
  heartbeat_interval_seconds: 300,
  timezone: 'Asia/Shanghai',
  target_type: 'agent_reminder',
  target_ref_id: '',
  rule_type: 'none',
  enabled: true,
};

interface ScheduledTaskFormProps {
  mode: TaskFormMode;
  task?: ScheduledTaskDefinition | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (task: ScheduledTaskDefinition) => void;
}

export function ScheduledTaskForm({ mode, task, isOpen, onClose, onSuccess }: ScheduledTaskFormProps) {
  const t = useMemoriesText();
  const { currentHouseholdId } = useHouseholdContext();
  const { actor } = useAuthContext();
  const [formData, setFormData] = useState<TaskFormData>(defaultFormData);
  const [members, setMembers] = useState<Member[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!isOpen || !currentHouseholdId) {
      return;
    }

    let cancelled = false;

    const loadMembers = async () => {
      setMembersLoading(true);
      try {
        const result = await api.listMembers(currentHouseholdId);
        if (!cancelled) {
          setMembers(result.items);
        }
      } catch {
        if (!cancelled) {
          setMembers([]);
        }
      } finally {
        if (!cancelled) {
          setMembersLoading(false);
        }
      }
    };

    void loadMembers();

    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId, isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    if (mode === 'create') {
      setFormData({
        ...defaultFormData,
        owner_member_id: actor?.member_id ?? null,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai',
      });
    } else if (task) {
      setFormData({
        name: mode === 'copy' ? `${task.name}${t('scheduledTasks.form.copySuffix')}` : task.name,
        description: task.description ?? '',
        owner_scope: task.owner_scope,
        owner_member_id: task.owner_member_id,
        trigger_type: task.trigger_type,
        schedule_type: task.schedule_type,
        schedule_expr: task.schedule_expr ?? '09:00',
        heartbeat_interval_seconds: task.heartbeat_interval_seconds ?? 300,
        timezone: task.timezone,
        target_type: task.target_type,
        target_ref_id: task.target_ref_id ?? '',
        rule_type: task.rule_type,
        enabled: mode === 'copy' ? true : task.enabled,
      });
    }

    setError('');
  }, [actor?.member_id, isOpen, mode, task, t]);

  const timezones = useMemo(() => [
    { value: 'Asia/Shanghai', label: t('scheduledTasks.timezone.beijing') },
    { value: 'Asia/Tokyo', label: t('scheduledTasks.timezone.tokyo') },
    { value: 'America/New_York', label: t('scheduledTasks.timezone.newYork') },
    { value: 'America/Los_Angeles', label: t('scheduledTasks.timezone.losAngeles') },
    { value: 'Europe/London', label: t('scheduledTasks.timezone.london') },
    { value: 'UTC', label: t('scheduledTasks.timezone.utc') },
  ], [t]);

  const updateField = <K extends keyof TaskFormData>(key: K, value: TaskFormData[K]) => {
    setFormData(current => ({ ...current, [key]: value }));
  };

  async function handleSubmit() {
    if (!currentHouseholdId) {
      return;
    }

    if (!formData.name.trim()) {
      setError(t('scheduledTasks.form.nameRequired'));
      return;
    }

    if (formData.trigger_type === 'schedule' && !formData.schedule_expr.trim()) {
      setError(t('scheduledTasks.form.scheduleRequired'));
      return;
    }

    if (formData.owner_scope === 'member' && !formData.owner_member_id) {
      setError(t('scheduledTasks.form.ownerRequired'));
      return;
    }

    setSubmitting(true);
    setError('');

    try {
    let result: ScheduledTaskDefinition;

    if (mode === 'edit' && task) {
      result = await api.updateScheduledTask(task.id, {
        name: formData.name,
        description: formData.description || null,
        schedule_type: formData.trigger_type === 'schedule' ? formData.schedule_type : null,
        schedule_expr: formData.trigger_type === 'schedule' ? formData.schedule_expr : null,
        heartbeat_interval_seconds: formData.trigger_type === 'heartbeat' ? formData.heartbeat_interval_seconds : null,
        timezone: formData.timezone,
        target_type: formData.target_type,
        target_ref_id: formData.target_ref_id || null,
        rule_type: formData.rule_type,
        enabled: formData.enabled,
      });
    } else {
      const createPayload: ScheduledTaskDefinitionCreate = {
        household_id: currentHouseholdId,
        owner_scope: formData.owner_scope,
        owner_member_id: formData.owner_scope === 'member' ? formData.owner_member_id : null,
        code: `task_${Date.now()}`,
        name: formData.name,
        description: formData.description || null,
        trigger_type: formData.trigger_type,
        schedule_type: formData.trigger_type === 'schedule' ? formData.schedule_type : null,
        schedule_expr: formData.trigger_type === 'schedule' ? formData.schedule_expr : null,
        heartbeat_interval_seconds: formData.trigger_type === 'heartbeat' ? formData.heartbeat_interval_seconds : null,
        timezone: formData.timezone,
        target_type: formData.target_type,
        target_ref_id: formData.target_ref_id || null,
        rule_type: formData.rule_type,
        enabled: formData.enabled,
      };
      result = await api.createScheduledTask(createPayload);
    }

    onSuccess(result);
    onClose();
  } catch (submitError) {
    setError(submitError instanceof ApiError ? submitError.message : t('scheduledTasks.error.saveFailed'));
  } finally {
    setSubmitting(false);
  }
  }

  const dialogTitle = mode === 'create'
    ? t('scheduledTasks.newTask')
    : mode === 'edit'
      ? t('scheduledTasks.action.edit')
      : t('scheduledTasks.action.copy');

  return (
    <SettingsDialog
      open={isOpen}
      title={dialogTitle}
      className="scheduled-task-form-modal"
      closeDisabled={submitting}
      onClose={onClose}
      onSubmit={(event) => { event.preventDefault(); void handleSubmit(); }}
      actions={(
        <>
          <button className="btn btn--outline btn--sm" type="button" onClick={onClose} disabled={submitting}>
            {t('common.cancel')}
          </button>
          <button className="btn btn--primary btn--sm" type="submit" disabled={submitting}>
            {submitting ? t('common.loading') : t('common.save')}
          </button>
        </>
      )}
    >
      {error ? <div className="form-error">{error}</div> : null}
      <div className="settings-form">
        <div className="form-field">
          <label className="form-label">{t('scheduledTasks.detail.name')} *</label>
          <input className="form-input" type="text" placeholder={t('scheduledTasks.form.namePlaceholder')} value={formData.name} onChange={event => updateField('name', event.target.value)} />
        </div>
        <div className="form-field">
          <label className="form-label">{t('scheduledTasks.detail.description')}</label>
          <textarea className="form-input" rows={3} placeholder={t('scheduledTasks.form.descriptionPlaceholder')} value={formData.description} onChange={event => updateField('description', event.target.value)} />
        </div>
        <div className="form-field">
          <label className="form-label">{t('scheduledTasks.form.ownerScope')} *</label>
          <div className="form-radio-group">
            <label className="form-radio">
              <input type="radio" name="owner_scope" checked={formData.owner_scope === 'member'} onChange={() => updateField('owner_scope', 'member')} />
              <span className="form-radio__label">{t('scheduledTasks.owner.member')}</span>
              <span className="form-radio__hint">{t('scheduledTasks.form.ownerMemberHint')}</span>
            </label>
            <label className="form-radio">
              <input type="radio" name="owner_scope" checked={formData.owner_scope === 'household'} onChange={() => updateField('owner_scope', 'household')} />
              <span className="form-radio__label">{t('scheduledTasks.owner.household')}</span>
              <span className="form-radio__hint">{t('scheduledTasks.form.ownerHouseholdHint')}</span>
            </label>
          </div>
        </div>
        {formData.owner_scope === 'member' ? (
          <div className="form-field">
            <label className="form-label">{t('scheduledTasks.form.ownerMember')} *</label>
            <select className="form-select" value={formData.owner_member_id ?? ''} onChange={event => updateField('owner_member_id', event.target.value || null)} disabled={membersLoading}>
              <option value="">{t('scheduledTasks.form.selectMember')}</option>
              {members.map(member => <option key={member.id} value={member.id}>{member.name}</option>)}
            </select>
          </div>
        ) : null}
        <div className="form-field">
          <label className="form-label">{t('scheduledTasks.detail.triggerType')} *</label>
          <div className="form-radio-group">
            <label className="form-radio">
              <input type="radio" name="trigger_type" checked={formData.trigger_type === 'schedule'} onChange={() => updateField('trigger_type', 'schedule')} />
              <span className="form-radio__label">{t('scheduledTasks.trigger.schedule')}</span>
              <span className="form-radio__hint">{t('scheduledTasks.form.scheduleHint')}</span>
            </label>
            <label className="form-radio">
              <input type="radio" name="trigger_type" checked={formData.trigger_type === 'heartbeat'} onChange={() => updateField('trigger_type', 'heartbeat')} />
              <span className="form-radio__label">{t('scheduledTasks.trigger.heartbeat')}</span>
              <span className="form-radio__hint">{t('scheduledTasks.form.heartbeatHint')}</span>
            </label>
          </div>
        </div>
        {formData.trigger_type === 'schedule' ? (
          <>
            <div className="form-field">
              <label className="form-label">{t('scheduledTasks.form.scheduleType')} *</label>
              <select className="form-select" value={formData.schedule_type ?? 'daily'} onChange={event => updateField('schedule_type', event.target.value as ScheduleType)}>
                <option value="daily">{t('scheduledTasks.form.scheduleDaily')}</option>
                <option value="interval">{t('scheduledTasks.form.scheduleInterval')}</option>
                <option value="cron">{t('scheduledTasks.form.scheduleCron')}</option>
              </select>
            </div>
            <div className="form-field">
              <label className="form-label">{formData.schedule_type === 'daily' ? t('scheduledTasks.form.dailyTime') : formData.schedule_type === 'interval' ? t('scheduledTasks.form.intervalExpr') : t('scheduledTasks.form.cronExpr')} *</label>
              <input className="form-input" type="text" placeholder={t('scheduledTasks.form.schedulePlaceholder')} value={formData.schedule_expr} onChange={event => updateField('schedule_expr', event.target.value)} />
            </div>
          </>
        ) : null}
        {formData.trigger_type === 'heartbeat' ? (
          <div className="form-field">
            <label className="form-label">{t('scheduledTasks.form.checkInterval')} *</label>
            <div className="form-input-with-unit">
              <input className="form-input" type="number" min={60} max={86400} value={formData.heartbeat_interval_seconds} onChange={event => updateField('heartbeat_interval_seconds', Number.parseInt(event.target.value, 10) || 300)} />
              <span className="form-input-unit">{t('common.seconds')}</span>
            </div>
            <p className="form-hint">{t('scheduledTasks.form.checkIntervalHint')}</p>
          </div>
        ) : null}
        <div className="form-field">
          <label className="form-label">{t('scheduledTasks.form.timezone')}</label>
          <select className="form-select" value={formData.timezone} onChange={event => updateField('timezone', event.target.value)}>
            {timezones.map(timezone => <option key={timezone.value} value={timezone.value}>{timezone.label}</option>)}
          </select>
        </div>
        <div className="form-field">
          <label className="form-label">{t('scheduledTasks.form.targetType')} *</label>
          <select className="form-select" value={formData.target_type} onChange={event => updateField('target_type', event.target.value as TargetType)}>
            <option value="agent_reminder">{t('scheduledTasks.target.agent')}</option>
            <option value="plugin_job">{t('scheduledTasks.target.plugin')}</option>
            <option value="system_notice">{t('scheduledTasks.target.system')}</option>
          </select>
        </div>
        <div className="form-field">
          <label className="form-label">{t('scheduledTasks.form.targetRef')}</label>
          <input className="form-input" type="text" placeholder={t('scheduledTasks.form.targetRefPlaceholder')} value={formData.target_ref_id} onChange={event => updateField('target_ref_id', event.target.value)} />
        </div>
        <div className="form-field">
          <label className="form-checkbox">
            <input type="checkbox" checked={formData.enabled} onChange={event => updateField('enabled', event.target.checked)} />
            <span className="form-checkbox__label">{t('scheduledTasks.form.enableNow')}</span>
          </label>
        </div>
      </div>
    </SettingsDialog>
  );
}
