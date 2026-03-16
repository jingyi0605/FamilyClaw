import { View } from '@tarojs/components';
import { type CSSProperties, type PropsWithChildren } from 'react';
import {
  EmptyStateCard as SharedEmptyStateCard,
  FormField as SharedFormField,
  userAppFoundationTokens,
  UiButton,
  UiInput,
  UiText,
} from '@familyclaw/user-ui';

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
  const toneMap: Record<'muted' | 'warning' | 'success', 'secondary' | 'warning' | 'success'> = {
    muted: 'secondary',
    warning: 'warning',
    success: 'success',
  };

  return (
    <UiText variant="body" tone={toneMap[tone]}>
      {children}
    </UiText>
  );
}

export function FormField({
  label,
  hint,
  children,
}: PropsWithChildren<{ label: string; hint?: string }>) {
  return (
    <SharedFormField label={label} hint={hint}>
      {children}
    </SharedFormField>
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
  return <UiInput value={props.value} placeholder={props.placeholder} password={props.password} disabled={props.disabled} onInput={props.onInput} style={props.style} />;
}

export function OptionPills<T extends string>({ value, options, disabled, onChange }: OptionPillsProps<T>) {
  return (
    <View style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', gap: userAppFoundationTokens.spacing.xs }}>
      {options.map(option => {
        const active = option.value === value;
        return (
          <UiButton
            key={option.value}
            disabled={disabled}
            onClick={() => onChange(option.value)}
            size="sm"
            variant={active ? 'primary' : 'secondary'}
          >
            {option.label}
          </UiButton>
        );
      })}
    </View>
  );
}

export function ActionRow({ children }: PropsWithChildren) {
  return (
    <View style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', gap: userAppFoundationTokens.spacing.sm }}>
      {children}
    </View>
  );
}

export function PrimaryButton({
  children,
  disabled,
  onClick,
}: PropsWithChildren<{ disabled?: boolean; onClick?: () => void }>) {
  return <UiButton disabled={disabled} onClick={onClick}>{children}</UiButton>;
}

export function SecondaryButton({
  children,
  disabled,
  onClick,
}: PropsWithChildren<{ disabled?: boolean; onClick?: () => void }>) {
  return <UiButton variant="secondary" disabled={disabled} onClick={onClick}>{children}</UiButton>;
}

export function EmptyStateCard(props: EmptyStateCardProps) {
  return <SharedEmptyStateCard {...props} />;
}
