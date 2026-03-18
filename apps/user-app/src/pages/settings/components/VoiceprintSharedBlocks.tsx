import { type FormEventHandler, type PropsWithChildren, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

export function VoiceprintToggleSwitch(props: {
  checked: boolean;
  label: string;
  description?: string;
  disabled?: boolean;
  onChange?: (nextValue: boolean) => void;
}) {
  return (
    <label className={`toggle-row ${props.disabled ? 'toggle-row--disabled' : ''}`.trim()}>
      <div className="toggle-row__text">
        <span className="toggle-row__label">{props.label}</span>
        {props.description ? <span className="toggle-row__desc">{props.description}</span> : null}
      </div>
      <div
        className={`toggle-switch ${props.checked ? 'toggle-switch--on' : ''} ${props.disabled ? 'toggle-switch--disabled' : ''}`.trim()}
        role="switch"
        aria-checked={props.checked}
        aria-label={props.label}
        aria-disabled={props.disabled}
        onClick={() => {
          if (!props.disabled) {
            props.onChange?.(!props.checked);
          }
        }}
      >
        <div className="toggle-switch__thumb" />
      </div>
    </label>
  );
}

export function VoiceprintEmptyState(props: {
  title: string;
  description: string;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`ai-config-detail-card agent-config-empty ${props.className ?? ''}`.trim()}>
      <div className="empty-state">
        <div className="empty-state__icon">{props.icon ?? '声纹'}</div>
        <h3 className="empty-state__title">{props.title}</h3>
        <p className="empty-state__description">{props.description}</p>
        {props.action ? <div className="empty-state__action">{props.action}</div> : null}
      </div>
    </div>
  );
}

export function VoiceprintDialog(props: PropsWithChildren<{
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
