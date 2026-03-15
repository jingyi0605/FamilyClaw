const isH5 = typeof process !== 'undefined' && process.env.TARO_ENV === 'h5';

function tokenValue(h5Value: string, fallbackValue: string) {
  return isH5 ? h5Value : fallbackValue;
}

export const userAppTokens = {
  colorBg: tokenValue('var(--bg-app)', '#f5f6f8'),
  colorSurface: tokenValue('var(--bg-card)', '#ffffff'),
  colorSurfaceMuted: tokenValue('var(--bg-input)', '#f9fbff'),
  colorBorder: tokenValue('var(--border-light)', '#d6dbe4'),
  colorText: tokenValue('var(--text-primary)', '#152033'),
  colorMuted: tokenValue('var(--text-secondary)', '#5c6b80'),
  colorPrimary: tokenValue('var(--brand-primary)', '#1d6fd6'),
  colorSuccess: tokenValue('var(--color-success)', '#0f9d6c'),
  colorWarning: tokenValue('var(--color-warning)', '#c47900'),
  spacingXs: tokenValue('var(--spacing-xs)', '12px'),
  spacingSm: tokenValue('var(--spacing-sm)', '16px'),
  spacingMd: tokenValue('var(--spacing-md)', '24px'),
  radiusMd: tokenValue('var(--radius-md)', '16px'),
  radiusLg: tokenValue('var(--radius-lg)', '24px'),
} as const;
