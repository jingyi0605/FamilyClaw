import { useEffect, useState, useCallback, type FormEvent } from 'react';
import {
  KeyRound,
  Plus,
  Trash2,
  UserCog,
  ShieldAlert,
  ShieldCheck,
  ShieldOff,
  MoreVertical,
  User,
  RefreshCcw,
} from 'lucide-react';
import { EmptyStateCard, PageSection, UiButton } from '@familyclaw/user-ui';
import { GuardedPage, useHouseholdContext, useI18n, useAuthContext } from '../../../runtime';
import { SettingsPageShell } from '../SettingsPageShell';
import { SettingsDialog, SettingsNotice } from '../components/SettingsSharedBlocks';
import { ApiError, settingsApi } from '../settingsApi';
import type { AccountWithBinding, Member } from '../settingsTypes';

type AccountStatus = 'active' | 'disabled' | 'locked';

const STATUS_CONFIG: Record<AccountStatus, { icon: typeof ShieldCheck; labelKey: string; className: string }> = {
  active: { icon: ShieldCheck, labelKey: 'settings.accounts.status.active', className: 'status-badge--success' },
  disabled: { icon: ShieldOff, labelKey: 'settings.accounts.status.disabled', className: 'status-badge--neutral' },
  locked: { icon: ShieldAlert, labelKey: 'settings.accounts.status.locked', className: 'status-badge--error' },
};

type CreateAccountFormState = {
  member_id: string;
  username: string;
  password: string;
  confirm_password: string;
  must_change_password: boolean;
};

type ResetPasswordFormState = {
  new_password: string;
  confirm_password: string;
  must_change_password: boolean;
};

function AccountActionMenu({
  onEditStatus,
  onResetPassword,
  onDelete,
}: {
  onEditStatus: () => void;
  onResetPassword: () => void;
  onDelete: () => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const { t } = useI18n();

  return (
    <div className="account-action-menu">
      <button
        type="button"
        className="account-action-menu__trigger"
        onClick={() => setIsOpen(!isOpen)}
      >
        <MoreVertical size={18} />
      </button>
      {isOpen && (
        <>
          <div className="account-action-menu__backdrop" onClick={() => setIsOpen(false)} />
          <div className="account-action-menu__dropdown">
            <button
              type="button"
              className="account-action-menu__item"
              onClick={() => {
                setIsOpen(false);
                onEditStatus();
              }}
            >
              <UserCog size={16} />
              <span>{t('settings.accounts.actions.editStatus')}</span>
            </button>
            <button
              type="button"
              className="account-action-menu__item"
              onClick={() => {
                setIsOpen(false);
                onResetPassword();
              }}
            >
              <KeyRound size={16} />
              <span>{t('settings.accounts.actions.resetPassword')}</span>
            </button>
            <button
              type="button"
              className="account-action-menu__item account-action-menu__item--danger"
              onClick={() => {
                setIsOpen(false);
                onDelete();
              }}
            >
              <Trash2 size={16} />
              <span>{t('settings.accounts.actions.delete')}</span>
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function AccountsSettingsContent() {
  const { t } = useI18n();
  const { currentHouseholdId, householdsLoading } = useHouseholdContext();
  const { actor } = useAuthContext();

  const [accounts, setAccounts] = useState<AccountWithBinding[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Dialog states
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showStatusDialog, setShowStatusDialog] = useState(false);
  const [showResetPasswordDialog, setShowResetPasswordDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState<AccountWithBinding | null>(null);

  // Form states
  const [createForm, setCreateForm] = useState<CreateAccountFormState>({
    member_id: '',
    username: '',
    password: '',
    confirm_password: '',
    must_change_password: true,
  });
  const [resetPasswordForm, setResetPasswordForm] = useState<ResetPasswordFormState>({
    new_password: '',
    confirm_password: '',
    must_change_password: true,
  });
  const [newStatus, setNewStatus] = useState<AccountStatus>('active');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const isAdmin = actor?.member_role === 'admin';

  const loadData = useCallback(async () => {
    if (!currentHouseholdId) return;

    setLoading(true);
    setError(null);

    try {
      const [accountsRes, membersRes] = await Promise.all([
        settingsApi.listHouseholdAccounts(currentHouseholdId),
        settingsApi.listMembers(currentHouseholdId),
      ]);
      setAccounts(accountsRes.items);
      setMembers(membersRes.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('common.error.loading'));
    } finally {
      setLoading(false);
    }
  }, [currentHouseholdId, t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Get unbound members for create form
  const boundMemberIds = new Set(
    accounts
      .map((a) => a.binding?.member_id)
      .filter((id): id is string => Boolean(id)),
  );
  const unboundMembers = members.filter((m) => !boundMemberIds.has(m.id) && m.status === 'active');

  const handleCreateAccount = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentHouseholdId) return;

    setFormError(null);

    if (createForm.password !== createForm.confirm_password) {
      setFormError(t('settings.accounts.error.passwordMismatch'));
      return;
    }

    if (createForm.password.length < 6) {
      setFormError(t('settings.accounts.error.passwordTooShort'));
      return;
    }

    setSubmitting(true);
    try {
      await settingsApi.createHouseholdAccount({
        household_id: currentHouseholdId,
        member_id: createForm.member_id,
        username: createForm.username,
        password: createForm.password,
        must_change_password: createForm.must_change_password,
      });
      setShowCreateDialog(false);
      setCreateForm({
        member_id: '',
        username: '',
        password: '',
        confirm_password: '',
        must_change_password: true,
      });
      await loadData();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : t('common.error.saving'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdateStatus = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentHouseholdId || !selectedAccount) return;

    setFormError(null);
    setSubmitting(true);
    try {
      await settingsApi.updateHouseholdAccount(currentHouseholdId, selectedAccount.account.id, {
        status: newStatus,
      });
      setShowStatusDialog(false);
      setSelectedAccount(null);
      await loadData();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : t('common.error.saving'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleResetPassword = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentHouseholdId || !selectedAccount) return;

    setFormError(null);

    if (resetPasswordForm.new_password !== resetPasswordForm.confirm_password) {
      setFormError(t('settings.accounts.error.passwordMismatch'));
      return;
    }

    if (resetPasswordForm.new_password.length < 6) {
      setFormError(t('settings.accounts.error.passwordTooShort'));
      return;
    }

    setSubmitting(true);
    try {
      await settingsApi.resetHouseholdAccountPassword(currentHouseholdId, selectedAccount.account.id, {
        new_password: resetPasswordForm.new_password,
        must_change_password: resetPasswordForm.must_change_password,
      });
      setShowResetPasswordDialog(false);
      setSelectedAccount(null);
      setResetPasswordForm({
        new_password: '',
        confirm_password: '',
        must_change_password: true,
      });
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : t('common.error.saving'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (!currentHouseholdId || !selectedAccount) return;

    setSubmitting(true);
    try {
      await settingsApi.deleteHouseholdAccount(currentHouseholdId, selectedAccount.account.id);
      setShowDeleteDialog(false);
      setSelectedAccount(null);
      await loadData();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : t('common.error.deleting'));
    } finally {
      setSubmitting(false);
    }
  };

  const getMemberName = (memberId: string | undefined) => {
    if (!memberId) return '-';
    const member = members.find((m) => m.id === memberId);
    return member?.name || member?.nickname || memberId;
  };

  const openStatusDialog = (account: AccountWithBinding) => {
    setSelectedAccount(account);
    setNewStatus(account.account.status as AccountStatus);
    setFormError(null);
    setShowStatusDialog(true);
  };

  const openResetPasswordDialog = (account: AccountWithBinding) => {
    setSelectedAccount(account);
    setResetPasswordForm({
      new_password: '',
      confirm_password: '',
      must_change_password: true,
    });
    setFormError(null);
    setShowResetPasswordDialog(true);
  };

  const openDeleteDialog = (account: AccountWithBinding) => {
    setSelectedAccount(account);
    setFormError(null);
    setShowDeleteDialog(true);
  };

  // Loading state for household context
  if (householdsLoading) {
    return (
      <SettingsPageShell activeKey="accounts">
        <div className="settings-page settings-page--accounts">
          <PageSection title={t('settings.accounts.title')} contentStyle={{ marginTop: 0 }}>
            <div className="loading-indicator">{t('common.loading')}</div>
          </PageSection>
        </div>
      </SettingsPageShell>
    );
  }

  // No household selected
  if (!currentHouseholdId) {
    return (
      <SettingsPageShell activeKey="accounts">
        <div className="settings-page settings-page--accounts">
          <PageSection title={t('settings.accounts.title')} contentStyle={{ marginTop: 0 }}>
            <EmptyStateCard
              icon="🔒"
              title={t('settings.accounts.empty.title')}
              description={t('settings.accounts.empty.description')}
            />
          </PageSection>
        </div>
      </SettingsPageShell>
    );
  }

  // Not admin
  if (!isAdmin) {
    return (
      <SettingsPageShell activeKey="accounts">
        <div className="settings-page settings-page--accounts">
          <PageSection title={t('settings.accounts.title')} contentStyle={{ marginTop: 0 }}>
            <SettingsNotice icon={<ShieldAlert size={20} />}>
              {t('settings.accounts.adminOnly')}
            </SettingsNotice>
          </PageSection>
        </div>
      </SettingsPageShell>
    );
  }

  return (
    <SettingsPageShell activeKey="accounts">
      <div className="settings-page settings-page--accounts">
        <PageSection
          title={t('settings.accounts.title')}
          contentStyle={{ marginTop: 0 }}
          actions={
            <UiButton
              variant="primary"
              size="sm"
              onClick={() => {
                setFormError(null);
                setShowCreateDialog(true);
              }}
              disabled={unboundMembers.length === 0}
            >
              <Plus size={16} />
              <span>{t('settings.accounts.createAccount')}</span>
            </UiButton>
          }
        >
          {loading ? (
            <div className="loading-indicator">{t('common.loading')}</div>
          ) : error ? (
            <SettingsNotice tone="error" icon={<ShieldAlert size={20} />}>
              {error}
            </SettingsNotice>
          ) : accounts.length === 0 ? (
            <EmptyStateCard
              icon={<UserCog size={48} />}
              title={t('settings.accounts.empty.title')}
              description={t('settings.accounts.empty.description')}
              action={
                unboundMembers.length > 0 ? (
                  <UiButton
                    variant="primary"
                    onClick={() => setShowCreateDialog(true)}
                  >
                    <Plus size={16} />
                    <span>{t('settings.accounts.createAccount')}</span>
                  </UiButton>
                ) : undefined
              }
            />
          ) : (
            <div className="accounts-list">
              {accounts.map((item) => {
                const statusConfig = STATUS_CONFIG[item.account.status as AccountStatus];
                const StatusIcon = statusConfig?.icon || ShieldOff;
                return (
                  <div key={item.account.id} className="account-card card">
                    <div className="account-card__header">
                      <div className="account-card__info">
                        <div className="account-card__username">
                          <User size={18} />
                          <span>{item.account.username}</span>
                        </div>
                        <div className="account-card__member">
                          {t('settings.accounts.boundTo')}: {getMemberName(item.binding?.member_id)}
                        </div>
                      </div>
                      <div className="account-card__actions">
                        <span className={`status-badge ${statusConfig?.className || ''}`}>
                          <StatusIcon size={14} />
                          <span>{t(statusConfig?.labelKey || item.account.status)}</span>
                        </span>
                        {item.account.must_change_password && (
                          <span className="must-change-badge" title={t('settings.accounts.mustChangePassword')}>
                            <RefreshCcw size={14} />
                          </span>
                        )}
                        <AccountActionMenu
                          onEditStatus={() => openStatusDialog(item)}
                          onResetPassword={() => openResetPasswordDialog(item)}
                          onDelete={() => openDeleteDialog(item)}
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </PageSection>
      </div>

      {/* Create Account Dialog */}
      {showCreateDialog && (
        <SettingsDialog
          title={t('settings.accounts.createDialog.title')}
          description={t('settings.accounts.createDialog.description')}
          onClose={() => setShowCreateDialog(false)}
          onSubmit={handleCreateAccount}
          actions={
            <>
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => setShowCreateDialog(false)}
                disabled={submitting}
              >
                {t('common.cancel')}
              </button>
              <button
                type="submit"
                className="btn btn--primary"
                disabled={submitting || !createForm.member_id || !createForm.username || !createForm.password}
              >
                {submitting ? t('common.saving') : t('common.create')}
              </button>
            </>
          }
        >
          <div className="settings-form__body">
            {formError && <div className="form-error">{formError}</div>}
            <div className="form-field">
              <label className="form-label">{t('settings.accounts.createDialog.member')}</label>
              <select
                className="form-select"
                value={createForm.member_id}
                onChange={(e) => setCreateForm((f) => ({ ...f, member_id: e.target.value }))}
                required
              >
                <option value="">{t('settings.accounts.createDialog.selectMember')}</option>
                {unboundMembers.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name || m.nickname}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-field">
              <label className="form-label">{t('settings.accounts.createDialog.username')}</label>
              <input
                type="text"
                className="form-input"
                value={createForm.username}
                onChange={(e) => setCreateForm((f) => ({ ...f, username: e.target.value }))}
                required
                autoComplete="username"
              />
            </div>
            <div className="form-field">
              <label className="form-label">{t('settings.accounts.createDialog.password')}</label>
              <input
                type="password"
                className="form-input"
                value={createForm.password}
                onChange={(e) => setCreateForm((f) => ({ ...f, password: e.target.value }))}
                required
                autoComplete="new-password"
              />
            </div>
            <div className="form-field">
              <label className="form-label">{t('settings.accounts.createDialog.confirmPassword')}</label>
              <input
                type="password"
                className="form-input"
                value={createForm.confirm_password}
                onChange={(e) => setCreateForm((f) => ({ ...f, confirm_password: e.target.value }))}
                required
                autoComplete="new-password"
              />
            </div>
            <div className="form-field">
              <label className="form-checkbox">
                <input
                  type="checkbox"
                  checked={createForm.must_change_password}
                  onChange={(e) => setCreateForm((f) => ({ ...f, must_change_password: e.target.checked }))}
                />
                <span>{t('settings.accounts.createDialog.mustChangePassword')}</span>
              </label>
            </div>
          </div>
        </SettingsDialog>
      )}

      {/* Edit Status Dialog */}
      {showStatusDialog && selectedAccount && (
        <SettingsDialog
          title={t('settings.accounts.statusDialog.title')}
          description={t('settings.accounts.statusDialog.description', {
            username: selectedAccount.account.username,
          })}
          onClose={() => setShowStatusDialog(false)}
          onSubmit={handleUpdateStatus}
          actions={
            <>
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => setShowStatusDialog(false)}
                disabled={submitting}
              >
                {t('common.cancel')}
              </button>
              <button type="submit" className="btn btn--primary" disabled={submitting}>
                {submitting ? t('common.saving') : t('common.save')}
              </button>
            </>
          }
        >
          <div className="settings-form__body">
            {formError && <div className="form-error">{formError}</div>}
            <div className="form-field">
              <label className="form-label">{t('settings.accounts.statusDialog.status')}</label>
              <select
                className="form-select"
                value={newStatus}
                onChange={(e) => setNewStatus(e.target.value as AccountStatus)}
              >
                <option value="active">{t('settings.accounts.status.active')}</option>
                <option value="disabled">{t('settings.accounts.status.disabled')}</option>
                <option value="locked">{t('settings.accounts.status.locked')}</option>
              </select>
            </div>
          </div>
        </SettingsDialog>
      )}

      {/* Reset Password Dialog */}
      {showResetPasswordDialog && selectedAccount && (
        <SettingsDialog
          title={t('settings.accounts.resetPasswordDialog.title')}
          description={t('settings.accounts.resetPasswordDialog.description', {
            username: selectedAccount.account.username,
          })}
          onClose={() => setShowResetPasswordDialog(false)}
          onSubmit={handleResetPassword}
          actions={
            <>
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => setShowResetPasswordDialog(false)}
                disabled={submitting}
              >
                {t('common.cancel')}
              </button>
              <button
                type="submit"
                className="btn btn--primary"
                disabled={submitting || !resetPasswordForm.new_password}
              >
                {submitting ? t('common.saving') : t('settings.accounts.actions.resetPassword')}
              </button>
            </>
          }
        >
          <div className="settings-form__body">
            {formError && <div className="form-error">{formError}</div>}
            <div className="form-field">
              <label className="form-label">{t('settings.accounts.resetPasswordDialog.newPassword')}</label>
              <input
                type="password"
                className="form-input"
                value={resetPasswordForm.new_password}
                onChange={(e) => setResetPasswordForm((f) => ({ ...f, new_password: e.target.value }))}
                required
                autoComplete="new-password"
              />
            </div>
            <div className="form-field">
              <label className="form-label">{t('settings.accounts.resetPasswordDialog.confirmPassword')}</label>
              <input
                type="password"
                className="form-input"
                value={resetPasswordForm.confirm_password}
                onChange={(e) => setResetPasswordForm((f) => ({ ...f, confirm_password: e.target.value }))}
                required
                autoComplete="new-password"
              />
            </div>
            <div className="form-field">
              <label className="form-checkbox">
                <input
                  type="checkbox"
                  checked={resetPasswordForm.must_change_password}
                  onChange={(e) => setResetPasswordForm((f) => ({ ...f, must_change_password: e.target.checked }))}
                />
                <span>{t('settings.accounts.createDialog.mustChangePassword')}</span>
              </label>
            </div>
          </div>
        </SettingsDialog>
      )}

      {/* Delete Confirmation Dialog */}
      {showDeleteDialog && selectedAccount && (
        <SettingsDialog
          title={t('settings.accounts.deleteDialog.title')}
          onClose={() => setShowDeleteDialog(false)}
          className="dialog--danger"
          actions={
            <>
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => setShowDeleteDialog(false)}
                disabled={submitting}
              >
                {t('common.cancel')}
              </button>
              <button
                type="button"
                className="btn btn--danger"
                onClick={handleDeleteAccount}
                disabled={submitting}
              >
                {submitting ? t('common.deleting') : t('common.delete')}
              </button>
            </>
          }
        >
          <div className="settings-form__body">
            {formError && <div className="form-error">{formError}</div>}
            <SettingsNotice tone="error" icon={<ShieldAlert size={20} />}>
              {t('settings.accounts.deleteDialog.warning', {
                username: selectedAccount.account.username,
              })}
            </SettingsNotice>
          </div>
        </SettingsDialog>
      )}
    </SettingsPageShell>
  );
}

export default function AccountsSettingsPage() {
  return (
    <GuardedPage mode="protected" path="/pages/settings/accounts/index">
      <AccountsSettingsContent />
    </GuardedPage>
  );
}
