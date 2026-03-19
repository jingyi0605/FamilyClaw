import { useMemo, useState } from 'react';
import { useI18n } from '../../runtime';
import './WelcomeStep.css';

export function WelcomeStep(props: { onComplete: () => void }) {
  const { t } = useI18n();
  const [fadeOut, setFadeOut] = useState(false);

  const particles = useMemo(() => [...Array(8)].map((_, i) => ({
    id: i,
    width: Math.random() * 20 + 10,
    left: Math.random() * 100,
    top: Math.random() * 100,
    delay: Math.random() * 2,
    duration: Math.random() * 2 + 3,
  })), []);

  return (
    <div className={`welcome-overlay ${fadeOut ? 'welcome-fade-out' : ''}`}>
      <div className="welcome-particles">
        {particles.map(p => (
          <div
            key={p.id}
            className="particle"
            style={{
              width: `${p.width}px`,
              height: `${p.width}px`,
              left: `${p.left}%`,
              top: `${p.top}%`,
              animationDelay: `${p.delay}s`,
              animationDuration: `${p.duration}s`,
            }}
          />
        ))}
      </div>
      <div className="welcome-content">
        <div className="welcome-logo-wrapper">
          <div className="welcome-logo">
            <svg viewBox="0 0 56 56" width="1em" height="1em" aria-hidden="true" className="welcome-logo-svg">
              {/* 中心心形 - 从下方聚合 */}
              <path
                className="welcome-logo-part welcome-logo-heart"
                d="M28 50c-2.2 0-4.4-1.4-6.6-3.6C17.2 41 14 36 14 30c0-5.6 4-10 9-10 2.4 0 4 1 5 2.6 1-1.6 2.6-2.6 5-2.6 5 0 9 4.4 9 10 0 6-3.2 11-7.4 16.4C32.4 48.6 30.2 50 28 50Z"
                fill="var(--brand-primary, #d97756)"
              />
              {/* 上方左爪印 - 从左上分散 */}
              <ellipse
                className="welcome-logo-part welcome-logo-claw-1"
                cx="15" cy="16" rx="5" ry="6"
                fill="var(--brand-primary, #d97756)"
              />
              {/* 上方中爪印 - 从上方分散 */}
              <ellipse
                className="welcome-logo-part welcome-logo-claw-2"
                cx="28" cy="12" rx="5" ry="6"
                fill="var(--brand-primary, #d97756)"
              />
              {/* 上方右爪印 - 从右上分散 */}
              <ellipse
                className="welcome-logo-part welcome-logo-claw-3"
                cx="41" cy="16" rx="5" ry="6"
                fill="var(--brand-primary, #d97756)"
              />
              {/* 左侧小爪印 - 从左下分散 */}
              <ellipse
                className="welcome-logo-part welcome-logo-claw-4"
                cx="9" cy="25" rx="4" ry="5"
                fill="var(--brand-primary, #d97756)"
                opacity="0.8"
              />
              {/* 右侧小爪印 - 从右下分散 */}
              <ellipse
                className="welcome-logo-part welcome-logo-claw-5"
                cx="47" cy="25" rx="4" ry="5"
                fill="var(--brand-primary, #d97756)"
                opacity="0.8"
              />
            </svg>
          </div>
        </div>
        <div className="welcome-text-wrapper">
          <h1 className="welcome-text">{t('setup.welcome.title')}</h1>
        </div>
        <div className="welcome-text-wrapper">
          <p className="welcome-subtext">{t('setup.welcome.subtitle')}</p>
        </div>
        <div className="welcome-action">
          <button
            type="button"
            className="btn btn--primary welcome-btn"
            onClick={() => {
              setFadeOut(true);
              window.setTimeout(() => props.onComplete(), 500);
            }}
          >
            {t('setup.welcome.continue')}
          </button>
        </div>
      </div>
    </div>
  );
}
