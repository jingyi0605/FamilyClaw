/* ============================================================
 * 家庭页 - 包含概览/房间/成员/关系四个子路由
 * ============================================================ */
import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useI18n } from '../i18n';
import { PageHeader, Card, Section } from '../components/base';
import { useHouseholdContext } from '../state/household';
import { api } from '../lib/api';
import { formatRoomType, ROOM_TYPE_OPTIONS } from '../lib/roomTypes';
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

function validatePhoneNumber(value: string) {
  if (!value.trim()) {
    return '';
  }

  return /^[0-9+\-\s]{6,20}$/.test(value.trim()) ? '' : '请输入有效手机号，支持数字、空格、+ 和 -';
}

function roleNeedsGuardian(role: Member['role']) {
  return role === 'child';
}

function getAllowedStatusOptions(role: Member['role']) {
  if (role === 'admin') {
    return [{ value: 'active' as const, label: '启用' }];
  }

  return [
    { value: 'active' as const, label: '启用' },
    { value: 'inactive' as const, label: '停用' },
  ];
}

function inferAgeGroupFromBirthday(birthday: string): NonNullable<Member['age_group']> | null {
  if (!birthday) {
    return null;
  }

  const birthDate = new Date(`${birthday}T00:00:00`);
  if (Number.isNaN(birthDate.getTime())) {
    return null;
  }

  const now = new Date();
  let age = now.getFullYear() - birthDate.getFullYear();
  const hasBirthdayPassed =
    now.getMonth() > birthDate.getMonth()
    || (now.getMonth() === birthDate.getMonth() && now.getDate() >= birthDate.getDate());

  if (!hasBirthdayPassed) {
    age -= 1;
  }

  if (age <= 3) return 'toddler';
  if (age <= 12) return 'child';
  if (age <= 17) return 'teen';
  if (age >= 65) return 'elder';
  return 'adult';
}

function getAgeFromBirthday(birthday: string | null) {
  if (!birthday) {
    return null;
  }

  const birthDate = new Date(`${birthday}T00:00:00`);
  if (Number.isNaN(birthDate.getTime())) {
    return null;
  }

  const now = new Date();
  let age = now.getFullYear() - birthDate.getFullYear();
  const hasBirthdayPassed =
    now.getMonth() > birthDate.getMonth()
    || (now.getMonth() === birthDate.getMonth() && now.getDate() >= birthDate.getDate());

  if (!hasBirthdayPassed) {
    age -= 1;
  }

  return Math.max(age, 0);
}

function getBirthdayCountdownText(birthday: string | null) {
  if (!birthday) {
    return '未设置生日';
  }

  const birthDate = new Date(`${birthday}T00:00:00`);
  if (Number.isNaN(birthDate.getTime())) {
    return '生日格式无效';
  }

  const today = new Date();
  const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  let nextBirthday = new Date(today.getFullYear(), birthDate.getMonth(), birthDate.getDate());
  if (nextBirthday < startOfToday) {
    nextBirthday = new Date(today.getFullYear() + 1, birthDate.getMonth(), birthDate.getDate());
  }

  const diffDays = Math.round((nextBirthday.getTime() - startOfToday.getTime()) / 86400000);
  if (diffDays === 0) return '今天生日';
  if (diffDays === 1) return '明天生日';
  return `${diffDays} 天后生日`;
}

function getBirthdayCountdownDays(birthday: string | null) {
  if (!birthday) {
    return null;
  }

  const birthDate = new Date(`${birthday}T00:00:00`);
  if (Number.isNaN(birthDate.getTime())) {
    return null;
  }

  const today = new Date();
  const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  let nextBirthday = new Date(today.getFullYear(), birthDate.getMonth(), birthDate.getDate());
  if (nextBirthday < startOfToday) {
    nextBirthday = new Date(today.getFullYear() + 1, birthDate.getMonth(), birthDate.getDate());
  }

  return Math.round((nextBirthday.getTime() - startOfToday.getTime()) / 86400000);
}

function getLunarMonthDayInfo(date: Date) {
  const parts = new Intl.DateTimeFormat('zh-CN-u-ca-chinese', { month: 'long', day: 'numeric' }).formatToParts(date);
  const month = parts.find(part => part.type === 'month')?.value;
  const day = parts.find(part => part.type === 'day')?.value;
  if (!month || !day) {
    return null;
  }

  return {
    month,
    day,
    isLeapMonth: month.startsWith('闰'),
    key: `${month}|${day}`,
  };
}

function getLunarBirthdayCountdownDays(birthday: string | null) {
  if (!birthday) {
    return null;
  }

  const birthDate = new Date(`${birthday}T00:00:00`);
  if (Number.isNaN(birthDate.getTime())) {
    return null;
  }

  const targetInfo = getLunarMonthDayInfo(birthDate);
  if (!targetInfo) {
    return null;
  }

  const today = new Date();
  const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  for (let offset = 0; offset <= 4000; offset += 1) {
    const candidate = new Date(startOfToday);
    candidate.setDate(startOfToday.getDate() + offset);
    const candidateInfo = getLunarMonthDayInfo(candidate);
    if (candidateInfo && candidateInfo.key === targetInfo.key && candidateInfo.isLeapMonth === targetInfo.isLeapMonth) {
      return offset;
    }
  }

  return null;
}

function formatBirthdayCountdown(days: number | null, isLunarBirthday: boolean) {
  if (days === null) {
    return isLunarBirthday ? '暂未匹配到下一个农历生日' : '未设置生日';
  }

  if (days === 0) return '今天生日';
  if (days === 1) return '明天生日';
  return `${days} 天后生日`;
}

function getMemberRoleOptions() {
  return [
    { value: 'admin' as const, label: '管理员' },
    { value: 'adult' as const, label: '成人' },
    { value: 'child' as const, label: '儿童' },
    { value: 'elder' as const, label: '长辈' },
    { value: 'guest' as const, label: '访客' },
  ];
}

function getAgeGroupOptionsForRole(role: Member['role']) {
  switch (role) {
    case 'child':
      return [
        { value: 'toddler' as const, label: '幼儿' },
        { value: 'child' as const, label: '儿童' },
        { value: 'teen' as const, label: '青少年' },
      ];
    case 'elder':
      return [{ value: 'elder' as const, label: '长辈' }];
    default:
      return [{ value: 'adult' as const, label: '成人' }];
  }
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
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [createErrors, setCreateErrors] = useState<{ name?: string }>({});
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [toastMessage, setToastMessage] = useState('');
  const [pendingScrollRoomId, setPendingScrollRoomId] = useState<string | null>(null);

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

  useEffect(() => {
    if (!toastMessage) {
      return;
    }

    const timer = window.setTimeout(() => setToastMessage(''), 2200);
    return () => window.clearTimeout(timer);
  }, [toastMessage]);

  useEffect(() => {
    if (!isCreateModalOpen) {
      return;
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsCreateModalOpen(false);
        setCreateErrors({});
        setError('');
      }
    }

    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isCreateModalOpen]);

  useEffect(() => {
    if (!pendingScrollRoomId || !rooms.some(room => room.id === pendingScrollRoomId)) {
      return;
    }

    const timer = window.setTimeout(() => {
      const element = document.getElementById(`family-room-card-${pendingScrollRoomId}`);
      element?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setPendingScrollRoomId(null);
    }, 120);

    return () => window.clearTimeout(timer);
  }, [pendingScrollRoomId, rooms]);

  function validateCreateRoomForm() {
    const nextErrors: { name?: string } = {};

    if (!createForm.name.trim()) {
      nextErrors.name = '请输入房间名称';
    }

    setCreateErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleCreateRoom(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId) {
      setError('请先选择家庭。');
      return;
    }
    if (!validateCreateRoomForm()) {
      return;
    }
    try {
      setError('');
      const createdRoom = await api.createRoom({ household_id: currentHouseholdId, ...createForm, name: createForm.name.trim() });
      setCreateForm({ name: '', room_type: 'living_room', privacy_level: 'public' });
      setCreateErrors({});
      setIsCreateModalOpen(false);
      setPendingScrollRoomId(createdRoom.id);
      await refreshWorkspace();
      setStatus('房间已创建。');
      setToastMessage('房间已创建');
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : '创建房间失败');
    }
  }

  function openCreateRoomModal() {
    setError('');
    setStatus('');
    setCreateErrors({});
    setIsCreateModalOpen(true);
  }

  function closeCreateRoomModal() {
    setIsCreateModalOpen(false);
    setError('');
    setCreateErrors({});
  }

  return (
    <div className="family-rooms">
      {toastMessage && <div className="page-toast">{toastMessage}</div>}
      <div className="member-page-toolbar">
        <div>
          <h2 className="member-page-toolbar__title">房间列表</h2>
          <p className="member-page-toolbar__desc">在这里查看家庭空间，并按需补充新的房间。</p>
        </div>
        <button className="btn btn--primary" type="button" onClick={openCreateRoomModal}>新增房间</button>
      </div>
      {(status || error) && <div className="text-text-secondary" style={{ marginBottom: '1rem' }}>{error || status}</div>}
      <div className="room-grid">
        {loading && roomCards.length === 0 ? <div className="text-text-secondary">正在加载房间数据...</div> : roomCards.map(room => (
          <Card key={room.id} className="room-detail-card">
            <div id={`family-room-card-${room.id}`} className="card-scroll-anchor" />
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
      {isCreateModalOpen && (
        <div className="member-modal-overlay" onClick={closeCreateRoomModal}>
          <div className="member-modal" onClick={event => event.stopPropagation()}>
            <div className="member-modal__header">
              <div>
                <h3>新增房间</h3>
                <p>填写房间名称和类型后，会直接加入当前家庭空间。</p>
              </div>
              <button className="card-action-btn" type="button" onClick={closeCreateRoomModal}>{t('common.cancel')}</button>
            </div>
            <form className="settings-form" onSubmit={handleCreateRoom} noValidate>
              <div className="form-group">
                <label>房间名称</label>
                <input
                  className={`form-input${createErrors.name ? ' form-input--error' : ''}`}
                  value={createForm.name}
                  onChange={event => {
                    const value = event.target.value;
                    setCreateForm(current => ({ ...current, name: value }));
                    if (createErrors.name) {
                      setCreateErrors(current => ({ ...current, name: value.trim() ? '' : '请输入房间名称' }));
                    }
                  }}
                />
                {createErrors.name && <div className="form-error">{createErrors.name}</div>}
              </div>
              <div className="form-group">
                <label>房间类型</label>
                <select className="form-select" value={createForm.room_type} onChange={event => setCreateForm(current => ({ ...current, room_type: event.target.value as Room['room_type'] }))}>
                  {ROOM_TYPE_OPTIONS.map(option => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
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
              <div className="member-modal__actions">
                <button className="btn btn--outline" type="button" onClick={closeCreateRoomModal}>{t('common.cancel')}</button>
                <button className="btn btn--primary" type="submit">新增房间</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

/* ---- 成员页 ---- */
export function FamilyMembers() {
  const { t } = useI18n();
  const { members, overview, preferencesByMemberId, loading, refreshWorkspace } = useFamilyWorkspace();
  const { currentHouseholdId } = useHouseholdContext();
  const [createForm, setCreateForm] = useState({ name: '', nickname: '', gender: '' as '' | 'male' | 'female', role: 'adult' as Member['role'], age_group: 'adult' as NonNullable<Member['age_group']>, birthday: '', birthday_is_lunar: false, phone: '', status: 'active' as Member['status'], guardian_member_id: '' });
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [createErrors, setCreateErrors] = useState<{ name?: string; phone?: string; guardian_member_id?: string }>({});
  const [editingMemberId, setEditingMemberId] = useState<string | null>(null);
  const [editingMemberDraft, setEditingMemberDraft] = useState({ nickname: '', gender: '' as '' | 'male' | 'female', role: 'adult' as Member['role'], age_group: 'adult' as NonNullable<Member['age_group']>, birthday: '', birthday_is_lunar: false, phone: '', status: 'active' as Member['status'], guardian_member_id: '' });
  const [editingPreferencesMemberId, setEditingPreferencesMemberId] = useState<string | null>(null);
  const [preferencesDraft, setPreferencesDraft] = useState({ preferred_name: '', reminder_channel: '', sleep_start: '', sleep_end: '' });
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [toastMessage, setToastMessage] = useState('');
  const [pendingScrollMemberId, setPendingScrollMemberId] = useState<string | null>(null);
  const guardianCandidates = useMemo(
    () => members.filter(member => member.id !== editingMemberId && member.status === 'active' && (member.role === 'admin' || member.role === 'adult')),
    [editingMemberId, members],
  );
  const createAgeGroupOptions = useMemo(() => getAgeGroupOptionsForRole(createForm.role), [createForm.role]);
  const createStatusOptions = useMemo(() => getAllowedStatusOptions(createForm.role), [createForm.role]);
  const editingAgeGroupOptions = useMemo(() => getAgeGroupOptionsForRole(editingMemberDraft.role), [editingMemberDraft.role]);
  const editingStatusOptions = useMemo(() => getAllowedStatusOptions(editingMemberDraft.role), [editingMemberDraft.role]);
  const sortedMembers = useMemo(
    () => [...members].sort((left, right) => {
      if (left.status !== right.status) {
        return left.status === 'active' ? -1 : 1;
      }
      return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime();
    }),
    [members],
  );

  useEffect(() => {
    if (!toastMessage) {
      return;
    }

    const timer = window.setTimeout(() => setToastMessage(''), 2200);
    return () => window.clearTimeout(timer);
  }, [toastMessage]);

  useEffect(() => {
    if (!isCreateModalOpen) {
      return;
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsCreateModalOpen(false);
        setCreateErrors({});
        setError('');
      }
    }

    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isCreateModalOpen]);

  useEffect(() => {
    if (!pendingScrollMemberId || !members.some(member => member.id === pendingScrollMemberId)) {
      return;
    }

    const timer = window.setTimeout(() => {
      const element = document.getElementById(`family-member-card-${pendingScrollMemberId}`);
      element?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setPendingScrollMemberId(null);
    }, 120);

    return () => window.clearTimeout(timer);
  }, [members, pendingScrollMemberId]);

  useEffect(() => {
    const inferredAgeGroup = inferAgeGroupFromBirthday(createForm.birthday);
    const allowedAgeGroups = getAgeGroupOptionsForRole(createForm.role).map(option => option.value);

    if (inferredAgeGroup && allowedAgeGroups.includes(inferredAgeGroup)) {
      if (createForm.age_group !== inferredAgeGroup) {
        setCreateForm(current => ({ ...current, age_group: inferredAgeGroup }));
      }
      return;
    }

    if (!allowedAgeGroups.includes(createForm.age_group)) {
      setCreateForm(current => ({ ...current, age_group: allowedAgeGroups[0] }));
    }
  }, [createForm.age_group, createForm.birthday, createForm.role]);

  useEffect(() => {
    if (!roleNeedsGuardian(createForm.role) && createForm.guardian_member_id) {
      setCreateForm(current => ({ ...current, guardian_member_id: '' }));
    }

    if (!roleNeedsGuardian(createForm.role) && createErrors.guardian_member_id) {
      setCreateErrors(current => ({ ...current, guardian_member_id: '' }));
    }

    if (!getAllowedStatusOptions(createForm.role).some(option => option.value === createForm.status)) {
      setCreateForm(current => ({ ...current, status: 'active' }));
    }
  }, [createErrors.guardian_member_id, createForm.guardian_member_id, createForm.role, createForm.status]);

  useEffect(() => {
    const inferredAgeGroup = inferAgeGroupFromBirthday(editingMemberDraft.birthday);
    const allowedAgeGroups = getAgeGroupOptionsForRole(editingMemberDraft.role).map(option => option.value);

    if (inferredAgeGroup && allowedAgeGroups.includes(inferredAgeGroup)) {
      if (editingMemberDraft.age_group !== inferredAgeGroup) {
        setEditingMemberDraft(current => ({ ...current, age_group: inferredAgeGroup }));
      }
      return;
    }

    if (!allowedAgeGroups.includes(editingMemberDraft.age_group)) {
      setEditingMemberDraft(current => ({ ...current, age_group: allowedAgeGroups[0] }));
    }
  }, [editingMemberDraft.age_group, editingMemberDraft.birthday, editingMemberDraft.role]);

  useEffect(() => {
    if (!roleNeedsGuardian(editingMemberDraft.role) && editingMemberDraft.guardian_member_id) {
      setEditingMemberDraft(current => ({ ...current, guardian_member_id: '' }));
    }

    if (!getAllowedStatusOptions(editingMemberDraft.role).some(option => option.value === editingMemberDraft.status)) {
      setEditingMemberDraft(current => ({ ...current, status: 'active' }));
    }
  }, [editingMemberDraft.guardian_member_id, editingMemberDraft.role, editingMemberDraft.status]);

  function validateCreateMemberForm() {
    const nextErrors: { name?: string; phone?: string; guardian_member_id?: string } = {};

    if (!createForm.name.trim()) {
      nextErrors.name = '请输入成员姓名';
    }

    const phoneError = validatePhoneNumber(createForm.phone);
    if (phoneError) {
      nextErrors.phone = phoneError;
    }

    if (roleNeedsGuardian(createForm.role) && !createForm.guardian_member_id) {
      nextErrors.guardian_member_id = '儿童成员需要指定监护人';
    }

    setCreateErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleCreateMember(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId) {
      setError('请先选择家庭。');
      return;
    }
    if (!validateCreateMemberForm()) {
      return;
    }

    try {
      setError('');
      const createdMember = await api.createMember({
        household_id: currentHouseholdId,
        name: createForm.name.trim(),
        nickname: createForm.nickname || null,
        gender: createForm.gender || null,
        role: createForm.role,
        age_group: createForm.age_group,
        birthday: createForm.birthday || null,
        phone: createForm.phone.trim() || null,
        status: createForm.status,
        guardian_member_id: createForm.guardian_member_id || null,
      });
      await api.upsertMemberPreferences(createdMember.id, {
        preferred_name: null,
        light_preference: null,
        climate_preference: null,
        content_preference: null,
        reminder_channel_preference: null,
        sleep_schedule: null,
        birthday_is_lunar: createForm.birthday_is_lunar,
      });
      setCreateForm({ name: '', nickname: '', gender: '', role: 'adult', age_group: 'adult', birthday: '', birthday_is_lunar: false, phone: '', status: 'active', guardian_member_id: '' });
      setCreateErrors({});
      setIsCreateModalOpen(false);
      setPendingScrollMemberId(createdMember.id);
      await refreshWorkspace();
      setStatus('成员已创建。');
      setToastMessage('成员已创建');
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : '创建成员失败');
    }
  }

  function openCreateMemberModal() {
    setEditingMemberId(null);
    setEditingPreferencesMemberId(null);
    setError('');
    setStatus('');
    setCreateErrors({});
    setIsCreateModalOpen(true);
  }

  function closeCreateMemberModal() {
    setIsCreateModalOpen(false);
    setError('');
    setCreateErrors({});
  }

  function openPreferencesEditor(member: Member) {
    const preference = preferencesByMemberId[member.id];
    const sleepSchedule = preference?.sleep_schedule;
    const sleepStart = sleepSchedule && typeof sleepSchedule === 'object' && 'start' in sleepSchedule ? String((sleepSchedule as { start?: unknown }).start ?? '') : '';
    const sleepEnd = sleepSchedule && typeof sleepSchedule === 'object' && 'end' in sleepSchedule ? String((sleepSchedule as { end?: unknown }).end ?? '') : '';

    setEditingPreferencesMemberId(member.id);
    setEditingMemberId(null);
    setPreferencesDraft({
      preferred_name: preference?.preferred_name ?? member.nickname ?? '',
      reminder_channel: preference?.reminder_channel_preference ? JSON.stringify(preference.reminder_channel_preference) : '',
      sleep_start: sleepStart,
      sleep_end: sleepEnd,
    });
    setStatus('');
    setError('');
  }

  function openMemberEditor(member: Member) {
    setEditingPreferencesMemberId(null);
    setEditingMemberId(member.id);
    setEditingMemberDraft({
      nickname: member.nickname ?? '',
      gender: member.gender ?? '',
      role: member.role,
      age_group: member.age_group ?? 'adult',
      birthday: member.birthday ?? '',
      birthday_is_lunar: preferencesByMemberId[member.id]?.birthday_is_lunar ?? false,
      phone: member.phone ?? '',
      status: member.status,
      guardian_member_id: member.guardian_member_id ?? '',
    });
    setStatus('');
    setError('');
  }

  async function handleSaveMember() {
    if (!editingMemberId) {
      return;
    }

    if (roleNeedsGuardian(editingMemberDraft.role) && !editingMemberDraft.guardian_member_id) {
      setError('儿童成员需要指定监护人后才能保存。');
      return;
    }

    const phoneError = validatePhoneNumber(editingMemberDraft.phone);
    if (phoneError) {
      setError(phoneError);
      return;
    }

    try {
      setError('');
      await api.updateMember(editingMemberId, {
        nickname: editingMemberDraft.nickname || null,
        gender: editingMemberDraft.gender || null,
        role: editingMemberDraft.role,
        age_group: editingMemberDraft.age_group,
        birthday: editingMemberDraft.birthday || null,
        phone: editingMemberDraft.phone || null,
        status: editingMemberDraft.status,
        guardian_member_id: editingMemberDraft.guardian_member_id || null,
      });
      await api.upsertMemberPreferences(editingMemberId, {
        preferred_name: preferencesByMemberId[editingMemberId]?.preferred_name ?? null,
        light_preference: preferencesByMemberId[editingMemberId]?.light_preference ?? null,
        climate_preference: preferencesByMemberId[editingMemberId]?.climate_preference ?? null,
        content_preference: preferencesByMemberId[editingMemberId]?.content_preference ?? null,
        reminder_channel_preference: preferencesByMemberId[editingMemberId]?.reminder_channel_preference ?? null,
        sleep_schedule: preferencesByMemberId[editingMemberId]?.sleep_schedule ?? null,
        birthday_is_lunar: editingMemberDraft.birthday_is_lunar,
      });
      await refreshWorkspace();
      setEditingMemberId(null);
      setStatus('成员信息已保存。');
      setToastMessage('成员信息已保存');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存成员信息失败');
    }
  }

  async function handleToggleMemberStatus(member: Member) {
    const nextStatus: Member['status'] = member.status === 'active' ? 'inactive' : 'active';

    if (nextStatus === 'inactive') {
      const confirmed = window.confirm(`确认停用成员“${member.name}”吗？停用后该成员会保留在列表里，但状态会变成停用。`);
      if (!confirmed) {
        return;
      }
    }

    try {
      setError('');
      await api.updateMember(member.id, { status: nextStatus });
      await refreshWorkspace();
      if (editingMemberId === member.id) {
        setEditingMemberId(null);
      }
      setStatus(nextStatus === 'inactive' ? '成员已停用。' : '成员已启用。');
      setToastMessage(nextStatus === 'inactive' ? '成员已停用' : '成员已启用');
    } catch (toggleError) {
      setError(toggleError instanceof Error ? toggleError.message : `${nextStatus === 'inactive' ? '停用' : '启用'}成员失败`);
    }
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
        birthday_is_lunar: preferencesByMemberId[editingPreferencesMemberId]?.birthday_is_lunar ?? false,
      });
      await refreshWorkspace();
      setEditingPreferencesMemberId(null);
      setStatus('成员偏好已保存。');
      setToastMessage('成员偏好已保存');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存成员偏好失败');
    }
  }

  return (
    <div className="family-members">
      {toastMessage && <div className="page-toast">{toastMessage}</div>}
      <div className="member-page-toolbar">
        <div>
          <h2 className="member-page-toolbar__title">成员列表</h2>
          <p className="member-page-toolbar__desc">在这里查看家庭成员，并按需编辑、停用或维护偏好。</p>
        </div>
        <button className="btn btn--primary" type="button" onClick={openCreateMemberModal}>新增成员</button>
      </div>
      {(status || error) && <div className="text-text-secondary" style={{ marginBottom: '1rem' }}>{error || status}</div>}
      <div className="member-detail-grid">
        {loading && sortedMembers.length === 0 ? <div className="text-text-secondary">正在加载成员数据...</div> : sortedMembers.map(member => {
          const status = getMemberStatus(member.id, overview);
          const isEditingMember = editingMemberId === member.id;
          const isInactiveMember = member.status === 'inactive';
          const isLunarBirthday = preferencesByMemberId[member.id]?.birthday_is_lunar ?? false;
          const age = getAgeFromBirthday(member.birthday);
          const birthdayCountdownDays = isLunarBirthday ? getLunarBirthdayCountdownDays(member.birthday) : getBirthdayCountdownDays(member.birthday);
          const birthdayCountdown = formatBirthdayCountdown(birthdayCountdownDays, isLunarBirthday);
          const isBirthdaySoon = birthdayCountdownDays !== null && birthdayCountdownDays >= 0 && birthdayCountdownDays <= 7;

          return (
            <Card key={member.id} className={`member-detail-card${isInactiveMember ? ' member-detail-card--inactive' : ''}${isBirthdaySoon ? ' member-detail-card--birthday-soon' : ''}`}>
              <div id={`family-member-card-${member.id}`} className="card-scroll-anchor" />
              <div className="member-detail-card__top">
                <div className="member-detail-card__avatar">
                  {member.role === 'elder' ? '👵' : member.role === 'child' ? '👦' : member.role === 'guest' ? '🧑' : '👨'}
                </div>
                <div className="member-detail-card__info">
                  <div className="member-detail-card__name-row">
                    <h3 className="member-detail-card__name">{member.name}</h3>
                    {isInactiveMember && <span className="badge badge--inactive">已停用</span>}
                  </div>
                  <span className="member-detail-card__role">{formatRole(member.role)}</span>
                </div>
                <span className={`badge badge--${status === 'home' ? 'success' : status === 'resting' ? 'warning' : 'secondary'}`}>
                  {status === 'home' ? t('member.atHome') : status === 'resting' ? t('member.resting') : t('member.away')}
                </span>
              </div>
              <div className="member-detail-card__meta">
                <span className={`birthday-kind-badge ${isLunarBirthday ? 'birthday-kind-badge--lunar' : 'birthday-kind-badge--solar'}`}>
                  {isLunarBirthday ? '农历生日' : '公历生日'}
                </span>
                <span className="meta-item">🎂 {member.birthday ?? '未设置生日'}</span>
                <span className="meta-item">🧮 {age === null ? '年龄待补充' : `${age} 岁`}</span>
                <span className="meta-item">🎉 {birthdayCountdown}</span>
                {isBirthdaySoon && <span className="meta-item meta-item--highlight">✨ 生日快到了</span>}
              </div>
              <p className="member-detail-card__prefs">{formatPreferenceSummary(preferencesByMemberId[member.id])}</p>
              <div className="member-detail-card__actions">
                <button className="card-action-btn" type="button" onClick={() => isEditingMember ? setEditingMemberId(null) : openMemberEditor(member)}>
                  {isEditingMember ? t('common.cancel') : t('member.edit')}
                </button>
                <button className="card-action-btn" type="button" onClick={() => void handleToggleMemberStatus(member)}>
                  {member.status === 'active' ? '停用成员' : '启用成员'}
                </button>
                <button className="card-action-btn" type="button" onClick={() => openPreferencesEditor(member)}>{t('member.preferences')}</button>
              </div>
              {isEditingMember && (
                <div className="settings-form" style={{ marginTop: '1rem' }}>
                  <div className="form-group">
                    <label>昵称</label>
                    <input className="form-input" value={editingMemberDraft.nickname} onChange={event => setEditingMemberDraft(current => ({ ...current, nickname: event.target.value }))} />
                  </div>
                  <div className="form-group">
                    <label>性别</label>
                    <select className="form-select" value={editingMemberDraft.gender} onChange={event => setEditingMemberDraft(current => ({ ...current, gender: event.target.value as '' | 'male' | 'female' }))}>
                      <option value="">未设置</option>
                      <option value="male">男</option>
                      <option value="female">女</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>角色</label>
                    <select className="form-select" value={editingMemberDraft.role} onChange={event => setEditingMemberDraft(current => ({ ...current, role: event.target.value as Member['role'] }))}>
                      {getMemberRoleOptions().map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>年龄分组</label>
                    <select className="form-select" value={editingMemberDraft.age_group} disabled={Boolean(editingMemberDraft.birthday)} onChange={event => setEditingMemberDraft(current => ({ ...current, age_group: event.target.value as NonNullable<Member['age_group']> }))}>
                      {editingAgeGroupOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                    {editingMemberDraft.birthday && <div className="form-help">已根据生日自动计算年龄分组</div>}
                  </div>
                  <div className="form-group">
                    <label>生日</label>
                    <input className="form-input" type="date" value={editingMemberDraft.birthday} onChange={event => setEditingMemberDraft(current => ({ ...current, birthday: event.target.value }))} />
                  </div>
                  <label className="toggle-row member-inline-toggle">
                    <div className="toggle-row__text">
                      <span className="toggle-row__label">按农历生日提醒</span>
                    </div>
                    <div className={`toggle-switch ${editingMemberDraft.birthday_is_lunar ? 'toggle-switch--on' : ''}`} onClick={() => setEditingMemberDraft(current => ({ ...current, birthday_is_lunar: !current.birthday_is_lunar }))}>
                      <div className="toggle-switch__thumb" />
                    </div>
                  </label>
                  <div className="form-group">
                    <label>手机号</label>
                    <input className="form-input" value={editingMemberDraft.phone} onChange={event => setEditingMemberDraft(current => ({ ...current, phone: event.target.value }))} />
                  </div>
                  <div className="form-group">
                    <label>状态</label>
                    <select className="form-select" value={editingMemberDraft.status} onChange={event => setEditingMemberDraft(current => ({ ...current, status: event.target.value as Member['status'] }))}>
                      {editingStatusOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                    {editingMemberDraft.role === 'admin' && <div className="form-help">管理员默认保持启用，避免影响家庭管理</div>}
                  </div>
                  {roleNeedsGuardian(editingMemberDraft.role) && (
                    <div className="form-group">
                      <label>监护人</label>
                      <select className="form-select" value={editingMemberDraft.guardian_member_id} onChange={event => setEditingMemberDraft(current => ({ ...current, guardian_member_id: event.target.value }))}>
                        <option value="">请选择监护人</option>
                        {guardianCandidates.map(candidate => <option key={candidate.id} value={candidate.id}>{candidate.name}（{formatRole(candidate.role)}）</option>)}
                      </select>
                      <div className="form-help">儿童角色需要绑定一位已启用的成人或管理员</div>
                    </div>
                  )}
                  <div style={{ display: 'flex', gap: '0.75rem' }}>
                    <button className="btn btn--primary" type="button" onClick={() => void handleSaveMember()}>{t('common.save')}</button>
                    <button className="btn btn--outline" type="button" onClick={() => setEditingMemberId(null)}>{t('common.cancel')}</button>
                  </div>
                </div>
              )}
            </Card>
          );
        })}
      </div>
      {isCreateModalOpen && (
        <div className="member-modal-overlay" onClick={closeCreateMemberModal}>
          <div className="member-modal" onClick={event => event.stopPropagation()}>
            <div className="member-modal__header">
              <div>
                <h3>新增成员</h3>
                <p>填写基础信息后，成员会直接加入当前家庭。</p>
              </div>
              <button className="card-action-btn" type="button" onClick={closeCreateMemberModal}>{t('common.cancel')}</button>
            </div>
            <form className="settings-form" onSubmit={handleCreateMember} noValidate>
              <div className="form-group">
                <label>姓名</label>
                <input
                  className={`form-input${createErrors.name ? ' form-input--error' : ''}`}
                  value={createForm.name}
                  onChange={event => {
                    const value = event.target.value;
                    setCreateForm(current => ({ ...current, name: value }));
                    if (createErrors.name) {
                      setCreateErrors(current => ({ ...current, name: value.trim() ? '' : '请输入成员姓名' }));
                    }
                  }}
                />
                {createErrors.name && <div className="form-error">{createErrors.name}</div>}
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
                  {getMemberRoleOptions().map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>年龄分组</label>
                <select className="form-select" value={createForm.age_group} disabled={Boolean(createForm.birthday)} onChange={event => setCreateForm(current => ({ ...current, age_group: event.target.value as NonNullable<Member['age_group']> }))}>
                  {createAgeGroupOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
                {createForm.birthday && <div className="form-help">已根据生日自动计算年龄分组</div>}
              </div>
              <div className="form-group">
                <label>生日</label>
                <input className="form-input" type="date" value={createForm.birthday} onChange={event => setCreateForm(current => ({ ...current, birthday: event.target.value }))} />
              </div>
              <label className="toggle-row member-inline-toggle">
                <div className="toggle-row__text">
                  <span className="toggle-row__label">按农历生日提醒</span>
                </div>
                <div className={`toggle-switch ${createForm.birthday_is_lunar ? 'toggle-switch--on' : ''}`} onClick={() => setCreateForm(current => ({ ...current, birthday_is_lunar: !current.birthday_is_lunar }))}>
                  <div className="toggle-switch__thumb" />
                </div>
              </label>
              <div className="form-group">
                <label>手机号</label>
                <input
                  className={`form-input${createErrors.phone ? ' form-input--error' : ''}`}
                  value={createForm.phone}
                  onChange={event => {
                    const value = event.target.value;
                    setCreateForm(current => ({ ...current, phone: value }));
                    if (createErrors.phone) {
                      setCreateErrors(current => ({ ...current, phone: validatePhoneNumber(value) || '' }));
                    }
                  }}
                />
                {createErrors.phone && <div className="form-error">{createErrors.phone}</div>}
              </div>
              <div className="form-group">
                <label>状态</label>
                <select className="form-select" value={createForm.status} onChange={event => setCreateForm(current => ({ ...current, status: event.target.value as Member['status'] }))}>
                  {createStatusOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
                {createForm.role === 'admin' && <div className="form-help">管理员默认保持启用，避免影响家庭管理</div>}
              </div>
              {roleNeedsGuardian(createForm.role) && (
                <div className="form-group">
                  <label>监护人</label>
                  <select className={`form-select${createErrors.guardian_member_id ? ' form-select--error' : ''}`} value={createForm.guardian_member_id} onChange={event => {
                    const value = event.target.value;
                    setCreateForm(current => ({ ...current, guardian_member_id: value }));
                    if (createErrors.guardian_member_id) {
                      setCreateErrors(current => ({ ...current, guardian_member_id: value ? '' : '儿童成员需要指定监护人' }));
                    }
                  }}>
                    <option value="">请选择监护人</option>
                    {guardianCandidates.map(candidate => <option key={candidate.id} value={candidate.id}>{candidate.name}（{formatRole(candidate.role)}）</option>)}
                  </select>
                  {createErrors.guardian_member_id ? <div className="form-error">{createErrors.guardian_member_id}</div> : <div className="form-help">儿童角色需要绑定一位已启用的成人或管理员</div>}
                </div>
              )}
              <div className="member-modal__actions">
                <button className="btn btn--outline" type="button" onClick={closeCreateMemberModal}>{t('common.cancel')}</button>
                <button className="btn btn--primary" type="submit">新增成员</button>
              </div>
            </form>
          </div>
        </div>
      )}
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
  grandfather_maternal: '外孙', grandmother_maternal: '外孙',
  grandson: '孙子', granddaughter: '孙子',
  guardian: '监护', ward: '监护',
  caregiver: '照护',
};

/* 根据成员角色筛选可选的关系类型 */
function coalesceGender(...genders: Array<Member['gender'] | undefined>): Member['gender'] {
  for (const gender of genders) {
    if (gender === 'male' || gender === 'female') {
      return gender;
    }
  }
  return null;
}

function inferRoleGender(
  relationType: MemberRelationship['relation_type'] | undefined,
  role: 'source' | 'target',
): Member['gender'] {
  if (role === 'source') {
    return null;
  }

  switch (relationType) {
    case 'husband':
    case 'father':
    case 'son':
    case 'older_brother':
    case 'younger_brother':
    case 'grandfather_paternal':
    case 'grandfather_maternal':
    case 'grandson':
      return 'male';
    case 'wife':
    case 'mother':
    case 'daughter':
    case 'older_sister':
    case 'younger_sister':
    case 'grandmother_paternal':
    case 'grandmother_maternal':
    case 'granddaughter':
      return 'female';
    default:
      return null;
  }
}

function getResolvedPairGender(
  member: Member | undefined,
  relationType: MemberRelationship['relation_type'],
  reverseRelationType: MemberRelationship['relation_type'] | undefined,
  role: 'source' | 'target',
): Member['gender'] {
  const reverseRole = role === 'source' ? 'target' : 'source';
  return coalesceGender(
    member?.gender,
    inferRoleGender(relationType, role),
    inferRoleGender(reverseRelationType, reverseRole),
  );
}

function getSpouseCategoryLabel(firstGender: Member['gender'], secondGender: Member['gender']) {
  if (firstGender === 'male' && secondGender === 'male') return '夫夫';
  if (firstGender === 'female' && secondGender === 'female') return '妻妻';
  if (
    (firstGender === 'male' && secondGender === 'female')
    || (firstGender === 'female' && secondGender === 'male')
  ) {
    return '夫妻';
  }
  return '伴侣';
}

function getParentChildCategoryLabel(parentGender: Member['gender'], childGender: Member['gender']) {
  if (parentGender === 'male') {
    if (childGender === 'male') return '父子';
    if (childGender === 'female') return '父女';
    return '父子/父女';
  }

  if (parentGender === 'female') {
    if (childGender === 'male') return '母子';
    if (childGender === 'female') return '母女';
    return '母子/母女';
  }

  if (childGender === 'male') return '父子/母子';
  if (childGender === 'female') return '父女/母女';
  return '亲子';
}

function getSiblingCategoryLabel(olderGender: Member['gender'], youngerGender: Member['gender']) {
  if (olderGender === 'male') {
    if (youngerGender === 'male') return '兄弟';
    if (youngerGender === 'female') return '兄妹';
    return '兄弟/兄妹';
  }

  if (olderGender === 'female') {
    if (youngerGender === 'male') return '姐弟';
    if (youngerGender === 'female') return '姐妹';
    return '姐弟/姐妹';
  }

  if (youngerGender === 'male') return '兄弟/姐弟';
  if (youngerGender === 'female') return '兄妹/姐妹';
  return '手足';
}

function inferGrandparentSide(
  relationType: MemberRelationship['relation_type'],
  reverseRelationType: MemberRelationship['relation_type'] | undefined,
): 'paternal' | 'maternal' | null {
  if (
    relationType === 'grandfather_maternal'
    || relationType === 'grandmother_maternal'
    || reverseRelationType === 'grandfather_maternal'
    || reverseRelationType === 'grandmother_maternal'
  ) {
    return 'maternal';
  }

  if (
    relationType === 'grandfather_paternal'
    || relationType === 'grandmother_paternal'
    || reverseRelationType === 'grandfather_paternal'
    || reverseRelationType === 'grandmother_paternal'
  ) {
    return 'paternal';
  }

  return null;
}

function getGrandparentCategoryLabel(
  grandchildGender: Member['gender'],
  side: 'paternal' | 'maternal' | null,
) {
  const maleLabel = side === 'maternal' ? '外孙' : '孙子';
  const femaleLabel = side === 'maternal' ? '外孙女' : '孙女';

  if (grandchildGender === 'male') return maleLabel;
  if (grandchildGender === 'female') return femaleLabel;
  return `${maleLabel}/${femaleLabel}`;
}

function getRelationCategoryLabel(
  relationship: MemberRelationship,
  reverseRelationship: MemberRelationship | undefined,
  sourceMember?: Member,
  targetMember?: Member,
) {
  const relationType = relationship.relation_type;
  const reverseRelationType = reverseRelationship?.relation_type;
  const sourceGender = getResolvedPairGender(sourceMember, relationType, reverseRelationType, 'source');
  const targetGender = getResolvedPairGender(targetMember, relationType, reverseRelationType, 'target');

  switch (relationType) {
    case 'husband':
    case 'wife':
    case 'spouse':
      return getSpouseCategoryLabel(sourceGender, targetGender);
    case 'father':
    case 'mother':
    case 'parent':
      return getParentChildCategoryLabel(targetGender, sourceGender);
    case 'son':
    case 'daughter':
    case 'child':
      return getParentChildCategoryLabel(sourceGender, targetGender);
    case 'older_brother':
    case 'older_sister':
      return getSiblingCategoryLabel(targetGender, sourceGender);
    case 'younger_brother':
    case 'younger_sister':
      return getSiblingCategoryLabel(sourceGender, targetGender);
    case 'grandfather_paternal':
    case 'grandmother_paternal':
    case 'grandfather_maternal':
    case 'grandmother_maternal':
      return getGrandparentCategoryLabel(
        sourceGender,
        inferGrandparentSide(relationType, reverseRelationType),
      );
    case 'grandson':
    case 'granddaughter':
      return getGrandparentCategoryLabel(
        targetGender,
        inferGrandparentSide(relationType, reverseRelationType),
      );
    case 'guardian':
    case 'ward':
      return '监护';
    case 'caregiver':
      return '照护';
    default:
      return RELATION_CATEGORY_LABELS[relationType] ?? relationType;
  }
}

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
  const memberMap = new Map(members.map(member => [member.id, member] as const));
  const relationshipMap = new Map(relationships.map(relationship => [
    `${relationship.source_member_id}|${relationship.target_member_id}`,
    relationship,
  ] as const));

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
        label: getRelationCategoryLabel(
          rel,
          relationshipMap.get(`${rel.target_member_id}|${rel.source_member_id}`),
          memberMap.get(rel.source_member_id),
          memberMap.get(rel.target_member_id),
        ),
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

const DYNAMIC_GRAPH_WIDTH = 760;
const DYNAMIC_GRAPH_HEIGHT = 520;
const DYNAMIC_GRAPH_CENTER = { x: DYNAMIC_GRAPH_WIDTH / 2, y: DYNAMIC_GRAPH_HEIGHT / 2 };
const DYNAMIC_GRAPH_PADDING = 56;
const DYNAMIC_GRAPH_NODE_RADIUS = 30;

type DynamicGraphNode = {
  id: string;
  name: string;
  role: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
};

type DynamicGraphEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
  relationType: string;
};

type DynamicGraphPoint = {
  x: number;
  y: number;
};

type GraphViewport = {
  scale: number;
  x: number;
  y: number;
};

function clampGraphValue(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function clampGraphPoint(point: DynamicGraphPoint): DynamicGraphPoint {
  return {
    x: clampGraphValue(point.x, DYNAMIC_GRAPH_PADDING, DYNAMIC_GRAPH_WIDTH - DYNAMIC_GRAPH_PADDING),
    y: clampGraphValue(point.y, DYNAMIC_GRAPH_PADDING, DYNAMIC_GRAPH_HEIGHT - DYNAMIC_GRAPH_PADDING),
  };
}

function normalizeViewport(nextViewport: GraphViewport): GraphViewport {
  const scale = clampGraphValue(nextViewport.scale, 0.65, 2.2);
  const scaledWidth = DYNAMIC_GRAPH_WIDTH * scale;
  const scaledHeight = DYNAMIC_GRAPH_HEIGHT * scale;

  const x = scaledWidth <= DYNAMIC_GRAPH_WIDTH
    ? (DYNAMIC_GRAPH_WIDTH - scaledWidth) / 2
    : clampGraphValue(nextViewport.x, DYNAMIC_GRAPH_WIDTH - scaledWidth - 48, 48);
  const y = scaledHeight <= DYNAMIC_GRAPH_HEIGHT
    ? (DYNAMIC_GRAPH_HEIGHT - scaledHeight) / 2
    : clampGraphValue(nextViewport.y, DYNAMIC_GRAPH_HEIGHT - scaledHeight - 48, 48);

  return { scale, x, y };
}

function hashGraphEdge(value: string) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 33 + value.charCodeAt(index)) % 10007;
  }
  return hash;
}

function getGraphUnitVector(from: DynamicGraphPoint, to: DynamicGraphPoint) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const distance = Math.hypot(dx, dy) || 1;
  return {
    x: dx / distance,
    y: dy / distance,
    distance,
  };
}

function getQuadraticCurvePoint(
  start: DynamicGraphPoint,
  control: DynamicGraphPoint,
  end: DynamicGraphPoint,
  t: number,
): DynamicGraphPoint {
  const oneMinusT = 1 - t;
  return {
    x: oneMinusT * oneMinusT * start.x + 2 * oneMinusT * t * control.x + t * t * end.x,
    y: oneMinusT * oneMinusT * start.y + 2 * oneMinusT * t * control.y + t * t * end.y,
  };
}

function getQuadraticCurveNormal(
  start: DynamicGraphPoint,
  control: DynamicGraphPoint,
  end: DynamicGraphPoint,
  t: number,
): DynamicGraphPoint {
  const derivative = {
    x: 2 * (1 - t) * (control.x - start.x) + 2 * t * (end.x - control.x),
    y: 2 * (1 - t) * (control.y - start.y) + 2 * t * (end.y - control.y),
  };
  const length = Math.hypot(derivative.x, derivative.y) || 1;
  return {
    x: -derivative.y / length,
    y: derivative.x / length,
  };
}

function getDynamicEdgeGeometry(source: DynamicGraphPoint, target: DynamicGraphPoint, edgeId: string) {
  const direction = getGraphUnitVector(source, target);
  const start = {
    x: source.x + direction.x * DYNAMIC_GRAPH_NODE_RADIUS,
    y: source.y + direction.y * DYNAMIC_GRAPH_NODE_RADIUS,
  };
  const end = {
    x: target.x - direction.x * DYNAMIC_GRAPH_NODE_RADIUS,
    y: target.y - direction.y * DYNAMIC_GRAPH_NODE_RADIUS,
  };
  const midpoint = {
    x: (start.x + end.x) / 2,
    y: (start.y + end.y) / 2,
  };
  const perpendicular = {
    x: -direction.y,
    y: direction.x,
  };
  const sign = hashGraphEdge(edgeId) % 2 === 0 ? 1 : -1;
  const curvature = clampGraphValue(direction.distance * 0.18, 24, 72);
  const control = {
    x: midpoint.x + perpendicular.x * curvature * sign,
    y: midpoint.y + perpendicular.y * curvature * sign,
  };
  const labelBase = getQuadraticCurvePoint(start, control, end, 0.5);
  const labelNormal = getQuadraticCurveNormal(start, control, end, 0.5);

  return {
    path: `M ${start.x} ${start.y} Q ${control.x} ${control.y} ${end.x} ${end.y}`,
    labelAnchor: {
      x: labelBase.x + labelNormal.x * 18,
      y: labelBase.y + labelNormal.y * 18,
    },
  };
}

function buildDynamicGraphData(
  members: Member[],
  relationships: MemberRelationship[],
): { nodes: DynamicGraphNode[]; edges: DynamicGraphEdge[] } {
  const angle = (2 * Math.PI) / Math.max(members.length, 1);
  const radius = Math.min(210, 80 + members.length * 24);
  const memberMap = new Map(members.map(member => [member.id, member] as const));
  const relationshipMap = new Map<string, MemberRelationship>(relationships.map(relationship => [
    `${relationship.source_member_id}|${relationship.target_member_id}`,
    relationship,
  ] as const));

  const nodes: DynamicGraphNode[] = members.map((member, index) => {
    const seed = hashGraphEdge(`${member.id}-${index}`);
    const angleJitter = ((((seed % 100) / 100) - 0.5) * Math.PI) / 2.4;
    const radiusScale = 0.62 + (((Math.floor(seed / 100) % 100) / 100) * 0.42);
    const offsetX = ((((Math.floor(seed / 10000) % 100) / 100) - 0.5) * 34);
    const offsetY = ((((Math.floor(seed / 1000000) % 100) / 100) - 0.5) * 28);
    const point = clampGraphPoint({
      x: DYNAMIC_GRAPH_CENTER.x + radius * radiusScale * Math.cos(angle * index - Math.PI / 2 + angleJitter) + offsetX,
      y: DYNAMIC_GRAPH_CENTER.y + radius * radiusScale * Math.sin(angle * index - Math.PI / 2 + angleJitter) + offsetY,
    });

    return {
      id: member.id,
      name: member.name,
      role: member.role,
      x: point.x,
      y: point.y,
      vx: 0,
      vy: 0,
    };
  });

  const edgeSet = new Set<string>();
  const edges: DynamicGraphEdge[] = [];
  for (const relationship of relationships) {
    const key = `${relationship.source_member_id}|${relationship.target_member_id}`;
    const reverseKey = `${relationship.target_member_id}|${relationship.source_member_id}` as const;
    if (edgeSet.has(key) || edgeSet.has(reverseKey)) {
      continue;
    }

    edgeSet.add(key);
    edges.push({
      id: [relationship.source_member_id, relationship.target_member_id].sort().join('|'),
      source: relationship.source_member_id,
      target: relationship.target_member_id,
      label: getRelationCategoryLabel(
        relationship,
        relationshipMap.get(reverseKey),
        memberMap.get(relationship.source_member_id),
        memberMap.get(relationship.target_member_id),
      ),
      relationType: relationship.relation_type,
    });
  }

  return { nodes, edges };
}

function DynamicRelationshipGraph({ members, relationships, selectedMemberId, onSelectMember }: {
  members: Member[];
  relationships: MemberRelationship[];
  selectedMemberId: string | null;
  onSelectMember: (id: string | null) => void;
}) {
  const { nodes, edges } = useMemo(
    () => buildDynamicGraphData(members, relationships),
    [members, relationships],
  );
  const svgRef = useRef<SVGSVGElement | null>(null);
  const positionsRef = useRef<Record<string, DynamicGraphPoint>>({});
  const dragMovedRef = useRef(false);
  const viewportRef = useRef<GraphViewport>({
    scale: 1,
    x: 0,
    y: 0,
  });
  const [positions, setPositions] = useState<Record<string, DynamicGraphPoint>>({});
  const [fixedNodes, setFixedNodes] = useState<Record<string, DynamicGraphPoint>>({});
  const [dragState, setDragState] = useState<{ nodeId: string; offsetX: number; offsetY: number } | null>(null);
  const [panState, setPanState] = useState<{ startClientX: number; startClientY: number; startX: number; startY: number } | null>(null);
  const [viewport, setViewport] = useState<GraphViewport>(() => normalizeViewport({
    scale: 1,
    x: 0,
    y: 0,
  }));

  useEffect(() => {
    positionsRef.current = positions;
  }, [positions]);

  useEffect(() => {
    viewportRef.current = viewport;
  }, [viewport]);

  useEffect(() => {
    const nextPositions = Object.fromEntries(
      nodes.map(node => {
        const currentPosition = positionsRef.current[node.id];
        const nextPosition = fixedNodes[node.id] ?? currentPosition ?? { x: node.x, y: node.y };
        return [
          node.id,
          clampGraphPoint(nextPosition),
        ];
      }),
    );
    positionsRef.current = nextPositions;
    setPositions(nextPositions);
  }, [nodes, fixedNodes]);

  useEffect(() => {
    if (nodes.length === 0) {
      return;
    }

    const simNodes = nodes.map(node => {
      const currentPosition = positionsRef.current[node.id] ?? { x: node.x, y: node.y };
      const fixedPosition = fixedNodes[node.id];
      return {
        ...node,
        x: fixedPosition?.x ?? currentPosition.x,
        y: fixedPosition?.y ?? currentPosition.y,
      };
    });
    const nodeMap = Object.fromEntries(simNodes.map(node => [node.id, node]));

    let frame = 0;
    let iterations = 0;
    const maxIterations = 180;

    function tick() {
      for (const node of simNodes) {
        if (fixedNodes[node.id]) {
          node.x = fixedNodes[node.id].x;
          node.y = fixedNodes[node.id].y;
          node.vx = 0;
          node.vy = 0;
          continue;
        }

        node.vx *= 0.86;
        node.vy *= 0.86;
      }

      for (let i = 0; i < simNodes.length; i += 1) {
        for (let j = i + 1; j < simNodes.length; j += 1) {
          const a = simNodes[i];
          const b = simNodes[j];
          let dx = b.x - a.x;
          let dy = b.y - a.y;
          const distance = Math.hypot(dx, dy) || 1;
          const minDistance = 140;
          if (distance >= minDistance) {
            continue;
          }

          const force = (minDistance - distance) * 0.035;
          dx /= distance;
          dy /= distance;
          if (!fixedNodes[a.id]) {
            a.vx -= dx * force;
            a.vy -= dy * force;
          }
          if (!fixedNodes[b.id]) {
            b.vx += dx * force;
            b.vy += dy * force;
          }
        }
      }

      for (const edge of edges) {
        const source = nodeMap[edge.source];
        const target = nodeMap[edge.target];
        if (!source || !target) {
          continue;
        }

        let dx = target.x - source.x;
        let dy = target.y - source.y;
        const distance = Math.hypot(dx, dy) || 1;
        const idealDistance = clampGraphValue(120 + edges.length * 2, 130, 190);
        const force = (distance - idealDistance) * 0.008;
        dx /= distance;
        dy /= distance;
        if (!fixedNodes[source.id]) {
          source.vx += dx * force;
          source.vy += dy * force;
        }
        if (!fixedNodes[target.id]) {
          target.vx -= dx * force;
          target.vy -= dy * force;
        }
      }

      for (const node of simNodes) {
        if (fixedNodes[node.id]) {
          continue;
        }

        node.vx += (DYNAMIC_GRAPH_CENTER.x - node.x) * 0.0016;
        node.vy += (DYNAMIC_GRAPH_CENTER.y - node.y) * 0.0016;
        node.x = clampGraphValue(node.x + node.vx, DYNAMIC_GRAPH_PADDING, DYNAMIC_GRAPH_WIDTH - DYNAMIC_GRAPH_PADDING);
        node.y = clampGraphValue(node.y + node.vy, DYNAMIC_GRAPH_PADDING, DYNAMIC_GRAPH_HEIGHT - DYNAMIC_GRAPH_PADDING);
      }

      iterations += 1;
      const nextPositions = Object.fromEntries(
        simNodes.map(node => [node.id, clampGraphPoint({ x: node.x, y: node.y })]),
      );
      positionsRef.current = nextPositions;
      setPositions(nextPositions);

      if (iterations < maxIterations) {
        frame = requestAnimationFrame(tick);
      }
    }

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [nodes, edges, fixedNodes]);

  useEffect(() => {
    if (!dragState) {
      return;
    }

    const activeDragState = dragState;

    function toGraphPoint(clientX: number, clientY: number) {
      const svg = svgRef.current;
      if (!svg) {
        return null;
      }

      const point = svg.createSVGPoint();
      point.x = clientX;
      point.y = clientY;
      const matrix = svg.getScreenCTM();
      if (!matrix) {
        return null;
      }

      const transformed = point.matrixTransform(matrix.inverse());
      const activeViewport = viewportRef.current;
      return clampGraphPoint({
        x: (transformed.x - activeViewport.x) / activeViewport.scale - activeDragState.offsetX,
        y: (transformed.y - activeViewport.y) / activeViewport.scale - activeDragState.offsetY,
      });
    }

    function handlePointerMove(event: PointerEvent) {
      const nextPoint = toGraphPoint(event.clientX, event.clientY);
      if (!nextPoint) {
        return;
      }

      dragMovedRef.current = true;
      positionsRef.current = {
        ...positionsRef.current,
        [activeDragState.nodeId]: nextPoint,
      };
      setPositions(current => ({
        ...current,
        [activeDragState.nodeId]: nextPoint,
      }));
    }

    function handlePointerUp() {
      const finalPoint = positionsRef.current[activeDragState.nodeId];
      if (finalPoint) {
        setFixedNodes(current => ({
          ...current,
          [activeDragState.nodeId]: finalPoint,
        }));
      }
      setDragState(null);
    }

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp, { once: true });
    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };
  }, [dragState]);

  useEffect(() => {
    if (!panState) {
      return;
    }

    const activePan = panState;

    function handlePointerMove(event: PointerEvent) {
      dragMovedRef.current = true;
      setViewport(normalizeViewport({
        scale: viewportRef.current.scale,
        x: activePan.startX + (event.clientX - activePan.startClientX),
        y: activePan.startY + (event.clientY - activePan.startClientY),
      }));
    }

    function handlePointerUp() {
      setPanState(null);
    }

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp, { once: true });
    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };
  }, [panState]);

  const getPos = (id: string) => positions[id] ?? nodes.find(node => node.id === id) ?? DYNAMIC_GRAPH_CENTER;

  function zoomGraph(nextScale: number, focusPoint: DynamicGraphPoint = DYNAMIC_GRAPH_CENTER) {
    const currentViewport = viewportRef.current;
    const normalizedScale = clampGraphValue(nextScale, 0.65, 2.2);
    const graphFocusX = (focusPoint.x - currentViewport.x) / currentViewport.scale;
    const graphFocusY = (focusPoint.y - currentViewport.y) / currentViewport.scale;
    setViewport(normalizeViewport({
      scale: normalizedScale,
      x: focusPoint.x - graphFocusX * normalizedScale,
      y: focusPoint.y - graphFocusY * normalizedScale,
    }));
  }

  function resetViewport() {
    setViewport(normalizeViewport({
      scale: 1,
      x: 0,
      y: 0,
    }));
  }

  const roleEmoji = (role: string) => {
    switch (role) {
      case 'elder': return '👵';
      case 'child': return '🧒';
      case 'guest': return '🧑‍🤝‍🧑';
      default: return '🧑';
    }
  };

  return (
    <div
      className={`relationship-graph${dragState || panState ? ' relationship-graph--dragging' : ''}`}
      onClick={() => {
        if (dragMovedRef.current) {
          dragMovedRef.current = false;
          return;
        }
        onSelectMember(null);
      }}
    >
      <svg
        ref={svgRef}
        viewBox={`0 0 ${DYNAMIC_GRAPH_WIDTH} ${DYNAMIC_GRAPH_HEIGHT}`}
        className="relationship-graph__svg"
        onWheel={event => {
          event.preventDefault();
          const svg = svgRef.current;
          if (!svg) {
            return;
          }

          const point = svg.createSVGPoint();
          point.x = event.clientX;
          point.y = event.clientY;
          const matrix = svg.getScreenCTM();
          if (!matrix) {
            return;
          }

          const transformed = point.matrixTransform(matrix.inverse());
          const scaleFactor = event.deltaY < 0 ? 1.12 : 0.9;
          zoomGraph(viewportRef.current.scale * scaleFactor, { x: transformed.x, y: transformed.y });
        }}
        onPointerDown={event => {
          const target = event.target as SVGElement;
          if (target.closest('.graph-node')) {
            return;
          }

          dragMovedRef.current = false;
          setPanState({
            startClientX: event.clientX,
            startClientY: event.clientY,
            startX: viewportRef.current.x,
            startY: viewportRef.current.y,
          });
        }}
      >
        <defs>
          <filter id="node-shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.15" />
          </filter>
          <pattern id="graph-grid" width="28" height="28" patternUnits="userSpaceOnUse">
            <path d="M 28 0 L 0 0 0 28" fill="none" className="graph-grid__line" />
          </pattern>
        </defs>
        <rect x="0" y="0" width={DYNAMIC_GRAPH_WIDTH} height={DYNAMIC_GRAPH_HEIGHT} className="graph-grid" />
        <g transform={`translate(${viewport.x} ${viewport.y}) scale(${viewport.scale})`}>
        {edges.map(edge => {
          const source = getPos(edge.source);
          const target = getPos(edge.target);
          const geometry = getDynamicEdgeGeometry(source, target, edge.id);
          const isHighlighted = selectedMemberId && (edge.source === selectedMemberId || edge.target === selectedMemberId);
          const isDimmed = selectedMemberId && !isHighlighted;
          const label = selectedMemberId && isHighlighted
            ? getEdgeLabelForPerspective(edge, selectedMemberId, relationships)
            : edge.label;
          const labelWidth = Math.max(48, label.length * 16);

          return (
            <g key={edge.id}>
              <path
                d={geometry.path}
                className={`graph-edge ${isHighlighted ? 'graph-edge--highlight' : ''} ${isDimmed ? 'graph-edge--dim' : ''}`}
              />
              <rect
                x={geometry.labelAnchor.x - labelWidth / 2}
                y={geometry.labelAnchor.y - 12}
                width={labelWidth}
                height={24}
                rx={6}
                className={`graph-edge-label-bg ${isDimmed ? 'graph-edge-label-bg--dim' : ''}`}
              />
              <text
                x={geometry.labelAnchor.x}
                y={geometry.labelAnchor.y + 4}
                textAnchor="middle"
                className={`graph-edge-label ${isHighlighted ? 'graph-edge-label--highlight' : ''} ${isDimmed ? 'graph-edge-label--dim' : ''}`}
              >
                {label}
              </text>
            </g>
          );
        })}

        {nodes.map(node => {
          const pos = getPos(node.id);
          const isSelected = selectedMemberId === node.id;
          const isConnected = selectedMemberId && edges.some(edge => (
            (edge.source === selectedMemberId || edge.target === selectedMemberId)
            && (edge.source === node.id || edge.target === node.id)
          ));
          const isDimmed = selectedMemberId && !isSelected && !isConnected;
          const isFixed = Boolean(fixedNodes[node.id]);

          return (
            <g
              key={node.id}
              transform={`translate(${pos.x},${pos.y})`}
              className={`graph-node ${isSelected ? 'graph-node--selected' : ''} ${isFixed ? 'graph-node--fixed' : ''} ${isDimmed ? 'graph-node--dim' : ''}`}
              onPointerDown={event => {
                event.stopPropagation();
                const svg = svgRef.current;
                if (!svg) {
                  return;
                }

                dragMovedRef.current = false;
                const point = svg.createSVGPoint();
                point.x = event.clientX;
                point.y = event.clientY;
                const matrix = svg.getScreenCTM();
                if (!matrix) {
                  return;
                }

                const transformed = point.matrixTransform(matrix.inverse());
                const activeViewport = viewportRef.current;
                setDragState({
                  nodeId: node.id,
                  offsetX: (transformed.x - activeViewport.x) / activeViewport.scale - pos.x,
                  offsetY: (transformed.y - activeViewport.y) / activeViewport.scale - pos.y,
                });
              }}
              onDoubleClick={event => {
                event.stopPropagation();
                setFixedNodes(current => {
                  const next = { ...current };
                  delete next[node.id];
                  return next;
                });
              }}
              onClick={event => {
                event.stopPropagation();
                if (dragMovedRef.current) {
                  dragMovedRef.current = false;
                  return;
                }
                onSelectMember(isSelected ? null : node.id);
              }}
              style={{ cursor: dragState?.nodeId === node.id ? 'grabbing' : 'grab' }}
            >
              <circle r={28} className="graph-node__circle" filter="url(#node-shadow)" />
              <text y={4} textAnchor="middle" className="graph-node__emoji">{roleEmoji(node.role)}</text>
              <text y={46} textAnchor="middle" className="graph-node__name">{node.name}</text>
              {isFixed && <circle r={33} className="graph-node__pin" />}
            </g>
          );
        })}
        </g>
      </svg>
      <div className="relationship-graph__toolbar">
        <button className="relationship-graph__toolbtn" type="button" onClick={() => zoomGraph(viewport.scale * 1.12)}>
          ＋
        </button>
        <button className="relationship-graph__toolbtn" type="button" onClick={() => zoomGraph(viewport.scale * 0.9)}>
          －
        </button>
        <button className="relationship-graph__toolbtn relationship-graph__toolbtn--wide" type="button" onClick={resetViewport}>
          重置
        </button>
        <span className="relationship-graph__zoom">{Math.round(viewport.scale * 100)}%</span>
      </div>
      <div className="graph-legend">
        🔗 拖拽节点可整理图谱，双击节点可取消固定；点击成员切换关系视角，点击空白取消选中。
      </div>
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
          <DynamicRelationshipGraph
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
