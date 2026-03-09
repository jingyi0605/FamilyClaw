import { useEffect, useMemo, useState } from "react";

import { PageSection } from "../components/PageSection";
import { StatusMessage } from "../components/StatusMessage";
import { api } from "../lib/api";
import { useHousehold } from "../state/household";
import type { Member } from "../types";

const defaultCreateForm = {
  name: "",
  nickname: "",
  role: "adult" as Member["role"],
  age_group: "adult" as NonNullable<Member["age_group"]>,
  phone: "",
  guardian_member_id: "",
};

export function MembersPage() {
  const { household } = useHousehold();
  const [members, setMembers] = useState<Member[]>([]);
  const [createForm, setCreateForm] = useState(defaultCreateForm);
  const [editingId, setEditingId] = useState<string>("");
  const [editingDraft, setEditingDraft] = useState<Partial<Member>>({});
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(false);

  const guardianCandidates = useMemo(
    () => members.filter((member) => member.role === "admin" || member.role === "adult"),
    [members],
  );

  async function loadMembers() {
    if (!household?.id) {
      setMembers([]);
      return;
    }
    const response = await api.listMembers(household.id);
    setMembers(response.items);
  }

  useEffect(() => {
    loadMembers().catch((err) => setError(err instanceof Error ? err.message : "加载成员失败"));
  }, [household?.id]);

  async function handleCreateMember(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!household?.id) {
      setError("请先创建或加载家庭。");
      return;
    }

    setLoading(true);
    setError("");
    setStatus("");
    try {
      await api.createMember({
        household_id: household.id,
        name: createForm.name,
        nickname: createForm.nickname || null,
        role: createForm.role,
        age_group: createForm.age_group,
        phone: createForm.phone || null,
        guardian_member_id: createForm.guardian_member_id || null,
      });
      setCreateForm(defaultCreateForm);
      await loadMembers();
      setStatus("成员创建成功。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建成员失败");
    } finally {
      setLoading(false);
    }
  }

  function startEdit(member: Member) {
    setEditingId(member.id);
    setEditingDraft({
      nickname: member.nickname,
      role: member.role,
      age_group: member.age_group,
      phone: member.phone,
      status: member.status,
      guardian_member_id: member.guardian_member_id,
    });
  }

  async function saveEdit(memberId: string) {
    setLoading(true);
    setError("");
    setStatus("");
    try {
      await api.updateMember(memberId, editingDraft);
      setEditingId("");
      setEditingDraft({});
      await loadMembers();
      setStatus("成员更新成功。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新成员失败");
    } finally {
      setLoading(false);
    }
  }

  async function deactivateMember(memberId: string) {
    setLoading(true);
    setError("");
    setStatus("");
    try {
      await api.updateMember(memberId, { status: "inactive" });
      await loadMembers();
      setStatus("成员已停用。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "停用成员失败");
    } finally {
      setLoading(false);
    }
  }

  if (!household?.id) {
    return <StatusMessage tone="info" message="请先在“家庭管理”页面创建或加载当前家庭。" />;
  }

  return (
    <div className="page-grid">
      <PageSection title="新增成员" description="对接 `POST /api/v1/members`。">
        <form className="form-grid" onSubmit={handleCreateMember}>
          <label>
            姓名
            <input
              value={createForm.name}
              onChange={(event) =>
                setCreateForm((current) => ({ ...current, name: event.target.value }))
              }
              required
            />
          </label>
          <label>
            昵称
            <input
              value={createForm.nickname}
              onChange={(event) =>
                setCreateForm((current) => ({ ...current, nickname: event.target.value }))
              }
            />
          </label>
          <label>
            角色
            <select
              value={createForm.role}
              onChange={(event) =>
                setCreateForm((current) => ({
                  ...current,
                  role: event.target.value as Member["role"],
                }))
              }
            >
              <option value="admin">管理员</option>
              <option value="adult">成人</option>
              <option value="child">儿童</option>
              <option value="elder">老人</option>
              <option value="guest">访客</option>
            </select>
          </label>
          <label>
            年龄分组
            <select
              value={createForm.age_group}
              onChange={(event) =>
                setCreateForm((current) => ({
                  ...current,
                  age_group: event.target.value as NonNullable<Member["age_group"]>,
                }))
              }
            >
              <option value="adult">adult</option>
              <option value="child">child</option>
              <option value="teen">teen</option>
              <option value="toddler">toddler</option>
              <option value="elder">elder</option>
            </select>
          </label>
          <label>
            电话
            <input
              value={createForm.phone}
              onChange={(event) =>
                setCreateForm((current) => ({ ...current, phone: event.target.value }))
              }
            />
          </label>
          <label>
            监护人
            <select
              value={createForm.guardian_member_id}
              onChange={(event) =>
                setCreateForm((current) => ({
                  ...current,
                  guardian_member_id: event.target.value,
                }))
              }
            >
              <option value="">无</option>
              {guardianCandidates.map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  {candidate.name}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={loading}>
            {loading ? "提交中..." : "创建成员"}
          </button>
        </form>
        {status ? <StatusMessage tone="success" message={status} /> : null}
        {error ? <StatusMessage tone="error" message={error} /> : null}
      </PageSection>

      <PageSection title="成员列表" description="对接成员查询、编辑与停用接口。">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>姓名</th>
                <th>昵称</th>
                <th>角色</th>
                <th>状态</th>
                <th>监护人</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {members.map((member) => {
                const isEditing = editingId === member.id;
                return (
                  <tr key={member.id}>
                    <td>{member.name}</td>
                    <td>
                      {isEditing ? (
                        <input
                          value={(editingDraft.nickname as string | undefined) ?? ""}
                          onChange={(event) =>
                            setEditingDraft((current) => ({
                              ...current,
                              nickname: event.target.value,
                            }))
                          }
                        />
                      ) : (
                        member.nickname ?? "-"
                      )}
                    </td>
                    <td>
                      {isEditing ? (
                        <select
                          value={(editingDraft.role as Member["role"] | undefined) ?? member.role}
                          onChange={(event) =>
                            setEditingDraft((current) => ({
                              ...current,
                              role: event.target.value as Member["role"],
                            }))
                          }
                        >
                          <option value="admin">admin</option>
                          <option value="adult">adult</option>
                          <option value="child">child</option>
                          <option value="elder">elder</option>
                          <option value="guest">guest</option>
                        </select>
                      ) : (
                        member.role
                      )}
                    </td>
                    <td>
                      {isEditing ? (
                        <select
                          value={
                            (editingDraft.status as Member["status"] | undefined) ?? member.status
                          }
                          onChange={(event) =>
                            setEditingDraft((current) => ({
                              ...current,
                              status: event.target.value as Member["status"],
                            }))
                          }
                        >
                          <option value="active">active</option>
                          <option value="inactive">inactive</option>
                        </select>
                      ) : (
                        member.status
                      )}
                    </td>
                    <td>{member.guardian_member_id ?? "-"}</td>
                    <td className="table-actions">
                      {isEditing ? (
                        <>
                          <button onClick={() => saveEdit(member.id)} disabled={loading}>
                            保存
                          </button>
                          <button
                            className="ghost"
                            onClick={() => {
                              setEditingId("");
                              setEditingDraft({});
                            }}
                            disabled={loading}
                          >
                            取消
                          </button>
                        </>
                      ) : (
                        <>
                          <button onClick={() => startEdit(member)} disabled={loading}>
                            编辑
                          </button>
                          <button
                            className="ghost"
                            onClick={() => deactivateMember(member.id)}
                            disabled={loading || member.status === "inactive"}
                          >
                            停用
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </PageSection>
    </div>
  );
}

