import { useEffect, useMemo, useState } from "react";

import { PageSection } from "../components/PageSection";
import { StatusMessage } from "../components/StatusMessage";
import { api } from "../lib/api";
import {
  getRelationCategoryLabel,
  getRelationDirectionLabel,
  RELATION_TYPE_OPTIONS,
} from "../lib/relationshipLabels";
import { useHousehold } from "../state/household";
import type { Member, MemberRelationship } from "../types";

type RelationshipFormState = {
  source_member_id: string;
  target_member_id: string;
  relation_type: MemberRelationship["relation_type"];
  visibility_scope: MemberRelationship["visibility_scope"];
  delegation_scope: MemberRelationship["delegation_scope"];
};

type RelationshipFilters = {
  source_member_id: string;
  target_member_id: string;
  relation_type: "" | MemberRelationship["relation_type"];
};

const defaultCreateForm: RelationshipFormState = {
  source_member_id: "",
  target_member_id: "",
  relation_type: "parent",
  visibility_scope: "family",
  delegation_scope: "none",
};

const defaultFilters: RelationshipFilters = {
  source_member_id: "",
  target_member_id: "",
  relation_type: "",
};

function formatMemberLabel(member: Member): string {
  return `${member.name} · ${member.role} · ${member.status}`;
}

export function MemberRelationshipsPage() {
  const { household } = useHousehold();
  const [members, setMembers] = useState<Member[]>([]);
  const [relationships, setRelationships] = useState<MemberRelationship[]>([]);
  const [createForm, setCreateForm] = useState<RelationshipFormState>(defaultCreateForm);
  const [filters, setFilters] = useState<RelationshipFilters>(defaultFilters);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [membersLoading, setMembersLoading] = useState(false);
  const [relationshipsLoading, setRelationshipsLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const memberNameMap = useMemo(
    () =>
      Object.fromEntries(
        members.map((member) => [member.id, member.name] satisfies [string, string]),
      ),
    [members],
  );
  const memberMap = useMemo(
    () => new Map(members.map((member) => [member.id, member] as const)),
    [members],
  );
  const relationshipMap = useMemo(
    () =>
      new Map(
        relationships.map((relationship) => [
          `${relationship.source_member_id}|${relationship.target_member_id}`,
          relationship,
        ] as const),
      ),
    [relationships],
  );

  async function loadMembers() {
    if (!household?.id) {
      setMembers([]);
      return;
    }

    setMembersLoading(true);
    setError("");
    try {
      const response = await api.listMembers(household.id);
      setMembers(response.items);
      setCreateForm((current) => {
        const sourceMemberId =
          current.source_member_id && response.items.some((member) => member.id === current.source_member_id)
            ? current.source_member_id
            : response.items[0]?.id ?? "";
        const fallbackTarget =
          response.items.find((member) => member.id !== sourceMemberId)?.id ?? "";
        const targetMemberId =
          current.target_member_id && response.items.some((member) => member.id === current.target_member_id)
            ? current.target_member_id
            : fallbackTarget;

        return {
          ...current,
          source_member_id: sourceMemberId,
          target_member_id: targetMemberId === sourceMemberId ? fallbackTarget : targetMemberId,
        };
      });
      setFilters((current) => ({
        source_member_id:
          current.source_member_id && response.items.some((member) => member.id === current.source_member_id)
            ? current.source_member_id
            : "",
        target_member_id:
          current.target_member_id && response.items.some((member) => member.id === current.target_member_id)
            ? current.target_member_id
            : "",
        relation_type: current.relation_type,
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载成员失败");
    } finally {
      setMembersLoading(false);
    }
  }

  async function loadRelationships(nextFilters = filters) {
    if (!household?.id) {
      setRelationships([]);
      return;
    }

    setRelationshipsLoading(true);
    setError("");
    try {
      const response = await api.listMemberRelationships({
        householdId: household.id,
        sourceMemberId: nextFilters.source_member_id || undefined,
        targetMemberId: nextFilters.target_member_id || undefined,
        relationType: nextFilters.relation_type || undefined,
      });
      setRelationships(response.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载成员关系失败");
    } finally {
      setRelationshipsLoading(false);
    }
  }

  useEffect(() => {
    if (!household?.id) {
      setMembers([]);
      setRelationships([]);
      setCreateForm(defaultCreateForm);
      setFilters(defaultFilters);
      return;
    }

    void loadMembers();
    void loadRelationships(defaultFilters);
  }, [household?.id]);

  async function handleCreateRelationship(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!household?.id) {
      setError("请先创建或加载家庭。");
      return;
    }
    if (!createForm.source_member_id || !createForm.target_member_id) {
      setError("请先选择关系双方成员。");
      return;
    }

    setSubmitting(true);
    setStatus("");
    setError("");
    try {
      await api.createMemberRelationship({
        household_id: household.id,
        source_member_id: createForm.source_member_id,
        target_member_id: createForm.target_member_id,
        relation_type: createForm.relation_type,
        visibility_scope: createForm.visibility_scope,
        delegation_scope: createForm.delegation_scope,
      });
      await loadRelationships();
      setStatus("成员关系创建成功。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建成员关系失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleApplyFilters(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("");
    setError("");
    await loadRelationships(filters);
  }

  if (!household?.id) {
    return <StatusMessage tone="info" message="请先在“家庭管理”页面创建或加载当前家庭。" />;
  }

  if (!membersLoading && members.length < 2) {
    return (
      <StatusMessage
        tone="info"
        message="当前家庭至少需要 2 个成员才能配置关系，请先到“成员管理”页面补充成员。"
      />
    );
  }

  return (
    <div className="page-grid">
      <PageSection title="新增关系" description="对接 `POST /api/v1/member-relationships`。">
        <form className="form-grid" onSubmit={handleCreateRelationship}>
          <label>
            发起成员
            <select
              value={createForm.source_member_id}
              onChange={(event) =>
                setCreateForm((current) => ({
                  ...current,
                  source_member_id: event.target.value,
                }))
              }
              disabled={submitting}
            >
              <option value="">请选择成员</option>
              {members.map((member) => (
                <option key={member.id} value={member.id}>
                  {formatMemberLabel(member)}
                </option>
              ))}
            </select>
          </label>
          <label>
            目标成员
            <select
              value={createForm.target_member_id}
              onChange={(event) =>
                setCreateForm((current) => ({
                  ...current,
                  target_member_id: event.target.value,
                }))
              }
              disabled={submitting}
            >
              <option value="">请选择成员</option>
              {members.map((member) => (
                <option key={member.id} value={member.id}>
                  {formatMemberLabel(member)}
                </option>
              ))}
            </select>
          </label>
          <label>
            关系类型
            <select
              value={createForm.relation_type}
              onChange={(event) =>
                setCreateForm((current) => ({
                  ...current,
                  relation_type: event.target.value as MemberRelationship["relation_type"],
                }))
              }
              disabled={submitting}
            >
              {RELATION_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {`${option.label} (${option.value})`}
                </option>
              ))}
            </select>
          </label>
          <label>
            可见范围
            <select
              value={createForm.visibility_scope}
              onChange={(event) =>
                setCreateForm((current) => ({
                  ...current,
                  visibility_scope: event.target.value as MemberRelationship["visibility_scope"],
                }))
              }
              disabled={submitting}
            >
              <option value="family">family</option>
              <option value="public">public</option>
              <option value="private">private</option>
            </select>
          </label>
          <label>
            委托范围
            <select
              value={createForm.delegation_scope}
              onChange={(event) =>
                setCreateForm((current) => ({
                  ...current,
                  delegation_scope: event.target.value as MemberRelationship["delegation_scope"],
                }))
              }
              disabled={submitting}
            >
              <option value="none">none</option>
              <option value="reminder">reminder</option>
              <option value="health">health</option>
              <option value="device">device</option>
            </select>
          </label>
          <button type="submit" disabled={submitting || membersLoading}>
            {submitting ? "提交中..." : "创建关系"}
          </button>
        </form>
        {status ? <StatusMessage tone="success" message={status} /> : null}
        {error ? <StatusMessage tone="error" message={error} /> : null}
      </PageSection>

      <PageSection title="关系列表" description="支持按成员与关系类型筛选当前家庭中的关系。">
        <form className="form-grid" onSubmit={handleApplyFilters}>
          <label>
            发起成员筛选
            <select
              value={filters.source_member_id}
              onChange={(event) =>
                setFilters((current) => ({
                  ...current,
                  source_member_id: event.target.value,
                }))
              }
            >
              <option value="">全部</option>
              {members.map((member) => (
                <option key={member.id} value={member.id}>
                  {formatMemberLabel(member)}
                </option>
              ))}
            </select>
          </label>
          <label>
            目标成员筛选
            <select
              value={filters.target_member_id}
              onChange={(event) =>
                setFilters((current) => ({
                  ...current,
                  target_member_id: event.target.value,
                }))
              }
            >
              <option value="">全部</option>
              {members.map((member) => (
                <option key={member.id} value={member.id}>
                  {formatMemberLabel(member)}
                </option>
              ))}
            </select>
          </label>
          <label>
            关系类型筛选
            <select
              value={filters.relation_type}
              onChange={(event) =>
                setFilters((current) => ({
                  ...current,
                  relation_type: event.target.value as RelationshipFilters["relation_type"],
                }))
              }
            >
              <option value="">全部</option>
              {RELATION_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {`${option.label} (${option.value})`}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={relationshipsLoading}>
            {relationshipsLoading ? "加载中..." : "应用筛选"}
          </button>
        </form>

        <div className="summary-grid">
          <div className="summary-card">
            <span>关系数量</span>
            <strong>{relationships.length}</strong>
            <small>当前筛选结果</small>
          </div>
          <div className="summary-card">
            <span>成员数量</span>
            <strong>{members.length}</strong>
            <small>当前家庭成员总数</small>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>发起成员</th>
                <th>关系类型</th>
                <th>目标成员</th>
                <th>可见范围</th>
                <th>委托范围</th>
                <th>创建时间</th>
              </tr>
            </thead>
            <tbody>
              {relationships.length === 0 ? (
                <tr>
                  <td colSpan={6}>当前没有符合条件的成员关系。</td>
                </tr>
              ) : (
                relationships.map((relationship) => (
                  <tr key={relationship.id}>
                    <td>{memberNameMap[relationship.source_member_id] ?? relationship.source_member_id}</td>
                    <td>
                      <div>
                        {getRelationCategoryLabel(
                          relationship,
                          relationshipMap.get(
                            `${relationship.target_member_id}|${relationship.source_member_id}`,
                          ),
                          memberMap.get(relationship.source_member_id),
                          memberMap.get(relationship.target_member_id),
                        )}
                      </div>
                      <small>
                        {getRelationDirectionLabel(relationship.relation_type)}
                        {" · "}
                        {relationship.relation_type}
                      </small>
                    </td>
                    <td>{memberNameMap[relationship.target_member_id] ?? relationship.target_member_id}</td>
                    <td>{relationship.visibility_scope}</td>
                    <td>{relationship.delegation_scope}</td>
                    <td>{relationship.created_at}</td>
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
