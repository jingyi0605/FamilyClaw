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
            style={{ width: `${p.width}px`, height: `${p.width}px`, left: `${p.left}%`, top: `${p.top}%`, animationDelay: `${p.delay}s`, animationDuration: `${p.duration}s` }}
          />
        ))}
      </div>
      <div className="welcome-content">
        <div className="welcome-logo-wrapper"><div className="welcome-logo">✨</div></div>
        <div className="welcome-text-wrapper"><h1 className="welcome-text">{t('setup.welcome.title')}</h1></div>
        <div className="welcome-text-wrapper"><p className="welcome-subtext">{t('setup.welcome.subtitle')}</p></div>
        <div className="welcome-action">
          <button className="welcome-btn" onClick={() => {
            setFadeOut(true);
            window.setTimeout(() => props.onComplete(), 500);
          }}>{t('setup.welcome.continue')}</button>
        </div>
      </div>
    </div>
  );
}
