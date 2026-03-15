import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { ToggleSwitch } from '../../family/base';
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
  const { device } = props;
  const [activeTab, setActiveTab] = useState<'takeover' | 'voiceprint'>('takeover');
  const [draft, setDraft] = useState<SpeakerTakeoverDraft>({
    voice_auto_takeover_enabled: device.voice_auto_takeover_enabled,
    voice_takeover_prefixes_text: (device.voice_takeover_prefixes.length > 0 ? device.voice_takeover_prefixes : ['请']).join(', '),
  });
  const [validationError, setValidationError] = useState('');

  useEffect(() => {
    setDraft({
      voice_auto_takeover_enabled: device.voice_auto_takeover_enabled,
      voice_takeover_prefixes_text: (device.voice_takeover_prefixes.length > 0 ? device.voice_takeover_prefixes : ['请']).join(', '),
    });
    setValidationError('');
  }, [device]);

  const normalizedPrefixes = useMemo(
    () => normalizeTakeoverPrefixes(draft.voice_takeover_prefixes_text),
    [draft.voice_takeover_prefixes_text],
  );

  async function handleSave() {
    if (!draft.voice_auto_takeover_enabled && normalizedPrefixes.length === 0) {
      setValidationError('至少填一个请求前缀，例如“请”。');
      return;
    }
    setValidationError('');
    await props.onSaveTakeover({
      voice_auto_takeover_enabled: draft.voice_auto_takeover_enabled,
      voice_takeover_prefixes: normalizedPrefixes.length > 0 ? normalizedPrefixes : ['请'],
    });
  }

  return (
    <div className="member-modal-overlay" onClick={props.onClose}>
      <div className="member-modal speaker-device-detail-dialog" onClick={(event) => event.stopPropagation()}>
        <div className="member-modal__header">
          <div>
            <h3>{device.name} · 设备详情</h3>
            <p>先把这台音箱的设备级入口立住，后面语音接管和声纹管理都从这里进，不再继续堆零散弹窗。</p>
          </div>
          <span className={`badge badge--${device.status === 'active' ? 'success' : 'secondary'}`}>
            {device.status === 'active' ? '在线' : device.status === 'offline' ? '离线' : '未启用'}
          </span>
        </div>

        <div className="speaker-device-detail-dialog__summary">
          <div className="speaker-device-detail-dialog__summary-item">
            <span className="speaker-device-detail-dialog__summary-label">所在房间</span>
            <strong>{props.roomName}</strong>
          </div>
          <div className="speaker-device-detail-dialog__summary-item">
            <span className="speaker-device-detail-dialog__summary-label">设备厂商</span>
            <strong>小米小爱音箱</strong>
          </div>
          <div className="speaker-device-detail-dialog__summary-item">
            <span className="speaker-device-detail-dialog__summary-label">当前语音策略</span>
            <strong>{draft.voice_auto_takeover_enabled ? '默认接管全部请求' : `仅响应 ${normalizedPrefixes.join('、') || '请'} 开头的请求`}</strong>
          </div>
        </div>

        <div className="speaker-device-detail-dialog__tabs">
          <button
            type="button"
            className={`speaker-device-detail-dialog__tab ${activeTab === 'takeover' ? 'speaker-device-detail-dialog__tab--active' : ''}`}
            onClick={() => setActiveTab('takeover')}
          >
            语音接管
          </button>
          <button
            type="button"
            className={`speaker-device-detail-dialog__tab ${activeTab === 'voiceprint' ? 'speaker-device-detail-dialog__tab--active' : ''}`}
            onClick={() => setActiveTab('voiceprint')}
          >
            声纹管理
          </button>
        </div>

        {activeTab === 'takeover' ? (
          <div className="speaker-device-detail-dialog__panel">
            <div className="speaker-device-detail-dialog__panel-header">
              <h4>语音接管</h4>
              <p>这里只控制这台音箱何时把请求交给 FamilyClaw。现有语音接管能力不重做，只换到正式设备详情里。</p>
            </div>
            <div className="settings-form">
              {validationError ? <div className="form-error">{validationError}</div> : null}
              {props.error ? <div className="form-error">{props.error}</div> : null}
              <div className="speaker-device-detail-dialog__toggle-card">
                <ToggleSwitch
                  checked={draft.voice_auto_takeover_enabled}
                  label="默认接管所有语音请求"
                  description="打开后，这台音箱的请求会优先进入 FamilyClaw，不用再依赖前缀词。"
                  onChange={(value) => setDraft((current) => ({ ...current, voice_auto_takeover_enabled: value }))}
                  disabled={props.saving}
                />
              </div>
              <div className="form-group">
                <label>仅响应这些开头词</label>
                <input
                  className="form-input"
                  value={draft.voice_takeover_prefixes_text}
                  onChange={(event) => setDraft((current) => ({ ...current, voice_takeover_prefixes_text: event.target.value }))}
                  placeholder="请，帮我"
                />
                <div className="form-hint">只有在关闭“默认接管所有语音请求”时才生效，多个前缀用逗号分隔。</div>
              </div>
            </div>
          </div>
        ) : props.voiceprintTab}

        <div className="member-modal__actions">
          <button className="btn btn--outline btn--sm" type="button" onClick={props.onClose} disabled={props.saving}>关闭</button>
          {activeTab === 'takeover' ? (
            <button className="btn btn--outline btn--sm" type="button" onClick={() => void handleSave()} disabled={props.saving}>
              {props.saving ? '保存中...' : '保存设备详情'}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
