import { useEffect, useMemo, useState } from "react";

import { PageSection } from "../components/PageSection";
import { StatusMessage } from "../components/StatusMessage";
import { api } from "../lib/api";
import { useHousehold } from "../state/household";
import type { AgentDetail, AgentSummary } from "../types";

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

export function AiConfigPage() {
  const { household } = useHousehold();
  const householdId = household?.id ?? "";

  const [items, setItems] = useState<AgentSummary[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [message, setMessage] = useState<{ tone: "info" | "success" | "error"; text: string } | null>(null);

  const selectedSummary = useMemo(
    () => items.find((item) => item.id === selectedAgentId) ?? null,
    [items, selectedAgentId],
  );

  async function refreshAgents() {
    if (!householdId) {
      setItems([]);
      setSelectedAgentId("");
      setDetail(null);
      return;
    }
    setLoading(true);
    try {
      const response = await api.listAgents(householdId);
      setItems(response.items);
      const nextSelectedId = response.items.find((item) => item.id === selectedAgentId)?.id ?? response.items[0]?.id ?? "";
      setSelectedAgentId(nextSelectedId);
      if (!response.items.length) {
        setDetail(null);
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
      return;
    }
    setDetailLoading(true);
    try {
      const response = await api.getAgentDetail(householdId, agentId);
      setDetail(response);
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
      return;
    }
    void loadAgentDetail(selectedAgentId);
  }, [householdId, selectedAgentId]);

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
        title="Agent 详情"
        description="A6 先做到可查看详情，A7 再把这里补成真正可编辑的配置页。"
      >
        {!selectedSummary ? (
          <p className="muted">先从上面选择一个 Agent。</p>
        ) : detailLoading ? (
          <p className="muted">正在加载详情...</p>
        ) : !detail ? (
          <p className="muted">还没有加载到详情。</p>
        ) : (
          <div className="page-grid">
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
                <span>对话入口</span>
                <strong>{detail.runtime_policy?.conversation_enabled ? "已启用" : "未启用"}</strong>
                <small>{detail.runtime_policy?.default_entry ? "可作为默认入口" : "不是默认入口"}</small>
              </div>
            </div>

            <div className="service-grid">
              <div className="service-card">
                <h4>人格摘要</h4>
                {detail.soul ? (
                  <>
                    <p><strong>角色定位：</strong>{detail.soul.role_summary}</p>
                    <p><strong>自我认知：</strong>{detail.soul.self_identity}</p>
                    <p><strong>说话风格：</strong>{detail.soul.speaking_style ?? "未配置"}</p>
                    <div className="chip-list">
                      {detail.soul.personality_traits.map((item) => (
                        <span key={item} className="chip">{item}</span>
                      ))}
                      {!detail.soul.personality_traits.length ? <span className="muted">暂无性格标签</span> : null}
                    </div>
                  </>
                ) : (
                  <p className="muted">当前还没有激活中的人格配置。</p>
                )}
              </div>

              <div className="service-card">
                <h4>运行时策略</h4>
                <p><strong>对话可见：</strong>{detail.runtime_policy?.conversation_enabled ? "是" : "否"}</p>
                <p><strong>默认入口：</strong>{detail.runtime_policy?.default_entry ? "是" : "否"}</p>
                <div className="chip-list">
                  {(detail.runtime_policy?.routing_tags ?? []).map((item) => (
                    <span key={item} className="chip">{item}</span>
                  ))}
                  {!(detail.runtime_policy?.routing_tags ?? []).length ? <span className="muted">暂无路由标签</span> : null}
                </div>
              </div>
            </div>

            <div className="table-shell">
              <table>
                <thead>
                  <tr>
                    <th>成员 ID</th>
                    <th>称呼</th>
                    <th>亲近度</th>
                    <th>服务优先级</th>
                    <th>沟通风格</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.member_cognitions.length ? (
                    detail.member_cognitions.map((item) => (
                      <tr key={item.id}>
                        <td>{item.member_id}</td>
                        <td>{item.display_address ?? "未配置"}</td>
                        <td>{item.closeness_level}</td>
                        <td>{item.service_priority}</td>
                        <td>{item.communication_style ?? "未配置"}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5} className="muted">当前还没有成员认知配置。</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </PageSection>
    </div>
  );
}
