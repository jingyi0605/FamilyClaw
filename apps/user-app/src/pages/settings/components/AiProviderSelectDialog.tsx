/**
 * AI 供应商选择弹窗
 */
import type { AiProviderAdapter } from '../settingsTypes';
import { getLocalizedAdapterMeta, getLocalizedCapabilityLabel } from './aiProviderCatalog';
import { getAiProviderLogo } from './AiProviderLogos';

export function AiProviderSelectDialog(props: {
  open: boolean;
  locale: string | undefined;
  adapters: AiProviderAdapter[];
  copy: {
    title: string;
    description: string;
    close: string;
  };
  onSelect: (adapterCode: string) => void;
  onClose: () => void;
}) {
  const { open, locale, adapters, copy, onSelect, onClose } = props;

  if (!open) {
    return null;
  }

  return (
    <div className="member-modal-overlay" onClick={onClose}>
      <div className="member-modal ai-provider-select-modal" onClick={event => event.stopPropagation()}>
        <div className="member-modal__header">
          <div>
            <h3>{copy.title}</h3>
            <p>{copy.description}</p>
          </div>
          <button
            type="button"
            className="member-modal__close"
            onClick={onClose}
            aria-label={copy.close}
          >
            x
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
                    {(adapter.default_supported_capabilities ?? []).slice(0, 3).map(capability => (
                      <span key={capability} className="ai-provider-select-card__tag">
                        {getLocalizedCapabilityLabel(capability, locale)}
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
      </div>
    </div>
  );
}
