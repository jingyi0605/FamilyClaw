import { useMemo, useState } from "react";

import { PageSection } from "../components/PageSection";
import { StatusMessage } from "../components/StatusMessage";
import { api } from "../lib/api";
import { useHousehold } from "../state/household";

export function HouseholdPage() {
  const {
    household,
    households,
    currentHouseholdId,
    refreshHousehold,
    refreshHouseholds,
    setCurrentHouseholdId,
  } = useHousehold();
  const [createForm, setCreateForm] = useState({
    name: "[模拟数据] 管理台新家庭",
    timezone: "Asia/Shanghai",
    locale: "zh-CN",
  });
  const [lookupId, setLookupId] = useState(currentHouseholdId);
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(false);

  const summaryItems = useMemo(
    () => [
      { label: "家庭名称", value: household?.name ?? "-" },
      { label: "时区", value: household?.timezone ?? "-" },
      { label: "语言区域", value: household?.locale ?? "-" },
      { label: "状态", value: household?.status ?? "-" },
      { label: "家庭 ID", value: household?.id ?? "-" },
    ],
    [household],
  );

  async function handleCreateHousehold(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setStatus("");

    try {
      const nextHousehold = await api.createHousehold(createForm);
      setCurrentHouseholdId(nextHousehold.id);
      await refreshHouseholds();
      await refreshHousehold(nextHousehold.id);
      setLookupId(nextHousehold.id);
      setStatus("家庭创建成功，已自动设为当前家庭。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建家庭失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleLookupHousehold(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setStatus("");

    try {
      setCurrentHouseholdId(lookupId);
      await refreshHousehold(lookupId);
      setStatus("家庭详情加载成功。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载家庭失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-grid">
      <PageSection
        title="创建家庭"
        description="对接 `POST /api/v1/households`，创建后自动切换到当前家庭。"
      >
        <form className="form-grid" onSubmit={handleCreateHousehold}>
          <label>
            家庭名称
            <input
              value={createForm.name}
              onChange={(event) =>
                setCreateForm((current) => ({ ...current, name: event.target.value }))
              }
              required
            />
          </label>
          <label>
            时区
            <input
              value={createForm.timezone}
              onChange={(event) =>
                setCreateForm((current) => ({ ...current, timezone: event.target.value }))
              }
              required
            />
          </label>
          <label>
            语言区域
            <input
              value={createForm.locale}
              onChange={(event) =>
                setCreateForm((current) => ({ ...current, locale: event.target.value }))
              }
              required
            />
          </label>
          <button type="submit" disabled={loading}>
            {loading ? "提交中..." : "创建家庭"}
          </button>
        </form>
      </PageSection>

      <PageSection
        title="家庭列表与切换"
        description="对接 `GET /api/v1/households`，可查看现有家庭并切换当前上下文。"
      >
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>家庭名称</th>
                <th>时区</th>
                <th>语言区域</th>
                <th>状态</th>
                <th>家庭 ID</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {households.map((item) => (
                <tr key={item.id}>
                  <td>{item.name}</td>
                  <td>{item.timezone}</td>
                  <td>{item.locale}</td>
                  <td>{item.status}</td>
                  <td>{item.id}</td>
                  <td>
                    <button
                      className={item.id === currentHouseholdId ? "ghost" : ""}
                      disabled={loading}
                      onClick={() => {
                        setLookupId(item.id);
                        void handleLookupById(item.id);
                      }}
                    >
                      {item.id === currentHouseholdId ? "当前家庭" : "切换到此家庭"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </PageSection>

      <PageSection
        title="按 ID 加载家庭详情"
        description="保留按 household_id 直查，方便联调时快速定位目标家庭。"
      >
        <form className="inline-form" onSubmit={handleLookupHousehold}>
          <input
            placeholder="输入 household_id"
            value={lookupId}
            onChange={(event) => setLookupId(event.target.value)}
          />
          <button type="submit" disabled={loading || !lookupId}>
            加载详情
          </button>
        </form>
        {status ? <StatusMessage tone="success" message={status} /> : null}
        {error ? <StatusMessage tone="error" message={error} /> : null}
      </PageSection>

      <PageSection title="当前家庭详情" description="对接 `GET /api/v1/households/{id}`。">
        <div className="summary-grid">
          {summaryItems.map((item) => (
            <div key={item.label} className="summary-card">
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
      </PageSection>
    </div>
  );

  async function handleLookupById(householdId: string) {
    setLoading(true);
    setError("");
    setStatus("");

    try {
      setCurrentHouseholdId(householdId);
      await refreshHousehold(householdId);
      setStatus("已切换到目标家庭。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载家庭失败");
    } finally {
      setLoading(false);
    }
  }
}
