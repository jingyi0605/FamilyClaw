import type { AiProviderAdapter } from '../settingsTypes';

export function AiProviderBrandMark(props: {
  adapter: AiProviderAdapter;
  size?: number;
  className?: string;
}) {
  const { adapter, size = 32, className } = props;
  const logoUrl = adapter.branding.logo_url || adapter.branding.logo_dark_url;
  return (
    <img
      className={className}
      src={logoUrl || ''}
      alt={adapter.display_name}
      width={size}
      height={size}
      style={{ width: size, height: size, objectFit: 'contain' }}
    />
  );
}
