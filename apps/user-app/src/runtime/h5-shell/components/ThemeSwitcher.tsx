import { useEffect, useRef, useState } from 'react';
import { useTheme } from '../theme/ThemeProvider';

export function ThemeSwitcher() {
  const { themeId, themeList, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const currentTheme = themeList.find(item => item.id === themeId) ?? themeList[0];

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
    <div className="theme-switcher" ref={containerRef}>
      <button
        className="theme-switcher__trigger"
        type="button"
        title={currentTheme?.label}
        onClick={() => setOpen(current => !current)}
      >
        <span className="theme-switcher__icon">{currentTheme?.emoji}</span>
      </button>

      {open ? (
        <div className="theme-switcher__dropdown">
          <div className="theme-switcher__header">选择主题</div>
          <div className="theme-switcher__list">
            {themeList.map(theme => (
              <button
                key={theme.id}
                type="button"
                className={`theme-switcher__item ${theme.id === themeId ? 'theme-switcher__item--active' : ''}`}
                onClick={() => {
                  setTheme(theme.id);
                  setOpen(false);
                }}
              >
                <span className="theme-switcher__item-emoji">{theme.emoji}</span>
                <span className="theme-switcher__item-info">
                  <span className="theme-switcher__item-label">{theme.label}</span>
                  <span className="theme-switcher__item-desc">{theme.description}</span>
                </span>
                {theme.id === themeId ? <span className="theme-switcher__item-check">✓</span> : null}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
