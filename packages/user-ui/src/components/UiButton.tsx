import { Button } from '@tarojs/components';
import { type CSSProperties, type PropsWithChildren } from 'react';
import { userAppComponentTokens } from '../theme/tokens';

type UiButtonVariant = 'primary' | 'secondary' | 'warning';
type UiButtonSize = 'sm' | 'md';

type UiButtonProps = PropsWithChildren<{
  variant?: UiButtonVariant;
  size?: UiButtonSize;
  disabled?: boolean;
  loading?: boolean;
  formType?: 'submit' | 'reset';
  onClick?: () => void;
  style?: CSSProperties;
}>;

export function UiButton({
  children,
  variant = 'primary',
  size = 'md',
  disabled,
  loading,
  formType,
  onClick,
  style,
}: UiButtonProps) {
  const sizeTokens = userAppComponentTokens.button.size[size];
  const variantTokens = userAppComponentTokens.button.variant[variant];

  return (
    <Button
      disabled={disabled}
      loading={loading}
      formType={formType}
      onClick={onClick}
      style={{
        background: variantTokens.background,
        border: `1px solid ${variantTokens.borderColor}`,
        borderRadius: sizeTokens.radius,
        color: variantTokens.textColor,
        fontSize: sizeTokens.fontSize,
        minHeight: sizeTokens.minHeight,
        padding: `0 ${sizeTokens.paddingInline}`,
        ...style,
      }}
    >
      {children}
    </Button>
  );
}
