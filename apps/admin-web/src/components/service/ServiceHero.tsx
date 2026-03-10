import { ServiceSummaryCard } from "./ServiceSummaryCard";

type ServiceHeroProps = {
  serviceHealth: string;
  pendingReminders: number;
  latestSceneStatus: string;
  qaStatus: string;
};

export function ServiceHero({
  serviceHealth,
  pendingReminders,
  latestSceneStatus,
  qaStatus,
}: ServiceHeroProps) {
  return (
    <div className="summary-grid">
      <ServiceSummaryCard
        title="服务健康度"
        value={serviceHealth}
        note="综合问答、提醒、场景和 AI 路由摘要。"
      />
      <ServiceSummaryCard
        title="待确认提醒"
        value={String(pendingReminders)}
        note="来自提醒总览接口。"
      />
      <ServiceSummaryCard
        title="最近场景执行"
        value={latestSceneStatus}
        note="优先看有没有 blocked 或 partial。"
      />
      <ServiceSummaryCard
        title="问答可用状态"
        value={qaStatus}
        note="看当前是否有建议问题和 AI 降级。"
      />
    </div>
  );
}
