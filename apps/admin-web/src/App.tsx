import { NavLink, Route, Routes } from "react-router-dom";

import { useHousehold } from "./state/household";
import { AuditLogsPage } from "./pages/AuditLogsPage";
import { HouseholdPage } from "./pages/HouseholdPage";
import { MemberPreferencesPermissionsPage } from "./pages/MemberPreferencesPermissionsPage";
import { MemberRelationshipsPage } from "./pages/MemberRelationshipsPage";
import { MembersPage } from "./pages/MembersPage";
import { RoomsDevicesPage } from "./pages/RoomsDevicesPage";

const navItems = [
  { to: "/", label: "家庭管理" },
  { to: "/members", label: "成员管理" },
  { to: "/member-relationships", label: "成员关系" },
  { to: "/member-settings", label: "偏好与权限" },
  { to: "/spaces", label: "房间与设备" },
  { to: "/audit-logs", label: "审计日志" },
];

export default function App() {
  const {
    household,
    households,
    householdsLoading,
    currentHouseholdId,
    refreshHousehold,
    setCurrentHouseholdId,
  } = useHousehold();

  async function handleSwitchHousehold(nextHouseholdId: string) {
    setCurrentHouseholdId(nextHouseholdId);
    await refreshHousehold(nextHouseholdId);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <h1>FamilyClaw</h1>
          <p>家庭底座管理台</p>
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
          <div>
            <h2>管理控制台</h2>
            <p>先围绕家庭、成员、房间、设备与审计做最小可运行闭环。</p>
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
          </div>
        </header>

        <Routes>
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
