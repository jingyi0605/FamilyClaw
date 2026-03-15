import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useAuthContext } from '../../auth';
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
  const [username, setUsername] = useState('user');
  const [password, setPassword] = useState('user');
  const [focusedField, setFocusedField] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      await login(username.trim(), password);
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
          <form className="login-form" onSubmit={event => void handleSubmit(event)}>
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
                  type="text"
                  autoComplete="username"
                  value={username}
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
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
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
        <p>© 2024 FamilyClaw · {t('login.footer')}</p>
      </div>
    </div>
  );
}
