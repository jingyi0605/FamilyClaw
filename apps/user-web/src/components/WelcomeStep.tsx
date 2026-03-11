import { useEffect, useState, useMemo } from 'react';
import './WelcomeStep.css';

interface WelcomeStepProps {
  onComplete: () => void;
}

export function WelcomeStep({ onComplete }: WelcomeStepProps) {
  const [fadeOut, setFadeOut] = useState(false);
  const [lang, setLang] = useState<'zh' | 'en'>('zh');

  useEffect(() => {
    const browserLang = navigator.language || navigator.languages?.[0];
    if (browserLang && browserLang.toLowerCase().startsWith('en')) {
      setLang('en');
    }
  }, []);

  const handleNext = () => {
    setFadeOut(true);
    setTimeout(() => {
      onComplete();
    }, 500);
  };

  const texts = {
    zh: {
      title: "欢迎来到 Family Claw",
      subtitle: "一个你外婆都可以玩懂的AI助手！",
      btn: "继续"
    },
    en: {
      title: "Welcome to Family Claw",
      subtitle: "An AI assistant even your grandma can play with!",
      btn: "Continue"
    }
  };

  const t = texts[lang];

  // Randomize particles once
  const particles = useMemo(() => {
    return [...Array(8)].map((_, i) => ({
      id: i,
      width: Math.random() * 20 + 10,
      left: Math.random() * 100,
      top: Math.random() * 100,
      delay: Math.random() * 2,
      duration: Math.random() * 2 + 3,
    }));
  }, []);

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
          <div className="welcome-logo">✨</div>
        </div>

        <div className="welcome-text-wrapper">
          <h1 className="welcome-text">{t.title}</h1>
        </div>

        <div className="welcome-text-wrapper">
          <p className="welcome-subtext">{t.subtitle}</p>
        </div>

        <div className="welcome-action">
          <button className="welcome-btn" onClick={handleNext}>
            {t.btn}
          </button>
        </div>
      </div>
    </div>
  );
}
