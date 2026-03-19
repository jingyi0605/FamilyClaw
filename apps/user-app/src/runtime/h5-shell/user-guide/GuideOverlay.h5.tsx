import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { useI18n } from '../i18n/I18nProvider';
import { getGuideAnchor } from '../../shared/user-guide/anchorRegistry';
import type { UserGuideOverlayProps } from '../../shared/user-guide/GuideOverlay.types';

type AnchorRect = {
  top: number;
  left: number;
  width: number;
  height: number;
};

function readAnchorRect(anchorId: string | null): AnchorRect | null {
  if (!anchorId) {
    return null;
  }

  const anchor = getGuideAnchor(anchorId);
  const rect = anchor?.element?.getBoundingClientRect();
  if (!rect || rect.width <= 0 || rect.height <= 0) {
    return null;
  }

  return {
    top: rect.top,
    left: rect.left,
    width: rect.width,
    height: rect.height,
  };
}

function shouldUseAnchorLayout(rect: AnchorRect | null) {
  if (!rect || typeof window === 'undefined') {
    return false;
  }

  return rect.width < window.innerWidth * 0.78 && rect.height < window.innerHeight * 0.6;
}

export function GuideOverlay(props: UserGuideOverlayProps) {
  const { t } = useI18n();
  const [anchorRect, setAnchorRect] = useState<AnchorRect | null>(null);

  useEffect(() => {
    if (!props.anchorId) {
      setAnchorRect(null);
      return undefined;
    }

    const syncAnchorRect = () => {
      setAnchorRect(readAnchorRect(props.anchorId));
    };

    syncAnchorRect();
    window.addEventListener('resize', syncAnchorRect);
    window.addEventListener('scroll', syncAnchorRect, true);
    return () => {
      window.removeEventListener('resize', syncAnchorRect);
      window.removeEventListener('scroll', syncAnchorRect, true);
    };
  }, [props.anchorId]);

  const isBusy = props.status === 'waiting_anchor' || props.status === 'completing' || props.isActionPending;
  const useAnchorLayout = shouldUseAnchorLayout(anchorRect);
  const bubbleStyle = useMemo(() => {
    if (!useAnchorLayout || !anchorRect || typeof window === 'undefined') {
      return null;
    }

    const width = Math.min(360, window.innerWidth - 32);
    const desiredTop = anchorRect.top + anchorRect.height + 16;
    const fallbackTop = Math.max(16, anchorRect.top - 200 - 16);
    const top = desiredTop + 200 < window.innerHeight ? desiredTop : fallbackTop;
    const left = Math.min(
      Math.max(16, anchorRect.left),
      Math.max(16, window.innerWidth - width - 16),
    );

    return {
      top,
      left,
      width,
    };
  }, [anchorRect, useAnchorLayout]);

  if (typeof document === 'undefined') {
    return null;
  }

  const overlay = (
    <>
      {useAnchorLayout && anchorRect ? (
        <div
          style={{
            position: 'fixed',
            top: Math.max(8, anchorRect.top - 8),
            left: Math.max(8, anchorRect.left - 8),
            width: anchorRect.width + 16,
            height: anchorRect.height + 16,
            borderRadius: 24,
            border: '2px solid #f58a3a',
            boxShadow: '0 0 0 9999px rgba(20, 17, 25, 0.34)',
            pointerEvents: 'none',
            zIndex: 1200,
          }}
        />
      ) : (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(20, 17, 25, 0.18)',
            pointerEvents: 'none',
            zIndex: 1190,
          }}
        />
      )}

      <div
        style={{
          position: 'fixed',
          zIndex: 1210,
          right: bubbleStyle ? undefined : 24,
          bottom: bubbleStyle ? undefined : 24,
          top: bubbleStyle?.top,
          left: bubbleStyle?.left,
          width: bubbleStyle?.width ?? 'min(360px, calc(100vw - 32px))',
          background: 'linear-gradient(180deg, rgba(255,255,255,0.98), rgba(255,248,242,0.98))',
          borderRadius: 24,
          border: '1px solid rgba(245, 138, 58, 0.24)',
          boxShadow: '0 24px 60px rgba(26, 20, 33, 0.2)',
          padding: '18px 18px 16px',
          color: '#1d1a20',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 10 }}>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '4px 10px',
              borderRadius: 999,
              background: 'rgba(245, 138, 58, 0.12)',
              color: '#b55416',
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: '0.02em',
            }}
          >
            {t('userGuide.badge')}
          </span>
          <span style={{ fontSize: 12, color: '#6d6477' }}>
            {t('userGuide.progress', {
              current: props.currentStepIndex + 1,
              total: props.totalSteps,
            })}
          </span>
        </div>

        <h3 style={{ margin: '0 0 8px', fontSize: 20, lineHeight: 1.3 }}>{props.title}</h3>
        <p style={{ margin: 0, fontSize: 14, lineHeight: 1.7, color: '#51475d' }}>{props.content}</p>

        {isBusy ? (
          <p style={{ margin: '10px 0 0', fontSize: 12, color: '#8a5b27' }}>
            {props.status === 'completing' || props.isActionPending
              ? t('userGuide.status.completing')
              : t('userGuide.status.locating')}
          </p>
        ) : null}

        {props.errorMessage ? (
          <p style={{ margin: '10px 0 0', fontSize: 12, color: '#b42318' }}>
            {props.errorMessage}
          </p>
        ) : null}

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginTop: 16 }}>
          <button
            type="button"
            onClick={() => props.onSkip()}
            disabled={isBusy}
            style={{
              border: 'none',
              background: 'transparent',
              color: '#6d6477',
              fontSize: 14,
              cursor: isBusy ? 'not-allowed' : 'pointer',
            }}
          >
            {t('userGuide.actions.skip')}
          </button>
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              type="button"
              onClick={() => props.onPrevious()}
              disabled={props.currentStepIndex === 0 || isBusy}
              style={{
                minWidth: 88,
                padding: '10px 14px',
                borderRadius: 999,
                border: '1px solid rgba(79, 65, 94, 0.16)',
                background: '#ffffff',
                color: '#3a3342',
                cursor: props.currentStepIndex === 0 || isBusy ? 'not-allowed' : 'pointer',
              }}
            >
              {t('userGuide.actions.previous')}
            </button>
            <button
              type="button"
              onClick={() => (props.isLastStep ? props.onFinish() : props.onNext())}
              disabled={isBusy}
              style={{
                minWidth: 88,
                padding: '10px 16px',
                borderRadius: 999,
                border: 'none',
                background: '#f58a3a',
                color: '#fff8f2',
                fontWeight: 700,
                cursor: isBusy ? 'not-allowed' : 'pointer',
              }}
            >
              {props.isLastStep ? t('userGuide.actions.finish') : t('userGuide.actions.next')}
            </button>
          </div>
        </div>
      </div>
    </>
  );

  return createPortal(overlay, document.body);
}
