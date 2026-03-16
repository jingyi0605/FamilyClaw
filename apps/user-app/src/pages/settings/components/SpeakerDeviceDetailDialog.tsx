import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { useI18n } from '../../../runtime';
import { ToggleSwitch } from '../../family/base';
import { SettingsDialog } from './SettingsSharedBlocks';
import type { Device } from '../settingsTypes';

type SpeakerTakeoverDraft = {
  voice_auto_takeover_enabled: boolean;
  voice_takeover_prefixes_text: string;
};

function normalizeTakeoverPrefixes(text: string) {
  return text
    .replace(/，/g, ',')
    .split(',')
    .map((item) => item.trim())
    .filter((item, index, array) => item.length > 0 && array.indexOf(item) === index);
}

export function SpeakerDeviceDetailDialog(props: {
  device: Device;
  roomName: string;
  saving: boolean;
  error: string;
  voiceprintTab: ReactNode;
  onClose: () => void;
  onSaveTakeover: (payload: { voice_auto_takeover_enabled: boolean; voice_takeover_prefixes: string[] }) => Promise<void>;
}) {
  const { t } = useI18n();
  const { device } = props;
  const defaultPrefix = t('speaker.detail.defaultPrefix');
  const [activeTab, setActiveTab] = useState<'takeover' | 'voiceprint'>('takeover');
  const [draft, setDraft] = useState<SpeakerTakeoverDraft>({
    voice_auto_takeover_enabled: device.voice_auto_takeover_enabled,
    voice_takeover_prefixes_text: (device.voice_takeover_prefixes.length > 0 ? device.voice_takeover_prefixes : [defaultPrefix]).join(', '),
  });
  const [validationError, setValidationError] = useState('');

  useEffect(() => {
    setDraft({
      voice_auto_takeover_enabled: device.voice_auto_takeover_enabled,
      voice_takeover_prefixes_text: (device.voice_takeover_prefixes.length > 0 ? device.voice_takeover_prefixes : [defaultPrefix]).join(', '),
    });
    setValidationError('');
  }, [defaultPrefix, device]);

  const normalizedPrefixes = useMemo(
    () => normalizeTakeoverPrefixes(draft.voice_takeover_prefixes_text),
    [draft.voice_takeover_prefixes_text],
  );

  async function handleSave() {
    if (!draft.voice_auto_takeover_enabled && normalizedPrefixes.length === 0) {
      setValidationError(t('speaker.detail.validationPrefix'));
      return;
    }
    setValidationError('');
    await props.onSaveTakeover({
      voice_auto_takeover_enabled: draft.voice_auto_takeover_enabled,
      voice_takeover_prefixes: normalizedPrefixes.length > 0 ? normalizedPrefixes : [defaultPrefix],
    });
  }

  return (
    <SettingsDialog
      title={t('speaker.detail.title', { name: device.name })}
      description={t('speaker.detail.desc')}
      className="speaker-device-detail-dialog"
      onClose={props.onClose}
      headerExtra={(
        <span className={`badge badge--${device.status === 'active' ? 'success' : 'secondary'}`}>
          {device.status === 'active' ? t('speaker.detail.status.online') : device.status === 'offline' ? t('speaker.detail.status.offline') : t('speaker.detail.status.inactive')}
        </span>
      )}
      actions={(
        <>
          <button className="btn btn--outline btn--sm" type="button" onClick={props.onClose} disabled={props.saving}>{t('speaker.detail.close')}</button>
          {activeTab === 'takeover' ? (
            <button className="btn btn--outline btn--sm" type="button" onClick={() => void handleSave()} disabled={props.saving}>
              {props.saving ? t('speaker.detail.saving') : t('speaker.detail.save')}
            </button>
          ) : null}
        </>
      )}
    >
        <div className="speaker-device-detail-dialog__summary">
          <div className="speaker-device-detail-dialog__summary-item">
            <span className="speaker-device-detail-dialog__summary-label">{t('speaker.detail.summary.room')}</span>
            <strong>{props.roomName}</strong>
          </div>
          <div className="speaker-device-detail-dialog__summary-item">
            <span className="speaker-device-detail-dialog__summary-label">{t('speaker.detail.summary.vendor')}</span>
            <strong>{t('speaker.detail.summary.vendorName')}</strong>
          </div>
          <div className="speaker-device-detail-dialog__summary-item">
            <span className="speaker-device-detail-dialog__summary-label">{t('speaker.detail.summary.strategy')}</span>
            <strong>
              {draft.voice_auto_takeover_enabled
                ? t('speaker.detail.summary.strategy.all')
                : t('speaker.detail.summary.strategy.prefixes', { prefixes: normalizedPrefixes.join('、') || defaultPrefix })}
            </strong>
          </div>
        </div>

        <div className="speaker-device-detail-dialog__tabs">
          <button
            type="button"
            className={`speaker-device-detail-dialog__tab ${activeTab === 'takeover' ? 'speaker-device-detail-dialog__tab--active' : ''}`}
            onClick={() => setActiveTab('takeover')}
          >
            {t('speaker.detail.tab.takeover')}
          </button>
          <button
            type="button"
            className={`speaker-device-detail-dialog__tab ${activeTab === 'voiceprint' ? 'speaker-device-detail-dialog__tab--active' : ''}`}
            onClick={() => setActiveTab('voiceprint')}
          >
            {t('speaker.detail.tab.voiceprint')}
          </button>
        </div>

        {activeTab === 'takeover' ? (
          <div className="speaker-device-detail-dialog__panel">
            <div className="speaker-device-detail-dialog__panel-header">
              <h4>{t('speaker.detail.panel.title')}</h4>
              <p>{t('speaker.detail.panel.desc')}</p>
            </div>
            <div className="settings-form">
              {validationError ? <div className="form-error">{validationError}</div> : null}
              {props.error ? <div className="form-error">{props.error}</div> : null}
              <div className="speaker-device-detail-dialog__toggle-card">
                <ToggleSwitch
                  checked={draft.voice_auto_takeover_enabled}
                  label={t('speaker.detail.toggle.label')}
                  description={t('speaker.detail.toggle.desc')}
                  onChange={(value) => setDraft((current) => ({ ...current, voice_auto_takeover_enabled: value }))}
                  disabled={props.saving}
                />
              </div>
              <div className="form-group">
                <label>{t('speaker.detail.prefixLabel')}</label>
                <input
                  className="form-input"
                  value={draft.voice_takeover_prefixes_text}
                  onChange={(event) => setDraft((current) => ({ ...current, voice_takeover_prefixes_text: event.target.value }))}
                  placeholder={t('speaker.detail.prefixPlaceholder')}
                />
                <div className="form-hint">{t('speaker.detail.prefixHint')}</div>
              </div>
            </div>
          </div>
        ) : props.voiceprintTab}
    </SettingsDialog>
  );
}
