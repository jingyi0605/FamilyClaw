import { EmptyStateCard } from '@familyclaw/user-ui';
import { type FormEventHandler, type PropsWithChildren, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { Card } from '../../family/base';

type SettingsNoticeTone = 'info' | 'success' | 'error';

export function SettingsNotice(props: {
  tone?: SettingsNoticeTone;
  icon: ReactNode;
  children: ReactNode;
}) {
  const toneClass = props.tone === 'success'
    ? 'settings-note--success'
    : props.tone === 'error'
      ? 'settings-note--error'
      : '';

  return (
    <div className={`settings-note ${toneClass}`.trim()}>
      <span>{props.icon}</span>
      <span>{props.children}</span>
    </div>
  );
}

export function SettingsPanelCard(props: PropsWithChildren<{
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}>) {
  return (
    <Card className={`ai-config-detail-card ${props.className ?? ''}`.trim()}>
      <div className="agent-config-center__toolbar">
        <div className="agent-config-center__intro">
          <h3>{props.title}</h3>
          {props.description ? <p>{props.description}</p> : null}
        </div>
        {props.actions}
      </div>
      {props.children}
    </Card>
  );
}

export function SettingsEmptyState(props: {
  title: string;
  description: string;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <EmptyStateCard
      className={`ai-config-detail-card agent-config-empty ${props.className ?? ''}`.trim()}
      icon={props.icon ?? '🧩'}
      title={props.title}
      description={props.description}
      action={props.action}
    />
  );
}

export function SettingsDialog(props: PropsWithChildren<{
  open?: boolean;
  title: string;
  description?: string;
  headerExtra?: ReactNode;
  className?: string;
  formClassName?: string;
  closeDisabled?: boolean;
  onClose?: () => void;
  onSubmit?: FormEventHandler<HTMLFormElement>;
  actions?: ReactNode;
}>) {
  const {
    open = true,
    title,
    description,
    headerExtra,
    className,
    formClassName,
    closeDisabled = false,
    onClose,
    onSubmit,
    actions,
    children,
  } = props;

  if (!open) {
    return null;
  }

  const content = (
    <>
      <div className="member-modal__header">
        <div>
          <h3>{title}</h3>
          {description ? <p>{description}</p> : null}
        </div>
        {headerExtra}
      </div>
      {children}
      {actions ? <div className="member-modal__actions">{actions}</div> : null}
    </>
  );

  const overlay = (
    <div className="member-modal-overlay" onClick={closeDisabled ? undefined : onClose}>
      <div className={`member-modal ${className ?? ''}`.trim()} onClick={(event) => event.stopPropagation()}>
        {onSubmit ? (
          <form className={`settings-form ${formClassName ?? ''}`.trim()} onSubmit={onSubmit}>
            {content}
          </form>
        ) : content}
      </div>
    </div>
  );

  if (typeof document === 'undefined') {
    return overlay;
  }

  return createPortal(overlay, document.body);
}
