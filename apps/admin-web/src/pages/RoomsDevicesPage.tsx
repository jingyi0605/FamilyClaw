import { useEffect, useMemo, useState } from "react";

import { PageSection } from "../components/PageSection";
import { StatusMessage } from "../components/StatusMessage";
import { api } from "../lib/api";
import { formatRoomType, ROOM_TYPE_OPTIONS } from "../lib/roomTypes";
import { useHousehold } from "../state/household";
import type {
  Device,
  HomeAssistantConfig,
  HomeAssistantRoomSyncResponse,
  HomeAssistantSyncResponse,
  Room,
} from "../types";

const defaultRoomForm = {
  name: "",
  room_type: "living_room" as Room["room_type"],
  privacy_level: "public" as Room["privacy_level"],
};

type RoomDraftMap = Record<string, Pick<Room, "name" | "room_type" | "privacy_level">>;
type DeviceDraftMap = Record<string, Pick<Device, "name" | "room_id" | "status" | "controllable">>;

export function RoomsDevicesPage() {
  const { household } = useHousehold();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [haConfig, setHaConfig] = useState<HomeAssistantConfig | null>(null);
  const [haForm, setHaForm] = useState({ base_url: "", access_token: "", sync_rooms_enabled: false, clear_access_token: false });
  const [roomForm, setRoomForm] = useState(defaultRoomForm);
  const [roomDrafts, setRoomDrafts] = useState<RoomDraftMap>({});
  const [deviceDrafts, setDeviceDrafts] = useState<DeviceDraftMap>({});
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [syncSummary, setSyncSummary] = useState<HomeAssistantSyncResponse | null>(null);
  const [roomSyncSummary, setRoomSyncSummary] = useState<HomeAssistantRoomSyncResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const roomOptions = useMemo(
    () => [{ id: "", name: "未分配房间" }, ...rooms.map((room) => ({ id: room.id, name: room.name }))],
    [rooms],
  );

  async function loadData() {
    if (!household?.id) {
      setRooms([]);
      setDevices([]);
      setHaConfig(null);
      return;
    }

    const [configResponse, roomsResponse, devicesResponse] = await Promise.all([
      api.getHomeAssistantConfig(household.id),
      api.listRooms(household.id),
      api.listDevices(household.id),
    ]);

    setHaConfig(configResponse);
    setHaForm({
      base_url: configResponse.base_url ?? "",
      access_token: "",
      sync_rooms_enabled: configResponse.sync_rooms_enabled,
      clear_access_token: false,
    });
    setRooms(roomsResponse.items);
    setDevices(devicesResponse.items);
    setRoomDrafts(
      Object.fromEntries(
        roomsResponse.items.map((room) => [room.id, { name: room.name, room_type: room.room_type, privacy_level: room.privacy_level }]),
      ),
    );
    setDeviceDrafts(
      Object.fromEntries(
        devicesResponse.items.map((device) => [device.id, { name: device.name, room_id: device.room_id, status: device.status, controllable: device.controllable }]),
      ),
    );
  }

  useEffect(() => {
    if (!household?.id) {
      return;
    }

    loadData().catch((loadError) => setError(loadError instanceof Error ? loadError.message : "加载房间设备数据失败"));
  }, [household?.id]);

  async function runAction(action: () => Promise<void>) {
    setLoading(true);
    setStatus("");
    setError("");
    try {
      await action();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "操作失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveHaConfig(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!household?.id) {
      return;
    }

    await runAction(async () => {
      const nextConfig = await api.updateHomeAssistantConfig(household.id, {
        base_url: haForm.base_url.trim() || null,
        access_token: haForm.access_token.trim() || undefined,
        clear_access_token: haForm.clear_access_token,
        sync_rooms_enabled: haForm.sync_rooms_enabled,
      });
      setHaConfig(nextConfig);
      setHaForm((current) => ({
        ...current,
        base_url: nextConfig.base_url ?? "",
        access_token: "",
        clear_access_token: false,
        sync_rooms_enabled: nextConfig.sync_rooms_enabled,
      }));
      setStatus("Home Assistant 配置已保存到当前家庭。");
    });
  }

  async function handleCreateRoom(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!household?.id) {
      return;
    }

    await runAction(async () => {
      await api.createRoom({ household_id: household.id, ...roomForm });
      setRoomForm(defaultRoomForm);
      await loadData();
      setStatus("房间创建成功。");
    });
  }

  async function handleSyncDevices() {
    if (!household?.id) {
      return;
    }

    await runAction(async () => {
      const response = await api.syncHomeAssistant(household.id);
      setSyncSummary(response);
      await loadData();
      setStatus("Home Assistant 设备同步完成。");
    });
  }

  async function handleSyncRooms() {
    if (!household?.id) {
      return;
    }

    await runAction(async () => {
      const response = await api.syncHomeAssistantRooms(household.id);
      setRoomSyncSummary(response);
      await loadData();
      setStatus("Home Assistant 房间同步完成。");
    });
  }

  async function handleSaveRoom(roomId: string) {
    const draft = roomDrafts[roomId];
    if (!draft) {
      return;
    }

    await runAction(async () => {
      await api.updateRoom(roomId, draft);
      await loadData();
      setStatus("房间已更新。");
    });
  }

  async function handleDeleteRoom(roomId: string) {
    await runAction(async () => {
      await api.deleteRoom(roomId);
      await loadData();
      setStatus("房间已删除，关联设备已自动改为未分配。");
    });
  }

  async function handleSaveDevice(deviceId: string) {
    const draft = deviceDrafts[deviceId];
    if (!draft) {
      return;
    }

    await runAction(async () => {
      await api.updateDevice(deviceId, draft);
      await loadData();
      setStatus("设备信息已更新。");
    });
  }

  if (!household?.id) {
    return <StatusMessage tone="info" message="请先在“家庭管理”页面创建或加载当前家庭。" />;
  }

  return (
    <div className="page-grid">
      <PageSection title="HA 对接配置" description="每个家庭单独保存自己的 Home Assistant 地址、Token 和房间同步策略。">
        <form className="form-grid" onSubmit={handleSaveHaConfig}>
          <label>
            Home Assistant 地址
            <input
              value={haForm.base_url}
              onChange={(event) => setHaForm((current) => ({ ...current, base_url: event.target.value }))}
              placeholder="http://homeassistant.local:8123"
            />
          </label>
          <label>
            Long-Lived Token
            <input
              type="password"
              value={haForm.access_token}
              onChange={(event) => setHaForm((current) => ({ ...current, access_token: event.target.value, clear_access_token: false }))}
              placeholder={haConfig?.token_configured ? "已配置，留空表示不改" : "粘贴当前家庭专用 Token"}
            />
          </label>
          <label>
            自动同步房间
            <select
              value={haForm.sync_rooms_enabled ? "true" : "false"}
              onChange={(event) => setHaForm((current) => ({ ...current, sync_rooms_enabled: event.target.value === "true" }))}
            >
              <option value="false">关闭</option>
              <option value="true">开启</option>
            </select>
          </label>
          <label>
            Token 操作
            <select
              value={haForm.clear_access_token ? "clear" : "keep"}
              onChange={(event) => setHaForm((current) => ({ ...current, clear_access_token: event.target.value === "clear", access_token: event.target.value === "clear" ? "" : current.access_token }))}
            >
              <option value="keep">保留现有 Token</option>
              <option value="clear">清空 Token</option>
            </select>
          </label>
          <button type="submit" disabled={loading}>{loading ? "保存中..." : "保存配置"}</button>
        </form>

        <div className="summary-grid" style={{ marginTop: "1rem" }}>
          <div className="summary-card">
            <span>当前家庭</span>
            <strong>{household.name}</strong>
            <small>{household.id}</small>
          </div>
          <div className="summary-card">
            <span>Token 状态</span>
            <strong>{haConfig?.token_configured ? "已配置" : "未配置"}</strong>
            <small>{haConfig?.updated_at ?? "还没有保存过"}</small>
          </div>
          <div className="summary-card">
            <span>最近设备同步</span>
            <strong>{haConfig?.last_device_sync_at ?? "暂无记录"}</strong>
            <small>{haConfig?.sync_rooms_enabled ? "同步设备时会顺带分配房间" : "只同步设备，不自动建房间"}</small>
          </div>
        </div>

        <div className="button-row">
          <button onClick={handleSyncDevices} disabled={loading} type="button">{loading ? "处理中..." : "同步 HA 设备"}</button>
          <button onClick={handleSyncRooms} disabled={loading} type="button">{loading ? "处理中..." : "从 HA 同步房间"}</button>
        </div>

        {syncSummary ? (
          <div className="sync-summary">
            <strong>最近一次设备同步</strong>
            <span>新增设备：{syncSummary.created_devices}</span>
            <span>更新设备：{syncSummary.updated_devices}</span>
            <span>新增房间：{syncSummary.created_rooms}</span>
            <span>分配房间：{syncSummary.assigned_rooms}</span>
            <span>失败实体：{syncSummary.failed_entities}</span>
          </div>
        ) : null}

        {roomSyncSummary ? (
          <div className="sync-summary">
            <strong>最近一次房间同步</strong>
            <span>新增房间：{roomSyncSummary.created_rooms}</span>
            <span>匹配实体：{roomSyncSummary.matched_entities}</span>
            <span>跳过实体：{roomSyncSummary.skipped_entities}</span>
          </div>
        ) : null}

        {status ? <StatusMessage tone="success" message={status} /> : null}
        {error ? <StatusMessage tone="error" message={error} /> : null}
      </PageSection>

      <PageSection title="房间管理" description="支持手动建房间，也支持把 HA 里识别到的房间补进来。">
        <form className="form-grid" onSubmit={handleCreateRoom}>
          <label>
            房间名称
            <input value={roomForm.name} onChange={(event) => setRoomForm((current) => ({ ...current, name: event.target.value }))} required />
          </label>
          <label>
            房间类型
            <select value={roomForm.room_type} onChange={(event) => setRoomForm((current) => ({ ...current, room_type: event.target.value as Room["room_type"] }))}>
              {ROOM_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
          <label>
            隐私等级
            <select value={roomForm.privacy_level} onChange={(event) => setRoomForm((current) => ({ ...current, privacy_level: event.target.value as Room["privacy_level"] }))}>
              <option value="public">public</option>
              <option value="private">private</option>
              <option value="sensitive">sensitive</option>
            </select>
          </label>
          <button type="submit" disabled={loading}>{loading ? "提交中..." : "创建房间"}</button>
        </form>

        <div className="table-wrap" style={{ marginTop: "1rem" }}>
          <table>
            <thead>
              <tr>
                <th>房间名称</th>
                <th>类型</th>
                <th>隐私等级</th>
                <th>当前设备数</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {rooms.map((room) => {
                const draft = roomDrafts[room.id];
                return (
                  <tr key={room.id}>
                    <td>
                      <input
                        value={draft?.name ?? room.name}
                        onChange={(event) => setRoomDrafts((current) => ({ ...current, [room.id]: { ...(current[room.id] ?? room), name: event.target.value } }))}
                      />
                    </td>
                    <td>
                      <select
                        value={draft?.room_type ?? room.room_type}
                        onChange={(event) => setRoomDrafts((current) => ({ ...current, [room.id]: { ...(current[room.id] ?? room), room_type: event.target.value as Room["room_type"] } }))}
                      >
                        {ROOM_TYPE_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <select
                        value={draft?.privacy_level ?? room.privacy_level}
                        onChange={(event) => setRoomDrafts((current) => ({ ...current, [room.id]: { ...(current[room.id] ?? room), privacy_level: event.target.value as Room["privacy_level"] } }))}
                      >
                        <option value="public">public</option>
                        <option value="private">private</option>
                        <option value="sensitive">sensitive</option>
                      </select>
                    </td>
                    <td>{devices.filter((device) => device.room_id === room.id).length}</td>
                    <td>
                      <div className="table-actions">
                        <button type="button" onClick={() => void handleSaveRoom(room.id)} disabled={loading}>保存</button>
                        <button type="button" onClick={() => void handleDeleteRoom(room.id)} disabled={loading}>删除</button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="chip-list">
          {rooms.map((room) => (
            <span key={room.id} className="chip">
              {room.name} · {formatRoomType(room.room_type)} · {room.privacy_level}
            </span>
          ))}
        </div>
      </PageSection>

      <PageSection title="设备管理" description="支持查看真实 HA 设备，同步后可改名称、状态和房间归属。">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>设备名称</th>
                <th>类型</th>
                <th>厂商</th>
                <th>状态</th>
                <th>当前房间</th>
                <th>可控</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {devices.map((device) => {
                const draft = deviceDrafts[device.id];
                return (
                  <tr key={device.id}>
                    <td>
                      <input
                        value={draft?.name ?? device.name}
                        onChange={(event) => setDeviceDrafts((current) => ({ ...current, [device.id]: { ...(current[device.id] ?? device), name: event.target.value } }))}
                      />
                    </td>
                    <td>{device.device_type}</td>
                    <td>{device.vendor}</td>
                    <td>
                      <select
                        value={draft?.status ?? device.status}
                        onChange={(event) => setDeviceDrafts((current) => ({ ...current, [device.id]: { ...(current[device.id] ?? device), status: event.target.value as Device["status"] } }))}
                      >
                        <option value="active">active</option>
                        <option value="offline">offline</option>
                        <option value="inactive">inactive</option>
                      </select>
                    </td>
                    <td>
                      <select
                        value={draft?.room_id ?? ""}
                        onChange={(event) => setDeviceDrafts((current) => ({ ...current, [device.id]: { ...(current[device.id] ?? device), room_id: event.target.value || null } }))}
                      >
                        {roomOptions.map((option) => (
                          <option key={option.id || "unassigned"} value={option.id}>{option.name}</option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <select
                        value={(draft?.controllable ?? device.controllable) ? "true" : "false"}
                        onChange={(event) => setDeviceDrafts((current) => ({ ...current, [device.id]: { ...(current[device.id] ?? device), controllable: event.target.value === "true" } }))}
                      >
                        <option value="true">是</option>
                        <option value="false">否</option>
                      </select>
                    </td>
                    <td>
                      <button type="button" onClick={() => void handleSaveDevice(device.id)} disabled={loading}>保存</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </PageSection>
    </div>
  );
}
