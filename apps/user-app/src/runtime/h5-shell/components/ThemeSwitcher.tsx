import { useEffect, useRef, useState } from 'react';
import { useI18n } from '../i18n/I18nProvider';
import { useTheme } from '../theme/ThemeProvider';

export function ThemeSwitcher() {
  const {
    theme,
    themeList,
    themeListLoading,
    themeListError,
    themeFallbackNotice,
    setTheme,
  } = useTheme();
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, []);

  const missingThemeTip = themeFallbackNotice
    ? t('theme.switcher.missingNotice', {
      theme: themeFallbackNotice.disabledThemeId,
    })
    : '';

  return (
    <div className="theme-switcher" ref={containerRef}>
      <button
        className="theme-switcher__trigger"
        type="button"
        title={theme.label}
        onClick={() => setOpen(current => !current)}
      >
        <span className="theme-switcher__icon">{theme.emoji}</span>
      </button>

      {open ? (
        <div className="theme-switcher__dropdown">
          <div className="theme-switcher__header">{t('theme.switcher.title')}</div>
          {themeListLoading ? (
            <div className="theme-switcher__header">{t('theme.switcher.loading')}</div>
          ) : null}
          {themeListError ? (
            <div className="theme-switcher__header">{themeListError}</div>
          ) : null}
          {missingThemeTip ? (
            <div className="theme-switcher__header">{missingThemeTip}</div>
          ) : null}
          <div className="theme-switcher__list">
            {themeList.map(item => {
              const isActive = item.id === theme.id && item.plugin_id === theme.plugin_id;
              return (
                <button
                  key={`${item.plugin_id}:${item.id}`}
                  type="button"
                  className={`theme-switcher__item ${isActive ? 'theme-switcher__item--active' : ''}`}
                  onClick={() => {
                    setTheme({
                      plugin_id: item.plugin_id,
                      theme_id: item.id,
                    });
                    setOpen(false);
                  }}
                >
                  <span className="theme-switcher__item-emoji">{item.emoji}</span>
                  <span className="theme-switcher__item-info">
                    <span className="theme-switcher__item-label">{item.label}</span>
                    <span className="theme-switcher__item-desc">{item.description}</span>
                  </span>
                  {isActive ? <span className="theme-switcher__item-check">✓</span> : null}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}
