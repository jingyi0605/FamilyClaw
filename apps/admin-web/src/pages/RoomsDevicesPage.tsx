import { useEffect, useMemo, useState } from "react";

import { PageSection } from "../components/PageSection";
import { StatusMessage } from "../components/StatusMessage";
import { api } from "../lib/api";
import { formatRoomType, ROOM_TYPE_OPTIONS } from "../lib/roomTypes";
import { useHousehold } from "../state/household";
import type { Device, HomeAssistantSyncResponse, Room } from "../types";

const defaultRoomForm = {
  name: "",
  room_type: "living_room" as Room["room_type"],
  privacy_level: "public" as Room["privacy_level"],
};

export function RoomsDevicesPage() {
  const { household } = useHousehold();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [roomForm, setRoomForm] = useState(defaultRoomForm);
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [syncSummary, setSyncSummary] = useState<HomeAssistantSyncResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const roomOptions = useMemo(
    () => [{ id: "", name: "未分配房间" }, ...rooms.map((room) => ({ id: room.id, name: room.name }))],
    [rooms],
  );

  async function loadData() {
    if (!household?.id) {
      setRooms([]);
      setDevices([]);
      return;
    }

    const [roomsResponse, devicesResponse] = await Promise.all([
      api.listRooms(household.id),
      api.listDevices(household.id),
    ]);
    setRooms(roomsResponse.items);
    setDevices(devicesResponse.items);
  }

  useEffect(() => {
    loadData().catch((err) => setError(err instanceof Error ? err.message : "加载空间数据失败"));
  }, [household?.id]);

  async function handleCreateRoom(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!household?.id) {
      setError("请先创建或加载家庭。");
      return;
    }

    setLoading(true);
    setStatus("");
    setError("");
    try {
      await api.createRoom({ household_id: household.id, ...roomForm });
      setRoomForm(defaultRoomForm);
      await loadData();
      setStatus("房间创建成功。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建房间失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleSync() {
    if (!household?.id) {
      setError("请先创建或加载家庭。");
      return;
    }

    setLoading(true);
    setStatus("");
    setError("");
    try {
      const response = await api.syncHomeAssistant(household.id);
      setSyncSummary(response);
      await loadData();
      setStatus("Home Assistant 设备同步完成。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "同步设备失败");
    } finally {
      setLoading(false);
    }
  }

  async function assignDeviceRoom(deviceId: string, roomId: string) {
    setLoading(true);
    setStatus("");
    setError("");
    try {
      await api.updateDevice(deviceId, { room_id: roomId || null });
      await loadData();
      setStatus("设备归属更新成功。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新设备归属失败");
    } finally {
      setLoading(false);
    }
  }

  if (!household?.id) {
    return <StatusMessage tone="info" message="请先在“家庭管理”页面创建或加载当前家庭。" />;
  }

  return (
    <div className="page-grid">
      <PageSection title="房间管理" description="支持创建与查询房间。">
        <form className="form-grid" onSubmit={handleCreateRoom}>
          <label>
            房间名称
            <input
              value={roomForm.name}
              onChange={(event) =>
                setRoomForm((current) => ({ ...current, name: event.target.value }))
              }
              required
            />
          </label>
          <label>
            房间类型
            <select
              value={roomForm.room_type}
              onChange={(event) =>
                setRoomForm((current) => ({
                  ...current,
                  room_type: event.target.value as Room["room_type"],
                }))
              }
            >
              {ROOM_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            隐私等级
            <select
              value={roomForm.privacy_level}
              onChange={(event) =>
                setRoomForm((current) => ({
                  ...current,
                  privacy_level: event.target.value as Room["privacy_level"],
                }))
              }
            >
              <option value="public">public</option>
              <option value="private">private</option>
              <option value="sensitive">sensitive</option>
            </select>
          </label>
          <button type="submit" disabled={loading}>
            {loading ? "提交中..." : "创建房间"}
          </button>
        </form>
        <div className="chip-list">
          {rooms.map((room) => (
            <span key={room.id} className="chip">
              {room.name} · {formatRoomType(room.room_type)} · {room.privacy_level}
            </span>
          ))}
        </div>
      </PageSection>

      <PageSection
        title="设备管理"
        description="可查看设备、触发 HA 同步，并调整房间归属。"
        actions={
          <button onClick={handleSync} disabled={loading}>
            {loading ? "同步中..." : "手动同步 HA 设备"}
          </button>
        }
      >
        {status ? <StatusMessage tone="success" message={status} /> : null}
        {error ? <StatusMessage tone="error" message={error} /> : null}
        {syncSummary ? (
          <div className="sync-summary">
            <strong>最近一次同步</strong>
            <span>创建设备：{syncSummary.created_devices}</span>
            <span>更新设备：{syncSummary.updated_devices}</span>
            <span>跳过实体：{syncSummary.skipped_entities}</span>
            <span>失败实体：{syncSummary.failed_entities}</span>
          </div>
        ) : null}

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>设备名称</th>
                <th>类型</th>
                <th>厂商</th>
                <th>状态</th>
                <th>当前房间</th>
                <th>调整归属</th>
              </tr>
            </thead>
            <tbody>
              {devices.map((device) => (
                <tr key={device.id}>
                  <td>{device.name}</td>
                  <td>{device.device_type}</td>
                  <td>{device.vendor}</td>
                  <td>{device.status}</td>
                  <td>{rooms.find((room) => room.id === device.room_id)?.name ?? "未分配"}</td>
                  <td>
                    <select
                      value={device.room_id ?? ""}
                      onChange={(event) => assignDeviceRoom(device.id, event.target.value)}
                      disabled={loading}
                    >
                      {roomOptions.map((option) => (
                        <option key={option.id || "unassigned"} value={option.id}>
                          {option.name}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </PageSection>
    </div>
  );
}

