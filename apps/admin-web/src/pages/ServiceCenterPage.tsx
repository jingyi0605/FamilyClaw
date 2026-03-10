import { useEffect, useMemo, useState } from "react";

import { PageSection } from "../components/PageSection";
import { StatusMessage } from "../components/StatusMessage";
import { ServiceHero } from "../components/service/ServiceHero";
import { api, ApiError } from "../lib/api";
import { useHousehold } from "../state/household";
import type {
  AiCallLog,
  AiCapabilityRoute,
  AiProviderProfile,
  FamilyQaQueryResponse,
  FamilyQaSuggestionItem,
  ReminderOverviewRead,
  SceneExecution,
  SceneExecutionDetailRead,
  ScenePreviewResponse,
  SceneTemplate,
  SceneTemplatePresetItem,
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

export function ServiceCenterPage() {
  const { household } = useHousehold();
  const householdId = household?.id ?? "";

  const [suggestions, setSuggestions] = useState<FamilyQaSuggestionItem[]>([]);
  const [question, setQuestion] = useState("");
  const [qaResult, setQaResult] = useState<FamilyQaQueryResponse | null>(null);
  const [qaLoading, setQaLoading] = useState(false);

  const [reminderOverview, setReminderOverview] = useState<ReminderOverviewRead | null>(null);
  const [sceneTemplates, setSceneTemplates] = useState<SceneTemplate[]>([]);
  const [sceneExecutions, setSceneExecutions] = useState<SceneExecution[]>([]);
  const [scenePreview, setScenePreview] = useState<ScenePreviewResponse | null>(null);
  const [sceneExecutionDetail, setSceneExecutionDetail] = useState<SceneExecutionDetailRead | null>(null);
  const [templatePresets, setTemplatePresets] = useState<SceneTemplatePresetItem[]>([]);
  const [aiProviders, setAiProviders] = useState<AiProviderProfile[]>([]);
  const [aiRoutes, setAiRoutes] = useState<AiCapabilityRoute[]>([]);
  const [aiCallLogs, setAiCallLogs] = useState<AiCallLog[]>([]);
  const [message, setMessage] = useState<{ tone: "info" | "success" | "error"; text: string } | null>(null);

  async function refreshAll() {
    if (!householdId) {
      return;
    }
    const [
      suggestionResponse,
      reminderResponse,
      templateResponse,
      executionResponse,
      presetResponse,
      providerResponse,
      routeResponse,
      callLogResponse,
    ] = await Promise.all([
      api.listFamilyQaSuggestions(householdId),
      api.getReminderOverview(householdId),
      api.listSceneTemplates(householdId),
      api.listSceneExecutions(householdId),
      api.listSceneTemplatePresets(householdId),
      api.listAiProviders(),
      api.listAiRoutes(householdId),
      api.listAiCallLogs(householdId),
    ]);
    setSuggestions(suggestionResponse.items);
    setReminderOverview(reminderResponse);
    setSceneTemplates(templateResponse);
    setSceneExecutions(executionResponse);
    setTemplatePresets(presetResponse);
    setAiProviders(providerResponse);
    setAiRoutes(routeResponse);
    setAiCallLogs(callLogResponse);
  }

  useEffect(() => {
    refreshAll().catch((error) => {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    });
  }, [householdId]);

  const latestScene = sceneExecutions[0] ?? null;
  const latestAiRoute = aiRoutes[0] ?? null;
  const latestAiLog = aiCallLogs[0] ?? null;
  const serviceHealth = useMemo(() => {
    if (!householdId) {
      return "未选择家庭";
    }
    if (latestScene?.status === "blocked" || latestScene?.status === "failed") {
      return "需要处理";
    }
    if (latestAiLog?.status === "fallback_success") {
      return "已降级";
    }
    return "正常";
  }, [householdId, latestScene, latestAiLog]);

  async function handleAskQuestion(nextQuestion?: string) {
    if (!householdId) {
      setMessage({ tone: "error", text: "请先选择家庭。" });
      return;
    }
    const finalQuestion = (nextQuestion ?? question).trim();
    if (!finalQuestion) {
      setMessage({ tone: "error", text: "先输入一个问题。" });
      return;
    }
    setQaLoading(true);
    setMessage(null);
    try {
      const result = await api.queryFamilyQa({
        household_id: householdId,
        question: finalQuestion,
        channel: "admin_web",
      });
      setQaResult(result);
      setQuestion(finalQuestion);
      await refreshAll();
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    } finally {
      setQaLoading(false);
    }
  }

  async function handleRegisterPreset(preset: SceneTemplatePresetItem) {
    try {
      await api.upsertSceneTemplate(preset.template_code, {
        ...preset.payload,
        updated_by: "service-center",
      });
      setMessage({ tone: "success", text: `已注册模板：${preset.name}` });
      await refreshAll();
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    }
  }

  async function handlePreviewTemplate(templateCode: string) {
    if (!householdId) {
      return;
    }
    try {
      const result = await api.previewSceneTemplate(templateCode, {
        household_id: householdId,
        trigger_source: "manual",
      });
      setScenePreview(result);
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    }
  }

  async function handleTriggerTemplate(templateCode: string) {
    if (!householdId) {
      return;
    }
    try {
      const result = await api.triggerSceneTemplate(templateCode, {
        household_id: householdId,
        trigger_source: "manual",
        updated_by: "service-center",
      });
      setSceneExecutionDetail(result);
      setMessage({ tone: "success", text: `场景 ${templateCode} 已手动触发。` });
      await refreshAll();
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    }
  }

  async function handleTriggerReminder(reminderId: string) {
    try {
      await api.triggerReminder(reminderId);
      setMessage({ tone: "success", text: "提醒已手动触发。" });
      await refreshAll();
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    }
  }

  async function handleDispatchScheduler() {
    if (!householdId) {
      return;
    }
    try {
      const result = await api.dispatchReminderScheduler(householdId);
      setMessage({
        tone: "success",
        text: `调度完成：新建 ${result.created_runs.length} 个运行，升级 ${result.escalated_runs.length} 个运行。`,
      });
      await refreshAll();
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    }
  }

  async function handleAckLatestRun() {
    const latestItem = reminderOverview?.items.find((item) => item.latest_run_status);
    if (!latestItem || !sceneExecutions) {
      return;
    }
    try {
      const runs = await api.dispatchReminderScheduler(householdId);
      const targetRun = runs.created_runs[0] ?? runs.escalated_runs[0];
      if (!targetRun) {
        throw new ApiError(400, "当前没有可确认的提醒运行。", null);
      }
      await api.acknowledgeReminderRun(targetRun.id, {
        run_id: targetRun.id,
        action: "done",
        note: "服务中心手动确认",
      });
      setMessage({ tone: "success", text: "提醒已确认完成。" });
      await refreshAll();
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    }
  }

  return (
    <div className="page-grid">
      {message ? <StatusMessage tone={message.tone} message={message.text} /> : null}

      <PageSection
        title="服务总览"
        description="先看全局状态，别一上来就盯某个按钮。"
      >
        <ServiceHero
          serviceHealth={serviceHealth}
          pendingReminders={reminderOverview?.pending_runs ?? 0}
          latestSceneStatus={latestScene?.status ?? "暂无"}
          qaStatus={suggestions.length > 0 ? "可用" : "待补数据"}
        />
      </PageSection>

      <PageSection
        title="问答工作台"
        description="先问高频问题，再看证据和 AI 降级情况。"
        actions={
          <button type="button" className="ghost" onClick={() => refreshAll().catch(() => undefined)}>
            刷新建议
          </button>
        }
      >
        <div className="service-grid">
          <div className="service-card">
            <label>
              问题
              <textarea
                value={question}
                rows={3}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="例如：爷爷今天吃药了吗？"
              />
            </label>
            <div className="button-row">
              <button type="button" onClick={() => handleAskQuestion()} disabled={qaLoading}>
                {qaLoading ? "正在查询..." : "提交问题"}
              </button>
            </div>
            <div className="chip-list">
              {suggestions.map((item) => (
                <button key={item.question} type="button" className="ghost chip" onClick={() => handleAskQuestion(item.question)}>
                  {item.question}
                </button>
              ))}
            </div>
          </div>
          <div className="service-card">
            <h4>回答结果</h4>
            {qaResult ? (
              <>
                <p>{qaResult.answer}</p>
                <p className="muted">
                  类型：{qaResult.answer_type} · 置信度：{Math.round(qaResult.confidence * 100)}% · AI：
                  {qaResult.ai_provider_code ?? "未使用"}
                  {qaResult.ai_degraded ? "（已降级）" : ""}
                </p>
                <ul className="fact-list">
                  {qaResult.facts.map((fact) => (
                    <li key={`${fact.type}-${fact.label}`}>{fact.label} · {fact.source}</li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="muted">还没有问答结果。</p>
            )}
          </div>
        </div>
      </PageSection>

      <PageSection
        title="提醒与广播"
        description="这里看任务、今日待确认、手动触发和调度。"
        actions={
          <div className="button-row">
            <button type="button" className="ghost" onClick={() => handleDispatchScheduler()}>
              跑一次调度
            </button>
            <button type="button" className="ghost" onClick={() => handleAckLatestRun()}>
              确认一条提醒
            </button>
          </div>
        }
      >
        <div className="summary-grid">
          <ServiceHero
            serviceHealth="提醒面板"
            pendingReminders={reminderOverview?.pending_runs ?? 0}
            latestSceneStatus={String(reminderOverview?.enabled_tasks ?? 0)}
            qaStatus={`${reminderOverview?.ack_required_tasks ?? 0} 条需确认`}
          />
        </div>
        <div className="table-shell">
          <table>
            <thead>
              <tr>
                <th>标题</th>
                <th>类型</th>
                <th>下次触发</th>
                <th>最近状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {(reminderOverview?.items ?? []).map((item) => (
                <tr key={item.task_id}>
                  <td>{item.title}</td>
                  <td>{item.reminder_type}</td>
                  <td>{formatDateTime(item.next_trigger_at)}</td>
                  <td>{item.latest_run_status ?? "暂无"}</td>
                  <td>
                    <button type="button" className="ghost" onClick={() => handleTriggerReminder(item.task_id)}>
                      手动触发
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </PageSection>

      <PageSection
        title="场景编排"
        description="先注册模板，再预览，再手动触发。"
      >
        <div className="service-grid">
          <div className="service-card">
            <h4>内置模板</h4>
            <div className="stack-list">
              {templatePresets.map((preset) => (
                <article key={preset.template_code} className="stack-item">
                  <strong>{preset.name}</strong>
                  <p>{preset.description}</p>
                  <div className="button-row">
                    <button type="button" className="ghost" onClick={() => handleRegisterPreset(preset)}>
                      注册模板
                    </button>
                    <button type="button" className="ghost" onClick={() => handlePreviewTemplate(preset.template_code)}>
                      预览
                    </button>
                    <button type="button" onClick={() => handleTriggerTemplate(preset.template_code)}>
                      手动触发
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </div>
          <div className="service-card">
            <h4>预览结果</h4>
            {scenePreview ? (
              <>
                <p>{scenePreview.explanation ?? "暂无解释"}</p>
                <p className="muted">触发键：{scenePreview.trigger_key}</p>
                <ul className="fact-list">
                  {scenePreview.steps.map((step) => (
                    <li key={`${step.step_index}-${step.target_ref ?? "none"}`}>
                      {step.step_index + 1}. {step.step_type} · {step.summary}
                    </li>
                  ))}
                </ul>
                {scenePreview.blocked_guards.length > 0 ? (
                  <p className="muted">阻断原因：{scenePreview.blocked_guards.join("；")}</p>
                ) : null}
              </>
            ) : (
              <p className="muted">还没有预览结果。</p>
            )}
          </div>
        </div>
        <div className="table-shell">
          <table>
            <thead>
              <tr>
                <th>模板</th>
                <th>状态</th>
                <th>最近执行</th>
              </tr>
            </thead>
            <tbody>
              {sceneTemplates.map((template) => {
                const latest = sceneExecutions.find((item) => item.template_id === template.id);
                return (
                  <tr key={template.id}>
                    <td>{template.name}</td>
                    <td>{template.enabled ? "已启用" : "已停用"}</td>
                    <td>{latest ? `${latest.status} · ${formatDateTime(latest.started_at)}` : "暂无"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {sceneExecutionDetail ? (
          <div className="service-card">
            <h4>最近一次手动执行</h4>
            <p>状态：{sceneExecutionDetail.execution.status}</p>
            <ul className="fact-list">
              {sceneExecutionDetail.steps.map((step) => (
                <li key={step.id}>
                  {step.step_index + 1}. {step.step_type} · {step.status}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </PageSection>

      <PageSection
        title="AI 路由摘要"
        description="首期不做完整治理台，但至少要让人看出现在走谁、有没有降级。"
      >
        <div className="service-grid">
          <div className="service-card">
            <h4>当前路由</h4>
            {latestAiRoute ? (
              <ul className="fact-list">
                <li>能力：{latestAiRoute.capability}</li>
                <li>路由模式：{latestAiRoute.routing_mode}</li>
                <li>允许远端：{latestAiRoute.allow_remote ? "是" : "否"}</li>
              </ul>
            ) : (
              <p className="muted">当前家庭还没有单独的 AI 路由。</p>
            )}
          </div>
          <div className="service-card">
            <h4>供应商与最近调用</h4>
            <p>供应商数量：{aiProviders.length}</p>
            <p>最近调用：{latestAiLog ? `${latestAiLog.provider_code} · ${latestAiLog.status}` : "暂无"}</p>
            <p className="muted">最近调用时间：{formatDateTime(latestAiLog?.created_at)}</p>
          </div>
        </div>
      </PageSection>
    </div>
  );
}
