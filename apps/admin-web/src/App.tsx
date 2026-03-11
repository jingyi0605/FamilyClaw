import { NavLink, Route, Routes, useLocation } from "react-router-dom";

import { LoginPage } from "./pages/LoginPage";
import { useAuth } from "./state/auth";
import { HouseholdProvider } from "./state/household";
import { AiConfigPage } from "./pages/AiConfigPage";
import { AuditLogsPage } from "./pages/AuditLogsPage";
import { AiProviderConfigPage } from "./pages/AiProviderConfigPage";
import { ContextCenterPage } from "./pages/ContextCenterPage";
import { HouseholdPage } from "./pages/HouseholdPage";
import { MemoryCenterPage } from "./pages/MemoryCenterPage";
import { MemberPreferencesPermissionsPage } from "./pages/MemberPreferencesPermissionsPage";
import { MemberRelationshipsPage } from "./pages/MemberRelationshipsPage";
import { MembersPage } from "./pages/MembersPage";
import { RoomsDevicesPage } from "./pages/RoomsDevicesPage";
import { ServiceCenterPage } from "./pages/ServiceCenterPage";
import { useHousehold } from "./state/household";

type NavItem = {
  to: string;
  label: string;
  title: string;
  description: string;
};

const navItems: NavItem[] = [
  {
    to: "/ai-config",
    label: "AI 配置",
    title: "多 Agent AI 配置",
    description: "查看家庭下的主管家和专业 Agent，先把角色、状态和人格摘要理清。 ",
  },
  {
    to: "/ai-provider-config",
    label: "模型供应商",
    title: "AI 模型供应商配置",
    description: "手动配置供应商、能力路由和预览调用，方便完整测试。",
  },
  {
    to: "/context-center",
    label: "家庭总览",
    title: "家居上下文中心",
    description: "查看家庭状态、成员状态、设备热区与上下文配置。",
  },
  {
    to: "/",
    label: "家庭管理",
    title: "家庭底座管理",
    description: "维护家庭主数据、时区、语言和最基础的家庭信息。",
  },
  {
    to: "/members",
    label: "成员管理",
    title: "成员中心",
    description: "管理成员资料、角色和启停状态。",
  },
  {
    to: "/member-relationships",
    label: "成员关系",
    title: "关系图谱",
    description: "维护家庭成员关系、监护链路和可见范围。",
  },
  {
    to: "/member-settings",
    label: "偏好与权限",
    title: "成员偏好与权限",
    description: "配置成员偏好、访问规则和执行边界。",
  },
  {
    to: "/spaces",
    label: "房间与设备",
    title: "房间与设备管理",
    description: "维护房间主数据、设备归属和 HA 同步结果。",
  },
  {
    to: "/memory-center",
    label: "记忆中心",
    title: "家庭长期记忆中心",
    description: "查看事件流水、手动写入记忆卡，并验证长期记忆底层骨架。",
  },
  {
    to: "/service-center",
    label: "服务中心",
    title: "家庭服务中心",
    description: "统一查看问答、提醒、场景和 AI 路由摘要。",
  },
  {
    to: "/audit-logs",
    label: "审计日志",
    title: "审计与追踪",
    description: "查看关键写操作、同步动作和失败记录。",
  },
];

function matchNavItem(pathname: string, item: NavItem) {
  if (item.to === "/") {
    return pathname === "/";
  }

  return pathname.startsWith(item.to);
}

function AppShell() {
  const location = useLocation();
  const { actor, logout } = useAuth();
  const {
    household,
    households,
    householdsLoading,
    currentHouseholdId,
    refreshHousehold,
    setCurrentHouseholdId,
  } = useHousehold();

  const currentNavItem =
    navItems.find((item) => matchNavItem(location.pathname, item)) ?? navItems[0];

  async function handleSwitchHousehold(nextHouseholdId: string) {
    setCurrentHouseholdId(nextHouseholdId);
    await refreshHousehold(nextHouseholdId);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <h1>FamilyClaw</h1>
          <p>家庭 AI 中枢管理台</p>
        </div>
        <div className="sidebar-note">
          <strong>当前阶段重点</strong>
          <p>先把家庭主数据、家居接入和上下文中心做成闭环，别急着堆花哨功能。</p>
        </div>
        <nav className="nav">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="content">
        <header className="topbar">
          <div className="topbar-copy">
            <span className="topbar-kicker">FamilyClaw Console</span>
            <h2>{currentNavItem.title}</h2>
            <p>{currentNavItem.description}</p>
            <div className="topbar-auth-meta">
              <span>当前账号：{actor?.username ?? "未登录"}</span>
              <span>身份：{actor?.role ?? "unknown"}</span>
            </div>
          </div>
          <div className="household-badge">
            <span>当前家庭</span>
            <strong>{household?.name ?? "未选择"}</strong>
            <small>{household?.id ?? "请先创建或加载家庭"}</small>
            <div className="household-switcher">
              <select
                value={currentHouseholdId}
                onChange={(event) => {
                  void handleSwitchHousehold(event.target.value);
                }}
                disabled={householdsLoading || households.length === 0}
              >
                <option value="">请选择家庭</option>
                {households.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </div>
            <button className="ghost logout-button" type="button" onClick={() => void logout()}>
              退出登录
            </button>
          </div>
        </header>

        <Routes>
          <Route path="/ai-config" element={<AiConfigPage />} />
          <Route path="/ai-provider-config" element={<AiProviderConfigPage />} />
          <Route path="/context-center" element={<ContextCenterPage />} />
          <Route path="/memory-center" element={<MemoryCenterPage />} />
          <Route path="/service-center" element={<ServiceCenterPage />} />
          <Route path="/" element={<HouseholdPage />} />
          <Route path="/members" element={<MembersPage />} />
          <Route path="/member-relationships" element={<MemberRelationshipsPage />} />
          <Route path="/member-settings" element={<MemberPreferencesPermissionsPage />} />
          <Route path="/spaces" element={<RoomsDevicesPage />} />
          <Route path="/audit-logs" element={<AuditLogsPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  const { actor, authLoading } = useAuth();

  if (authLoading) {
    return <div className="auth-loading">正在校验登录状态...</div>;
  }

  if (!actor || !actor.authenticated) {
    return <LoginPage />;
  }

  return (
    <HouseholdProvider>
      <AppShell />
    </HouseholdProvider>
  );
}
