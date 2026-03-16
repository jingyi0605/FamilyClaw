/* ============================================================
 * 基础组件集合 - PageHeader / Card / Section / EmptyState
 * ============================================================ */
import type { ReactNode, CSSProperties } from 'react';
import {
  EmptyStateCard,
  PageHeader as SharedPageHeader,
  PageSection,
  ToggleSwitch as SharedToggleSwitch,
  UiCard,
  UiText,
} from '@familyclaw/user-ui';

/* ---- PageHeader ---- */
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return <SharedPageHeader title={title} description={description} actions={actions} className="page-header" />;
}

/* ---- Card ---- */
export function Card({
  children,
  className = '',
  style,
  onClick,
}: {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  onClick?: () => void;
}) {
  return (
    <UiCard
      className={`card ${onClick ? 'card--clickable' : ''} ${className}`.trim()}
      style={style}
      onClick={onClick}
    >
      {children}
    </UiCard>
  );
}

/* ---- Section ---- */
export function Section({
  title,
  actions,
  children,
  className = '',
}: {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <PageSection
      title={title}
      actions={actions}
      className={`section ${className}`.trim()}
      contentStyle={{ marginTop: 0 }}
    >
      {children}
    </PageSection>
  );
}

/* ---- EmptyState ---- */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <EmptyStateCard
      className="empty-state"
      icon={icon}
      title={title}
      description={description ?? ''}
      action={action}
    />
  );
}

/* ---- StatCard（首页关键指标卡） ---- */
export function StatCard({
  icon,
  label,
  value,
  color,
}: {
  icon: ReactNode;
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <UiCard className="stat-card" style={color ? { '--stat-accent': color } as CSSProperties : undefined}>
      <div className="stat-card__icon">{icon}</div>
      <div className="stat-card__info">
        <UiText className="stat-card__value" variant="title">{value}</UiText>
        <UiText className="stat-card__label" variant="caption">{label}</UiText>
      </div>
    </UiCard>
  );
}

/* ---- ToggleSwitch ---- */
export function ToggleSwitch({
  checked,
  label,
  description,
  onChange,
  disabled = false,
}: {
  checked: boolean;
  label: string;
  description?: string;
  onChange?: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <SharedToggleSwitch
      className={`toggle-row ${disabled ? 'toggle-row--disabled' : ''}`.trim()}
      checked={checked}
      label={label}
      description={description}
      onChange={onChange}
      disabled={disabled}
    />
  );
}
