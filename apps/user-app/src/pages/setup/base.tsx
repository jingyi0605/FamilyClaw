import type { CSSProperties, ReactNode } from 'react';
import { EmptyStateCard, PageHeader as SharedPageHeader, UiCard } from '@familyclaw/user-ui';

export function PageHeader(props: { title: string; description?: string; actions?: ReactNode }) {
  return <SharedPageHeader title={props.title} description={props.description} actions={props.actions} className="page-header" />;
}

export function Card(props: {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  onClick?: () => void;
}) {
  return (
    <UiCard
      className={`card ${props.onClick ? 'card--clickable' : ''} ${props.className ?? ''}`.trim()}
      style={props.style}
      onClick={props.onClick}
    >
      {props.children}
    </UiCard>
  );
}

export function EmptyState(props: { icon?: ReactNode; title: string; description?: string; action?: ReactNode }) {
  return <EmptyStateCard className="empty-state" icon={props.icon} title={props.title} description={props.description ?? ''} action={props.action} />;
}
