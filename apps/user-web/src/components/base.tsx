/* ============================================================
 * 基础组件集合 - PageHeader / Card / Section / EmptyState
 * ============================================================ */
import type { ReactNode, CSSProperties } from 'react';

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
  return (
    <div className="page-header">
      <div className="page-header__text">
        <h1 className="page-header__title">{title}</h1>
        {description && <p className="page-header__desc">{description}</p>}
      </div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </div>
  );
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
    <div
      className={`card ${onClick ? 'card--clickable' : ''} ${className}`}
      style={style}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      {children}
    </div>
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
    <section className={`section ${className}`}>
      <div className="section__header">
        <h2 className="section__title">{title}</h2>
        {actions && <div className="section__actions">{actions}</div>}
      </div>
      <div className="section__content">{children}</div>
    </section>
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
    <div className="empty-state">
      {icon && <div className="empty-state__icon">{icon}</div>}
      <h3 className="empty-state__title">{title}</h3>
      {description && <p className="empty-state__desc">{description}</p>}
      {action && <div className="empty-state__action">{action}</div>}
    </div>
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
    <div className="stat-card" style={color ? { '--stat-accent': color } as CSSProperties : undefined}>
      <div className="stat-card__icon">{icon}</div>
      <div className="stat-card__info">
        <span className="stat-card__value">{value}</span>
        <span className="stat-card__label">{label}</span>
      </div>
    </div>
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
    <label className={`toggle-row ${disabled ? 'toggle-row--disabled' : ''}`}>
      <div className="toggle-row__text">
        <span className="toggle-row__label">{label}</span>
        {description && <span className="toggle-row__desc">{description}</span>}
      </div>
      <div
        className={`toggle-switch ${checked ? 'toggle-switch--on' : ''} ${disabled ? 'toggle-switch--disabled' : ''}`}
        onClick={() => {
          if (!disabled) {
            onChange?.(!checked);
          }
        }}
        aria-disabled={disabled}
      >
        <div className="toggle-switch__thumb" />
      </div>
    </label>
  );
}
