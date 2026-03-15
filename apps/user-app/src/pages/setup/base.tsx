import type { CSSProperties, ReactNode } from 'react';

export function PageHeader(props: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="page-header">
      <div className="page-header__text">
        <h1 className="page-header__title">{props.title}</h1>
        {props.description ? <p className="page-header__desc">{props.description}</p> : null}
      </div>
      {props.actions ? <div className="page-header__actions">{props.actions}</div> : null}
    </div>
  );
}

export function Card(props: {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  onClick?: () => void;
}) {
  return (
    <div
      className={`card ${props.onClick ? 'card--clickable' : ''} ${props.className ?? ''}`.trim()}
      style={props.style}
      onClick={props.onClick}
      role={props.onClick ? 'button' : undefined}
      tabIndex={props.onClick ? 0 : undefined}
    >
      {props.children}
    </div>
  );
}

export function EmptyState(props: { icon?: ReactNode; title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      {props.icon ? <div className="empty-state__icon">{props.icon}</div> : null}
      <h3 className="empty-state__title">{props.title}</h3>
      {props.description ? <p className="empty-state__desc">{props.description}</p> : null}
      {props.action ? <div className="empty-state__action">{props.action}</div> : null}
    </div>
  );
}
