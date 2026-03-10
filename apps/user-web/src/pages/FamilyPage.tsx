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
  const [createForm, setCreateForm] = useState({ name: '', nickname: '', gender: '' as '' | 'male' | 'female', role: 'adult' as Member['role'], age_group: 'adult' as NonNullable<Member['age_group']>, phone: '', guardian_member_id: '' });
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
        gender: createForm.gender || null,
        role: createForm.role,
        age_group: createForm.age_group,
        phone: createForm.phone || null,
        guardian_member_id: createForm.guardian_member_id || null,
      });
      setCreateForm({ name: '', nickname: '', gender: '', role: 'adult', age_group: 'adult', phone: '', guardian_member_id: '' });
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
            <label>性别</label>
            <select className="form-select" value={createForm.gender} onChange={event => setCreateForm(current => ({ ...current, gender: event.target.value as '' | 'male' | 'female' }))}>
              <option value="">未设置</option>
              <option value="male">男</option>
              <option value="female">女</option>
            </select>
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

/* 关系中文标签 */
const RELATION_LABELS: Record<string, string> = {
  husband: '丈夫', wife: '妻子', spouse: '配偶',
  father: '爸爸', mother: '妈妈', parent: '父/母',
  son: '儿子', daughter: '女儿', child: '子女',
  older_brother: '哥哥', older_sister: '姐姐',
  younger_brother: '弟弟', younger_sister: '妹妹',
  grandfather_paternal: '爷爷', grandmother_paternal: '奶奶',
  grandfather_maternal: '姥爷', grandmother_maternal: '姥姥',
  grandson: '孙子', granddaughter: '孙女',
  guardian: '监护人', ward: '被监护人',
  caregiver: '照护者',
};

/* 通用关系分类标签 (用于图谱默认连线) */
const RELATION_CATEGORY_LABELS: Record<string, string> = {
  husband: '配偶', wife: '配偶', spouse: '配偶',
  father: '父子/父女', mother: '母子/母女', parent: '亲子',
  son: '父子/母子', daughter: '父女/母女', child: '亲子',
  older_brother: '兄弟/兄妹', older_sister: '姐弟/姐妹',
  younger_brother: '兄弟/姐弟', younger_sister: '兄妹/姐妹',
  grandfather_paternal: '祖孙', grandmother_paternal: '祖孙',
  grandfather_maternal: '外祖孙', grandmother_maternal: '外祖孙',
  grandson: '祖孙', granddaughter: '祖孙',
  guardian: '监护', ward: '监护',
  caregiver: '照护',
};

/* 根据成员角色筛选可选的关系类型 */
type RelationOption = { value: string; label: string };

function getRelationOptionsForRole(role: string): RelationOption[] {
  const childOptions: RelationOption[] = [
    { value: 'father', label: '爸爸' }, { value: 'mother', label: '妈妈' },
    { value: 'older_brother', label: '哥哥' }, { value: 'older_sister', label: '姐姐' },
    { value: 'younger_brother', label: '弟弟' }, { value: 'younger_sister', label: '妹妹' },
    { value: 'grandfather_paternal', label: '爷爷' }, { value: 'grandmother_paternal', label: '奶奶' },
    { value: 'grandfather_maternal', label: '姥爷' }, { value: 'grandmother_maternal', label: '姥姥' },
    { value: 'guardian', label: '监护人' },
  ];

  const adultOptions: RelationOption[] = [
    { value: 'husband', label: '丈夫' }, { value: 'wife', label: '妻子' },
    { value: 'father', label: '爸爸' }, { value: 'mother', label: '妈妈' },
    { value: 'son', label: '儿子' }, { value: 'daughter', label: '女儿' },
    { value: 'older_brother', label: '哥哥' }, { value: 'older_sister', label: '姐姐' },
    { value: 'younger_brother', label: '弟弟' }, { value: 'younger_sister', label: '妹妹' },
    { value: 'grandfather_paternal', label: '爷爷' }, { value: 'grandmother_paternal', label: '奶奶' },
    { value: 'grandfather_maternal', label: '姥爷' }, { value: 'grandmother_maternal', label: '姥姥' },
    { value: 'grandson', label: '孙子' }, { value: 'granddaughter', label: '孙女' },
    { value: 'guardian', label: '监护人' }, { value: 'ward', label: '被监护人' },
    { value: 'caregiver', label: '照护者' },
  ];

  const elderOptions: RelationOption[] = [
    { value: 'husband', label: '丈夫' }, { value: 'wife', label: '妻子' },
    { value: 'son', label: '儿子' }, { value: 'daughter', label: '女儿' },
    { value: 'grandson', label: '孙子' }, { value: 'granddaughter', label: '孙女' },
    { value: 'older_brother', label: '哥哥' }, { value: 'older_sister', label: '姐姐' },
    { value: 'younger_brother', label: '弟弟' }, { value: 'younger_sister', label: '妹妹' },
    { value: 'ward', label: '被监护人' },
    { value: 'caregiver', label: '照护者' },
  ];

  switch (role) {
    case 'child': return childOptions;
    case 'elder': return elderOptions;
    default: return adultOptions;
  }
}

/* ---- SVG 关系图谱 ---- */
type GraphNode = { id: string; name: string; role: string; x: number; y: number; vx: number; vy: number };
type GraphEdge = { source: string; target: string; label: string; relationType: string };

function buildGraphData(members: Member[], relationships: MemberRelationship[]): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const angle = (2 * Math.PI) / Math.max(members.length, 1);
  const radius = Math.min(180, 60 + members.length * 20);

  const nodes: GraphNode[] = members.map((m, i) => ({
    id: m.id,
    name: m.name,
    role: m.role,
    x: 250 + radius * Math.cos(angle * i - Math.PI / 2),
    y: 220 + radius * Math.sin(angle * i - Math.PI / 2),
    vx: 0, vy: 0,
  }));

  // 去重: 对于 A→B 和 B→A 这种双向关系，只保留一条边
  const edgeSet = new Set<string>();
  const edges: GraphEdge[] = [];
  for (const rel of relationships) {
    const key1 = `${rel.source_member_id}|${rel.target_member_id}`;
    const key2 = `${rel.target_member_id}|${rel.source_member_id}`;
    if (!edgeSet.has(key1) && !edgeSet.has(key2)) {
      edgeSet.add(key1);
      edges.push({
        source: rel.source_member_id,
        target: rel.target_member_id,
        label: RELATION_CATEGORY_LABELS[rel.relation_type] ?? rel.relation_type,
        relationType: rel.relation_type,
      });
    }
  }

  return { nodes, edges };
}

function getEdgeLabelForPerspective(
  edge: GraphEdge,
  selectedMemberId: string,
  relationships: MemberRelationship[],
): string {
  // 从 selectedMember 视角: 找 selectedMember → other 的 relation_type
  const otherId = edge.source === selectedMemberId ? edge.target : edge.source;
  const rel = relationships.find(
    r => r.source_member_id === selectedMemberId && r.target_member_id === otherId,
  );
  if (rel) return RELATION_LABELS[rel.relation_type] ?? rel.relation_type;
  // fallback: 反向
  const revRel = relationships.find(
    r => r.source_member_id === otherId && r.target_member_id === selectedMemberId,
  );
  if (revRel) return RELATION_LABELS[revRel.relation_type] ?? revRel.relation_type;
  return edge.label;
}

function RelationshipGraph({ members, relationships, selectedMemberId, onSelectMember }: {
  members: Member[];
  relationships: MemberRelationship[];
  selectedMemberId: string | null;
  onSelectMember: (id: string | null) => void;
}) {
  const { nodes, edges } = useMemo(() => buildGraphData(members, relationships), [members, relationships]);

  // 简单的力导向模拟
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({});

  useEffect(() => {
    if (nodes.length === 0) return;

    const simNodes = nodes.map(n => ({ ...n }));
    const nodeMap = Object.fromEntries(simNodes.map(n => [n.id, n]));

    let frame: number;
    let iterations = 0;
    const maxIterations = 120;

    function tick() {
      // 力导向计算
      for (const node of simNodes) {
        node.vx *= 0.85;
        node.vy *= 0.85;
      }

      // 排斥力
      for (let i = 0; i < simNodes.length; i++) {
        for (let j = i + 1; j < simNodes.length; j++) {
          const a = simNodes[i], b = simNodes[j];
          let dx = b.x - a.x, dy = b.y - a.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          if (dist < 200) {
            const force = (200 - dist) * 0.05;
            dx /= dist; dy /= dist;
            a.vx -= dx * force; a.vy -= dy * force;
            b.vx += dx * force; b.vy += dy * force;
          }
        }
      }

      // 引力 (连线的)
      for (const edge of edges) {
        const a = nodeMap[edge.source], b = nodeMap[edge.target];
        if (!a || !b) continue;
        let dx = b.x - a.x, dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const idealDist = 140;
        const force = (dist - idealDist) * 0.01;
        dx /= dist; dy /= dist;
        a.vx += dx * force; a.vy += dy * force;
        b.vx -= dx * force; b.vy -= dy * force;
      }

      // 居中力
      for (const node of simNodes) {
        node.vx += (250 - node.x) * 0.005;
        node.vy += (220 - node.y) * 0.005;
      }

      // 更新位置
      for (const node of simNodes) {
        node.x = Math.max(40, Math.min(460, node.x + node.vx));
        node.y = Math.max(40, Math.min(400, node.y + node.vy));
      }

      iterations++;
      setPositions(Object.fromEntries(simNodes.map(n => [n.id, { x: n.x, y: n.y }])));

      if (iterations < maxIterations) {
        frame = requestAnimationFrame(tick);
      }
    }

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [nodes, edges]);

  const getPos = (id: string) => positions[id] ?? nodes.find(n => n.id === id) ?? { x: 250, y: 220 };

  const roleEmoji = (role: string) => {
    switch (role) {
      case 'elder': return '👵';
      case 'child': return '👦';
      case 'guest': return '🧑';
      default: return '👨';
    }
  };

  return (
    <div className="relationship-graph" onClick={() => onSelectMember(null)}>
      <svg viewBox="0 0 500 440" className="relationship-graph__svg">
        <defs>
          <filter id="node-shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.15" />
          </filter>
        </defs>

        {/* 连线 */}
        {edges.map((edge, i) => {
          const s = getPos(edge.source), t = getPos(edge.target);
          const mx = (s.x + t.x) / 2, my = (s.y + t.y) / 2;
          const isHighlighted = selectedMemberId && (edge.source === selectedMemberId || edge.target === selectedMemberId);
          const isDimmed = selectedMemberId && !isHighlighted;
          const label = selectedMemberId && isHighlighted
            ? getEdgeLabelForPerspective(edge, selectedMemberId, relationships)
            : edge.label;

          return (
            <g key={`edge-${i}`}>
              <line
                x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                className={`graph-edge ${isHighlighted ? 'graph-edge--highlight' : ''} ${isDimmed ? 'graph-edge--dim' : ''}`}
              />
              <rect
                x={mx - label.length * 7} y={my - 10}
                width={label.length * 14} height={20}
                rx={4}
                className={`graph-edge-label-bg ${isDimmed ? 'graph-edge-label-bg--dim' : ''}`}
              />
              <text
                x={mx} y={my + 4}
                textAnchor="middle"
                className={`graph-edge-label ${isHighlighted ? 'graph-edge-label--highlight' : ''} ${isDimmed ? 'graph-edge-label--dim' : ''}`}
              >
                {label}
              </text>
            </g>
          );
        })}

        {/* 节点 */}
        {nodes.map(node => {
          const pos = getPos(node.id);
          const isSelected = selectedMemberId === node.id;
          const isConnected = selectedMemberId && edges.some(e => (e.source === selectedMemberId || e.target === selectedMemberId) && (e.source === node.id || e.target === node.id));
          const isDimmed = selectedMemberId && !isSelected && !isConnected;

          return (
            <g
              key={node.id}
              transform={`translate(${pos.x},${pos.y})`}
              className={`graph-node ${isSelected ? 'graph-node--selected' : ''} ${isDimmed ? 'graph-node--dim' : ''}`}
              onClick={e => { e.stopPropagation(); onSelectMember(isSelected ? null : node.id); }}
              style={{ cursor: 'pointer' }}
            >
              <circle r={28} className="graph-node__circle" filter="url(#node-shadow)" />
              <text y={4} textAnchor="middle" className="graph-node__emoji">{roleEmoji(node.role)}</text>
              <text y={46} textAnchor="middle" className="graph-node__name">{node.name}</text>
            </g>
          );
        })}
      </svg>
      {selectedMemberId && (
        <div className="graph-legend">
          👆 已选中 <strong>{members.find(m => m.id === selectedMemberId)?.name}</strong> 的视角，点击空白处取消
        </div>
      )}
    </div>
  );
}

export function FamilyRelationships() {
  const { t } = useI18n();
  const { relationships, members, loading, refreshWorkspace } = useFamilyWorkspace();
  const { currentHouseholdId } = useHouseholdContext();
  const [selectedMemberId, setSelectedMemberId] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState({
    source_member_id: '',
    target_member_id: '',
    relation_type: '' as MemberRelationship['relation_type'] | '',
  });
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [deleting, setDeleting] = useState<string | null>(null);

  const memberNameMap = Object.fromEntries(members.map(member => [member.id, member.name]));

  // 根据所选 source 成员过滤可选关系
  const sourceMember = members.find(m => m.id === createForm.source_member_id);
  const relationOptions = sourceMember ? getRelationOptionsForRole(sourceMember.role) : [];

  // 根据 source 去掉 source 自己
  const targetOptions = members.filter(m => m.id !== createForm.source_member_id);

  async function handleCreateRelationship(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId || !createForm.source_member_id || !createForm.target_member_id || !createForm.relation_type) {
      setError('请选择成员和关系类型。');
      return;
    }

    try {
      setError('');
      await api.createMemberRelationship({
        household_id: currentHouseholdId,
        source_member_id: createForm.source_member_id,
        target_member_id: createForm.target_member_id,
        relation_type: createForm.relation_type as MemberRelationship['relation_type'],
        visibility_scope: 'family',
        delegation_scope: 'none',
      });
      setCreateForm({ source_member_id: '', target_member_id: '', relation_type: '' });
      await refreshWorkspace();
      setStatus('关系已创建，反向关系已自动建立。');
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : '创建关系失败');
    }
  }

  async function handleDelete(relationshipId: string) {
    setDeleting(relationshipId);
    try {
      setError('');
      await api.deleteMemberRelationship(relationshipId);
      await refreshWorkspace();
      setStatus('关系已删除。');
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : '删除关系失败');
    } finally {
      setDeleting(null);
    }
  }

  // 按 source 分组
  const groupedBySource = useMemo(() => {
    const groups: Record<string, MemberRelationship[]> = {};
    for (const rel of relationships) {
      (groups[rel.source_member_id] ??= []).push(rel);
    }
    return groups;
  }, [relationships]);

  return (
    <div className="family-relationships">
      {/* 关系图谱 */}
      <Card className="relationship-graph-card">
        {members.length >= 2 && relationships.length > 0 ? (
          <RelationshipGraph
            members={members}
            relationships={relationships}
            selectedMemberId={selectedMemberId}
            onSelectMember={setSelectedMemberId}
          />
        ) : (
          <div className="relationship-graph__hint">
            <span className="relationship-graph__icon">🔗</span>
            <p>{loading ? '正在加载关系数据...' : members.length < 2 ? '至少需要 2 位成员才能创建关系' : '还没有创建任何关系，请在下方添加。'}</p>
          </div>
        )}
      </Card>

      {/* 添加关系 */}
      <Card className="relation-card" style={{ marginTop: '1rem' }}>
        <h3 style={{ fontSize: 'var(--font-size-md)', fontWeight: 600, marginBottom: 'var(--spacing-md)' }}>添加关系</h3>
        <form className="settings-form relationship-create-form" onSubmit={handleCreateRelationship}>
          <div className="form-group">
            <label>选择成员</label>
            <select className="form-select" value={createForm.source_member_id} onChange={event => { setCreateForm(current => ({ ...current, source_member_id: event.target.value, relation_type: '', target_member_id: '' })); setStatus(''); setError(''); }}>
              <option value="">请选择成员</option>
              {members.map(member => <option key={member.id} value={member.id}>{member.name}（{formatRole(member.role)}）</option>)}
            </select>
          </div>
          {createForm.source_member_id && (
            <>
              <div className="form-group">
                <label>关系类型（{memberNameMap[createForm.source_member_id]} 的…）</label>
                <select className="form-select" value={createForm.relation_type} onChange={event => setCreateForm(current => ({ ...current, relation_type: event.target.value as MemberRelationship['relation_type'] }))}>
                  <option value="">请选择关系</option>
                  {relationOptions.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>关系目标</label>
                <select className="form-select" value={createForm.target_member_id} onChange={event => setCreateForm(current => ({ ...current, target_member_id: event.target.value }))}>
                  <option value="">请选择目标成员</option>
                  {targetOptions.map(member => <option key={member.id} value={member.id}>{member.name}（{formatRole(member.role)}）</option>)}
                </select>
              </div>
            </>
          )}
          <button className="btn btn--primary" type="submit" disabled={!createForm.source_member_id || !createForm.target_member_id || !createForm.relation_type}>新增关系</button>
          {status && <div className="text-text-secondary" style={{ color: 'var(--color-success)' }}>{status}</div>}
          {error && <div className="text-text-secondary" style={{ color: 'var(--color-danger)' }}>{error}</div>}
        </form>
      </Card>

      {/* 关系列表（按成员分组） */}
      {Object.keys(groupedBySource).length > 0 && (
        <Section title="关系列表">
          {Object.entries(groupedBySource).map(([sourceId, rels]) => (
            <div key={sourceId} className="relation-group">
              <h4 className="relation-group__title">{memberNameMap[sourceId] ?? sourceId} 的关系</h4>
              <div className="relation-list">
                {rels.map(item => {
                  const toName = memberNameMap[item.target_member_id] ?? item.target_member_id;
                  return (
                    <Card key={item.id} className="relation-card relation-card--compact">
                      <div className="relation-card__pair">
                        <span className="relation-card__label">{RELATION_LABELS[item.relation_type] ?? item.relation_type}</span>
                        <span className="relation-card__arrow">→</span>
                        <span className="relation-card__name">{toName}</span>
                      </div>
                      <button
                        className="btn btn--danger btn--small"
                        onClick={() => void handleDelete(item.id)}
                        disabled={deleting === item.id}
                      >
                        {deleting === item.id ? '删除中...' : '删除'}
                      </button>
                    </Card>
                  );
                })}
              </div>
            </div>
          ))}
        </Section>
      )}
    </div>
  );
}
