/**
 * AI供应商选择对话框 - 第一步：选择供应商
 */
import { Puzzle } from 'lucide-react';
import type { AiProviderAdapter } from '../settingsTypes';
import { getLocalizedAdapterMeta, getLocalizedModelTypeLabel } from './aiProviderCatalog';
import { getAiProviderLogo } from './AiProviderLogos';

export function AiProviderSelectDialog(props: {
  locale: string | undefined;
  open: boolean;
  adapters: AiProviderAdapter[];
  onSelect: (adapterCode: string) => void;
  onClose: () => void;
}) {
  const { locale, open, adapters, onSelect, onClose } = props;

  if (!open) {
    return null;
  }

  const title = locale?.startsWith('en') ? 'Select AI Provider' : '选择AI供应商';
  const description = locale?.startsWith('en')
    ? 'Choose an AI provider to configure'
    : '选择要配置的AI供应商';
  const footerText = locale?.startsWith('en')
    ? 'More providers can be extended via plugins'
    : '更多供应商可通过插件扩展接入';

  return (
    <div className="member-modal-overlay" onClick={onClose}>
      <div className="member-modal ai-provider-select-modal" onClick={event => event.stopPropagation()}>
        <div className="member-modal__header">
          <div>
            <h3>{title}</h3>
            <p>{description}</p>
          </div>
          <button
            type="button"
            className="member-modal__close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <div className="ai-provider-select-grid">
          {adapters.map(adapter => {
            const adapterMeta = getLocalizedAdapterMeta(adapter, locale);
            const Logo = getAiProviderLogo(adapter.adapter_code);
            return (
              <button
                key={adapter.adapter_code}
                type="button"
                className="ai-provider-select-card"
                onClick={() => onSelect(adapter.adapter_code)}
              >
                <div className="ai-provider-select-card__logo">
                  <Logo width={40} height={40} />
                </div>
                <div className="ai-provider-select-card__body">
                  <h4 className="ai-provider-select-card__name">{adapterMeta.label}</h4>
                  <p className="ai-provider-select-card__desc">{adapterMeta.description}</p>
                  <div className="ai-provider-select-card__tags">
                    {(adapter.supported_model_types ?? []).slice(0, 3).map(type => (
                      <span key={type} className="ai-provider-select-card__tag">
                        {getLocalizedModelTypeLabel(type, locale)}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="ai-provider-select-card__arrow">
                  <span>+</span>
                </div>
              </button>
            );
          })}
        </div>
        <div className="ai-provider-select-footer">
          <div className="ai-provider-select-footer__icon">
            <Puzzle size={16} />
          </div>
          <span className="ai-provider-select-footer__text">{footerText}</span>
        </div>
      </div>
    </div>
  );
}
