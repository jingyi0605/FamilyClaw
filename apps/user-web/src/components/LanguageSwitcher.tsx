/* ============================================================
 * LanguageSwitcher - 语言切换组件
 * ============================================================ */
import { useState, useRef, useEffect } from 'react';
import { formatLocaleOptionLabel } from '../i18n';
import { useI18n } from '../i18n/I18nProvider';

export function LanguageSwitcher() {
  const { locale, setLocale, locales } = useI18n();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentLang = locales.find(l => l.id === locale);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="lang-switcher" ref={dropdownRef}>
      <button
        className="lang-switcher__trigger"
        onClick={() => setIsOpen(!isOpen)}
        title={currentLang ? formatLocaleOptionLabel(currentLang) : undefined}
      >
        <span className="lang-switcher__flag">{currentLang?.flag}</span>
        <span className="lang-switcher__label">{currentLang ? formatLocaleOptionLabel(currentLang) : ''}</span>
          <span className="lang-switcher__arrow">▾</span>
      </button>

      {isOpen && (
        <div className="lang-switcher__dropdown">
          {locales.map(lang => (
            <button
              key={lang.id}
              className={`lang-switcher__item ${locale === lang.id ? 'lang-switcher__item--active' : ''}`}
              onClick={() => {
                setLocale(lang.id);
                setIsOpen(false);
              }}
            >
              <span className="lang-switcher__item-flag">{lang.flag}</span>
              <span className="lang-switcher__item-label">{formatLocaleOptionLabel(lang)}</span>
              {locale === lang.id && (
                <span className="lang-switcher__item-check">✓</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
