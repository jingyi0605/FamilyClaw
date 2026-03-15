import { Text, View } from '@tarojs/components';
import { createElement } from 'react';

export const userAppTokens = {
  colorBg: '#f5f6f8',
  colorSurface: '#ffffff',
  colorBorder: '#d6dbe4',
  colorText: '#152033',
  colorMuted: '#5c6b80',
  colorPrimary: '#1d6fd6',
  colorSuccess: '#0f9d6c',
  colorWarning: '#c47900',
  spacingXs: '12px',
  spacingSm: '16px',
  spacingMd: '24px',
  radiusMd: '16px',
  radiusLg: '24px',
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
        background: '#f9fbff',
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
