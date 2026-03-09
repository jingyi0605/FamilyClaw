import { useEffect, useState } from "react";

import { PageSection } from "../components/PageSection";
import { StatusMessage } from "../components/StatusMessage";
import { api } from "../lib/api";
import { useHousehold } from "../state/household";
import type { AuditLog } from "../types";

function formatDetails(details: string | null) {
  if (!details) {
    return "-";
  }

  try {
    return JSON.stringify(JSON.parse(details), null, 2);
  } catch {
    return details;
  }
}

export function AuditLogsPage() {
  const { household } = useHousehold();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadLogs() {
      if (!household?.id) {
        setLogs([]);
        return;
      }

      const response = await api.listAuditLogs(household.id);
      setLogs(response.items);
    }

    loadLogs().catch((err) => setError(err instanceof Error ? err.message : "加载审计日志失败"));
  }, [household?.id]);

  if (!household?.id) {
    return <StatusMessage tone="info" message="请先在“家庭管理”页面创建或加载当前家庭。" />;
  }

  return (
    <PageSection title="审计日志" description="展示当前家庭最近的关键操作。">
      {error ? <StatusMessage tone="error" message={error} /> : null}
      <div className="audit-list">
        {logs.map((log) => (
          <article key={log.id} className="audit-item">
            <div className="audit-item-top">
              <strong>{log.action}</strong>
              <span className={`audit-result ${log.result}`}>{log.result}</span>
            </div>
            <div className="audit-meta">
              <span>target: {log.target_type}</span>
              <span>actor: {log.actor_type}</span>
              <span>time: {log.created_at}</span>
            </div>
            <pre>{formatDetails(log.details)}</pre>
          </article>
        ))}
      </div>
    </PageSection>
  );
}

