import { Input } from '@tarojs/components';
import { type CSSProperties } from 'react';
import { userAppComponentTokens } from '../theme/tokens';

type UiInputProps = {
  value: string;
  placeholder?: string;
  password?: boolean;
  disabled?: boolean;
  onInput: (value: string) => void;
  style?: CSSProperties;
};

export function UiInput({ value, placeholder, password, disabled, onInput, style }: UiInputProps) {
  const tokens = userAppComponentTokens.input;

  return (
    <Input
      value={value}
      placeholder={placeholder}
      password={password}
      disabled={disabled}
      onInput={event => onInput(event.detail.value)}
      style={{
        background: tokens.background,
        border: `1px solid ${tokens.borderColor}`,
        borderRadius: tokens.radius,
        color: tokens.textColor,
        fontSize: tokens.fontSize,
        minHeight: tokens.minHeight,
        padding: `${tokens.paddingBlock} ${tokens.paddingInline}`,
        ...style,
      }}
    />
  );
}
