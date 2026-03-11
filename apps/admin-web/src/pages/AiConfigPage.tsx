import { useEffect, useMemo, useState } from "react";

import { PageSection } from "../components/PageSection";
import { StatusMessage } from "../components/StatusMessage";
import { api } from "../lib/api";
import { useHousehold } from "../state/household";
import type {
  AgentDetail,
  AgentMemberCognitionUpsertItemPayload,
  AgentSummary,
  Member,
} from "../types";

function getErrorMessage(error: unknown) {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "未知错误";
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "暂无";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatAgentType(value: AgentSummary["agent_type"]) {
  switch (value) {
    case "butler":
      return "管家";
    case "nutritionist":
      return "营养师";
    case "fitness_coach":
      return "健身教练";
    case "study_coach":
      return "学习教练";
    default:
      return "自定义";
  }
}

function formatAgentStatus(value: AgentSummary["status"]) {
  switch (value) {
    case "active":
      return "启用中";
    case "inactive":
      return "已停用";
    default:
      return "草稿";
  }
}

function stringifyJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

function parseJsonObject(value: string, label: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = JSON.parse(trimmed) as unknown;
  if (parsed !== null && typeof parsed === "object" && !Array.isArray(parsed)) {
    return parsed as Record<string, unknown>;
  }
  throw new Error(`${label} 必须是 JSON 对象。`);
}

type AgentCognitionFormItem = {
  member_id: string;
  display_address: string;
  closeness_level: number;
  service_priority: number;
  communication_style: string;
  care_notes_json: string;
  prompt_notes: string;
};

export function AiConfigPage() {
  const { household } = useHousehold();
  const householdId = household?.id ?? "";

  const [items, setItems] = useState<AgentSummary[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [savingSoul, setSavingSoul] = useState(false);
  const [savingPolicy, setSavingPolicy] = useState(false);
  const [savingCognitions, setSavingCognitions] = useState(false);
  const [message, setMessage] = useState<{ tone: "info" | "success" | "error"; text: string } | null>(null);

  const [soulForm, setSoulForm] = useState({
    self_identity: "",
    role_summary: "",
    intro_message: "",
    speaking_style: "",
    personality_traits_text: "",
    service_focus_text: "",
    service_boundaries_json: "{}",
  });
  const [policyForm, setPolicyForm] = useState({
    conversation_enabled: true,
    default_entry: false,
    routing_tags_text: "",
    memory_scope_json: "{}",
  });
  const [cognitionForm, setCognitionForm] = useState<AgentCognitionFormItem[]>([]);

  const selectedSummary = useMemo(
    () => items.find((item) => item.id === selectedAgentId) ?? null,
    [items, selectedAgentId],
  );

  const memberOptions = useMemo(
    () => members.map((item) => ({ value: item.id, label: `${item.name}（${item.role}）` })),
    [members],
  );

  function syncForms(nextDetail: AgentDetail | null) {
    if (!nextDetail) {
      setSoulForm({
        self_identity: "",
        role_summary: "",
        intro_message: "",
        speaking_style: "",
        personality_traits_text: "",
        service_focus_text: "",
        service_boundaries_json: "{}",
      });
      setPolicyForm({
        conversation_enabled: true,
        default_entry: false,
        routing_tags_text: "",
        memory_scope_json: "{}",
      });
      setCognitionForm([]);
      return;
    }

    setSoulForm({
      self_identity: nextDetail.soul?.self_identity ?? "",
      role_summary: nextDetail.soul?.role_summary ?? "",
      intro_message: nextDetail.soul?.intro_message ?? "",
      speaking_style: nextDetail.soul?.speaking_style ?? "",
      personality_traits_text: (nextDetail.soul?.personality_traits ?? []).join(", "),
      service_focus_text: (nextDetail.soul?.service_focus ?? []).join(", "),
      service_boundaries_json: stringifyJson(nextDetail.soul?.service_boundaries ?? {}),
    });

    setPolicyForm({
      conversation_enabled: nextDetail.runtime_policy?.conversation_enabled ?? true,
      default_entry: nextDetail.runtime_policy?.default_entry ?? false,
      routing_tags_text: (nextDetail.runtime_policy?.routing_tags ?? []).join(", "),
      memory_scope_json: stringifyJson(nextDetail.runtime_policy?.memory_scope ?? {}),
    });

    setCognitionForm(
      nextDetail.member_cognitions.map((item) => ({
        member_id: item.member_id,
        display_address: item.display_address ?? "",
        closeness_level: item.closeness_level,
        service_priority: item.service_priority,
        communication_style: item.communication_style ?? "",
        care_notes_json: stringifyJson(item.care_notes ?? {}),
        prompt_notes: item.prompt_notes ?? "",
      })),
    );
  }

  async function refreshAgents() {
    if (!householdId) {
      setItems([]);
      setMembers([]);
      setSelectedAgentId("");
      setDetail(null);
      syncForms(null);
      return;
    }
    setLoading(true);
    try {
      const [agentResponse, memberResponse] = await Promise.all([
        api.listAgents(householdId),
        api.listMembers(householdId),
      ]);
      setItems(agentResponse.items);
      setMembers(memberResponse.items);
      const nextSelectedId =
        agentResponse.items.find((item) => item.id === selectedAgentId)?.id ?? agentResponse.items[0]?.id ?? "";
      setSelectedAgentId(nextSelectedId);
      if (!agentResponse.items.length) {
        setDetail(null);
        syncForms(null);
      }
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    } finally {
      setLoading(false);
    }
  }

  async function loadAgentDetail(agentId: string) {
    if (!householdId || !agentId) {
      setDetail(null);
      syncForms(null);
      return;
    }
    setDetailLoading(true);
    try {
      const response = await api.getAgentDetail(householdId, agentId);
      setDetail(response);
      syncForms(response);
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => {
    void refreshAgents();
  }, [householdId]);

  useEffect(() => {
    if (!selectedAgentId) {
      setDetail(null);
      syncForms(null);
      return;
    }
    void loadAgentDetail(selectedAgentId);
  }, [householdId, selectedAgentId]);

  function updateCognitionItem(index: number, patch: Partial<AgentCognitionFormItem>) {
    setCognitionForm((current) =>
      current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
    );
  }

  function addCognitionRow() {
    setCognitionForm((current) => [
      ...current,
      {
        member_id: memberOptions[0]?.value ?? "",
        display_address: "",
        closeness_level: 3,
        service_priority: 3,
        communication_style: "",
        care_notes_json: "{}",
        prompt_notes: "",
      },
    ]);
  }

  function removeCognitionRow(index: number) {
    setCognitionForm((current) => current.filter((_, itemIndex) => itemIndex !== index));
  }

  async function handleSaveSoul() {
    if (!householdId || !selectedAgentId) {
      return;
    }
    setSavingSoul(true);
    setMessage(null);
    try {
      await api.updateAgentSoul(householdId, selectedAgentId, {
        self_identity: soulForm.self_identity.trim(),
        role_summary: soulForm.role_summary.trim(),
        intro_message: soulForm.intro_message.trim() || null,
        speaking_style: soulForm.speaking_style.trim() || null,
        personality_traits: soulForm.personality_traits_text
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        service_focus: soulForm.service_focus_text
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        service_boundaries: parseJsonObject(soulForm.service_boundaries_json, "服务边界"),
        created_by: "admin",
      });
      await Promise.all([refreshAgents(), loadAgentDetail(selectedAgentId)]);
      setMessage({ tone: "success", text: "人格配置已保存。" });
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    } finally {
      setSavingSoul(false);
    }
  }

  async function handleSavePolicy() {
    if (!householdId || !selectedAgentId) {
      return;
    }
    setSavingPolicy(true);
    setMessage(null);
    try {
      await api.updateAgentRuntimePolicy(householdId, selectedAgentId, {
        conversation_enabled: policyForm.conversation_enabled,
        default_entry: policyForm.default_entry,
        routing_tags: policyForm.routing_tags_text
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        memory_scope: parseJsonObject(policyForm.memory_scope_json, "记忆范围"),
      });
      await Promise.all([refreshAgents(), loadAgentDetail(selectedAgentId)]);
      setMessage({ tone: "success", text: "运行时策略已保存。" });
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    } finally {
      setSavingPolicy(false);
    }
  }

  async function handleSaveCognitions() {
    if (!householdId || !selectedAgentId) {
      return;
    }
    setSavingCognitions(true);
    setMessage(null);
    try {
      const itemsPayload: AgentMemberCognitionUpsertItemPayload[] = cognitionForm
        .filter((item) => item.member_id.trim())
        .map((item) => ({
          member_id: item.member_id,
          display_address: item.display_address.trim() || null,
          closeness_level: item.closeness_level,
          service_priority: item.service_priority,
          communication_style: item.communication_style.trim() || null,
          care_notes: parseJsonObject(item.care_notes_json, "成员认知说明"),
          prompt_notes: item.prompt_notes.trim() || null,
        }));
      await api.updateAgentMemberCognitions(householdId, selectedAgentId, {
        items: itemsPayload,
      });
      await loadAgentDetail(selectedAgentId);
      setMessage({ tone: "success", text: "成员认知已保存。" });
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    } finally {
      setSavingCognitions(false);
    }
  }

  return (
    <div className="page-grid">
      {message ? <StatusMessage tone={message.tone} message={message.text} /> : null}

      <PageSection
        title="AI 配置总览"
        description="这里先看家庭下有哪些 Agent、谁是主管家、哪些角色已经启用。"
        actions={
          <button type="button" className="ghost" onClick={() => void refreshAgents()} disabled={!householdId || loading}>
            {loading ? "刷新中..." : "刷新"}
          </button>
        }
      >
        {!householdId ? (
          <p className="muted">请先选择家庭，才能查看当前家庭的 AI 配置。</p>
        ) : items.length === 0 ? (
          <p className="muted">当前家庭还没有 Agent。后续在这里支持创建主管家和专业 Agent。</p>
        ) : (
          <div className="summary-grid">
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`summary-card admin-agent-card${item.id === selectedAgentId ? " admin-agent-card--selected" : ""}`}
                onClick={() => setSelectedAgentId(item.id)}
              >
                <span>{formatAgentType(item.agent_type)}</span>
                <strong>
                  {item.display_name}
                  {item.is_primary ? " · 主管家" : ""}
                </strong>
                <small>{formatAgentStatus(item.status)}</small>
                <small>排序：{item.sort_order}</small>
                <small>{item.summary ?? "还没有人格摘要。"}</small>
              </button>
            ))}
          </div>
        )}
      </PageSection>

      <PageSection
        title="Agent 基础信息"
        description="这一段先看清角色类型、状态和最近更新时间。"
      >
        {!selectedSummary ? (
          <p className="muted">先从上面选择一个 Agent。</p>
        ) : detailLoading ? (
          <p className="muted">正在加载详情...</p>
        ) : !detail ? (
          <p className="muted">还没有加载到详情。</p>
        ) : (
          <div className="summary-grid">
            <div className="summary-card">
              <span>角色类型</span>
              <strong>{formatAgentType(detail.agent_type)}</strong>
              <small>{detail.code}</small>
            </div>
            <div className="summary-card">
              <span>当前状态</span>
              <strong>{formatAgentStatus(detail.status)}</strong>
              <small>{detail.is_primary ? "当前主 Agent" : "普通 Agent"}</small>
            </div>
            <div className="summary-card">
              <span>最近更新</span>
              <strong>{formatDateTime(detail.updated_at)}</strong>
              <small>创建于 {formatDateTime(detail.created_at)}</small>
            </div>
            <div className="summary-card">
              <span>当前对话入口</span>
              <strong>{detail.runtime_policy?.conversation_enabled ? "已启用" : "未启用"}</strong>
              <small>{detail.runtime_policy?.default_entry ? "可作为默认入口" : "不是默认入口"}</small>
            </div>
          </div>
        )}
      </PageSection>

      <PageSection
        title="人格配置"
        description="A7 先把人格配置做成真实可保存表单，别继续停在只读摘要。"
        actions={
          <button type="button" onClick={() => void handleSaveSoul()} disabled={!selectedAgentId || savingSoul}>
            {savingSoul ? "保存中..." : "保存人格"}
          </button>
        }
      >
        <div className="form-grid">
          <label>
            自我认知
            <textarea
              rows={4}
              value={soulForm.self_identity}
              onChange={(event) => setSoulForm((current) => ({ ...current, self_identity: event.target.value }))}
            />
          </label>
          <label>
            角色定位
            <textarea
              rows={4}
              value={soulForm.role_summary}
              onChange={(event) => setSoulForm((current) => ({ ...current, role_summary: event.target.value }))}
            />
          </label>
          <label>
            自我介绍
            <textarea
              rows={4}
              value={soulForm.intro_message}
              onChange={(event) => setSoulForm((current) => ({ ...current, intro_message: event.target.value }))}
            />
          </label>
          <label>
            说话风格
            <textarea
              rows={4}
              value={soulForm.speaking_style}
              onChange={(event) => setSoulForm((current) => ({ ...current, speaking_style: event.target.value }))}
            />
          </label>
          <label>
            性格标签
            <input
              value={soulForm.personality_traits_text}
              onChange={(event) => setSoulForm((current) => ({ ...current, personality_traits_text: event.target.value }))}
              placeholder="例如：温和, 可靠, 简洁"
            />
          </label>
          <label>
            服务重点
            <input
              value={soulForm.service_focus_text}
              onChange={(event) => setSoulForm((current) => ({ ...current, service_focus_text: event.target.value }))}
              placeholder="例如：家庭陪伴, 饮食建议"
            />
          </label>
        </div>
        <label>
          服务边界（JSON）
          <textarea
            rows={8}
            value={soulForm.service_boundaries_json}
            onChange={(event) => setSoulForm((current) => ({ ...current, service_boundaries_json: event.target.value }))}
          />
        </label>
      </PageSection>

      <PageSection
        title="运行时策略"
        description="这里控制该 Agent 是否能出现在对话入口，以及默认入口和路由标签。"
        actions={
          <button type="button" onClick={() => void handleSavePolicy()} disabled={!selectedAgentId || savingPolicy}>
            {savingPolicy ? "保存中..." : "保存策略"}
          </button>
        }
      >
        <div className="form-grid">
          <label>
            <input
              type="checkbox"
              checked={policyForm.conversation_enabled}
              onChange={(event) => setPolicyForm((current) => ({ ...current, conversation_enabled: event.target.checked }))}
            />
            对话入口可见
          </label>
          <label>
            <input
              type="checkbox"
              checked={policyForm.default_entry}
              onChange={(event) => setPolicyForm((current) => ({ ...current, default_entry: event.target.checked }))}
            />
            作为默认入口
          </label>
          <label>
            路由标签
            <input
              value={policyForm.routing_tags_text}
              onChange={(event) => setPolicyForm((current) => ({ ...current, routing_tags_text: event.target.value }))}
              placeholder="例如：家庭综合, 饮食, 运动"
            />
          </label>
        </div>
        <label>
          记忆范围（JSON）
          <textarea
            rows={8}
            value={policyForm.memory_scope_json}
            onChange={(event) => setPolicyForm((current) => ({ ...current, memory_scope_json: event.target.value }))}
          />
        </label>
      </PageSection>

      <PageSection
        title="成员认知配置"
        description="先把成员认知做成可编辑表格，后面再决定要不要拆成单独子页。"
        actions={
          <div className="button-row">
            <button type="button" className="ghost" onClick={addCognitionRow} disabled={!selectedAgentId}>
              新增一行
            </button>
            <button type="button" onClick={() => void handleSaveCognitions()} disabled={!selectedAgentId || savingCognitions}>
              {savingCognitions ? "保存中..." : "保存成员认知"}
            </button>
          </div>
        }
      >
        {!selectedAgentId ? (
          <p className="muted">先选择一个 Agent，再编辑成员认知。</p>
        ) : cognitionForm.length === 0 ? (
          <div className="button-row">
            <p className="muted">当前还没有成员认知配置。</p>
            <button type="button" className="ghost" onClick={addCognitionRow}>新增第一条</button>
          </div>
        ) : (
          <div className="page-grid">
            {cognitionForm.map((item, index) => (
              <div key={`${item.member_id}-${index}`} className="service-card">
                <div className="panel-actions-inline">
                  <strong>成员认知 #{index + 1}</strong>
                  <button type="button" className="ghost" onClick={() => removeCognitionRow(index)}>
                    删除
                  </button>
                </div>
                <div className="form-grid">
                  <label>
                    成员
                    <select
                      value={item.member_id}
                      onChange={(event) => updateCognitionItem(index, { member_id: event.target.value })}
                    >
                      <option value="">请选择成员</option>
                      {memberOptions.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    称呼
                    <input
                      value={item.display_address}
                      onChange={(event) => updateCognitionItem(index, { display_address: event.target.value })}
                    />
                  </label>
                  <label>
                    亲近度
                    <input
                      type="number"
                      min={1}
                      max={5}
                      value={item.closeness_level}
                      onChange={(event) => updateCognitionItem(index, { closeness_level: Number(event.target.value) || 1 })}
                    />
                  </label>
                  <label>
                    服务优先级
                    <input
                      type="number"
                      min={1}
                      max={5}
                      value={item.service_priority}
                      onChange={(event) => updateCognitionItem(index, { service_priority: Number(event.target.value) || 1 })}
                    />
                  </label>
                </div>
                <div className="form-grid">
                  <label>
                    沟通风格
                    <textarea
                      rows={4}
                      value={item.communication_style}
                      onChange={(event) => updateCognitionItem(index, { communication_style: event.target.value })}
                    />
                  </label>
                  <label>
                    Prompt 备注
                    <textarea
                      rows={4}
                      value={item.prompt_notes}
                      onChange={(event) => updateCognitionItem(index, { prompt_notes: event.target.value })}
                    />
                  </label>
                </div>
                <label>
                  关怀说明（JSON）
                  <textarea
                    rows={6}
                    value={item.care_notes_json}
                    onChange={(event) => updateCognitionItem(index, { care_notes_json: event.target.value })}
                  />
                </label>
              </div>
            ))}
          </div>
        )}
      </PageSection>
    </div>
  );
}
