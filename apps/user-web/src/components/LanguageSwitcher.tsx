/* ============================================================
 * LanguageSwitcher - 语言切换组件
 * ============================================================ */
import { useState, useRef, useEffect } from 'react';
import { useI18n, type LocaleId } from '../i18n/I18nProvider';

const languages: { id: LocaleId; label: string; nativeLabel: string; flag: string }[] = [
  { id: 'zh-CN', label: '简体中文', nativeLabel: '简体中文', flag: '🇨🇳' },
  { id: 'en-US', label: 'English', nativeLabel: 'English', flag: '🇺🇸' },
];

export function LanguageSwitcher() {
  const { locale, setLocale } = useI18n();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentLang = languages.find(l => l.id === locale);

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
        title={currentLang?.label}
      >
        <span className="lang-switcher__flag">{currentLang?.flag}</span>
        <span className="lang-switcher__label">{currentLang?.nativeLabel}</span>
        <span className="lang-switcher__arrow">▾</span>
      </button>

      {isOpen && (
        <div className="lang-switcher__dropdown">
          {languages.map(lang => (
            <button
              key={lang.id}
              className={`lang-switcher__item ${locale === lang.id ? 'lang-switcher__item--active' : ''}`}
              onClick={() => {
                setLocale(lang.id);
                setIsOpen(false);
              }}
            >
              <span className="lang-switcher__item-flag">{lang.flag}</span>
              <span className="lang-switcher__item-label">{lang.nativeLabel}</span>
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
