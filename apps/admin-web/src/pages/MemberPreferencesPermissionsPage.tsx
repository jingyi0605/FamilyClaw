import { useEffect, useMemo, useState } from "react";

import { PageSection } from "../components/PageSection";
import { StatusMessage } from "../components/StatusMessage";
import { ApiError, api } from "../lib/api";
import { useHousehold } from "../state/household";
import type { Member, MemberPermissionRule, MemberPreference } from "../types";

type PreferenceFormState = {
  preferred_name: string;
  light_preference: string;
  climate_preference: string;
  content_preference: string;
  reminder_channel_preference: string;
  sleep_schedule: string;
};

const defaultPreferenceForm: PreferenceFormState = {
  preferred_name: "",
  light_preference: "",
  climate_preference: "",
  content_preference: "",
  reminder_channel_preference: "",
  sleep_schedule: "",
};

const defaultRuleDraft: MemberPermissionRule = {
  resource_type: "device",
  resource_scope: "family",
  action: "read",
  effect: "allow",
};

function formatJsonValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }

  return JSON.stringify(value, null, 2);
}

function buildPreferenceForm(preference: MemberPreference | null): PreferenceFormState {
  if (!preference) {
    return defaultPreferenceForm;
  }

  return {
    preferred_name: preference.preferred_name ?? "",
    light_preference: formatJsonValue(preference.light_preference),
    climate_preference: formatJsonValue(preference.climate_preference),
    content_preference: formatJsonValue(preference.content_preference),
    reminder_channel_preference: formatJsonValue(preference.reminder_channel_preference),
    sleep_schedule: formatJsonValue(preference.sleep_schedule),
  };
}

function parseJsonField(label: string, value: string): unknown | null {
  const trimmedValue = value.trim();
  if (!trimmedValue) {
    return null;
  }

  try {
    return JSON.parse(trimmedValue);
  } catch {
    throw new Error(`${label} 不是合法 JSON，请检查格式后重试。`);
  }
}

function extractRules(rules: MemberPermissionRule[]): MemberPermissionRule[] {
  return rules.map((rule) => ({
    resource_type: rule.resource_type,
    resource_scope: rule.resource_scope,
    action: rule.action,
    effect: rule.effect,
  }));
}

function getMemberSubtitle(member: Member): string {
  return [member.role, member.status, member.nickname || "无昵称"].join(" · ");
}

export function MemberPreferencesPermissionsPage() {
  const { household } = useHousehold();
  const [members, setMembers] = useState<Member[]>([]);
  const [selectedMemberId, setSelectedMemberId] = useState("");
  const [preferenceForm, setPreferenceForm] = useState<PreferenceFormState>(defaultPreferenceForm);
  const [preferenceUpdatedAt, setPreferenceUpdatedAt] = useState("");
  const [permissionRules, setPermissionRules] = useState<MemberPermissionRule[]>([]);
  const [ruleDraft, setRuleDraft] = useState<MemberPermissionRule>(defaultRuleDraft);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [membersLoading, setMembersLoading] = useState(false);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [savingPreferences, setSavingPreferences] = useState(false);
  const [savingPermissions, setSavingPermissions] = useState(false);

  const selectedMember = useMemo(
    () => members.find((member) => member.id === selectedMemberId) ?? null,
    [members, selectedMemberId],
  );

  useEffect(() => {
    async function loadMembers() {
      if (!household?.id) {
        setMembers([]);
        setSelectedMemberId("");
        return;
      }

      setMembersLoading(true);
      setError("");
      try {
        const response = await api.listMembers(household.id);
        setMembers(response.items);
        setSelectedMemberId((currentId) => {
          if (currentId && response.items.some((member) => member.id === currentId)) {
            return currentId;
          }
          return response.items[0]?.id ?? "";
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载成员失败");
      } finally {
        setMembersLoading(false);
      }
    }

    void loadMembers();
  }, [household?.id]);

  useEffect(() => {
    async function loadMemberConfig() {
      if (!selectedMemberId) {
        setPreferenceForm(defaultPreferenceForm);
        setPreferenceUpdatedAt("");
        setPermissionRules([]);
        return;
      }

      setDetailsLoading(true);
      setError("");
      try {
        const [preference, permissions] = await Promise.all([
          api.getMemberPreferences(selectedMemberId).catch((err: unknown) => {
            if (err instanceof ApiError && err.status === 404) {
              return null;
            }
            throw err;
          }),
          api.getMemberPermissions(selectedMemberId),
        ]);

        setPreferenceForm(buildPreferenceForm(preference));
        setPreferenceUpdatedAt(preference?.updated_at ?? "");
        setPermissionRules(extractRules(permissions.items));
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载成员偏好与权限失败");
      } finally {
        setDetailsLoading(false);
      }
    }

    void loadMemberConfig();
  }, [selectedMemberId]);

  async function handleSavePreferences(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedMemberId) {
      setError("请先选择成员。");
      return;
    }

    setSavingPreferences(true);
    setStatus("");
    setError("");
    try {
      const response = await api.upsertMemberPreferences(selectedMemberId, {
        preferred_name: preferenceForm.preferred_name.trim() || null,
        light_preference: parseJsonField("灯光偏好", preferenceForm.light_preference),
        climate_preference: parseJsonField("气候偏好", preferenceForm.climate_preference),
        content_preference: parseJsonField("内容偏好", preferenceForm.content_preference),
        reminder_channel_preference: parseJsonField(
          "提醒渠道偏好",
          preferenceForm.reminder_channel_preference,
        ),
        sleep_schedule: parseJsonField("作息偏好", preferenceForm.sleep_schedule),
      });
      setPreferenceForm(buildPreferenceForm(response));
      setPreferenceUpdatedAt(response.updated_at);
      setStatus("成员偏好已保存。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存成员偏好失败");
    } finally {
      setSavingPreferences(false);
    }
  }

  function handleAddRule() {
    setPermissionRules((current) => [...current, { ...ruleDraft }]);
    setStatus("");
    setError("");
  }

  function handleRemoveRule(index: number) {
    setPermissionRules((current) => current.filter((_, currentIndex) => currentIndex !== index));
    setStatus("");
    setError("");
  }

  async function handleSavePermissions() {
    if (!selectedMemberId) {
      setError("请先选择成员。");
      return;
    }

    setSavingPermissions(true);
    setStatus("");
    setError("");
    try {
      const response = await api.replaceMemberPermissions(selectedMemberId, {
        rules: permissionRules,
      });
      setPermissionRules(extractRules(response.items));
      setStatus(`成员权限已保存，共 ${response.items.length} 条规则。`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存成员权限失败");
    } finally {
      setSavingPermissions(false);
    }
  }

  if (!household?.id) {
    return <StatusMessage tone="info" message="请先在“家庭管理”页面创建或加载当前家庭。" />;
  }

  if (!membersLoading && members.length === 0) {
    return <StatusMessage tone="info" message="当前家庭还没有成员，请先到“成员管理”页面创建成员。" />;
  }

  return (
    <div className="page-grid">
      <PageSection title="成员选择" description="先选择成员，再维护个人偏好与访问权限。">
        <div className="member-config-grid">
          <label>
            当前成员
            <select
              value={selectedMemberId}
              onChange={(event) => setSelectedMemberId(event.target.value)}
              disabled={membersLoading}
            >
              <option value="">请选择成员</option>
              {members.map((member) => (
                <option key={member.id} value={member.id}>
                  {member.name} · {member.role}
                </option>
              ))}
            </select>
          </label>

          {selectedMember ? (
            <div className="summary-grid">
              <div className="summary-card">
                <span>成员信息</span>
                <strong>{selectedMember.name}</strong>
                <small>{getMemberSubtitle(selectedMember)}</small>
              </div>
              <div className="summary-card">
                <span>联系电话</span>
                <strong>{selectedMember.phone || "-"}</strong>
                <small>监护人：{selectedMember.guardian_member_id || "无"}</small>
              </div>
              <div className="summary-card">
                <span>偏好更新时间</span>
                <strong>{preferenceUpdatedAt || "尚未配置"}</strong>
                <small>权限规则：{permissionRules.length} 条</small>
              </div>
            </div>
          ) : (
            <StatusMessage tone="info" message="请选择一个成员以加载偏好与权限。" />
          )}
        </div>
        {detailsLoading ? (
          <StatusMessage tone="info" message="正在加载成员偏好与权限..." />
        ) : null}
        {status ? <StatusMessage tone="success" message={status} /> : null}
        {error ? <StatusMessage tone="error" message={error} /> : null}
      </PageSection>

      <PageSection title="偏好配置" description="以 JSON 形式维护结构化偏好，保持最小可运行。">
        <form className="page-grid" onSubmit={handleSavePreferences}>
          <div className="form-grid">
            <label>
              展示称呼
              <input
                value={preferenceForm.preferred_name}
                onChange={(event) =>
                  setPreferenceForm((current) => ({
                    ...current,
                    preferred_name: event.target.value,
                  }))
                }
                placeholder="例如：爸爸、Jackson、奶奶"
              />
            </label>
          </div>

          <div className="json-grid">
            <label className="json-field">
              灯光偏好
              <textarea
                rows={6}
                value={preferenceForm.light_preference}
                onChange={(event) =>
                  setPreferenceForm((current) => ({
                    ...current,
                    light_preference: event.target.value,
                  }))
                }
                placeholder='{"brightness": 70, "tone": "warm"}'
              />
            </label>
            <label className="json-field">
              气候偏好
              <textarea
                rows={6}
                value={preferenceForm.climate_preference}
                onChange={(event) =>
                  setPreferenceForm((current) => ({
                    ...current,
                    climate_preference: event.target.value,
                  }))
                }
                placeholder='{"temperature": 25, "mode": "cool"}'
              />
            </label>
            <label className="json-field">
              内容偏好
              <textarea
                rows={6}
                value={preferenceForm.content_preference}
                onChange={(event) =>
                  setPreferenceForm((current) => ({
                    ...current,
                    content_preference: event.target.value,
                  }))
                }
                placeholder='{"topics": ["绘本", "科普"], "language": "zh-CN"}'
              />
            </label>
            <label className="json-field">
              提醒渠道偏好
              <textarea
                rows={6}
                value={preferenceForm.reminder_channel_preference}
                onChange={(event) =>
                  setPreferenceForm((current) => ({
                    ...current,
                    reminder_channel_preference: event.target.value,
                  }))
                }
                placeholder='{"channels": ["app", "speaker"], "silent_hours": ["22:00-07:00"]}'
              />
            </label>
            <label className="json-field">
              作息偏好
              <textarea
                rows={6}
                value={preferenceForm.sleep_schedule}
                onChange={(event) =>
                  setPreferenceForm((current) => ({
                    ...current,
                    sleep_schedule: event.target.value,
                  }))
                }
                placeholder='{"weekday_sleep": "22:30", "weekday_wake": "07:00"}'
              />
            </label>
          </div>

          <div className="section-actions">
            <button type="submit" disabled={!selectedMemberId || detailsLoading || savingPreferences}>
              {savingPreferences ? "保存中..." : "保存成员偏好"}
            </button>
          </div>
        </form>
      </PageSection>

      <PageSection
        title="权限规则"
        description="先在本地增删规则，再通过一次 PUT 覆盖保存。"
        actions={
          <button
            onClick={() => {
              void handleSavePermissions();
            }}
            disabled={!selectedMemberId || detailsLoading || savingPermissions}
          >
            {savingPermissions ? "保存中..." : "保存权限规则"}
          </button>
        }
      >
        <div className="rule-builder">
          <label>
            资源类型
            <select
              value={ruleDraft.resource_type}
              onChange={(event) =>
                setRuleDraft((current) => ({
                  ...current,
                  resource_type: event.target.value as MemberPermissionRule["resource_type"],
                }))
              }
            >
              <option value="device">device</option>
              <option value="memory">memory</option>
              <option value="health">health</option>
              <option value="photo">photo</option>
              <option value="scenario">scenario</option>
            </select>
          </label>
          <label>
            作用域
            <select
              value={ruleDraft.resource_scope}
              onChange={(event) =>
                setRuleDraft((current) => ({
                  ...current,
                  resource_scope: event.target.value as MemberPermissionRule["resource_scope"],
                }))
              }
            >
              <option value="self">self</option>
              <option value="children">children</option>
              <option value="family">family</option>
              <option value="public">public</option>
            </select>
          </label>
          <label>
            动作
            <select
              value={ruleDraft.action}
              onChange={(event) =>
                setRuleDraft((current) => ({
                  ...current,
                  action: event.target.value as MemberPermissionRule["action"],
                }))
              }
            >
              <option value="read">read</option>
              <option value="write">write</option>
              <option value="execute">execute</option>
              <option value="manage">manage</option>
            </select>
          </label>
          <label>
            效果
            <select
              value={ruleDraft.effect}
              onChange={(event) =>
                setRuleDraft((current) => ({
                  ...current,
                  effect: event.target.value as MemberPermissionRule["effect"],
                }))
              }
            >
              <option value="allow">allow</option>
              <option value="deny">deny</option>
            </select>
          </label>
          <button type="button" onClick={handleAddRule} disabled={!selectedMemberId || detailsLoading}>
            添加规则
          </button>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>资源类型</th>
                <th>作用域</th>
                <th>动作</th>
                <th>效果</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {permissionRules.length === 0 ? (
                <tr>
                  <td colSpan={5}>当前成员还没有权限规则，可先添加再保存。</td>
                </tr>
              ) : (
                permissionRules.map((rule, index) => (
                  <tr key={`${rule.resource_type}-${rule.resource_scope}-${rule.action}-${index}`}>
                    <td>{rule.resource_type}</td>
                    <td>{rule.resource_scope}</td>
                    <td>{rule.action}</td>
                    <td>{rule.effect}</td>
                    <td className="table-actions">
                      <button
                        type="button"
                        className="ghost"
                        onClick={() => handleRemoveRule(index)}
                        disabled={savingPermissions}
                      >
                        删除
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </PageSection>
    </div>
  );
}
