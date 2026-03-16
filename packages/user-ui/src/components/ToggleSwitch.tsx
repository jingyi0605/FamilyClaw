import { View } from '@tarojs/components';
import { type CSSProperties } from 'react';
import { userAppComponentTokens } from '../theme/tokens';
import { UiText } from './UiText';

type ToggleSwitchProps = {
  checked: boolean;
  label: string;
  description?: string;
  disabled?: boolean;
  className?: string;
  style?: CSSProperties;
  onChange?: (value: boolean) => void;
};

export function ToggleSwitch({
  checked,
  label,
  description,
  disabled = false,
  className,
  style,
  onChange,
}: ToggleSwitchProps) {
  const tokens = userAppComponentTokens.toggleSwitch;

  return (
    <View
      className={className}
      style={{
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: tokens.gap,
        opacity: disabled ? tokens.opacityDisabled : undefined,
        ...style,
      }}
    >
      <View style={{ flex: 1 }}>
        <UiText variant="label">{label}</UiText>
        {description ? (
          <UiText
            variant="caption"
            tone="secondary"
            style={{ marginTop: tokens.descriptionMarginTop }}
          >
            {description}
          </UiText>
        ) : null}
      </View>
      <View
        onClick={() => {
          if (!disabled) {
            onChange?.(!checked);
          }
        }}
        role="switch"
        aria-checked={checked}
        aria-disabled={disabled}
        style={{
          width: tokens.trackWidth,
          height: tokens.trackHeight,
          borderRadius: tokens.trackRadius,
          background: disabled
            ? tokens.trackBackgroundDisabled
            : checked
              ? tokens.trackBackgroundActive
              : tokens.trackBackground,
          padding: tokens.trackPadding,
          display: 'flex',
          alignItems: 'center',
          justifyContent: checked ? 'flex-end' : 'flex-start',
          transition: 'all 0.2s ease',
        }}
      >
        <View
          style={{
            width: tokens.thumbSize,
            height: tokens.thumbSize,
            borderRadius: tokens.thumbRadius,
            background: tokens.thumbBackground,
            boxShadow: tokens.thumbShadow,
          }}
        />
      </View>
    </View>
  );
}
