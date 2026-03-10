/* ============================================================
 * 家庭页 - 包含概览/房间/成员/关系四个子路由
 * ============================================================ */
import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useI18n } from '../i18n';
import { PageHeader, Card, Section } from '../components/base';
import { useHouseholdContext } from '../state/household';
import { api } from '../lib/api';
import type {
  ContextOverviewRead,
  Device,
  Household,
  Member,
  MemberPreference,
  MemberRelationship,
  Room,
} from '../lib/types';

/* ---- 家庭子导航 ---- */
const familyTabs = [
  { to: '/family', labelKey: 'family.overview' as const, end: true },
  { to: '/family/rooms', labelKey: 'family.rooms' as const },
  { to: '/family/members', labelKey: 'family.members' as const },
  { to: '/family/relationships', labelKey: 'family.relationships' as const },
];

const noopRefreshWorkspace = async () => {};

type FamilyWorkspaceValue = {
  household: Household | null;
  overview: ContextOverviewRead | null;
  rooms: Room[];
  members: Member[];
  devices: Device[];
  relationships: MemberRelationship[];
  preferencesByMemberId: Record<string, MemberPreference>;
  loading: boolean;
  errors: string[];
  refreshWorkspace: () => Promise<void>;
};

const FamilyWorkspaceContext = createContext<FamilyWorkspaceValue | null>(null);

function formatLocale(locale: string | null | undefined) {
  switch (locale) {
    case 'zh-CN': return '中文';
    case 'en-US': return 'English';
    default: return locale ?? '-';
  }
}

function formatHomeMode(mode: ContextOverviewRead['home_mode'] | undefined) {
  switch (mode) {
    case 'home': return '居家模式';
    case 'away': return '离家模式';
    case 'night': return '夜间模式';
    case 'sleep': return '睡眠模式';
    case 'custom': return '自定义模式';
    default: return '-';
  }
}

function formatPrivacyMode(mode: ContextOverviewRead['privacy_mode'] | undefined) {
  switch (mode) {
    case 'balanced': return '平衡保护';
    case 'strict': return '严格保护';
    case 'care': return '关怀优先';
    default: return '-';
  }
}

function formatRoomType(roomType: Room['room_type']) {
  switch (roomType) {
    case 'living_room': return '客厅';
    case 'bedroom': return '卧室';
    case 'study': return '书房';
    case 'entrance': return '玄关';
  }
}

function formatRole(role: Member['role']) {
  switch (role) {
    case 'admin': return '管理员';
    case 'adult': return '成人';
    case 'child': return '儿童';
    case 'elder': return '长辈';
    case 'guest': return '访客';
  }
}

function getMemberStatus(memberId: string, overview: ContextOverviewRead | null) {
  const state = overview?.member_states.find(item => item.member_id === memberId);
  if (!state || state.presence === 'away') {
    return 'away' as const;
  }
  if (state.activity === 'resting' || state.activity === 'sleeping') {
    return 'resting' as const;
  }
  return 'home' as const;
}

function formatPreferenceSummary(preference: MemberPreference | undefined) {
  if (!preference) {
    return '还没有成员偏好数据';
  }

  const parts: string[] = [];
  if (preference.preferred_name) parts.push(`称呼：${preference.preferred_name}`);
  if (preference.climate_preference) parts.push('已设置温度偏好');
  if (preference.light_preference) parts.push('已设置灯光偏好');
  if (preference.reminder_channel_preference) parts.push('已设置提醒方式');
  if (preference.sleep_schedule) parts.push('已设置作息');

  return parts.length > 0 ? parts.join(' · ') : '还没有成员偏好数据';
}

function formatRelationType(type: MemberRelationship['relation_type']) {
  switch (type) {
    case 'caregiver': return '照护关系';
    case 'guardian': return '监护关系';
    case 'parent': return '父母关系';
    case 'child': return '子女关系';
    case 'spouse': return '伴侣关系';
  }
}

function formatVisibilityScope(scope: MemberRelationship['visibility_scope']) {
  switch (scope) {
    case 'public': return '公开';
    case 'family': return '家庭内可见';
    case 'private': return '私密';
  }
}

function formatDelegationScope(scope: MemberRelationship['delegation_scope']) {
  switch (scope) {
    case 'none': return '不开放代办';
    case 'reminder': return '可代办提醒';
    case 'health': return '可代办健康事项';
    case 'device': return '可代办设备事项';
  }
}

function useFamilyWorkspace() {
  const context = useContext(FamilyWorkspaceContext);
  if (!context) {
    throw new Error('useFamilyWorkspace 必须在 FamilyLayout 内使用');
  }
  return context;
}

export function FamilyLayout() {
  const { t } = useI18n();
  const { currentHouseholdId } = useHouseholdContext();
  const [workspace, setWorkspace] = useState<FamilyWorkspaceValue>({
    household: null,
    overview: null,
    rooms: [],
    members: [],
    devices: [],
    relationships: [],
    preferencesByMemberId: {},
    loading: false,
    errors: [],
    refreshWorkspace: noopRefreshWorkspace,
  });

  const refreshWorkspace = useMemo(() => async () => {
    if (!currentHouseholdId) {
      setWorkspace(current => ({
        ...current,
        household: null,
        overview: null,
        rooms: [],
        members: [],
        devices: [],
        relationships: [],
        preferencesByMemberId: {},
        loading: false,
        errors: [],
      }));
      return;
    }

    setWorkspace(current => ({ ...current, loading: true, errors: [] }));

    const [householdResult, overviewResult, roomsResult, membersResult, devicesResult, relationshipsResult] = await Promise.allSettled([
      api.getHousehold(currentHouseholdId),
      api.getContextOverview(currentHouseholdId),
      api.listRooms(currentHouseholdId),
      api.listMembers(currentHouseholdId),
      api.listDevices(currentHouseholdId),
      api.listMemberRelationships(currentHouseholdId),
    ]);

    const members = membersResult.status === 'fulfilled' ? membersResult.value.items : [];
    const preferenceResults = await Promise.allSettled(members.map(member => api.getMemberPreferences(member.id)));
    const preferencesByMemberId = preferenceResults.reduce<Record<string, MemberPreference>>((acc, result) => {
      if (result.status === 'fulfilled') {
        acc[result.value.member_id] = result.value;
      }
      return acc;
    }, {});

    const errors = [householdResult, overviewResult, roomsResult, membersResult, devicesResult, relationshipsResult]
      .filter(result => result.status === 'rejected')
      .map(result => result.reason instanceof Error ? result.reason.message : '家庭数据加载失败');

    preferenceResults.forEach(result => {
      if (result.status === 'rejected') {
        errors.push(result.reason instanceof Error ? result.reason.message : '成员偏好加载失败');
      }
    });

    setWorkspace(current => ({
      ...current,
      household: householdResult.status === 'fulfilled' ? householdResult.value : null,
      overview: overviewResult.status === 'fulfilled' ? overviewResult.value : null,
      rooms: roomsResult.status === 'fulfilled' ? roomsResult.value.items : [],
      members,
      devices: devicesResult.status === 'fulfilled' ? devicesResult.value.items : [],
      relationships: relationshipsResult.status === 'fulfilled' ? relationshipsResult.value.items : [],
      preferencesByMemberId,
      loading: false,
      errors,
    }));
  }, [currentHouseholdId]);

  useEffect(() => {
    void refreshWorkspace();
  }, [refreshWorkspace]);

  const value = useMemo(() => ({ ...workspace, refreshWorkspace }), [workspace, refreshWorkspace]);

  return (
    <FamilyWorkspaceContext.Provider value={value}>
      <div className="page page--family">
        <PageHeader title={t('nav.family')} description={workspace.errors.length > 0 ? '部分数据加载失败，页面已自动显示已拿到的内容。' : undefined} />
        <nav className="family-tabs">
          {familyTabs.map(tab => (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.end}
              className={({ isActive }) => `family-tab ${isActive ? 'family-tab--active' : ''}`}
            >
              {t(tab.labelKey)}
            </NavLink>
          ))}
        </nav>
        <div className="family-content">
          <Outlet />
        </div>
      </div>
    </FamilyWorkspaceContext.Provider>
  );
}

/* ---- 家庭概览 ---- */
export function FamilyOverview() {
  const { t } = useI18n();
  const { currentHousehold } = useHouseholdContext();
  const { household, overview, loading } = useFamilyWorkspace();

  const serviceSummary = [
    overview?.voice_fast_path_enabled ? '语音快通道' : null,
    overview?.guest_mode_enabled ? '访客模式' : null,
    overview?.child_protection_enabled ? '儿童保护' : null,
    overview?.elder_care_watch_enabled ? '长辈关怀' : null,
  ].filter(Boolean).join(' · ');

  return (
    <div className="family-overview">
      <div className="overview-grid">
        <Card className="overview-card">
          <div className="overview-card__label">{t('family.name')}</div>
          <div className="overview-card__value">{household?.name ?? currentHousehold?.name ?? (loading ? '加载中...' : '-')}</div>
        </Card>
        <Card className="overview-card">
          <div className="overview-card__label">{t('family.timezone')}</div>
          <div className="overview-card__value">{household?.timezone ?? (loading ? '加载中...' : '-')}</div>
        </Card>
        <Card className="overview-card">
          <div className="overview-card__label">{t('family.language')}</div>
          <div className="overview-card__value">{formatLocale(household?.locale)}</div>
        </Card>
        <Card className="overview-card">
          <div className="overview-card__label">{t('family.mode')}</div>
          <div className="overview-card__value">{formatHomeMode(overview?.home_mode)}</div>
        </Card>
        <Card className="overview-card">
          <div className="overview-card__label">{t('family.privacy')}</div>
          <div className="overview-card__value">{formatPrivacyMode(overview?.privacy_mode)}</div>
        </Card>
        <Card className="overview-card">
          <div className="overview-card__label">{t('family.services')}</div>
          <div className="overview-card__value">{serviceSummary || (loading ? '加载中...' : '暂无服务摘要')}</div>
        </Card>
      </div>
    </div>
  );
}

/* ---- 房间页 ---- */
export function FamilyRooms() {
  const { t } = useI18n();
  const { rooms, overview, devices, loading, refreshWorkspace } = useFamilyWorkspace();
  const { currentHouseholdId } = useHouseholdContext();
  const [createForm, setCreateForm] = useState({ name: '', room_type: 'living_room' as Room['room_type'], privacy_level: 'public' as Room['privacy_level'] });
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');

  const roomCards = rooms.map(room => {
    const roomOverview = overview?.room_occupancy.find(item => item.room_id === room.id);
    const roomDeviceCount = roomOverview?.device_count ?? devices.filter(device => device.room_id === room.id).length;
    const isActive = (roomOverview?.occupant_count ?? 0) > 0 || (roomOverview?.online_device_count ?? 0) > 0;

    return {
      id: room.id,
      name: room.name,
      type: formatRoomType(room.room_type),
      devices: roomDeviceCount,
      active: isActive,
      sensitive: room.privacy_level === 'sensitive',
    };
  });

  async function handleCreateRoom(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId) {
      setError('请先选择家庭。');
      return;
    }
    try {
      setError('');
      await api.createRoom({ household_id: currentHouseholdId, ...createForm });
      setCreateForm({ name: '', room_type: 'living_room', privacy_level: 'public' });
      await refreshWorkspace();
      setStatus('房间已创建。');
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : '创建房间失败');
    }
  }

  return (
    <div className="family-rooms">
      <Card className="room-detail-card" style={{ marginBottom: '1rem' }}>
        <form className="settings-form" onSubmit={handleCreateRoom}>
          <div className="form-group">
            <label>房间名称</label>
            <input className="form-input" value={createForm.name} onChange={event => setCreateForm(current => ({ ...current, name: event.target.value }))} required />
          </div>
          <div className="form-group">
            <label>房间类型</label>
            <select className="form-select" value={createForm.room_type} onChange={event => setCreateForm(current => ({ ...current, room_type: event.target.value as Room['room_type'] }))}>
              <option value="living_room">客厅</option>
              <option value="bedroom">卧室</option>
              <option value="study">书房</option>
              <option value="entrance">玄关</option>
            </select>
          </div>
          <div className="form-group">
            <label>隐私等级</label>
            <select className="form-select" value={createForm.privacy_level} onChange={event => setCreateForm(current => ({ ...current, privacy_level: event.target.value as Room['privacy_level'] }))}>
              <option value="public">公共</option>
              <option value="private">私密</option>
              <option value="sensitive">敏感</option>
            </select>
          </div>
          <button className="btn btn--primary" type="submit">新建房间</button>
          {(status || error) && <div className="text-text-secondary">{error || status}</div>}
        </form>
      </Card>
      <div className="room-grid">
        {loading && roomCards.length === 0 ? <div className="text-text-secondary">正在加载房间数据...</div> : roomCards.map(room => (
          <Card key={room.id} className="room-detail-card">
            <div className="room-detail-card__top">
              <h3 className="room-detail-card__name">{room.name}</h3>
              {room.sensitive && <span className="badge badge--warning">{t('room.sensitive')}</span>}
            </div>
            <div className="room-detail-card__meta">
              <span className="meta-item">📦 {room.type}</span>
              <span className="meta-item">📱 {room.devices} {t('room.devices')}</span>
              <span className={`meta-item ${room.active ? 'meta-item--active' : ''}`}>
                {room.active ? `🟢 ${t('room.active')}` : `⚪ ${t('room.idle')}`}
              </span>
            </div>
            <button className="card-action-btn" disabled>{t('common.edit')}</button>
          </Card>
        ))}
      </div>
    </div>
  );
}

/* ---- 成员页 ---- */
export function FamilyMembers() {
  const { t } = useI18n();
  const { members, overview, preferencesByMemberId, loading, refreshWorkspace } = useFamilyWorkspace();
  const { currentHouseholdId } = useHouseholdContext();
  const [createForm, setCreateForm] = useState({ name: '', nickname: '', role: 'adult' as Member['role'], age_group: 'adult' as NonNullable<Member['age_group']>, phone: '', guardian_member_id: '' });
  const [editingPreferencesMemberId, setEditingPreferencesMemberId] = useState<string | null>(null);
  const [preferencesDraft, setPreferencesDraft] = useState({ preferred_name: '', reminder_channel: '', sleep_start: '', sleep_end: '' });
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');

  async function handleCreateMember(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId) {
      setError('请先选择家庭。');
      return;
    }

    try {
      setError('');
      await api.createMember({
        household_id: currentHouseholdId,
        name: createForm.name,
        nickname: createForm.nickname || null,
        role: createForm.role,
        age_group: createForm.age_group,
        phone: createForm.phone || null,
        guardian_member_id: createForm.guardian_member_id || null,
      });
      setCreateForm({ name: '', nickname: '', role: 'adult', age_group: 'adult', phone: '', guardian_member_id: '' });
      await refreshWorkspace();
      setStatus('成员已创建。');
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : '创建成员失败');
    }
  }

  function openPreferencesEditor(member: Member) {
    const preference = preferencesByMemberId[member.id];
    const sleepSchedule = preference?.sleep_schedule;
    const sleepStart = sleepSchedule && typeof sleepSchedule === 'object' && 'start' in sleepSchedule ? String((sleepSchedule as { start?: unknown }).start ?? '') : '';
    const sleepEnd = sleepSchedule && typeof sleepSchedule === 'object' && 'end' in sleepSchedule ? String((sleepSchedule as { end?: unknown }).end ?? '') : '';

    setEditingPreferencesMemberId(member.id);
    setPreferencesDraft({
      preferred_name: preference?.preferred_name ?? member.nickname ?? '',
      reminder_channel: preference?.reminder_channel_preference ? JSON.stringify(preference.reminder_channel_preference) : '',
      sleep_start: sleepStart,
      sleep_end: sleepEnd,
    });
    setStatus('');
    setError('');
  }

  async function handleSavePreferences() {
    if (!editingPreferencesMemberId) {
      return;
    }

    try {
      setError('');
      await api.upsertMemberPreferences(editingPreferencesMemberId, {
        preferred_name: preferencesDraft.preferred_name || null,
        light_preference: null,
        climate_preference: null,
        content_preference: null,
        reminder_channel_preference: preferencesDraft.reminder_channel ? { note: preferencesDraft.reminder_channel } : null,
        sleep_schedule: preferencesDraft.sleep_start || preferencesDraft.sleep_end ? { start: preferencesDraft.sleep_start, end: preferencesDraft.sleep_end } : null,
      });
      await refreshWorkspace();
      setEditingPreferencesMemberId(null);
      setStatus('成员偏好已保存。');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存成员偏好失败');
    }
  }

  return (
    <div className="family-members">
      <Card className="member-detail-card" style={{ marginBottom: '1rem' }}>
        <form className="settings-form" onSubmit={handleCreateMember}>
          <div className="form-group">
            <label>姓名</label>
            <input className="form-input" value={createForm.name} onChange={event => setCreateForm(current => ({ ...current, name: event.target.value }))} required />
          </div>
          <div className="form-group">
            <label>昵称</label>
            <input className="form-input" value={createForm.nickname} onChange={event => setCreateForm(current => ({ ...current, nickname: event.target.value }))} />
          </div>
          <div className="form-group">
            <label>角色</label>
            <select className="form-select" value={createForm.role} onChange={event => setCreateForm(current => ({ ...current, role: event.target.value as Member['role'] }))}>
              <option value="admin">管理员</option>
              <option value="adult">成人</option>
              <option value="child">儿童</option>
              <option value="elder">长辈</option>
              <option value="guest">访客</option>
            </select>
          </div>
          <div className="form-group">
            <label>年龄分组</label>
            <select className="form-select" value={createForm.age_group} onChange={event => setCreateForm(current => ({ ...current, age_group: event.target.value as NonNullable<Member['age_group']> }))}>
              <option value="adult">成人</option>
              <option value="child">儿童</option>
              <option value="teen">青少年</option>
              <option value="toddler">幼儿</option>
              <option value="elder">长辈</option>
            </select>
          </div>
          <button className="btn btn--primary" type="submit">新增成员</button>
          {(status || error) && <div className="text-text-secondary">{error || status}</div>}
        </form>
      </Card>
      <div className="member-detail-grid">
        {loading && members.length === 0 ? <div className="text-text-secondary">正在加载成员数据...</div> : members.map(member => {
          const status = getMemberStatus(member.id, overview);

          return (
            <Card key={member.id} className="member-detail-card">
              <div className="member-detail-card__top">
                <div className="member-detail-card__avatar">
                  {member.role === 'elder' ? '👵' : member.role === 'child' ? '👦' : member.role === 'guest' ? '🧑' : '👨'}
                </div>
                <div className="member-detail-card__info">
                  <h3 className="member-detail-card__name">{member.name}</h3>
                  <span className="member-detail-card__role">{formatRole(member.role)}</span>
                </div>
                <span className={`badge badge--${status === 'home' ? 'success' : status === 'resting' ? 'warning' : 'secondary'}`}>
                  {status === 'home' ? t('member.atHome') : status === 'resting' ? t('member.resting') : t('member.away')}
                </span>
              </div>
              <p className="member-detail-card__prefs">{formatPreferenceSummary(preferencesByMemberId[member.id])}</p>
              <div className="member-detail-card__actions">
                <button className="card-action-btn" disabled>{t('member.edit')}</button>
                <button className="card-action-btn" onClick={() => openPreferencesEditor(member)}>{t('member.preferences')}</button>
              </div>
            </Card>
          );
        })}
      </div>
      {editingPreferencesMemberId && (
        <Card className="member-detail-card" style={{ marginTop: '1rem' }}>
          <div className="settings-form">
            <div className="form-group">
              <label>偏好称呼</label>
              <input className="form-input" value={preferencesDraft.preferred_name} onChange={event => setPreferencesDraft(current => ({ ...current, preferred_name: event.target.value }))} />
            </div>
            <div className="form-group">
              <label>提醒方式备注</label>
              <input className="form-input" value={preferencesDraft.reminder_channel} onChange={event => setPreferencesDraft(current => ({ ...current, reminder_channel: event.target.value }))} placeholder="例如：语音+站内消息" />
            </div>
            <div className="form-group">
              <label>作息开始</label>
              <input className="form-input" value={preferencesDraft.sleep_start} onChange={event => setPreferencesDraft(current => ({ ...current, sleep_start: event.target.value }))} placeholder="22:00" />
            </div>
            <div className="form-group">
              <label>作息结束</label>
              <input className="form-input" value={preferencesDraft.sleep_end} onChange={event => setPreferencesDraft(current => ({ ...current, sleep_end: event.target.value }))} placeholder="07:00" />
            </div>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button className="btn btn--primary" type="button" onClick={() => void handleSavePreferences()}>{t('common.save')}</button>
              <button className="btn btn--outline" type="button" onClick={() => setEditingPreferencesMemberId(null)}>{t('common.cancel')}</button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

/* ---- 关系页 ---- */
export function FamilyRelationships() {
  const { t } = useI18n();
  const { relationships, members, loading, refreshWorkspace } = useFamilyWorkspace();
  const { currentHouseholdId } = useHouseholdContext();
  const [createForm, setCreateForm] = useState({ source_member_id: '', target_member_id: '', relation_type: 'guardian' as MemberRelationship['relation_type'], visibility_scope: 'family' as MemberRelationship['visibility_scope'], delegation_scope: 'none' as MemberRelationship['delegation_scope'] });
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');

  const memberNameMap = Object.fromEntries(members.map(member => [member.id, member.name]));

  const caregivingRelations = relationships.filter(item => item.relation_type === 'caregiver');
  const guardianshipRelations = relationships.filter(item => item.relation_type === 'guardian' || item.relation_type === 'parent' || item.relation_type === 'child');
  const otherRelations = relationships.filter(item => !caregivingRelations.includes(item) && !guardianshipRelations.includes(item));

  async function handleCreateRelationship(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId || !createForm.source_member_id || !createForm.target_member_id) {
      setError('请先选择关系双方成员。');
      return;
    }

    try {
      setError('');
      await api.createMemberRelationship({ household_id: currentHouseholdId, ...createForm });
      setCreateForm({ source_member_id: '', target_member_id: '', relation_type: 'guardian', visibility_scope: 'family', delegation_scope: 'none' });
      await refreshWorkspace();
      setStatus('关系已创建。');
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : '创建关系失败');
    }
  }

  const renderRelationCards = (items: MemberRelationship[]) => (
    <div className="relation-list">
      {items.map(item => {
        const fromName = memberNameMap[item.source_member_id] ?? item.source_member_id;
        const toName = memberNameMap[item.target_member_id] ?? item.target_member_id;

        return (
          <Card key={item.id} className="relation-card">
            <div className="relation-card__pair">
              <span>{fromName}</span>
              <span className="relation-card__arrow">→</span>
              <span>{toName}</span>
            </div>
            <p className="relation-card__desc">
              {formatRelationType(item.relation_type)} · {formatVisibilityScope(item.visibility_scope)} · {formatDelegationScope(item.delegation_scope)}
            </p>
          </Card>
        );
      })}
    </div>
  );

  return (
    <div className="family-relationships">
      <Card className="relation-card" style={{ marginBottom: '1rem' }}>
        <form className="settings-form" onSubmit={handleCreateRelationship}>
          <div className="form-group">
            <label>发起成员</label>
            <select className="form-select" value={createForm.source_member_id} onChange={event => setCreateForm(current => ({ ...current, source_member_id: event.target.value }))}>
              <option value="">请选择</option>
              {members.map(member => <option key={member.id} value={member.id}>{member.name}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>目标成员</label>
            <select className="form-select" value={createForm.target_member_id} onChange={event => setCreateForm(current => ({ ...current, target_member_id: event.target.value }))}>
              <option value="">请选择</option>
              {members.map(member => <option key={member.id} value={member.id}>{member.name}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>关系类型</label>
            <select className="form-select" value={createForm.relation_type} onChange={event => setCreateForm(current => ({ ...current, relation_type: event.target.value as MemberRelationship['relation_type'] }))}>
              <option value="guardian">监护</option>
              <option value="caregiver">照护</option>
              <option value="parent">父母</option>
              <option value="child">子女</option>
              <option value="spouse">伴侣</option>
            </select>
          </div>
          <button className="btn btn--primary" type="submit">新增关系</button>
          {(status || error) && <div className="text-text-secondary">{error || status}</div>}
        </form>
      </Card>
      <Card className="relationship-graph-placeholder">
        <div className="relationship-graph__hint">
          <span className="relationship-graph__icon">🔗</span>
          <p>{loading && relationships.length === 0 ? '正在加载关系数据...' : `当前已接入 ${relationships.length} 条真实关系数据，可视化图谱下一步补。`}</p>
        </div>
      </Card>

      <Section title={t('relationship.caregiving')}>
        {renderRelationCards(caregivingRelations)}
      </Section>

      <Section title={t('relationship.guardianship')}>
        {renderRelationCards(guardianshipRelations)}
      </Section>

      {otherRelations.length > 0 && (
        <Section title="其他关系">
          {renderRelationCards(otherRelations)}
        </Section>
      )}
    </div>
  );
}
