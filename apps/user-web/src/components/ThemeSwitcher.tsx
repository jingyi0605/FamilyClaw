/* ============================================================
 * ThemeSwitcher - 主题切换组件
 * ============================================================ */
import { useState, useRef, useEffect } from 'react';
import { useTheme } from '../theme/ThemeProvider';
import { themeList, type ThemeId } from '../theme/tokens';

export function ThemeSwitcher() {
  const { themeId, setTheme } = useTheme();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentTheme = themeList.find(t => t.id === themeId);

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
    <div className="theme-switcher" ref={dropdownRef}>
      <button
        className="theme-switcher__trigger"
        onClick={() => setIsOpen(!isOpen)}
        title={currentTheme?.label}
      >
        <span className="theme-switcher__icon">{currentTheme?.emoji}</span>
      </button>

      {isOpen && (
        <div className="theme-switcher__dropdown">
          <div className="theme-switcher__header">选择主题</div>
          <div className="theme-switcher__list">
            {themeList.map(theme => (
              <button
                key={theme.id}
                className={`theme-switcher__item ${themeId === theme.id ? 'theme-switcher__item--active' : ''}`}
                onClick={() => {
                  setTheme(theme.id as ThemeId);
                  setIsOpen(false);
                }}
              >
                <span className="theme-switcher__item-emoji">{theme.emoji}</span>
                <span className="theme-switcher__item-info">
                  <span className="theme-switcher__item-label">{theme.label}</span>
                  <span className="theme-switcher__item-desc">{theme.description}</span>
                </span>
                {themeId === theme.id && (
                  <span className="theme-switcher__item-check">✓</span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
