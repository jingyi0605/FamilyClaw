import { useEffect, useRef, useState } from 'react';
import { useI18n } from '../i18n/I18nProvider';

const LOCALE_FLAG_FALLBACK: Record<string, string> = {
  'zh-CN': '🇨🇳',
  'en-US': '🇺🇸',
};

function resolveFlag(localeId: string, flag?: string | null) {
  if (flag && /[\u{1F1E6}-\u{1F1FF}]/u.test(flag)) {
    return flag;
  }
  return LOCALE_FLAG_FALLBACK[localeId] ?? flag ?? '🌐';
}

export function LanguageSwitcher() {
  const { locale, locales, setLocale, formatLocaleLabel } = useI18n();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const currentLocale = locales.find(item => item.id === locale);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, []);

  return (
    <div className="lang-switcher" ref={containerRef}>
      <button
        className="lang-switcher__trigger"
        type="button"
        title={currentLocale ? formatLocaleLabel(currentLocale) : undefined}
        onClick={() => setOpen(current => !current)}
      >
        <span className="lang-switcher__flag">
          {resolveFlag(currentLocale?.id ?? locale, currentLocale?.flag)}
        </span>
        <span className="lang-switcher__label">{currentLocale ? formatLocaleLabel(currentLocale) : ''}</span>
        <span className="lang-switcher__arrow">▾</span>
      </button>

      {open ? (
        <div className="lang-switcher__dropdown">
          {locales.map(item => (
            <button
              key={item.id}
              type="button"
              className={`lang-switcher__item ${item.id === locale ? 'lang-switcher__item--active' : ''}`}
              onClick={() => {
                setLocale(item.id);
                setOpen(false);
              }}
            >
              <span className="lang-switcher__item-flag">{resolveFlag(item.id, item.flag)}</span>
              <span className="lang-switcher__item-label">{formatLocaleLabel(item)}</span>
              {item.id === locale ? <span className="lang-switcher__item-check">✓</span> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
