import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useAuthContext } from '../../auth';
import {
  BOOTSTRAP_LOGIN_PASSWORD,
  BOOTSTRAP_LOGIN_USERNAME,
  readBootstrapLoginPrefillDismissedFromBrowserStorage,
} from '../../shared/login/localState';
import { useI18n } from '../i18n/I18nProvider';
import { LanguageSwitcher } from './LanguageSwitcher';
import { ThemeSwitcher } from './ThemeSwitcher';

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
        color: colors[Math.floor(Math.random() * colors.length)] ?? colors[0],
      });
    }

    const animate = () => {
      context.clearRect(0, 0, canvas.width, canvas.height);

      particles.forEach(particle => {
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
      });

      context.globalAlpha = 1;
      animationId = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      cancelAnimationFrame(animationId);
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

export function H5LoginPage() {
  const { login, loginPending, loginError } = useAuthContext();
  const { t } = useI18n();
  const shouldPrefillBootstrapAccount = !readBootstrapLoginPrefillDismissedFromBrowserStorage();
  const [username, setUsername] = useState(() => (
    shouldPrefillBootstrapAccount ? BOOTSTRAP_LOGIN_USERNAME : ''
  ));
  const [password, setPassword] = useState(() => (
    shouldPrefillBootstrapAccount ? BOOTSTRAP_LOGIN_PASSWORD : ''
  ));
  const [focusedField, setFocusedField] = useState<string | null>(null);
  const usernameInputRef = useRef<HTMLInputElement>(null);
  const passwordInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const syncAutofilledValue = () => {
      const nextUsername = usernameInputRef.current?.value ?? '';
      const nextPassword = passwordInputRef.current?.value ?? '';
      setUsername(nextUsername);
      setPassword(nextPassword);
    };

    // 浏览器自动填充通常晚于首帧渲染，补两次同步，别让按钮状态和真实输入框脱节。
    const frameId = window.requestAnimationFrame(syncAutofilledValue);
    const timeoutId = window.setTimeout(syncAutofilledValue, 300);

    return () => {
      window.cancelAnimationFrame(frameId);
      window.clearTimeout(timeoutId);
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextUsername = (usernameInputRef.current?.value ?? username).trim();
    const nextPassword = passwordInputRef.current?.value ?? password;

    try {
      await login(nextUsername, nextPassword);
    } catch {
      return;
    }
  }

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
              <svg width="56" height="56" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg" className="login-brand__logo-icon">
                <path d="M14 25c-1.1 0-2.2-.7-3.3-1.8C8.6 20.5 7 18 7 15c0-2.8 2-5 4.5-5 1.2 0 2 .5 2.5 1.3.5-.8 1.3-1.3 2.5-1.3 2.5 0 4.5 2.2 4.5 5 0 3-1.6 5.5-3.7 8.2C16.2 24.3 15.1 25 14 25Z" fill="currentColor" opacity="0.9" />
                <ellipse cx="7.5" cy="8" rx="2.5" ry="3" fill="currentColor" />
                <ellipse cx="14" cy="6" rx="2.5" ry="3" fill="currentColor" />
                <ellipse cx="20.5" cy="8" rx="2.5" ry="3" fill="currentColor" />
                <ellipse cx="4.5" cy="12.5" rx="2" ry="2.5" fill="currentColor" opacity="0.8" />
                <ellipse cx="23.5" cy="12.5" rx="2" ry="2.5" fill="currentColor" opacity="0.8" />
              </svg>
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
          <form className="login-form" autoComplete="on" method="post" onSubmit={event => void handleSubmit(event)}>
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
                  ref={usernameInputRef}
                  id="username"
                  name="username"
                  type="text"
                  autoComplete="username"
                  autoCapitalize="none"
                  autoCorrect="off"
                  spellCheck={false}
                  defaultValue={shouldPrefillBootstrapAccount ? BOOTSTRAP_LOGIN_USERNAME : ''}
                  onChange={event => setUsername(event.target.value)}
                  onFocus={() => setFocusedField('username')}
                  onBlur={() => setFocusedField(null)}
                  placeholder={t('login.usernamePlaceholder')}
                  className="login-form__input"
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
                  ref={passwordInputRef}
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  defaultValue={shouldPrefillBootstrapAccount ? BOOTSTRAP_LOGIN_PASSWORD : ''}
                  onChange={event => setPassword(event.target.value)}
                  onFocus={() => setFocusedField('password')}
                  onBlur={() => setFocusedField(null)}
                  placeholder={t('login.passwordPlaceholder')}
                  className="login-form__input"
                />
              </div>
            </div>

            {loginError ? (
              <div className="login-form__error">
                <span className="login-form__error-icon">⚠️</span>
                <span>{loginError}</span>
              </div>
            ) : null}

            <button
              className="login-form__submit"
              type="submit"
              disabled={loginPending || !username.trim() || !password}
            >
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
        <p>© 2026 FamilyClaw · {t('login.footer')}</p>
      </div>
    </div>
  );
}
