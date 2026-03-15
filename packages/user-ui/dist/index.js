import { Text, View } from '@tarojs/components';
import { createElement } from 'react';

export const userAppTokens = {
  colorBg: typeof process !== 'undefined' && process.env.TARO_ENV === 'h5' ? 'var(--bg-app)' : '#f5f6f8',
  colorSurface: typeof process !== 'undefined' && process.env.TARO_ENV === 'h5' ? 'var(--bg-card)' : '#ffffff',
  colorSurfaceMuted: typeof process !== 'undefined' && process.env.TARO_ENV === 'h5' ? 'var(--bg-input)' : '#f9fbff',
  colorBorder: typeof process !== 'undefined' && process.env.TARO_ENV === 'h5' ? 'var(--border-light)' : '#d6dbe4',
  colorText: typeof process !== 'undefined' && process.env.TARO_ENV === 'h5' ? 'var(--text-primary)' : '#152033',
  colorMuted: typeof process !== 'undefined' && process.env.TARO_ENV === 'h5' ? 'var(--text-secondary)' : '#5c6b80',
  colorPrimary: typeof process !== 'undefined' && process.env.TARO_ENV === 'h5' ? 'var(--brand-primary)' : '#1d6fd6',
  colorSuccess: typeof process !== 'undefined' && process.env.TARO_ENV === 'h5' ? 'var(--color-success)' : '#0f9d6c',
  colorWarning: typeof process !== 'undefined' && process.env.TARO_ENV === 'h5' ? 'var(--color-warning)' : '#c47900',
  spacingXs: typeof process !== 'undefined' && process.env.TARO_ENV === 'h5' ? 'var(--spacing-xs)' : '12px',
  spacingSm: typeof process !== 'undefined' && process.env.TARO_ENV === 'h5' ? 'var(--spacing-sm)' : '16px',
  spacingMd: typeof process !== 'undefined' && process.env.TARO_ENV === 'h5' ? 'var(--spacing-md)' : '24px',
  radiusMd: typeof process !== 'undefined' && process.env.TARO_ENV === 'h5' ? 'var(--radius-md)' : '16px',
  radiusLg: typeof process !== 'undefined' && process.env.TARO_ENV === 'h5' ? 'var(--radius-lg)' : '24px',
};

export function PageSection({ title, description, children }) {
  return createElement(
    View,
    {
      style: {
        background: userAppTokens.colorSurface,
        border: `1px solid ${userAppTokens.colorBorder}`,
        borderRadius: userAppTokens.radiusLg,
        marginBottom: userAppTokens.spacingSm,
        padding: userAppTokens.spacingMd,
      },
    },
    createElement(
      Text,
      {
        style: { color: userAppTokens.colorText, display: 'block', fontSize: '32px', fontWeight: '600' },
      },
      title,
    ),
    description
      ? createElement(
          Text,
          {
            style: { color: userAppTokens.colorMuted, display: 'block', fontSize: '24px', marginTop: '8px' },
          },
          description,
        )
      : null,
    createElement(View, { style: { marginTop: userAppTokens.spacingSm } }, children),
  );
}

const TONE_COLOR = {
  info: userAppTokens.colorPrimary,
  success: userAppTokens.colorSuccess,
  warning: userAppTokens.colorWarning,
};

export function StatusCard({ label, value, tone = 'info' }) {
  return createElement(
    View,
    {
      style: {
        background: userAppTokens.colorSurfaceMuted,
        border: `1px solid ${userAppTokens.colorBorder}`,
        borderRadius: userAppTokens.radiusMd,
        marginBottom: userAppTokens.spacingXs,
        padding: userAppTokens.spacingSm,
      },
    },
    createElement(
      Text,
      {
        style: { color: userAppTokens.colorMuted, display: 'block', fontSize: '22px' },
      },
      label,
    ),
    createElement(
      Text,
      {
        style: { color: TONE_COLOR[tone], display: 'block', fontSize: '28px', fontWeight: '600', marginTop: '4px' },
      },
      value,
    ),
  );
}
