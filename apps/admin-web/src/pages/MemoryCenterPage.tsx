import { useEffect, useMemo, useState } from "react";

import { PageSection } from "../components/PageSection";
import { StatusMessage } from "../components/StatusMessage";
import { api } from "../lib/api";
import { useHousehold } from "../state/household";
import type {
  MemoryCard,
  MemoryCardRevision,
  MemoryDebugOverviewRead,
  MemoryEventRecord,
  Member,
  Room,
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
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function stringifyJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

export function MemoryCenterPage() {
  const { household } = useHousehold();
  const householdId = household?.id ?? "";

  const [overview, setOverview] = useState<MemoryDebugOverviewRead | null>(null);
  const [events, setEvents] = useState<MemoryEventRecord[]>([]);
  const [cards, setCards] = useState<MemoryCard[]>([]);
  const [revisions, setRevisions] = useState<MemoryCardRevision[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [selectedCardId, setSelectedCardId] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ tone: "info" | "success" | "error"; text: string } | null>(null);

  const [eventTypeFilter, setEventTypeFilter] = useState("");
  const [cardTypeFilter, setCardTypeFilter] = useState("");

  const [eventForm, setEventForm] = useState({
    event_type: "member_fact_observed",
    source_type: "admin",
    source_ref: "admin-web-debug",
    subject_member_id: "",
    room_id: "",
    dedupe_key: "",
    generate_memory_card: true,
    payload_json: stringifyJson({
      memory_type: "fact",
      title: "奶奶的饮食偏好",
      summary: "奶奶喜欢清淡饮食，不吃辣",
      visibility: "family",
      importance: 4,
      confidence: 0.92,
      content: {
        preference_type: "diet",
        likes: ["清淡"],
        dislikes: ["辛辣"],
      },
      related_members: [],
    }),
  });

  const [cardForm, setCardForm] = useState({
    memory_type: "fact" as MemoryCard["memory_type"],
    title: "",
    summary: "",
    visibility: "family" as MemoryCard["visibility"],
    status: "active" as MemoryCard["status"],
    importance: 3,
    confidence: 0.85,
    subject_member_id: "",
    source_event_id: "",
    dedupe_key: "",
    related_members_text: "",
    content_json: stringifyJson({}),
    reason: "管理员调试创建",
  });

  const [correctionForm, setCorrectionForm] = useState({
    action: "correct" as "correct" | "invalidate" | "delete",
    title: "",
    summary: "",
    visibility: "",
    status: "",
    importance: "",
    confidence: "",
    content_json: "",
    reason: "管理员调试修订",
  });

  async function loadRevisions(memoryId: string) {
    if (!memoryId) {
      setRevisions([]);
      return;
    }
    try {
      const response = await api.listMemoryCardRevisions(memoryId);
      setRevisions(response.items);
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    }
  }

  async function refreshAll() {
    if (!householdId) {
      setOverview(null);
      setEvents([]);
      setCards([]);
      setRevisions([]);
      return;
    }
    setLoading(true);
    try {
      const [overviewResponse, eventResponse, cardResponse, memberResponse, roomResponse] = await Promise.all([
        api.getMemoryDebugOverview(householdId),
        api.listMemoryEvents(householdId),
        api.listMemoryCards(householdId),
        api.listMembers(householdId),
        api.listRooms(householdId),
      ]);
      setOverview(overviewResponse);
      setEvents(eventResponse.items);
      setCards(cardResponse.items);
      setMembers(memberResponse.items);
      setRooms(roomResponse.items);

      const nextSelectedCardId =
        cardResponse.items.find((item) => item.id === selectedCardId)?.id ?? cardResponse.items[0]?.id ?? "";
      setSelectedCardId(nextSelectedCardId);
      if (nextSelectedCardId) {
        const revisionResponse = await api.listMemoryCardRevisions(nextSelectedCardId);
        setRevisions(revisionResponse.items);
      } else {
        setRevisions([]);
      }
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshAll();
  }, [householdId]);

  useEffect(() => {
    if (!selectedCardId) {
      setRevisions([]);
      return;
    }
    void loadRevisions(selectedCardId);
  }, [selectedCardId]);

  async function handleIngestEvent() {
    if (!householdId) {
      setMessage({ tone: "error", text: "请先选择家庭。" });
      return;
    }
    try {
      const parsedPayload = JSON.parse(eventForm.payload_json || "{}") as Record<string, unknown>;
      const result = await api.ingestMemoryEvent({
        household_id: householdId,
        event_type: eventForm.event_type,
        source_type: eventForm.source_type,
        source_ref: eventForm.source_ref || null,
        subject_member_id: eventForm.subject_member_id || null,
        room_id: eventForm.room_id || null,
        dedupe_key: eventForm.dedupe_key || null,
        generate_memory_card: eventForm.generate_memory_card,
        payload: parsedPayload,
      });
      setMessage({
        tone: "success",
        text: result.duplicate_detected
          ? `事件命中幂等键，复用记录 ${result.event_id}。`
          : `事件已写入，处理状态：${result.processing_status}。`,
      });
      await refreshAll();
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    }
  }

  async function handleCreateCard() {
    if (!householdId) {
      setMessage({ tone: "error", text: "请先选择家庭。" });
      return;
    }
    try {
      const parsedContent = JSON.parse(cardForm.content_json || "{}") as Record<string, unknown>;
      const relatedMembers = cardForm.related_members_text
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
          const [memberId, relationRole = "participant"] = line.split(":").map((item) => item.trim());
          return {
            member_id: memberId,
            relation_role: relationRole as "subject" | "participant" | "mentioned" | "owner",
          };
        });
      await api.createManualMemoryCard({
        household_id: householdId,
        memory_type: cardForm.memory_type,
        title: cardForm.title,
        summary: cardForm.summary,
        content: parsedContent,
        visibility: cardForm.visibility,
        status: cardForm.status,
        importance: Number(cardForm.importance),
        confidence: Number(cardForm.confidence),
        subject_member_id: cardForm.subject_member_id || null,
        source_event_id: cardForm.source_event_id || null,
        dedupe_key: cardForm.dedupe_key || null,
        related_members: relatedMembers,
        reason: cardForm.reason || null,
      });
      setMessage({ tone: "success", text: "手动记忆卡已创建。" });
      await refreshAll();
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    }
  }

  async function handleCorrectCard() {
    if (!selectedCardId) {
      setMessage({ tone: "error", text: "请先选择一张记忆卡。" });
      return;
    }
    try {
      const payload: {
        action: "correct" | "invalidate" | "delete";
        title?: string | null;
        summary?: string | null;
        content?: Record<string, unknown> | null;
        visibility?: MemoryCard["visibility"] | null;
        status?: MemoryCard["status"] | null;
        importance?: number | null;
        confidence?: number | null;
        reason?: string | null;
      } = {
        action: correctionForm.action,
        reason: correctionForm.reason || null,
      };

      if (correctionForm.title.trim()) {
        payload.title = correctionForm.title.trim();
      }
      if (correctionForm.summary.trim()) {
        payload.summary = correctionForm.summary.trim();
      }
      if (correctionForm.visibility) {
        payload.visibility = correctionForm.visibility as MemoryCard["visibility"];
      }
      if (correctionForm.status) {
        payload.status = correctionForm.status as MemoryCard["status"];
      }
      if (correctionForm.importance.trim()) {
        payload.importance = Number(correctionForm.importance);
      }
      if (correctionForm.confidence.trim()) {
        payload.confidence = Number(correctionForm.confidence);
      }
      if (correctionForm.content_json.trim()) {
        payload.content = JSON.parse(correctionForm.content_json) as Record<string, unknown>;
      }

      await api.correctMemoryCard(selectedCardId, payload);
      setMessage({ tone: "success", text: "记忆卡修订已写入。" });
      await refreshAll();
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    }
  }

  const filteredEvents = useMemo(
    () => events.filter((item) => (eventTypeFilter ? item.event_type.includes(eventTypeFilter) : true)),
    [events, eventTypeFilter],
  );
  const filteredCards = useMemo(
    () => cards.filter((item) => (cardTypeFilter ? item.memory_type === cardTypeFilter : true)),
    [cards, cardTypeFilter],
  );
  const selectedCard = cards.find((item) => item.id === selectedCardId) ?? null;

  return (
    <div className="page-grid">
      {message ? <StatusMessage tone={message.tone} message={message.text} /> : null}

      <PageSection
        title="记忆中心总览"
        description="先看事件流水有没有被处理，再看记忆卡有没有稳定长出来。"
        actions={
          <button type="button" className="ghost" onClick={() => void refreshAll()} disabled={loading}>
            {loading ? "刷新中..." : "刷新数据"}
          </button>
        }
      >
        <div className="summary-grid">
          <div className="summary-card">
            <span>事件总数</span>
            <strong>{overview?.total_events ?? 0}</strong>
            <small>待处理 {overview?.pending_events ?? 0} / 已处理 {overview?.processed_events ?? 0}</small>
          </div>
          <div className="summary-card">
            <span>记忆卡总数</span>
            <strong>{overview?.total_cards ?? 0}</strong>
            <small>有效 {overview?.active_cards ?? 0} / 待审 {overview?.pending_cards ?? 0}</small>
          </div>
          <div className="summary-card">
            <span>最近事件</span>
            <strong>{formatDateTime(overview?.latest_event_at)}</strong>
            <small>失败 {overview?.failed_events ?? 0} / 忽略 {overview?.ignored_events ?? 0}</small>
          </div>
          <div className="summary-card">
            <span>最近记忆卡</span>
            <strong>{formatDateTime(overview?.latest_card_at)}</strong>
            <small>失效 {overview?.invalidated_cards ?? 0} / 删除 {overview?.deleted_cards ?? 0}</small>
          </div>
        </div>
        <div className="inline-note">
          现在已经不是只有“事件落库”了。支持的事件会自动提炼成记忆卡；如果命中同一 `dedupe_key`，系统会更新旧卡并写 revision，而不是无脑新增重复卡。
        </div>
      </PageSection>

      <PageSection
        title="事件写回调试"
        description="这里直接对接 `POST /api/v1/memories/events`。推荐用结构化 payload 验证自动提炼。"
      >
        <div className="json-grid">
          <div className="service-card">
            <label>
              事件类型
              <input
                value={eventForm.event_type}
                onChange={(event) => setEventForm((current) => ({ ...current, event_type: event.target.value }))}
              />
            </label>
            <label>
              来源类型
              <input
                value={eventForm.source_type}
                onChange={(event) => setEventForm((current) => ({ ...current, source_type: event.target.value }))}
              />
            </label>
            <label>
              来源引用
              <input
                value={eventForm.source_ref}
                onChange={(event) => setEventForm((current) => ({ ...current, source_ref: event.target.value }))}
              />
            </label>
            <label>
              关联成员
              <select
                value={eventForm.subject_member_id}
                onChange={(event) => setEventForm((current) => ({ ...current, subject_member_id: event.target.value }))}
              >
                <option value="">不关联成员</option>
                {members.map((member) => (
                  <option key={member.id} value={member.id}>
                    {member.name} · {member.role}
                  </option>
                ))}
              </select>
            </label>
            <label>
              关联房间
              <select
                value={eventForm.room_id}
                onChange={(event) => setEventForm((current) => ({ ...current, room_id: event.target.value }))}
              >
                <option value="">不关联房间</option>
                {rooms.map((room) => (
                  <option key={room.id} value={room.id}>
                    {room.name} · {room.room_type}
                  </option>
                ))}
              </select>
            </label>
            <label>
              幂等键
              <input
                value={eventForm.dedupe_key}
                onChange={(event) => setEventForm((current) => ({ ...current, dedupe_key: event.target.value }))}
                placeholder="同一个事件重复发送时复用"
              />
            </label>
            <label className="inline-form compact">
              <span>尝试生成记忆卡</span>
              <input
                type="checkbox"
                checked={eventForm.generate_memory_card}
                onChange={(event) =>
                  setEventForm((current) => ({ ...current, generate_memory_card: event.target.checked }))
                }
              />
            </label>
            <div className="button-row">
              <button type="button" onClick={() => void handleIngestEvent()}>
                写入事件
              </button>
            </div>
          </div>

          <div className="service-card json-field">
            <label>
              事件负载 JSON
              <textarea
                rows={16}
                value={eventForm.payload_json}
                onChange={(event) => setEventForm((current) => ({ ...current, payload_json: event.target.value }))}
              />
            </label>
          </div>
        </div>
      </PageSection>

      <PageSection
        title="手动记忆卡调试"
        description="自动提炼之外，你也可以直接创建一张长期记忆卡，用来验证表结构和关联关系。"
      >
        <div className="json-grid">
          <div className="service-card">
            <label>
              记忆类型
              <select
                value={cardForm.memory_type}
                onChange={(event) =>
                  setCardForm((current) => ({ ...current, memory_type: event.target.value as MemoryCard["memory_type"] }))
                }
              >
                <option value="fact">事实</option>
                <option value="event">事件</option>
                <option value="preference">偏好</option>
                <option value="relation">关系</option>
                <option value="growth">成长</option>
              </select>
            </label>
            <label>
              标题
              <input
                value={cardForm.title}
                onChange={(event) => setCardForm((current) => ({ ...current, title: event.target.value }))}
              />
            </label>
            <label>
              摘要
              <textarea
                rows={5}
                value={cardForm.summary}
                onChange={(event) => setCardForm((current) => ({ ...current, summary: event.target.value }))}
              />
            </label>
            <label>
              可见性
              <select
                value={cardForm.visibility}
                onChange={(event) =>
                  setCardForm((current) => ({ ...current, visibility: event.target.value as MemoryCard["visibility"] }))
                }
              >
                <option value="public">公开</option>
                <option value="family">家庭</option>
                <option value="private">私密</option>
                <option value="sensitive">敏感</option>
              </select>
            </label>
            <label>
              状态
              <select
                value={cardForm.status}
                onChange={(event) =>
                  setCardForm((current) => ({ ...current, status: event.target.value as MemoryCard["status"] }))
                }
              >
                <option value="active">有效</option>
                <option value="pending_review">待审</option>
                <option value="invalidated">失效</option>
                <option value="deleted">删除</option>
              </select>
            </label>
            <label>
              主体成员
              <select
                value={cardForm.subject_member_id}
                onChange={(event) => setCardForm((current) => ({ ...current, subject_member_id: event.target.value }))}
              >
                <option value="">不关联主体成员</option>
                {members.map((member) => (
                  <option key={member.id} value={member.id}>
                    {member.name} · {member.role}
                  </option>
                ))}
              </select>
            </label>
            <label>
              来源事件 ID
              <input
                value={cardForm.source_event_id}
                onChange={(event) => setCardForm((current) => ({ ...current, source_event_id: event.target.value }))}
              />
            </label>
            <label>
              幂等键
              <input
                value={cardForm.dedupe_key}
                onChange={(event) => setCardForm((current) => ({ ...current, dedupe_key: event.target.value }))}
              />
            </label>
            <label>
              重要度
              <input
                type="number"
                min={1}
                max={5}
                value={cardForm.importance}
                onChange={(event) => setCardForm((current) => ({ ...current, importance: Number(event.target.value) }))}
              />
            </label>
            <label>
              置信度
              <input
                type="number"
                min={0}
                max={1}
                step={0.01}
                value={cardForm.confidence}
                onChange={(event) => setCardForm((current) => ({ ...current, confidence: Number(event.target.value) }))}
              />
            </label>
            <div className="button-row">
              <button type="button" onClick={() => void handleCreateCard()}>
                创建记忆卡
              </button>
            </div>
          </div>

          <div className="service-card json-field">
            <label>
              内容 JSON
              <textarea
                rows={10}
                value={cardForm.content_json}
                onChange={(event) => setCardForm((current) => ({ ...current, content_json: event.target.value }))}
              />
            </label>
            <label>
              关联成员
              <textarea
                rows={5}
                value={cardForm.related_members_text}
                onChange={(event) =>
                  setCardForm((current) => ({ ...current, related_members_text: event.target.value }))
                }
                placeholder={"每行一个，格式：member_id:participant"}
              />
            </label>
            <label>
              原因
              <input
                value={cardForm.reason}
                onChange={(event) => setCardForm((current) => ({ ...current, reason: event.target.value }))}
              />
            </label>
          </div>
        </div>
      </PageSection>

      <PageSection
        title="记忆卡修订调试"
        description="这里对接 correction 接口，用来验证更正、失效、删除和 revision 历史。"
      >
        <div className="json-grid">
          <div className="service-card">
            <label>
              选择记忆卡
              <select value={selectedCardId} onChange={(event) => setSelectedCardId(event.target.value)}>
                <option value="">请选择</option>
                {cards.map((card) => (
                  <option key={card.id} value={card.id}>
                    {card.title} · {card.memory_type} · {card.status}
                  </option>
                ))}
              </select>
            </label>
            <label>
              操作
              <select
                value={correctionForm.action}
                onChange={(event) =>
                  setCorrectionForm((current) => ({
                    ...current,
                    action: event.target.value as "correct" | "invalidate" | "delete",
                  }))
                }
              >
                <option value="correct">更正</option>
                <option value="invalidate">失效</option>
                <option value="delete">删除</option>
              </select>
            </label>
            <label>
              新标题
              <input
                value={correctionForm.title}
                onChange={(event) => setCorrectionForm((current) => ({ ...current, title: event.target.value }))}
                placeholder={selectedCard?.title ?? "留空表示不改"}
              />
            </label>
            <label>
              新摘要
              <textarea
                rows={4}
                value={correctionForm.summary}
                onChange={(event) => setCorrectionForm((current) => ({ ...current, summary: event.target.value }))}
                placeholder={selectedCard?.summary ?? "留空表示不改"}
              />
            </label>
            <label>
              可见性
              <select
                value={correctionForm.visibility}
                onChange={(event) => setCorrectionForm((current) => ({ ...current, visibility: event.target.value }))}
              >
                <option value="">不修改</option>
                <option value="public">公开</option>
                <option value="family">家庭</option>
                <option value="private">私密</option>
                <option value="sensitive">敏感</option>
              </select>
            </label>
            <label>
              状态
              <select
                value={correctionForm.status}
                onChange={(event) => setCorrectionForm((current) => ({ ...current, status: event.target.value }))}
              >
                <option value="">不修改</option>
                <option value="active">有效</option>
                <option value="pending_review">待审</option>
                <option value="invalidated">失效</option>
                <option value="deleted">删除</option>
              </select>
            </label>
            <label>
              重要度
              <input
                value={correctionForm.importance}
                onChange={(event) => setCorrectionForm((current) => ({ ...current, importance: event.target.value }))}
                placeholder={selectedCard ? String(selectedCard.importance) : "留空表示不改"}
              />
            </label>
            <label>
              置信度
              <input
                value={correctionForm.confidence}
                onChange={(event) => setCorrectionForm((current) => ({ ...current, confidence: event.target.value }))}
                placeholder={selectedCard ? String(selectedCard.confidence) : "留空表示不改"}
              />
            </label>
            <label>
              原因
              <input
                value={correctionForm.reason}
                onChange={(event) => setCorrectionForm((current) => ({ ...current, reason: event.target.value }))}
              />
            </label>
            <div className="button-row">
              <button type="button" onClick={() => void handleCorrectCard()}>
                提交修订
              </button>
            </div>
          </div>

          <div className="service-card json-field">
            <label>
              新内容 JSON
              <textarea
                rows={10}
                value={correctionForm.content_json}
                onChange={(event) =>
                  setCorrectionForm((current) => ({ ...current, content_json: event.target.value }))
                }
                placeholder={selectedCard ? stringifyJson(selectedCard.content) : "留空表示不改"}
              />
            </label>
            <h4>当前选中记忆卡</h4>
            {selectedCard ? (
              <pre>{stringifyJson(selectedCard)}</pre>
            ) : (
              <p className="muted">还没有选中记忆卡。</p>
            )}
          </div>
        </div>
      </PageSection>

      <PageSection
        title="最近事件流水"
        description="主要看自动提炼结果：是 processed、ignored，还是 failed。"
      >
        <div className="inline-form compact">
          <label>
            事件类型筛选
            <input value={eventTypeFilter} onChange={(event) => setEventTypeFilter(event.target.value)} />
          </label>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>类型</th>
                <th>来源</th>
                <th>成员/房间</th>
                <th>处理状态</th>
                <th>详情</th>
              </tr>
            </thead>
            <tbody>
              {filteredEvents.map((item) => (
                <tr key={item.id}>
                  <td>{formatDateTime(item.occurred_at)}</td>
                  <td>{item.event_type}</td>
                  <td>
                    {item.source_type}
                    <br />
                    <small>{item.source_ref ?? "—"}</small>
                  </td>
                  <td>
                    <div>成员：{item.subject_member_id ?? "—"}</div>
                    <div>房间：{item.room_id ?? "—"}</div>
                  </td>
                  <td>
                    {item.processing_status}
                    {item.failure_reason ? <div className="muted">{item.failure_reason}</div> : null}
                  </td>
                  <td>
                    <pre>{stringifyJson(item.payload)}</pre>
                  </td>
                </tr>
              ))}
              {filteredEvents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="muted">
                    还没有事件流水。
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </PageSection>

      <PageSection
        title="记忆卡与修订历史"
        description="上面看当前值，这里看它是不是被正确修订过。"
      >
        <div className="inline-form compact">
          <label>
            记忆类型筛选
            <select value={cardTypeFilter} onChange={(event) => setCardTypeFilter(event.target.value)}>
              <option value="">全部</option>
              <option value="fact">事实</option>
              <option value="event">事件</option>
              <option value="preference">偏好</option>
              <option value="relation">关系</option>
              <option value="growth">成长</option>
            </select>
          </label>
        </div>
        <div className="json-grid">
          <div className="service-card">
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>标题</th>
                    <th>类型/状态</th>
                    <th>主体成员</th>
                    <th>可见性</th>
                    <th>更新时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredCards.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <strong>{item.title}</strong>
                        <div className="muted">{item.summary}</div>
                      </td>
                      <td>
                        {item.memory_type}
                        <br />
                        <small>{item.status}</small>
                      </td>
                      <td>{item.subject_member_id ?? "—"}</td>
                      <td>
                        {item.visibility}
                        <br />
                        <small>重要度 {item.importance} / {Math.round(item.confidence * 100)}%</small>
                      </td>
                      <td>{formatDateTime(item.updated_at)}</td>
                      <td>
                        <button type="button" className="ghost" onClick={() => setSelectedCardId(item.id)}>
                          查看修订
                        </button>
                      </td>
                    </tr>
                  ))}
                  {filteredCards.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="muted">
                        还没有记忆卡。
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>

          <div className="service-card">
            <h4>Revision 历史</h4>
            {revisions.length > 0 ? (
              <div className="audit-list compact">
                {revisions.map((item) => (
                  <article key={item.id} className="audit-item">
                    <div className="audit-item-top">
                      <strong>v{item.revision_no} · {item.action}</strong>
                      <span>{formatDateTime(item.created_at)}</span>
                    </div>
                    <div className="audit-meta">
                      <span>{item.actor_type}</span>
                      <span>{item.actor_id ?? "system"}</span>
                      <span>{item.reason ?? "无说明"}</span>
                    </div>
                    <pre>{stringifyJson({ before: item.before_json, after: item.after_json })}</pre>
                  </article>
                ))}
              </div>
            ) : (
              <p className="muted">当前选中记忆卡还没有 revision，或者你还没选中任何记忆卡。</p>
            )}
          </div>
        </div>
      </PageSection>
    </div>
  );
}
