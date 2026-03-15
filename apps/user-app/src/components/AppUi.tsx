import { Button, Input, Text, View } from '@tarojs/components';
import { CSSProperties, PropsWithChildren } from 'react';
import { userAppTokens } from '@familyclaw/user-ui';

type OptionPillsProps<T extends string> = {
  value: T;
  options: Array<{
    value: T;
    label: string;
  }>;
  disabled?: boolean;
  onChange: (value: T) => void;
};

type EmptyStateCardProps = {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
};

export function SectionNote({
  children,
  tone = 'muted',
}: PropsWithChildren<{ tone?: 'muted' | 'warning' | 'success' }>) {
  const colorMap: Record<'muted' | 'warning' | 'success', string> = {
    muted: userAppTokens.colorMuted,
    warning: userAppTokens.colorWarning,
    success: userAppTokens.colorSuccess,
  };

  return (
    <Text
      style={{
        color: colorMap[tone],
        display: 'block',
        fontSize: '24px',
        lineHeight: '1.6',
      }}
    >
      {children}
    </Text>
  );
}

export function FormField({
  label,
  hint,
  children,
}: PropsWithChildren<{ label: string; hint?: string }>) {
  return (
    <View style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <Text style={{ color: userAppTokens.colorText, fontSize: '24px', fontWeight: '600' }}>
        {label}
      </Text>
      {children}
      {hint ? <SectionNote>{hint}</SectionNote> : null}
    </View>
  );
}

export function TextInput(props: {
  value: string;
  placeholder?: string;
  password?: boolean;
  disabled?: boolean;
  onInput: (value: string) => void;
  style?: CSSProperties;
}) {
  return (
    <Input
      value={props.value}
      password={props.password}
      disabled={props.disabled}
      placeholder={props.placeholder}
      onInput={event => props.onInput(event.detail.value)}
      style={{
        background: userAppTokens.colorSurface,
        border: `1px solid ${userAppTokens.colorBorder}`,
        borderRadius: userAppTokens.radiusMd,
        color: userAppTokens.colorText,
        fontSize: '26px',
        minHeight: '44px',
        padding: '10px 14px',
        ...props.style,
      }}
    />
  );
}

export function OptionPills<T extends string>({ value, options, disabled, onChange }: OptionPillsProps<T>) {
  return (
    <View style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', gap: '10px' }}>
      {options.map(option => {
        const active = option.value === value;
        return (
          <Button
            key={option.value}
            disabled={disabled}
            onClick={() => onChange(option.value)}
            size="mini"
            style={{
              background: active ? userAppTokens.colorPrimary : userAppTokens.colorSurface,
              border: `1px solid ${active ? userAppTokens.colorPrimary : userAppTokens.colorBorder}`,
              borderRadius: userAppTokens.radiusMd,
              color: active ? '#ffffff' : userAppTokens.colorText,
              fontSize: '22px',
              padding: '0 10px',
            }}
          >
            {option.label}
          </Button>
        );
      })}
    </View>
  );
}

export function ActionRow({ children }: PropsWithChildren) {
  return (
    <View style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', gap: '12px' }}>
      {children}
    </View>
  );
}

export function PrimaryButton({
  children,
  disabled,
  onClick,
}: PropsWithChildren<{ disabled?: boolean; onClick?: () => void }>) {
  return (
    <Button
      disabled={disabled}
      onClick={onClick}
      style={{
        background: userAppTokens.colorPrimary,
        borderRadius: userAppTokens.radiusMd,
        color: '#ffffff',
        fontSize: '24px',
      }}
    >
      {children}
    </Button>
  );
}

export function SecondaryButton({
  children,
  disabled,
  onClick,
}: PropsWithChildren<{ disabled?: boolean; onClick?: () => void }>) {
  return (
    <Button
      disabled={disabled}
      onClick={onClick}
      style={{
        background: userAppTokens.colorSurface,
        border: `1px solid ${userAppTokens.colorBorder}`,
        borderRadius: userAppTokens.radiusMd,
        color: userAppTokens.colorText,
        fontSize: '24px',
      }}
    >
      {children}
    </Button>
  );
}

export function EmptyStateCard(props: EmptyStateCardProps) {
  return (
    <View
      style={{
        background: '#f9fbff',
        border: `1px dashed ${userAppTokens.colorBorder}`,
        borderRadius: userAppTokens.radiusLg,
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        padding: userAppTokens.spacingMd,
      }}
    >
      <Text style={{ color: userAppTokens.colorText, fontSize: '30px', fontWeight: '600' }}>
        {props.title}
      </Text>
      <SectionNote>{props.description}</SectionNote>
      {props.actionLabel && props.onAction ? (
        <View style={{ marginTop: '4px' }}>
          <SecondaryButton onClick={props.onAction}>
            {props.actionLabel}
          </SecondaryButton>
        </View>
      ) : null}
    </View>
  );
}
