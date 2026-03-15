import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react';
import Taro from '@tarojs/taro';
import {
  DEFAULT_THEME_ID,
  formatLocaleOptionLabel,
  getStoredLocaleId,
  getStoredThemeId,
  persistLocaleId,
  persistThemeId,
} from '@familyclaw/user-core';
import { resolveBootstrapRoute, taroStorage, useAppRuntime } from '../../runtime';
import { loginMessages, type LoginLocaleId, type LoginMessageKey } from './messages';
import { applyLoginThemeCssVariables, loginThemeList } from './theme-presets';

if (process.env.TARO_ENV === 'h5') {
  require('./index.h5.scss');
} else {
  require('./index.rn.scss');
}

type LoginLocaleDefinition = {
  id: LoginLocaleId;
  label: string;
  nativeLabel: string;
  flag: string;
  source: 'builtin';
  sourceType: 'builtin';
};

type LoginThemeContextValue = {
  themeId: typeof loginThemeList[number]['id'];
  setTheme: (themeId: typeof loginThemeList[number]['id']) => void;
};

type LoginI18nContextValue = {
  locale: LoginLocaleId;
  setLocale: (locale: LoginLocaleId) => void;
  t: (key: LoginMessageKey) => string;
  locales: LoginLocaleDefinition[];
};

const LOGIN_LOCALES: LoginLocaleDefinition[] = [
  { id: 'zh-CN', label: '简体中文', nativeLabel: '简体中文', flag: '🇨🇳', source: 'builtin', sourceType: 'builtin' },
  { id: 'en-US', label: 'English', nativeLabel: 'English', flag: '🇺🇸', source: 'builtin', sourceType: 'builtin' },
];

const LoginThemeContext = createContext<LoginThemeContextValue | null>(null);
const LoginI18nContext = createContext<LoginI18nContextValue | null>(null);

function useLoginTheme() {
  const context = useContext(LoginThemeContext);
  if (!context) {
    throw new Error('useLoginTheme 必须在 LoginThemeProvider 内使用');
  }

  return context;
}

function useLoginI18n() {
  const context = useContext(LoginI18nContext);
  if (!context) {
    throw new Error('useLoginI18n 必须在 LoginI18nProvider 内使用');
  }

  return context;
}

function LoginThemeProvider({ children }: { children: ReactNode }) {
  const [themeId, setThemeId] = useState(DEFAULT_THEME_ID);

  useEffect(() => {
    void getStoredThemeId(taroStorage).then(storedThemeId => {
      setThemeId(storedThemeId);
    });
  }, []);

  useEffect(() => {
    applyLoginThemeCssVariables(themeId);
    void persistThemeId(taroStorage, themeId);
  }, [themeId]);

  const value = useMemo<LoginThemeContextValue>(() => ({
    themeId,
    setTheme: setThemeId,
  }), [themeId]);

  return <LoginThemeContext.Provider value={value}>{children}</LoginThemeContext.Provider>;
}

function LoginI18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<LoginLocaleId>('zh-CN');

  useEffect(() => {
    void getStoredLocaleId(taroStorage, LOGIN_LOCALES, 'zh-CN').then(storedLocale => {
      setLocaleState((storedLocale as LoginLocaleId) === 'en-US' ? 'en-US' : 'zh-CN');
    });
  }, []);

  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.lang = locale;
    }
    void persistLocaleId(taroStorage, locale, LOGIN_LOCALES, 'zh-CN');
  }, [locale]);

  const setLocale = useCallback((nextLocale: LoginLocaleId) => {
    setLocaleState(nextLocale);
  }, []);

  const t = useCallback((key: LoginMessageKey) => loginMessages[locale][key], [locale]);

  const value = useMemo<LoginI18nContextValue>(() => ({
    locale,
    setLocale,
    t,
    locales: LOGIN_LOCALES,
  }), [locale, setLocale, t]);

  return <LoginI18nContext.Provider value={value}>{children}</LoginI18nContext.Provider>;
}

function FloatingParticles() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }

    const context = canvas.getContext('2d');
    if (!context) {
      return;
    }

    let animationId = 0;
    const particles: Array<{
      x: number;
      y: number;
      vx: number;
      vy: number;
      size: number;
      opacity: number;
      color: string;
    }> = [];

    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    const colors = ['#d97756', '#7c9ef5', '#b480ff', '#52a960', '#ffd700'];
    for (let index = 0; index < 50; index += 1) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        size: Math.random() * 4 + 1,
        opacity: Math.random() * 0.5 + 0.1,
        color: colors[Math.floor(Math.random() * colors.length)],
      });
    }

    const animate = () => {
      context.clearRect(0, 0, canvas.width, canvas.height);

      for (const particle of particles) {
        particle.x += particle.vx;
        particle.y += particle.vy;

        if (particle.x < 0 || particle.x > canvas.width) {
          particle.vx *= -1;
        }
        if (particle.y < 0 || particle.y > canvas.height) {
          particle.vy *= -1;
        }

        context.beginPath();
        context.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
        context.fillStyle = particle.color;
        context.globalAlpha = particle.opacity;
        context.fill();
      }

      context.globalAlpha = 1;
      animationId = window.requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      window.cancelAnimationFrame(animationId);
    };
  }, []);

  return <canvas ref={canvasRef} className="login-particles" />;
}

function FloatingShapes() {
  return (
    <div className="login-shapes">
      <div className="login-shape login-shape--1" />
      <div className="login-shape login-shape--2" />
      <div className="login-shape login-shape--3" />
      <div className="login-shape login-shape--4" />
    </div>
  );
}

function ThemeSwitcher() {
  const { themeId, setTheme } = useLoginTheme();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const currentTheme = loginThemeList.find(theme => theme.id === themeId);

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
        onClick={() => setIsOpen(current => !current)}
        title={currentTheme?.label}
        type="button"
      >
        <span className="theme-switcher__icon">{currentTheme?.emoji}</span>
      </button>

      {isOpen ? (
        <div className="theme-switcher__dropdown">
          <div className="theme-switcher__header">选择主题</div>
          <div className="theme-switcher__list">
            {loginThemeList.map(theme => (
              <button
                key={theme.id}
                className={`theme-switcher__item ${themeId === theme.id ? 'theme-switcher__item--active' : ''}`}
                onClick={() => {
                  setTheme(theme.id);
                  setIsOpen(false);
                }}
                type="button"
              >
                <span className="theme-switcher__item-emoji">{theme.emoji}</span>
                <span className="theme-switcher__item-info">
                  <span className="theme-switcher__item-label">{theme.label}</span>
                  <span className="theme-switcher__item-desc">{theme.description}</span>
                </span>
                {themeId === theme.id ? <span className="theme-switcher__item-check">✓</span> : null}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function LanguageSwitcher() {
  const { locale, setLocale, locales } = useLoginI18n();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const currentLang = locales.find(item => item.id === locale);

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
        onClick={() => setIsOpen(current => !current)}
        title={currentLang ? formatLocaleOptionLabel(currentLang) : undefined}
        type="button"
      >
        <span className="lang-switcher__flag">{currentLang?.flag}</span>
        <span className="lang-switcher__label">{currentLang ? formatLocaleOptionLabel(currentLang) : ''}</span>
        <span className="lang-switcher__arrow">▾</span>
      </button>

      {isOpen ? (
        <div className="lang-switcher__dropdown">
          {locales.map(lang => (
            <button
              key={lang.id}
              className={`lang-switcher__item ${locale === lang.id ? 'lang-switcher__item--active' : ''}`}
              onClick={() => {
                setLocale(lang.id);
                setIsOpen(false);
              }}
              type="button"
            >
              <span className="lang-switcher__item-flag">{lang.flag}</span>
              <span className="lang-switcher__item-label">{formatLocaleOptionLabel(lang)}</span>
              {locale === lang.id ? <span className="lang-switcher__item-check">✓</span> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function LoginPageBody() {
  const { bootstrap, error, loading, login } = useAppRuntime();
  const { t } = useLoginI18n();
  const [username, setUsername] = useState('user');
  const [password, setPassword] = useState('user');
  const [focusedField, setFocusedField] = useState<string | null>(null);
  const [loginPending, setLoginPending] = useState(false);
  const [loginError, setLoginError] = useState('');

  useEffect(() => {
    if (loading || !bootstrap?.actor?.authenticated) {
      return;
    }

    void Taro.reLaunch({ url: resolveBootstrapRoute(bootstrap) });
  }, [bootstrap, loading]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoginPending(true);
    setLoginError('');

    try {
      const nextBootstrap = await login(username.trim(), password);
      await Taro.reLaunch({ url: resolveBootstrapRoute(nextBootstrap) });
    } catch (submitError) {
      setLoginError(submitError instanceof Error ? submitError.message : 'Login failed');
      return;
    } finally {
      setLoginPending(false);
    }
  }

  const visibleError = loginError || error;

  return (
    <div className="login-page">
      <div className="login-bg">
        <div className="login-bg__gradient" />
        <FloatingShapes />
        <FloatingParticles />
      </div>

      <div className="login-controls">
        <LanguageSwitcher />
        <ThemeSwitcher />
      </div>

      <div className="login-container">
        <div className="login-brand">
          <div className="login-brand__content">
            <div className="login-brand__logo">
              <span className="login-brand__logo-icon">🏠</span>
              <span className="login-brand__logo-text">FamilyClaw</span>
            </div>
            <h1 className="login-brand__title">{t('login.welcome')}</h1>
            <p className="login-brand__desc">{t('login.subtitle')}</p>
            <div className="login-brand__features">
              <div className="login-brand__feature">
                <span className="login-brand__feature-icon">💬</span>
                <span>{t('login.feature1')}</span>
              </div>
              <div className="login-brand__feature">
                <span className="login-brand__feature-icon">🧠</span>
                <span>{t('login.feature2')}</span>
              </div>
              <div className="login-brand__feature">
                <span className="login-brand__feature-icon">🔒</span>
                <span>{t('login.feature3')}</span>
              </div>
            </div>
          </div>
          <div className="login-brand__decoration">
            <div className="login-brand__orb login-brand__orb--1" />
            <div className="login-brand__orb login-brand__orb--2" />
            <div className="login-brand__orb login-brand__orb--3" />
          </div>
        </div>

        <div className="login-form-wrapper">
          <form className="login-form" onSubmit={(event) => void handleSubmit(event)}>
            <div className="login-form__header">
              <h2 className="login-form__title">{t('login.title')}</h2>
              <p className="login-form__subtitle">{t('login.formSubtitle')}</p>
            </div>

            <div className={`login-form__field ${focusedField === 'username' ? 'login-form__field--focused' : ''}`}>
              <label className="login-form__label" htmlFor="username">
                {t('login.username')}
              </label>
              <div className="login-form__input-wrapper">
                <span className="login-form__input-icon">
                  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                </span>
                <input
                  id="username"
                  autoComplete="username"
                  className="login-form__input"
                  placeholder={t('login.usernamePlaceholder')}
                  type="text"
                  value={username}
                  onBlur={() => setFocusedField(null)}
                  onChange={event => setUsername(event.target.value)}
                  onFocus={() => setFocusedField('username')}
                />
              </div>
            </div>

            <div className={`login-form__field ${focusedField === 'password' ? 'login-form__field--focused' : ''}`}>
              <label className="login-form__label" htmlFor="password">
                {t('login.password')}
              </label>
              <div className="login-form__input-wrapper">
                <span className="login-form__input-icon">
                  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                </span>
                <input
                  id="password"
                  autoComplete="current-password"
                  className="login-form__input"
                  placeholder={t('login.passwordPlaceholder')}
                  type="password"
                  value={password}
                  onBlur={() => setFocusedField(null)}
                  onChange={event => setPassword(event.target.value)}
                  onFocus={() => setFocusedField('password')}
                />
              </div>
            </div>

            {visibleError ? (
              <div className="login-form__error">
                <span className="login-form__error-icon">⚠️</span>
                <span>{visibleError}</span>
              </div>
            ) : null}

            <button className="login-form__submit" disabled={loginPending || !username.trim() || !password} type="submit">
              {loginPending ? (
                <>
                  <span className="login-form__spinner" />
                  <span>{t('login.loggingIn')}</span>
                </>
              ) : (
                <>
                  <span>{t('login.submit')}</span>
                  <span className="login-form__submit-arrow">→</span>
                </>
              )}
            </button>
          </form>
        </div>
      </div>

      <div className="login-footer">
        <p>© 2024 FamilyClaw · {t('login.footer')}</p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <LoginThemeProvider>
      <LoginI18nProvider>
        <LoginPageBody />
      </LoginI18nProvider>
    </LoginThemeProvider>
  );
}
