/* ============================================================
 * 家庭页 - 包含概览/房间/成员/关系四个子路由
 * ============================================================ */
import { createContext, useContext, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { getLocaleDefinition, type LocaleDefinition } from '@familyclaw/user-core';
import { DEFAULT_REGION_COUNTRY, DEFAULT_REGION_PROVIDER, RegionSelector, type RegionSelectionFormValue } from './RegionSelector';
import { PageHeader, Card, Section } from './base';
import { useHouseholdContext, useI18n } from '../../runtime';
import { api } from './api';
import { formatRoomType, ROOM_TYPE_OPTIONS } from './roomTypes';
import type {
  ContextOverviewRead,
  Device,
  Household,
  Member,
  MemberPreference,
  MemberRelationship,
  Room,
} from './types';

/* ---- 家庭子导航 ---- */
const familyTabs = [
  { key: 'overview' as const, hash: '#overview', labelKey: 'family.overview' as const },
  { key: 'rooms' as const, hash: '#rooms', labelKey: 'family.rooms' as const },
  { key: 'members' as const, hash: '#members', labelKey: 'family.members' as const },
  { key: 'relationships' as const, hash: '#relationships', labelKey: 'family.relationships' as const },
];

type FamilyTabKey = (typeof familyTabs)[number]['key'];

function getInitialFamilyTab(): FamilyTabKey {
  if (typeof window === 'undefined') {
    return 'overview';
  }
  const hash = window.location.hash.replace('#', '');
  const matched = familyTabs.find(tab => tab.key === hash);
  return matched?.key ?? 'overview';
}

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

function pickLocaleText(
  locale: string | undefined,
  values: { zhCN: string; zhTW: string; enUS: string },
) {
  if (locale?.toLowerCase().startsWith('en')) {
    return values.enUS;
  }
  if (locale?.toLowerCase().startsWith('zh-tw')) {
    return values.zhTW;
  }
  return values.zhCN;
}

function formatLocale(
  locale: string | null | undefined,
  localeDefinitions: LocaleDefinition[],
  formatLocaleLabel: (definition: Pick<LocaleDefinition, 'id' | 'nativeLabel'>) => string,
) {
  if (!locale) {
    return '-';
  }

  const definition = getLocaleDefinition(localeDefinitions, locale);
  return definition ? formatLocaleLabel(definition) : locale;
}

function formatFamilyRegion(household: Household | null | undefined) {
  if (!household) return '-';
  return household.region?.display_name ?? household.city ?? '-';
}

function getRegionLevelValue(value: { name: string } | null | undefined, locale: string | undefined) {
  return value?.name ?? pickLocaleText(locale, { zhCN: '未知', zhTW: '未知', enUS: 'Unknown' });
}

function formatHomeMode(mode: ContextOverviewRead['home_mode'] | undefined, locale: string | undefined) {
  switch (mode) {
    case 'home': return pickLocaleText(locale, { zhCN: '居家模式', zhTW: '居家模式', enUS: 'Home mode' });
    case 'away': return pickLocaleText(locale, { zhCN: '离家模式', zhTW: '離家模式', enUS: 'Away mode' });
    case 'night': return pickLocaleText(locale, { zhCN: '夜间模式', zhTW: '夜間模式', enUS: 'Night mode' });
    case 'sleep': return pickLocaleText(locale, { zhCN: '睡眠模式', zhTW: '睡眠模式', enUS: 'Sleep mode' });
    case 'custom': return pickLocaleText(locale, { zhCN: '自定义模式', zhTW: '自訂模式', enUS: 'Custom mode' });
    default: return '-';
  }
}

function formatPrivacyMode(mode: ContextOverviewRead['privacy_mode'] | undefined, locale: string | undefined) {
  switch (mode) {
    case 'balanced': return pickLocaleText(locale, { zhCN: '平衡保护', zhTW: '平衡保護', enUS: 'Balanced' });
    case 'strict': return pickLocaleText(locale, { zhCN: '严格保护', zhTW: '嚴格保護', enUS: 'Strict' });
    case 'care': return pickLocaleText(locale, { zhCN: '关怀优先', zhTW: '關懷優先', enUS: 'Care first' });
    default: return '-';
  }
}

function formatRole(role: Member['role'], locale: string | undefined) {
  switch (role) {
    case 'admin': return pickLocaleText(locale, { zhCN: '管理员', zhTW: '管理員', enUS: 'Admin' });
    case 'adult': return pickLocaleText(locale, { zhCN: '成人', zhTW: '成人', enUS: 'Adult' });
    case 'child': return pickLocaleText(locale, { zhCN: '儿童', zhTW: '兒童', enUS: 'Child' });
    case 'elder': return pickLocaleText(locale, { zhCN: '长辈', zhTW: '長輩', enUS: 'Elder' });
    case 'guest': return pickLocaleText(locale, { zhCN: '访客', zhTW: '訪客', enUS: 'Guest' });
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

function formatPreferenceSummary(preference: MemberPreference | undefined, locale: string | undefined) {
  if (!preference) {
    return pickLocaleText(locale, { zhCN: '还没有成员偏好数据', zhTW: '還沒有成員偏好資料', enUS: 'No member preferences yet' });
  }

  const parts: string[] = [];
  if (preference.preferred_name) parts.push(pickLocaleText(locale, { zhCN: `称呼：${preference.preferred_name}`, zhTW: `稱呼：${preference.preferred_name}`, enUS: `Preferred name: ${preference.preferred_name}` }));
  if (preference.climate_preference) parts.push(pickLocaleText(locale, { zhCN: '已设置温度偏好', zhTW: '已設定溫度偏好', enUS: 'Temperature preference set' }));
  if (preference.light_preference) parts.push(pickLocaleText(locale, { zhCN: '已设置灯光偏好', zhTW: '已設定燈光偏好', enUS: 'Lighting preference set' }));
  if (preference.reminder_channel_preference) parts.push(pickLocaleText(locale, { zhCN: '已设置提醒方式', zhTW: '已設定提醒方式', enUS: 'Reminder channel set' }));
  if (preference.sleep_schedule) parts.push(pickLocaleText(locale, { zhCN: '已设置作息', zhTW: '已設定作息', enUS: 'Sleep schedule set' }));

  return parts.length > 0 ? parts.join(' · ') : pickLocaleText(locale, { zhCN: '还没有成员偏好数据', zhTW: '還沒有成員偏好資料', enUS: 'No member preferences yet' });
}

function validatePhoneNumber(value: string, locale: string | undefined) {
  if (!value.trim()) {
    return '';
  }

  return /^[0-9+\-\s]{6,20}$/.test(value.trim()) ? '' : pickLocaleText(locale, {
    zhCN: '请输入有效手机号，支持数字、空格、+ 和 -',
    zhTW: '請輸入有效手機號，支援數字、空格、+ 和 -',
    enUS: 'Enter a valid phone number. Digits, spaces, + and - are supported.',
  });
}

function roleNeedsGuardian(role: Member['role']) {
  return role === 'child';
}

function getAllowedStatusOptions(role: Member['role'], locale: string | undefined) {
  if (role === 'admin') {
    return [{ value: 'active' as const, label: pickLocaleText(locale, { zhCN: '启用', zhTW: '啟用', enUS: 'Active' }) }];
  }

  return [
    { value: 'active' as const, label: pickLocaleText(locale, { zhCN: '启用', zhTW: '啟用', enUS: 'Active' }) },
    { value: 'inactive' as const, label: pickLocaleText(locale, { zhCN: '停用', zhTW: '停用', enUS: 'Disabled' }) },
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

function getBirthdayCountdownText(birthday: string | null, locale: string | undefined) {
  if (!birthday) {
    return pickLocaleText(locale, { zhCN: '未设置生日', zhTW: '未設定生日', enUS: 'Birthday not set' });
  }

  const birthDate = new Date(`${birthday}T00:00:00`);
  if (Number.isNaN(birthDate.getTime())) {
    return pickLocaleText(locale, { zhCN: '生日格式无效', zhTW: '生日格式無效', enUS: 'Invalid birthday format' });
  }

  const today = new Date();
  const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  let nextBirthday = new Date(today.getFullYear(), birthDate.getMonth(), birthDate.getDate());
  if (nextBirthday < startOfToday) {
    nextBirthday = new Date(today.getFullYear() + 1, birthDate.getMonth(), birthDate.getDate());
  }

  const diffDays = Math.round((nextBirthday.getTime() - startOfToday.getTime()) / 86400000);
  if (diffDays === 0) return pickLocaleText(locale, { zhCN: '今天生日', zhTW: '今天生日', enUS: 'Birthday is today' });
  if (diffDays === 1) return pickLocaleText(locale, { zhCN: '明天生日', zhTW: '明天生日', enUS: 'Birthday is tomorrow' });
  return pickLocaleText(locale, { zhCN: `${diffDays} 天后生日`, zhTW: `${diffDays} 天後生日`, enUS: `Birthday in ${diffDays} days` });
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

function formatBirthdayCountdown(days: number | null, isLunarBirthday: boolean, locale: string | undefined) {
  if (days === null) {
    return isLunarBirthday
      ? pickLocaleText(locale, { zhCN: '暂未匹配到下一个农历生日', zhTW: '暫未匹配到下一個農曆生日', enUS: 'The next lunar birthday could not be matched yet' })
      : pickLocaleText(locale, { zhCN: '未设置生日', zhTW: '未設定生日', enUS: 'Birthday not set' });
  }

  if (days === 0) return pickLocaleText(locale, { zhCN: '今天生日', zhTW: '今天生日', enUS: 'Birthday is today' });
  if (days === 1) return pickLocaleText(locale, { zhCN: '明天生日', zhTW: '明天生日', enUS: 'Birthday is tomorrow' });
  return pickLocaleText(locale, { zhCN: `${days} 天后生日`, zhTW: `${days} 天後生日`, enUS: `Birthday in ${days} days` });
}

function getMemberRoleOptions(locale: string | undefined) {
  return [
    { value: 'admin' as const, label: pickLocaleText(locale, { zhCN: '管理员', zhTW: '管理員', enUS: 'Admin' }) },
    { value: 'adult' as const, label: pickLocaleText(locale, { zhCN: '成人', zhTW: '成人', enUS: 'Adult' }) },
    { value: 'child' as const, label: pickLocaleText(locale, { zhCN: '儿童', zhTW: '兒童', enUS: 'Child' }) },
    { value: 'elder' as const, label: pickLocaleText(locale, { zhCN: '长辈', zhTW: '長輩', enUS: 'Elder' }) },
    { value: 'guest' as const, label: pickLocaleText(locale, { zhCN: '访客', zhTW: '訪客', enUS: 'Guest' }) },
  ];
}

function getAgeGroupOptionsForRole(role: Member['role'], locale: string | undefined) {
  switch (role) {
    case 'child':
      return [
        { value: 'toddler' as const, label: pickLocaleText(locale, { zhCN: '幼儿', zhTW: '幼兒', enUS: 'Toddler' }) },
        { value: 'child' as const, label: pickLocaleText(locale, { zhCN: '儿童', zhTW: '兒童', enUS: 'Child' }) },
        { value: 'teen' as const, label: pickLocaleText(locale, { zhCN: '青少年', zhTW: '青少年', enUS: 'Teen' }) },
      ];
    case 'elder':
      return [{ value: 'elder' as const, label: pickLocaleText(locale, { zhCN: '长辈', zhTW: '長輩', enUS: 'Elder' }) }];
    default:
      return [{ value: 'adult' as const, label: pickLocaleText(locale, { zhCN: '成人', zhTW: '成人', enUS: 'Adult' }) }];
  }
}

function formatRelationType(type: MemberRelationship['relation_type'], locale: string | undefined) {
  switch (type) {
    case 'caregiver': return pickLocaleText(locale, { zhCN: '照护关系', zhTW: '照護關係', enUS: 'Caregiver' });
    case 'guardian': return pickLocaleText(locale, { zhCN: '监护关系', zhTW: '監護關係', enUS: 'Guardian' });
    case 'parent': return pickLocaleText(locale, { zhCN: '父母关系', zhTW: '父母關係', enUS: 'Parent' });
    case 'child': return pickLocaleText(locale, { zhCN: '子女关系', zhTW: '子女關係', enUS: 'Child' });
    case 'spouse': return pickLocaleText(locale, { zhCN: '伴侣关系', zhTW: '伴侶關係', enUS: 'Spouse' });
  }
}

function formatVisibilityScope(scope: MemberRelationship['visibility_scope'], locale: string | undefined) {
  switch (scope) {
    case 'public': return pickLocaleText(locale, { zhCN: '公开', zhTW: '公開', enUS: 'Public' });
    case 'family': return pickLocaleText(locale, { zhCN: '家庭内可见', zhTW: '家庭內可見', enUS: 'Family only' });
    case 'private': return pickLocaleText(locale, { zhCN: '私密', zhTW: '私密', enUS: 'Private' });
  }
}

function formatDelegationScope(scope: MemberRelationship['delegation_scope'], locale: string | undefined) {
  switch (scope) {
    case 'none': return pickLocaleText(locale, { zhCN: '不开放代办', zhTW: '不開放代辦', enUS: 'No delegation' });
    case 'reminder': return pickLocaleText(locale, { zhCN: '可代办提醒', zhTW: '可代辦提醒', enUS: 'Reminder delegation' });
    case 'health': return pickLocaleText(locale, { zhCN: '可代办健康事项', zhTW: '可代辦健康事項', enUS: 'Health delegation' });
    case 'device': return pickLocaleText(locale, { zhCN: '可代办设备事项', zhTW: '可代辦設備事項', enUS: 'Device delegation' });
  }
}

function useFamilyWorkspace() {
  const context = useContext(FamilyWorkspaceContext);
  if (!context) {
    throw new Error('useFamilyWorkspace must be used within FamilyLayout');
  }
  return context;
}

export function FamilyLayout() {
  const { t, locale } = useI18n();
  const { currentHouseholdId } = useHouseholdContext();
  const [activeTab, setActiveTab] = useState<FamilyTabKey>(getInitialFamilyTab);
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
      .map(result => result.reason instanceof Error ? result.reason.message : pickLocaleText(locale, {
        zhCN: '家庭数据加载失败',
        zhTW: '家庭資料載入失敗',
        enUS: 'Failed to load family data',
      }));

    preferenceResults.forEach(result => {
      if (result.status === 'rejected') {
        errors.push(result.reason instanceof Error ? result.reason.message : pickLocaleText(locale, {
          zhCN: '成员偏好加载失败',
          zhTW: '成員偏好載入失敗',
          enUS: 'Failed to load member preferences',
        }));
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

  useEffect(() => {
    function handleHashChange() {
      setActiveTab(getInitialFamilyTab());
    }

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const value = useMemo(() => ({ ...workspace, refreshWorkspace }), [workspace, refreshWorkspace]);

  return (
    <FamilyWorkspaceContext.Provider value={value}>
      <div className="page page--family">
        <PageHeader title={t('nav.family')} description={workspace.errors.length > 0 ? pickLocaleText(locale, {
          zhCN: '部分数据加载失败，页面已自动显示已拿到的内容。',
          zhTW: '部分資料載入失敗，頁面已自動顯示目前拿到的內容。',
          enUS: 'Some data failed to load. The page is showing everything that is currently available.',
        }) : undefined} />
        <nav className="family-tabs">
          {familyTabs.map(tab => (
            <a
              key={tab.key}
              href={tab.hash}
              className={`family-tab ${activeTab === tab.key ? 'family-tab--active' : ''}`}
              onClick={event => {
                event.preventDefault();
                window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}${tab.hash}`);
                setActiveTab(tab.key);
              }}
            >
              {t(tab.labelKey)}
            </a>
          ))}
        </nav>
        <div className="family-content">
          {activeTab === 'overview' ? <FamilyOverview /> : null}
          {activeTab === 'rooms' ? <FamilyRooms /> : null}
          {activeTab === 'members' ? <FamilyMembers /> : null}
          {activeTab === 'relationships' ? <FamilyRelationships /> : null}
        </div>
      </div>
    </FamilyWorkspaceContext.Provider>
  );
}

/* ---- 家庭概览 ---- */
export function FamilyOverview() {
  const { t, locale, locales, formatLocaleLabel } = useI18n();
  const { currentHousehold, currentHouseholdId, refreshCurrentHousehold, refreshHouseholds } = useHouseholdContext();
  const { household, overview, loading, refreshWorkspace } = useFamilyWorkspace();
  const [editForm, setEditForm] = useState({
    name: '',
    timezone: 'Asia/Shanghai',
    locale: 'zh-CN',
    region: { countryCode: DEFAULT_REGION_COUNTRY, provinceCode: '', cityCode: '', districtCode: '' } as RegionSelectionFormValue,
  });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [saveStatus, setSaveStatus] = useState('');
  const copy = {
    loading: pickLocaleText(locale, { zhCN: '加载中...', zhTW: '載入中...', enUS: 'Loading...' }),
    regionLabel: pickLocaleText(locale, { zhCN: '所在地区', zhTW: '所在地區', enUS: 'Region' }),
    noServiceSummary: pickLocaleText(locale, { zhCN: '暂无服务摘要', zhTW: '暫無服務摘要', enUS: 'No service summary yet' }),
    regionStructureTitle: pickLocaleText(locale, { zhCN: '地区结构', zhTW: '地區結構', enUS: 'Region structure' }),
    regionStructureIntro: pickLocaleText(locale, {
      zhCN: '这里会显示您当前选择的国家、省、市和区县。',
      zhTW: '這裡會顯示您目前選擇的國家、省、市與區縣。',
      enUS: 'This shows the country, province, city, and district currently selected for this household.',
    }),
    regionCountry: pickLocaleText(locale, { zhCN: '国家 / 地区', zhTW: '國家 / 地區', enUS: 'Country / region' }),
    province: pickLocaleText(locale, { zhCN: '省级', zhTW: '省級', enUS: 'Province' }),
    city: pickLocaleText(locale, { zhCN: '市级', zhTW: '市級', enUS: 'City' }),
    district: pickLocaleText(locale, { zhCN: '区县', zhTW: '區縣', enUS: 'District' }),
    regionBindingStatus: pickLocaleText(locale, { zhCN: '绑定状态', zhTW: '綁定狀態', enUS: 'Binding status' }),
    regionFallbackHint: pickLocaleText(locale, {
      zhCN: `当前显示的“${household?.city ?? ''}”是之前保存的信息，请在下方重新选择完整地区。`,
      zhTW: `目前顯示的「${household?.city ?? ''}」是之前儲存的資訊，請在下方重新選擇完整地區。`,
      enUS: `The current value "${household?.city ?? ''}" was saved earlier. Please reselect the full region below.`,
    }),
    regionUnconfiguredHint: pickLocaleText(locale, {
      zhCN: `当前家庭之前保存的是“${household?.city ?? ''}”，请在这里重新选择完整地区。`,
      zhTW: `目前家庭先前儲存的是「${household?.city ?? ''}」，請在這裡重新選擇完整地區。`,
      enUS: `This household previously saved "${household?.city ?? ''}". Please reselect the full region here.`,
    }),
    profileTitle: pickLocaleText(locale, { zhCN: '家庭资料', zhTW: '家庭資料', enUS: 'Household profile' }),
    profileDesc: pickLocaleText(locale, {
      zhCN: '您可以在这里更新家庭名称、时区、语言和所在地区。',
      zhTW: '您可以在這裡更新家庭名稱、時區、語言與所在地區。',
      enUS: 'Update the household name, time zone, language, and region here.',
    }),
    nameLabel: pickLocaleText(locale, { zhCN: '家庭名称', zhTW: '家庭名稱', enUS: 'Household name' }),
    timezoneLabel: pickLocaleText(locale, { zhCN: '时区', zhTW: '時區', enUS: 'Time zone' }),
    defaultLanguageLabel: pickLocaleText(locale, { zhCN: '默认语言', zhTW: '預設語言', enUS: 'Default language' }),
    saveButton: pickLocaleText(locale, { zhCN: '保存家庭资料', zhTW: '儲存家庭資料', enUS: 'Save household profile' }),
    savingButton: pickLocaleText(locale, { zhCN: '保存中…', zhTW: '儲存中…', enUS: 'Saving...' }),
    saveSuccess: pickLocaleText(locale, { zhCN: '家庭资料已更新。', zhTW: '家庭資料已更新。', enUS: 'Household profile updated.' }),
    saveFailure: pickLocaleText(locale, { zhCN: '保存家庭资料失败', zhTW: '儲存家庭資料失敗', enUS: 'Failed to save household profile' }),
  };

  const serviceSummary = [
    overview?.voice_fast_path_enabled ? pickLocaleText(locale, { zhCN: '语音快通道', zhTW: '語音快通道', enUS: 'Voice fast path' }) : null,
    overview?.guest_mode_enabled ? pickLocaleText(locale, { zhCN: '访客模式', zhTW: '訪客模式', enUS: 'Guest mode' }) : null,
    overview?.child_protection_enabled ? pickLocaleText(locale, { zhCN: '儿童保护', zhTW: '兒童保護', enUS: 'Child protection' }) : null,
    overview?.elder_care_watch_enabled ? pickLocaleText(locale, { zhCN: '长辈关怀', zhTW: '長輩關懷', enUS: 'Elder care' }) : null,
  ].filter(Boolean).join(' · ');
  const regionCountryText = household?.region?.country_code === 'CN'
    ? pickLocaleText(locale, { zhCN: '中国', zhTW: '中國', enUS: 'China' })
    : pickLocaleText(locale, { zhCN: '未知', zhTW: '未知', enUS: 'Unknown' });
  const regionStatusText = household?.region?.status === 'configured'
    ? pickLocaleText(locale, { zhCN: '已设置完成', zhTW: '已設定完成', enUS: 'Configured' })
    : household?.region?.status === 'provider_unavailable'
      ? pickLocaleText(locale, { zhCN: '暂时无法读取', zhTW: '暫時無法讀取', enUS: 'Temporarily unavailable' })
      : pickLocaleText(locale, { zhCN: '待完善', zhTW: '待完善', enUS: 'Needs completion' });

  useEffect(() => {
    setEditForm({
      name: household?.name ?? currentHousehold?.name ?? '',
      timezone: household?.timezone ?? currentHousehold?.timezone ?? 'Asia/Shanghai',
      locale: household?.locale ?? currentHousehold?.locale ?? 'zh-CN',
      region: {
        countryCode: household?.region?.country_code ?? DEFAULT_REGION_COUNTRY,
        provinceCode: household?.region?.province?.code ?? '',
        cityCode: household?.region?.city?.code ?? '',
        districtCode: household?.region?.district?.code ?? '',
      },
    });
  }, [
    currentHousehold?.locale,
    currentHousehold?.name,
    currentHousehold?.timezone,
    household?.locale,
    household?.name,
    household?.timezone,
    household?.region?.province?.code,
    household?.region?.city?.code,
    household?.region?.district?.code,
  ]);

  async function handleHouseholdSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId) return;
    setSaving(true);
    setSaveError('');
    setSaveStatus('');
    try {
      await api.updateHousehold(currentHouseholdId, {
        name: editForm.name.trim(),
        timezone: editForm.timezone.trim(),
        locale: editForm.locale.trim(),
        region_selection: {
          provider_code: DEFAULT_REGION_PROVIDER,
          country_code: editForm.region.countryCode,
          region_code: editForm.region.districtCode,
        },
      });
      await refreshCurrentHousehold(currentHouseholdId);
      await refreshHouseholds();
      await refreshWorkspace();
      setSaveStatus(copy.saveSuccess);
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : copy.saveFailure);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="family-overview">
      <div className="overview-grid family-overview__summary-grid">
        <Card className="overview-card">
          <div className="overview-card__label">{t('family.name')}</div>
          <div className="overview-card__value">{household?.name ?? currentHousehold?.name ?? (loading ? copy.loading : '-')}</div>
        </Card>
        <Card className="overview-card">
          <div className="overview-card__label">{t('family.timezone')}</div>
          <div className="overview-card__value">{household?.timezone ?? (loading ? copy.loading : '-')}</div>
        </Card>
        <Card className="overview-card">
          <div className="overview-card__label">{t('family.language')}</div>
          <div className="overview-card__value">{formatLocale(household?.locale, locales, formatLocaleLabel)}</div>
        </Card>
        <Card className="overview-card">
          <div className="overview-card__label">{t('family.mode')}</div>
          <div className="overview-card__value">{formatHomeMode(overview?.home_mode, locale)}</div>
        </Card>
        <Card className="overview-card">
          <div className="overview-card__label">{t('family.privacy')}</div>
          <div className="overview-card__value">{formatPrivacyMode(overview?.privacy_mode, locale)}</div>
        </Card>
        <Card className="overview-card">
          <div className="overview-card__label">{copy.regionLabel}</div>
          <div className="overview-card__value">{formatFamilyRegion(household)}</div>
        </Card>
        <Card className="overview-card">
          <div className="overview-card__label">{t('family.services')}</div>
          <div className="overview-card__value">{serviceSummary || (loading ? copy.loading : copy.noServiceSummary)}</div>
        </Card>
      </div>
      <Card className="family-overview__panel">
        <Section title={copy.regionStructureTitle}>
          <p className="family-overview__intro">{copy.regionStructureIntro}</p>
          <div className="overview-grid family-overview__region-grid">
            <Card className="overview-card">
              <div className="overview-card__label">{copy.regionCountry}</div>
              <div className="overview-card__value">{regionCountryText}</div>
            </Card>
            <Card className="overview-card">
              <div className="overview-card__label">{copy.province}</div>
              <div className="overview-card__value">{getRegionLevelValue(household?.region?.province, locale)}</div>
            </Card>
            <Card className="overview-card">
              <div className="overview-card__label">{copy.city}</div>
              <div className="overview-card__value">{getRegionLevelValue(household?.region?.city, locale)}</div>
            </Card>
            <Card className="overview-card">
              <div className="overview-card__label">{copy.district}</div>
              <div className="overview-card__value">{getRegionLevelValue(household?.region?.district, locale)}</div>
            </Card>
            <Card className="overview-card">
              <div className="overview-card__label">{copy.regionBindingStatus}</div>
              <div className="overview-card__value">{regionStatusText}</div>
            </Card>
          </div>
          {household?.region?.status !== 'configured' && household?.city && (
            <div className="form-hint" style={{ marginTop: '0.75rem' }}>
              {copy.regionFallbackHint}
            </div>
          )}
        </Section>
      </Card>
      <Card className="family-overview__panel">
        <div className="setup-wizard-header family-overview__header">
          <h2 className="family-overview__title">{copy.profileTitle}</h2>
          <p>{copy.profileDesc}</p>
        </div>
        <form className="settings-form" onSubmit={handleHouseholdSave}>
          <div className="setup-form-grid">
            <div className="form-group">
              <label htmlFor="family-overview-name">{copy.nameLabel}</label>
              <input
                id="family-overview-name"
                className="form-input"
                value={editForm.name}
                onChange={event => setEditForm(current => ({ ...current, name: event.target.value }))}
                required
              />
            </div>
          </div>
          <div className="setup-form-grid">
            <div className="form-group">
              <label htmlFor="family-overview-timezone">{copy.timezoneLabel}</label>
              <input
                id="family-overview-timezone"
                className="form-input"
                value={editForm.timezone}
                onChange={event => setEditForm(current => ({ ...current, timezone: event.target.value }))}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="family-overview-locale">{copy.defaultLanguageLabel}</label>
              <select
                id="family-overview-locale"
                className="form-select"
                value={editForm.locale}
                onChange={event => setEditForm(current => ({ ...current, locale: event.target.value }))}
              >
                {locales.map(localeOption => (
                  <option key={localeOption.id} value={localeOption.id}>{formatLocaleLabel(localeOption)}</option>
                ))}
              </select>
            </div>
          </div>
          <RegionSelector value={editForm.region} onChange={region => setEditForm(current => ({ ...current, region }))} disabled={saving} />
          {household?.region?.status === 'unconfigured' && household?.city && (
            <div className="form-hint">{copy.regionUnconfiguredHint}</div>
          )}
          {saveError && <div className="form-error">{saveError}</div>}
          {saveStatus && <div className="form-hint">{saveStatus}</div>}
          <div className="setup-form-actions">
            <button type="submit" className="btn btn--primary" disabled={saving || !editForm.name.trim() || !editForm.region.districtCode}>
              {saving ? copy.savingButton : copy.saveButton}
            </button>
          </div>
        </form>
      </Card>
    </div>
  );
}

/* ---- 房间页 ---- */
export function FamilyRooms() {
  const { t, locale } = useI18n();
  const { rooms, overview, devices, loading, refreshWorkspace } = useFamilyWorkspace();
  const { currentHouseholdId } = useHouseholdContext();
  const [createForm, setCreateForm] = useState({ name: '', room_type: 'living_room' as Room['room_type'], privacy_level: 'public' as Room['privacy_level'] });
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [createErrors, setCreateErrors] = useState<{ name?: string }>({});
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [toastMessage, setToastMessage] = useState('');
  const [pendingScrollRoomId, setPendingScrollRoomId] = useState<string | null>(null);
  const copy = {
    nameRequired: pickLocaleText(locale, { zhCN: '请输入房间名称', zhTW: '請輸入房間名稱', enUS: 'Enter a room name' }),
    selectHousehold: pickLocaleText(locale, { zhCN: '请先选择家庭。', zhTW: '請先選擇家庭。', enUS: 'Select a household first.' }),
    createSuccess: pickLocaleText(locale, { zhCN: '房间已创建。', zhTW: '房間已建立。', enUS: 'Room created.' }),
    createToast: pickLocaleText(locale, { zhCN: '房间已创建', zhTW: '房間已建立', enUS: 'Room created' }),
    createFailure: pickLocaleText(locale, { zhCN: '创建房间失败', zhTW: '建立房間失敗', enUS: 'Failed to create room' }),
    title: pickLocaleText(locale, { zhCN: '房间列表', zhTW: '房間列表', enUS: 'Rooms' }),
    desc: pickLocaleText(locale, {
      zhCN: '在这里查看家庭空间，并按需补充新的房间。',
      zhTW: '在這裡查看家庭空間，並按需要補充新的房間。',
      enUS: 'Review household spaces here and add new rooms when needed.',
    }),
    addButton: pickLocaleText(locale, { zhCN: '新增房间', zhTW: '新增房間', enUS: 'Add room' }),
    loading: pickLocaleText(locale, { zhCN: '正在加载房间数据...', zhTW: '正在載入房間資料...', enUS: 'Loading room data...' }),
    modalDesc: pickLocaleText(locale, {
      zhCN: '填写房间名称和类型后，会直接加入当前家庭空间。',
      zhTW: '填寫房間名稱和類型後，會直接加入目前家庭空間。',
      enUS: 'The room will be added to the current household after you fill in its name and type.',
    }),
    roomName: pickLocaleText(locale, { zhCN: '房间名称', zhTW: '房間名稱', enUS: 'Room name' }),
    roomType: pickLocaleText(locale, { zhCN: '房间类型', zhTW: '房間類型', enUS: 'Room type' }),
    privacyLevel: pickLocaleText(locale, { zhCN: '隐私等级', zhTW: '隱私等級', enUS: 'Privacy level' }),
    privacyPublic: pickLocaleText(locale, { zhCN: '公共', zhTW: '公共', enUS: 'Public' }),
    privacyPrivate: pickLocaleText(locale, { zhCN: '私密', zhTW: '私密', enUS: 'Private' }),
    privacySensitive: pickLocaleText(locale, { zhCN: '敏感', zhTW: '敏感', enUS: 'Sensitive' }),
  };

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
      nextErrors.name = copy.nameRequired;
    }

    setCreateErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleCreateRoom(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId) {
      setError(copy.selectHousehold);
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
      setStatus(copy.createSuccess);
      setToastMessage(copy.createToast);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : copy.createFailure);
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
          <h2 className="member-page-toolbar__title">{copy.title}</h2>
          <p className="member-page-toolbar__desc">{copy.desc}</p>
        </div>
        <button className="btn btn--primary" type="button" onClick={openCreateRoomModal}>{copy.addButton}</button>
      </div>
      {(status || error) && <div className="text-text-secondary" style={{ marginBottom: '1rem' }}>{error || status}</div>}
      <div className="room-grid">
        {loading && roomCards.length === 0 ? <div className="text-text-secondary">{copy.loading}</div> : roomCards.map(room => (
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
                <h3>{copy.addButton}</h3>
                <p>{copy.modalDesc}</p>
              </div>
              <button className="card-action-btn" type="button" onClick={closeCreateRoomModal}>{t('common.cancel')}</button>
            </div>
            <form className="settings-form" onSubmit={handleCreateRoom} noValidate>
              <div className="form-group">
                <label>{copy.roomName}</label>
                <input
                  className={`form-input${createErrors.name ? ' form-input--error' : ''}`}
                  value={createForm.name}
                  onChange={event => {
                    const value = event.target.value;
                    setCreateForm(current => ({ ...current, name: value }));
                    if (createErrors.name) {
                      setCreateErrors(current => ({ ...current, name: value.trim() ? '' : copy.nameRequired }));
                    }
                  }}
                />
                {createErrors.name && <div className="form-error">{createErrors.name}</div>}
              </div>
              <div className="form-group">
                <label>{copy.roomType}</label>
                <select className="form-select" value={createForm.room_type} onChange={event => setCreateForm(current => ({ ...current, room_type: event.target.value as Room['room_type'] }))}>
                  {ROOM_TYPE_OPTIONS.map(option => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>{copy.privacyLevel}</label>
                <select className="form-select" value={createForm.privacy_level} onChange={event => setCreateForm(current => ({ ...current, privacy_level: event.target.value as Room['privacy_level'] }))}>
                  <option value="public">{copy.privacyPublic}</option>
                  <option value="private">{copy.privacyPrivate}</option>
                  <option value="sensitive">{copy.privacySensitive}</option>
                </select>
              </div>
              <div className="member-modal__actions">
                <button className="btn btn--outline" type="button" onClick={closeCreateRoomModal}>{t('common.cancel')}</button>
                <button className="btn btn--primary" type="submit">{copy.addButton}</button>
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
  const { t, locale } = useI18n();
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
  const copy = {
    nameRequired: pickLocaleText(locale, { zhCN: '请输入成员姓名', zhTW: '請輸入成員姓名', enUS: 'Enter the member name' }),
    guardianRequired: pickLocaleText(locale, { zhCN: '儿童成员需要指定监护人', zhTW: '兒童成員需要指定監護人', enUS: 'A child member must have a guardian' }),
    guardianRequiredBeforeSave: pickLocaleText(locale, {
      zhCN: '儿童成员需要指定监护人后才能保存。',
      zhTW: '兒童成員需要指定監護人後才能儲存。',
      enUS: 'A child member needs a guardian before it can be saved.',
    }),
    selectHousehold: pickLocaleText(locale, { zhCN: '请先选择家庭。', zhTW: '請先選擇家庭。', enUS: 'Select a household first.' }),
    createSuccess: pickLocaleText(locale, { zhCN: '成员已创建。', zhTW: '成員已建立。', enUS: 'Member created.' }),
    createToast: pickLocaleText(locale, { zhCN: '成员已创建', zhTW: '成員已建立', enUS: 'Member created' }),
    createFailure: pickLocaleText(locale, { zhCN: '创建成员失败', zhTW: '建立成員失敗', enUS: 'Failed to create member' }),
    saveSuccess: pickLocaleText(locale, { zhCN: '成员信息已保存。', zhTW: '成員資訊已儲存。', enUS: 'Member details saved.' }),
    saveToast: pickLocaleText(locale, { zhCN: '成员信息已保存', zhTW: '成員資訊已儲存', enUS: 'Member details saved' }),
    saveFailure: pickLocaleText(locale, { zhCN: '保存成员信息失败', zhTW: '儲存成員資訊失敗', enUS: 'Failed to save member details' }),
    disableConfirm: (memberName: string) => pickLocaleText(locale, {
      zhCN: `确认停用成员“${memberName}”吗？停用后该成员会保留在列表里，但状态会变成停用。`,
      zhTW: `確認停用成員「${memberName}」嗎？停用後該成員會保留在列表中，但狀態會變成停用。`,
      enUS: `Disable "${memberName}"? The member will stay in the list, but its status will become disabled.`,
    }),
    disabledStatus: pickLocaleText(locale, { zhCN: '已停用', zhTW: '已停用', enUS: 'Disabled' }),
    disabledAction: pickLocaleText(locale, { zhCN: '停用成员', zhTW: '停用成員', enUS: 'Disable member' }),
    enabledAction: pickLocaleText(locale, { zhCN: '启用成员', zhTW: '啟用成員', enUS: 'Enable member' }),
    disableSuccess: pickLocaleText(locale, { zhCN: '成员已停用。', zhTW: '成員已停用。', enUS: 'Member disabled.' }),
    enableSuccess: pickLocaleText(locale, { zhCN: '成员已启用。', zhTW: '成員已啟用。', enUS: 'Member enabled.' }),
    disableToast: pickLocaleText(locale, { zhCN: '成员已停用', zhTW: '成員已停用', enUS: 'Member disabled' }),
    enableToast: pickLocaleText(locale, { zhCN: '成员已启用', zhTW: '成員已啟用', enUS: 'Member enabled' }),
    disableFailure: pickLocaleText(locale, { zhCN: '停用成员失败', zhTW: '停用成員失敗', enUS: 'Failed to disable member' }),
    enableFailure: pickLocaleText(locale, { zhCN: '启用成员失败', zhTW: '啟用成員失敗', enUS: 'Failed to enable member' }),
    preferencesSaveSuccess: pickLocaleText(locale, { zhCN: '成员偏好已保存。', zhTW: '成員偏好已儲存。', enUS: 'Member preferences saved.' }),
    preferencesSaveToast: pickLocaleText(locale, { zhCN: '成员偏好已保存', zhTW: '成員偏好已儲存', enUS: 'Member preferences saved' }),
    preferencesSaveFailure: pickLocaleText(locale, { zhCN: '保存成员偏好失败', zhTW: '儲存成員偏好失敗', enUS: 'Failed to save member preferences' }),
    title: pickLocaleText(locale, { zhCN: '成员列表', zhTW: '成員列表', enUS: 'Members' }),
    desc: pickLocaleText(locale, {
      zhCN: '在这里查看家庭成员，并按需编辑、停用或维护偏好。',
      zhTW: '在這裡查看家庭成員，並按需要編輯、停用或維護偏好。',
      enUS: 'Review household members here, then edit, disable, or manage preferences as needed.',
    }),
    addButton: pickLocaleText(locale, { zhCN: '新增成员', zhTW: '新增成員', enUS: 'Add member' }),
    loading: pickLocaleText(locale, { zhCN: '正在加载成员数据...', zhTW: '正在載入成員資料...', enUS: 'Loading member data...' }),
    lunarBirthday: pickLocaleText(locale, { zhCN: '农历生日', zhTW: '農曆生日', enUS: 'Lunar birthday' }),
    solarBirthday: pickLocaleText(locale, { zhCN: '公历生日', zhTW: '公曆生日', enUS: 'Solar birthday' }),
    birthdayUnset: pickLocaleText(locale, { zhCN: '未设置生日', zhTW: '未設定生日', enUS: 'Birthday not set' }),
    agePending: pickLocaleText(locale, { zhCN: '年龄待补充', zhTW: '年齡待補充', enUS: 'Age pending' }),
    birthdaySoon: pickLocaleText(locale, { zhCN: '生日快到了', zhTW: '生日快到了', enUS: 'Birthday is coming soon' }),
    nickname: pickLocaleText(locale, { zhCN: '昵称', zhTW: '暱稱', enUS: 'Nickname' }),
    gender: pickLocaleText(locale, { zhCN: '性别', zhTW: '性別', enUS: 'Gender' }),
    genderUnset: pickLocaleText(locale, { zhCN: '未设置', zhTW: '未設定', enUS: 'Not set' }),
    genderMale: pickLocaleText(locale, { zhCN: '男', zhTW: '男', enUS: 'Male' }),
    genderFemale: pickLocaleText(locale, { zhCN: '女', zhTW: '女', enUS: 'Female' }),
    role: pickLocaleText(locale, { zhCN: '角色', zhTW: '角色', enUS: 'Role' }),
    ageGroup: pickLocaleText(locale, { zhCN: '年龄分组', zhTW: '年齡分組', enUS: 'Age group' }),
    ageGroupAuto: pickLocaleText(locale, {
      zhCN: '已根据生日自动计算年龄分组',
      zhTW: '已根據生日自動計算年齡分組',
      enUS: 'Age group is calculated automatically from the birthday.',
    }),
    birthday: pickLocaleText(locale, { zhCN: '生日', zhTW: '生日', enUS: 'Birthday' }),
    lunarReminder: pickLocaleText(locale, { zhCN: '按农历生日提醒', zhTW: '按農曆生日提醒', enUS: 'Use lunar birthday reminders' }),
    phone: pickLocaleText(locale, { zhCN: '手机号', zhTW: '手機號', enUS: 'Phone number' }),
    memberStatus: pickLocaleText(locale, { zhCN: '状态', zhTW: '狀態', enUS: 'Status' }),
    adminStatusHint: pickLocaleText(locale, {
      zhCN: '管理员默认保持启用，避免影响家庭管理',
      zhTW: '管理員預設保持啟用，避免影響家庭管理',
      enUS: 'Admins stay active by default to avoid breaking household management.',
    }),
    guardian: pickLocaleText(locale, { zhCN: '监护人', zhTW: '監護人', enUS: 'Guardian' }),
    guardianSelect: pickLocaleText(locale, { zhCN: '请选择监护人', zhTW: '請選擇監護人', enUS: 'Select a guardian' }),
    guardianHint: pickLocaleText(locale, {
      zhCN: '儿童角色需要绑定一位已启用的成人或管理员',
      zhTW: '兒童角色需要綁定一位已啟用的成人或管理員',
      enUS: 'A child role needs an active adult or admin as guardian.',
    }),
    modalDesc: pickLocaleText(locale, {
      zhCN: '填写基础信息后，成员会直接加入当前家庭。',
      zhTW: '填寫基礎資訊後，成員會直接加入目前家庭。',
      enUS: 'After filling in the basic information, the member will be added to the current household.',
    }),
    name: pickLocaleText(locale, { zhCN: '姓名', zhTW: '姓名', enUS: 'Name' }),
    preferredName: pickLocaleText(locale, { zhCN: '偏好称呼', zhTW: '偏好稱呼', enUS: 'Preferred name' }),
    reminderNote: pickLocaleText(locale, { zhCN: '提醒方式备注', zhTW: '提醒方式備註', enUS: 'Reminder note' }),
    reminderPlaceholder: pickLocaleText(locale, { zhCN: '例如：语音+站内消息', zhTW: '例如：語音 + 站內訊息', enUS: 'For example: voice + in-app message' }),
    sleepStart: pickLocaleText(locale, { zhCN: '作息开始', zhTW: '作息開始', enUS: 'Sleep start' }),
    sleepEnd: pickLocaleText(locale, { zhCN: '作息结束', zhTW: '作息結束', enUS: 'Sleep end' }),
  };
  const formatAgeText = (age: number | null) => age === null
    ? copy.agePending
    : pickLocaleText(locale, { zhCN: `${age} 岁`, zhTW: `${age} 歲`, enUS: `${age} years old` });
  const guardianCandidates = useMemo(
    () => members.filter(member => member.id !== editingMemberId && member.status === 'active' && (member.role === 'admin' || member.role === 'adult')),
    [editingMemberId, members],
  );
  const createAgeGroupOptions = useMemo(() => getAgeGroupOptionsForRole(createForm.role, locale), [createForm.role, locale]);
  const createStatusOptions = useMemo(() => getAllowedStatusOptions(createForm.role, locale), [createForm.role, locale]);
  const editingAgeGroupOptions = useMemo(() => getAgeGroupOptionsForRole(editingMemberDraft.role, locale), [editingMemberDraft.role, locale]);
  const editingStatusOptions = useMemo(() => getAllowedStatusOptions(editingMemberDraft.role, locale), [editingMemberDraft.role, locale]);
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
    const allowedAgeGroups = getAgeGroupOptionsForRole(createForm.role, locale).map(option => option.value);

    if (inferredAgeGroup && allowedAgeGroups.includes(inferredAgeGroup)) {
      if (createForm.age_group !== inferredAgeGroup) {
        setCreateForm(current => ({ ...current, age_group: inferredAgeGroup }));
      }
      return;
    }

    if (!allowedAgeGroups.includes(createForm.age_group)) {
      setCreateForm(current => ({ ...current, age_group: allowedAgeGroups[0] }));
    }
  }, [createForm.age_group, createForm.birthday, createForm.role, locale]);

  useEffect(() => {
    if (!roleNeedsGuardian(createForm.role) && createForm.guardian_member_id) {
      setCreateForm(current => ({ ...current, guardian_member_id: '' }));
    }

    if (!roleNeedsGuardian(createForm.role) && createErrors.guardian_member_id) {
      setCreateErrors(current => ({ ...current, guardian_member_id: '' }));
    }

    if (!getAllowedStatusOptions(createForm.role, locale).some(option => option.value === createForm.status)) {
      setCreateForm(current => ({ ...current, status: 'active' }));
    }
  }, [createErrors.guardian_member_id, createForm.guardian_member_id, createForm.role, createForm.status, locale]);

  useEffect(() => {
    const inferredAgeGroup = inferAgeGroupFromBirthday(editingMemberDraft.birthday);
    const allowedAgeGroups = getAgeGroupOptionsForRole(editingMemberDraft.role, locale).map(option => option.value);

    if (inferredAgeGroup && allowedAgeGroups.includes(inferredAgeGroup)) {
      if (editingMemberDraft.age_group !== inferredAgeGroup) {
        setEditingMemberDraft(current => ({ ...current, age_group: inferredAgeGroup }));
      }
      return;
    }

    if (!allowedAgeGroups.includes(editingMemberDraft.age_group)) {
      setEditingMemberDraft(current => ({ ...current, age_group: allowedAgeGroups[0] }));
    }
  }, [editingMemberDraft.age_group, editingMemberDraft.birthday, editingMemberDraft.role, locale]);

  useEffect(() => {
    if (!roleNeedsGuardian(editingMemberDraft.role) && editingMemberDraft.guardian_member_id) {
      setEditingMemberDraft(current => ({ ...current, guardian_member_id: '' }));
    }

    if (!getAllowedStatusOptions(editingMemberDraft.role, locale).some(option => option.value === editingMemberDraft.status)) {
      setEditingMemberDraft(current => ({ ...current, status: 'active' }));
    }
  }, [editingMemberDraft.guardian_member_id, editingMemberDraft.role, editingMemberDraft.status, locale]);

  function validateCreateMemberForm() {
    const nextErrors: { name?: string; phone?: string; guardian_member_id?: string } = {};

    if (!createForm.name.trim()) {
      nextErrors.name = copy.nameRequired;
    }

    const phoneError = validatePhoneNumber(createForm.phone, locale);
    if (phoneError) {
      nextErrors.phone = phoneError;
    }

    if (roleNeedsGuardian(createForm.role) && !createForm.guardian_member_id) {
      nextErrors.guardian_member_id = copy.guardianRequired;
    }

    setCreateErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleCreateMember(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId) {
      setError(copy.selectHousehold);
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
      setStatus(copy.createSuccess);
      setToastMessage(copy.createToast);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : copy.createFailure);
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
      setError(copy.guardianRequiredBeforeSave);
      return;
    }

    const phoneError = validatePhoneNumber(editingMemberDraft.phone, locale);
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
      setStatus(copy.saveSuccess);
      setToastMessage(copy.saveToast);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : copy.saveFailure);
    }
  }

  async function handleToggleMemberStatus(member: Member) {
    const nextStatus: Member['status'] = member.status === 'active' ? 'inactive' : 'active';

    if (nextStatus === 'inactive') {
      const confirmed = window.confirm(copy.disableConfirm(member.name));
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
      setStatus(nextStatus === 'inactive' ? copy.disableSuccess : copy.enableSuccess);
      setToastMessage(nextStatus === 'inactive' ? copy.disableToast : copy.enableToast);
    } catch (toggleError) {
      setError(toggleError instanceof Error ? toggleError.message : (nextStatus === 'inactive' ? copy.disableFailure : copy.enableFailure));
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
      setStatus(copy.preferencesSaveSuccess);
      setToastMessage(copy.preferencesSaveToast);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : copy.preferencesSaveFailure);
    }
  }

  return (
    <div className="family-members">
      {toastMessage && <div className="page-toast">{toastMessage}</div>}
      <div className="member-page-toolbar">
        <div>
          <h2 className="member-page-toolbar__title">{copy.title}</h2>
          <p className="member-page-toolbar__desc">{copy.desc}</p>
        </div>
        <button className="btn btn--primary" type="button" onClick={openCreateMemberModal}>{copy.addButton}</button>
      </div>
      {(status || error) && <div className="text-text-secondary" style={{ marginBottom: '1rem' }}>{error || status}</div>}
      <div className="member-detail-grid">
        {loading && sortedMembers.length === 0 ? <div className="text-text-secondary">{copy.loading}</div> : sortedMembers.map(member => {
          const status = getMemberStatus(member.id, overview);
          const isEditingMember = editingMemberId === member.id;
          const isInactiveMember = member.status === 'inactive';
          const isLunarBirthday = preferencesByMemberId[member.id]?.birthday_is_lunar ?? false;
          const age = getAgeFromBirthday(member.birthday);
          const birthdayCountdownDays = isLunarBirthday ? getLunarBirthdayCountdownDays(member.birthday) : getBirthdayCountdownDays(member.birthday);
          const birthdayCountdown = formatBirthdayCountdown(birthdayCountdownDays, isLunarBirthday, locale);
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
                    {isInactiveMember && <span className="badge badge--inactive">{copy.disabledStatus}</span>}
                  </div>
                  <span className="member-detail-card__role">{formatRole(member.role, locale)}</span>
                </div>
                <span className={`badge badge--${status === 'home' ? 'success' : status === 'resting' ? 'warning' : 'secondary'}`}>
                  {status === 'home' ? t('member.atHome') : status === 'resting' ? t('member.resting') : t('member.away')}
                </span>
              </div>
              <div className="member-detail-card__meta">
                <span className={`birthday-kind-badge ${isLunarBirthday ? 'birthday-kind-badge--lunar' : 'birthday-kind-badge--solar'}`}>
                  {isLunarBirthday ? copy.lunarBirthday : copy.solarBirthday}
                </span>
                <span className="meta-item">🎂 {member.birthday ?? copy.birthdayUnset}</span>
                <span className="meta-item">🧮 {formatAgeText(age)}</span>
                <span className="meta-item">🎉 {birthdayCountdown}</span>
                {isBirthdaySoon && <span className="meta-item meta-item--highlight">✨ {copy.birthdaySoon}</span>}
              </div>
              <p className="member-detail-card__prefs">{formatPreferenceSummary(preferencesByMemberId[member.id], locale)}</p>
              <div className="member-detail-card__actions">
                <button className="card-action-btn" type="button" onClick={() => isEditingMember ? setEditingMemberId(null) : openMemberEditor(member)}>
                  {isEditingMember ? t('common.cancel') : t('member.edit')}
                </button>
                <button className="card-action-btn" type="button" onClick={() => void handleToggleMemberStatus(member)}>
                  {member.status === 'active' ? copy.disabledAction : copy.enabledAction}
                </button>
                <button className="card-action-btn" type="button" onClick={() => openPreferencesEditor(member)}>{t('member.preferences')}</button>
              </div>
              {isEditingMember && (
                <div className="settings-form" style={{ marginTop: '1rem' }}>
                  <div className="form-group">
                    <label>{copy.nickname}</label>
                    <input className="form-input" value={editingMemberDraft.nickname} onChange={event => setEditingMemberDraft(current => ({ ...current, nickname: event.target.value }))} />
                  </div>
                  <div className="form-group">
                    <label>{copy.gender}</label>
                    <select className="form-select" value={editingMemberDraft.gender} onChange={event => setEditingMemberDraft(current => ({ ...current, gender: event.target.value as '' | 'male' | 'female' }))}>
                      <option value="">{copy.genderUnset}</option>
                      <option value="male">{copy.genderMale}</option>
                      <option value="female">{copy.genderFemale}</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>{copy.role}</label>
                    <select className="form-select" value={editingMemberDraft.role} onChange={event => setEditingMemberDraft(current => ({ ...current, role: event.target.value as Member['role'] }))}>
                      {getMemberRoleOptions(locale).map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>{copy.ageGroup}</label>
                    <select className="form-select" value={editingMemberDraft.age_group} disabled={Boolean(editingMemberDraft.birthday)} onChange={event => setEditingMemberDraft(current => ({ ...current, age_group: event.target.value as NonNullable<Member['age_group']> }))}>
                      {editingAgeGroupOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                    {editingMemberDraft.birthday && <div className="form-help">{copy.ageGroupAuto}</div>}
                  </div>
                  <div className="form-group">
                    <label>{copy.birthday}</label>
                    <input className="form-input" type="date" value={editingMemberDraft.birthday} onChange={event => setEditingMemberDraft(current => ({ ...current, birthday: event.target.value }))} />
                  </div>
                  <label className="toggle-row member-inline-toggle">
                    <div className="toggle-row__text">
                      <span className="toggle-row__label">{copy.lunarReminder}</span>
                    </div>
                    <div className={`toggle-switch ${editingMemberDraft.birthday_is_lunar ? 'toggle-switch--on' : ''}`} onClick={() => setEditingMemberDraft(current => ({ ...current, birthday_is_lunar: !current.birthday_is_lunar }))}>
                      <div className="toggle-switch__thumb" />
                    </div>
                  </label>
                  <div className="form-group">
                    <label>{copy.phone}</label>
                    <input className="form-input" value={editingMemberDraft.phone} onChange={event => setEditingMemberDraft(current => ({ ...current, phone: event.target.value }))} />
                  </div>
                  <div className="form-group">
                    <label>{copy.memberStatus}</label>
                    <select className="form-select" value={editingMemberDraft.status} onChange={event => setEditingMemberDraft(current => ({ ...current, status: event.target.value as Member['status'] }))}>
                      {editingStatusOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                    {editingMemberDraft.role === 'admin' && <div className="form-help">{copy.adminStatusHint}</div>}
                  </div>
                  {roleNeedsGuardian(editingMemberDraft.role) && (
                    <div className="form-group">
                      <label>{copy.guardian}</label>
                      <select className="form-select" value={editingMemberDraft.guardian_member_id} onChange={event => setEditingMemberDraft(current => ({ ...current, guardian_member_id: event.target.value }))}>
                        <option value="">{copy.guardianSelect}</option>
                        {guardianCandidates.map(candidate => <option key={candidate.id} value={candidate.id}>{candidate.name}（{formatRole(candidate.role, locale)}）</option>)}
                      </select>
                      <div className="form-help">{copy.guardianHint}</div>
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
                <h3>{copy.addButton}</h3>
                <p>{copy.modalDesc}</p>
              </div>
              <button className="card-action-btn" type="button" onClick={closeCreateMemberModal}>{t('common.cancel')}</button>
            </div>
            <form className="settings-form" onSubmit={handleCreateMember} noValidate>
              <div className="form-group">
                <label>{copy.name}</label>
                <input
                  className={`form-input${createErrors.name ? ' form-input--error' : ''}`}
                  value={createForm.name}
                  onChange={event => {
                    const value = event.target.value;
                    setCreateForm(current => ({ ...current, name: value }));
                    if (createErrors.name) {
                      setCreateErrors(current => ({ ...current, name: value.trim() ? '' : copy.nameRequired }));
                    }
                  }}
                />
                {createErrors.name && <div className="form-error">{createErrors.name}</div>}
              </div>
              <div className="form-group">
                <label>{copy.nickname}</label>
                <input className="form-input" value={createForm.nickname} onChange={event => setCreateForm(current => ({ ...current, nickname: event.target.value }))} />
              </div>
              <div className="form-group">
                <label>{copy.gender}</label>
                <select className="form-select" value={createForm.gender} onChange={event => setCreateForm(current => ({ ...current, gender: event.target.value as '' | 'male' | 'female' }))}>
                  <option value="">{copy.genderUnset}</option>
                  <option value="male">{copy.genderMale}</option>
                  <option value="female">{copy.genderFemale}</option>
                </select>
              </div>
              <div className="form-group">
                <label>{copy.role}</label>
                <select className="form-select" value={createForm.role} onChange={event => setCreateForm(current => ({ ...current, role: event.target.value as Member['role'] }))}>
                  {getMemberRoleOptions(locale).map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>{copy.ageGroup}</label>
                <select className="form-select" value={createForm.age_group} disabled={Boolean(createForm.birthday)} onChange={event => setCreateForm(current => ({ ...current, age_group: event.target.value as NonNullable<Member['age_group']> }))}>
                  {createAgeGroupOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
                {createForm.birthday && <div className="form-help">{copy.ageGroupAuto}</div>}
              </div>
              <div className="form-group">
                <label>{copy.birthday}</label>
                <input className="form-input" type="date" value={createForm.birthday} onChange={event => setCreateForm(current => ({ ...current, birthday: event.target.value }))} />
              </div>
              <label className="toggle-row member-inline-toggle">
                <div className="toggle-row__text">
                  <span className="toggle-row__label">{copy.lunarReminder}</span>
                </div>
                <div className={`toggle-switch ${createForm.birthday_is_lunar ? 'toggle-switch--on' : ''}`} onClick={() => setCreateForm(current => ({ ...current, birthday_is_lunar: !current.birthday_is_lunar }))}>
                  <div className="toggle-switch__thumb" />
                </div>
              </label>
              <div className="form-group">
                <label>{copy.phone}</label>
                <input
                  className={`form-input${createErrors.phone ? ' form-input--error' : ''}`}
                  value={createForm.phone}
                  onChange={event => {
                    const value = event.target.value;
                    setCreateForm(current => ({ ...current, phone: value }));
                    if (createErrors.phone) {
                      setCreateErrors(current => ({ ...current, phone: validatePhoneNumber(value, locale) || '' }));
                    }
                  }}
                />
                {createErrors.phone && <div className="form-error">{createErrors.phone}</div>}
              </div>
              <div className="form-group">
                <label>{copy.memberStatus}</label>
                <select className="form-select" value={createForm.status} onChange={event => setCreateForm(current => ({ ...current, status: event.target.value as Member['status'] }))}>
                  {createStatusOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
                {createForm.role === 'admin' && <div className="form-help">{copy.adminStatusHint}</div>}
              </div>
              {roleNeedsGuardian(createForm.role) && (
                <div className="form-group">
                  <label>{copy.guardian}</label>
                  <select className={`form-select${createErrors.guardian_member_id ? ' form-select--error' : ''}`} value={createForm.guardian_member_id} onChange={event => {
                    const value = event.target.value;
                    setCreateForm(current => ({ ...current, guardian_member_id: value }));
                    if (createErrors.guardian_member_id) {
                      setCreateErrors(current => ({ ...current, guardian_member_id: value ? '' : copy.guardianRequired }));
                    }
                  }}>
                    <option value="">{copy.guardianSelect}</option>
                    {guardianCandidates.map(candidate => <option key={candidate.id} value={candidate.id}>{candidate.name}（{formatRole(candidate.role, locale)}）</option>)}
                  </select>
                  {createErrors.guardian_member_id ? <div className="form-error">{createErrors.guardian_member_id}</div> : <div className="form-help">{copy.guardianHint}</div>}
                </div>
              )}
              <div className="member-modal__actions">
                <button className="btn btn--outline" type="button" onClick={closeCreateMemberModal}>{t('common.cancel')}</button>
                <button className="btn btn--primary" type="submit">{copy.addButton}</button>
              </div>
            </form>
          </div>
        </div>
      )}
      {editingPreferencesMemberId && (
        <Card className="member-detail-card" style={{ marginTop: '1rem' }}>
          <div className="settings-form">
            <div className="form-group">
              <label>{copy.preferredName}</label>
              <input className="form-input" value={preferencesDraft.preferred_name} onChange={event => setPreferencesDraft(current => ({ ...current, preferred_name: event.target.value }))} />
            </div>
            <div className="form-group">
              <label>{copy.reminderNote}</label>
              <input className="form-input" value={preferencesDraft.reminder_channel} onChange={event => setPreferencesDraft(current => ({ ...current, reminder_channel: event.target.value }))} placeholder={copy.reminderPlaceholder} />
            </div>
            <div className="form-group">
              <label>{copy.sleepStart}</label>
              <input className="form-input" value={preferencesDraft.sleep_start} onChange={event => setPreferencesDraft(current => ({ ...current, sleep_start: event.target.value }))} placeholder="22:00" />
            </div>
            <div className="form-group">
              <label>{copy.sleepEnd}</label>
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
const RELATION_LABELS: Record<string, { zhCN: string; zhTW: string; enUS: string }> = {
  husband: { zhCN: '丈夫', zhTW: '丈夫', enUS: 'Husband' },
  wife: { zhCN: '妻子', zhTW: '妻子', enUS: 'Wife' },
  spouse: { zhCN: '配偶', zhTW: '配偶', enUS: 'Spouse' },
  father: { zhCN: '爸爸', zhTW: '爸爸', enUS: 'Father' },
  mother: { zhCN: '妈妈', zhTW: '媽媽', enUS: 'Mother' },
  parent: { zhCN: '父/母', zhTW: '父／母', enUS: 'Parent' },
  son: { zhCN: '儿子', zhTW: '兒子', enUS: 'Son' },
  daughter: { zhCN: '女儿', zhTW: '女兒', enUS: 'Daughter' },
  child: { zhCN: '子女', zhTW: '子女', enUS: 'Child' },
  older_brother: { zhCN: '哥哥', zhTW: '哥哥', enUS: 'Older brother' },
  older_sister: { zhCN: '姐姐', zhTW: '姐姐', enUS: 'Older sister' },
  younger_brother: { zhCN: '弟弟', zhTW: '弟弟', enUS: 'Younger brother' },
  younger_sister: { zhCN: '妹妹', zhTW: '妹妹', enUS: 'Younger sister' },
  grandfather_paternal: { zhCN: '爷爷', zhTW: '爺爺', enUS: 'Paternal grandfather' },
  grandmother_paternal: { zhCN: '奶奶', zhTW: '奶奶', enUS: 'Paternal grandmother' },
  grandfather_maternal: { zhCN: '姥爷', zhTW: '姥爺', enUS: 'Maternal grandfather' },
  grandmother_maternal: { zhCN: '姥姥', zhTW: '姥姥', enUS: 'Maternal grandmother' },
  grandson: { zhCN: '孙子', zhTW: '孫子', enUS: 'Grandson' },
  granddaughter: { zhCN: '孙女', zhTW: '孫女', enUS: 'Granddaughter' },
  guardian: { zhCN: '监护人', zhTW: '監護人', enUS: 'Guardian' },
  ward: { zhCN: '被监护人', zhTW: '被監護人', enUS: 'Ward' },
  caregiver: { zhCN: '照护者', zhTW: '照護者', enUS: 'Caregiver' },
};

/* 通用关系分类标签 (用于图谱默认连线) */
const RELATION_CATEGORY_LABELS: Record<string, { zhCN: string; zhTW: string; enUS: string }> = {
  husband: { zhCN: '配偶', zhTW: '配偶', enUS: 'Spouse' },
  wife: { zhCN: '配偶', zhTW: '配偶', enUS: 'Spouse' },
  spouse: { zhCN: '配偶', zhTW: '配偶', enUS: 'Spouse' },
  father: { zhCN: '父子/父女', zhTW: '父子／父女', enUS: 'Parent-child' },
  mother: { zhCN: '母子/母女', zhTW: '母子／母女', enUS: 'Parent-child' },
  parent: { zhCN: '亲子', zhTW: '親子', enUS: 'Parent-child' },
  son: { zhCN: '父子/母子', zhTW: '父子／母子', enUS: 'Parent-child' },
  daughter: { zhCN: '父女/母女', zhTW: '父女／母女', enUS: 'Parent-child' },
  child: { zhCN: '亲子', zhTW: '親子', enUS: 'Parent-child' },
  older_brother: { zhCN: '兄弟/兄妹', zhTW: '兄弟／兄妹', enUS: 'Siblings' },
  older_sister: { zhCN: '姐弟/姐妹', zhTW: '姐弟／姐妹', enUS: 'Siblings' },
  younger_brother: { zhCN: '兄弟/姐弟', zhTW: '兄弟／姐弟', enUS: 'Siblings' },
  younger_sister: { zhCN: '兄妹/姐妹', zhTW: '兄妹／姐妹', enUS: 'Siblings' },
  grandfather_paternal: { zhCN: '祖孙', zhTW: '祖孫', enUS: 'Grandparent-grandchild' },
  grandmother_paternal: { zhCN: '祖孙', zhTW: '祖孫', enUS: 'Grandparent-grandchild' },
  grandfather_maternal: { zhCN: '外孙', zhTW: '外孫', enUS: 'Maternal grandchild' },
  grandmother_maternal: { zhCN: '外孙', zhTW: '外孫', enUS: 'Maternal grandchild' },
  grandson: { zhCN: '孙子', zhTW: '孫子', enUS: 'Grandson' },
  granddaughter: { zhCN: '孙女', zhTW: '孫女', enUS: 'Granddaughter' },
  guardian: { zhCN: '监护', zhTW: '監護', enUS: 'Guardianship' },
  ward: { zhCN: '监护', zhTW: '監護', enUS: 'Guardianship' },
  caregiver: { zhCN: '照护', zhTW: '照護', enUS: 'Care' },
};

function getRelationLabel(relationType: string, locale: string | undefined) {
  const label = RELATION_LABELS[relationType];
  return label ? pickLocaleText(locale, label) : relationType;
}

function getRelationCategoryFallback(relationType: string, locale: string | undefined) {
  const label = RELATION_CATEGORY_LABELS[relationType];
  return label ? pickLocaleText(locale, label) : relationType;
}

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

function getSpouseCategoryLabel(firstGender: Member['gender'], secondGender: Member['gender'], locale: string | undefined) {
  if (firstGender === 'male' && secondGender === 'male') return pickLocaleText(locale, { zhCN: '夫夫', zhTW: '夫夫', enUS: 'Husbands' });
  if (firstGender === 'female' && secondGender === 'female') return pickLocaleText(locale, { zhCN: '妻妻', zhTW: '妻妻', enUS: 'Wives' });
  if (
    (firstGender === 'male' && secondGender === 'female')
    || (firstGender === 'female' && secondGender === 'male')
  ) {
    return pickLocaleText(locale, { zhCN: '夫妻', zhTW: '夫妻', enUS: 'Married couple' });
  }
  return pickLocaleText(locale, { zhCN: '伴侣', zhTW: '伴侶', enUS: 'Partners' });
}

function getParentChildCategoryLabel(parentGender: Member['gender'], childGender: Member['gender'], locale: string | undefined) {
  if (parentGender === 'male') {
    if (childGender === 'male') return pickLocaleText(locale, { zhCN: '父子', zhTW: '父子', enUS: 'Father-son' });
    if (childGender === 'female') return pickLocaleText(locale, { zhCN: '父女', zhTW: '父女', enUS: 'Father-daughter' });
    return pickLocaleText(locale, { zhCN: '父子/父女', zhTW: '父子／父女', enUS: 'Father-child' });
  }

  if (parentGender === 'female') {
    if (childGender === 'male') return pickLocaleText(locale, { zhCN: '母子', zhTW: '母子', enUS: 'Mother-son' });
    if (childGender === 'female') return pickLocaleText(locale, { zhCN: '母女', zhTW: '母女', enUS: 'Mother-daughter' });
    return pickLocaleText(locale, { zhCN: '母子/母女', zhTW: '母子／母女', enUS: 'Mother-child' });
  }

  if (childGender === 'male') return pickLocaleText(locale, { zhCN: '父子/母子', zhTW: '父子／母子', enUS: 'Parent-son' });
  if (childGender === 'female') return pickLocaleText(locale, { zhCN: '父女/母女', zhTW: '父女／母女', enUS: 'Parent-daughter' });
  return pickLocaleText(locale, { zhCN: '亲子', zhTW: '親子', enUS: 'Parent-child' });
}

function getSiblingCategoryLabel(olderGender: Member['gender'], youngerGender: Member['gender'], locale: string | undefined) {
  if (olderGender === 'male') {
    if (youngerGender === 'male') return pickLocaleText(locale, { zhCN: '兄弟', zhTW: '兄弟', enUS: 'Brothers' });
    if (youngerGender === 'female') return pickLocaleText(locale, { zhCN: '兄妹', zhTW: '兄妹', enUS: 'Brother and sister' });
    return pickLocaleText(locale, { zhCN: '兄弟/兄妹', zhTW: '兄弟／兄妹', enUS: 'Siblings' });
  }

  if (olderGender === 'female') {
    if (youngerGender === 'male') return pickLocaleText(locale, { zhCN: '姐弟', zhTW: '姐弟', enUS: 'Sister and brother' });
    if (youngerGender === 'female') return pickLocaleText(locale, { zhCN: '姐妹', zhTW: '姐妹', enUS: 'Sisters' });
    return pickLocaleText(locale, { zhCN: '姐弟/姐妹', zhTW: '姐弟／姐妹', enUS: 'Siblings' });
  }

  if (youngerGender === 'male') return pickLocaleText(locale, { zhCN: '兄弟/姐弟', zhTW: '兄弟／姐弟', enUS: 'Siblings' });
  if (youngerGender === 'female') return pickLocaleText(locale, { zhCN: '兄妹/姐妹', zhTW: '兄妹／姐妹', enUS: 'Siblings' });
  return pickLocaleText(locale, { zhCN: '手足', zhTW: '手足', enUS: 'Siblings' });
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
  locale: string | undefined,
) {
  const maleLabel = side === 'maternal'
    ? pickLocaleText(locale, { zhCN: '外孙', zhTW: '外孫', enUS: 'Maternal grandson' })
    : pickLocaleText(locale, { zhCN: '孙子', zhTW: '孫子', enUS: 'Grandson' });
  const femaleLabel = side === 'maternal'
    ? pickLocaleText(locale, { zhCN: '外孙女', zhTW: '外孫女', enUS: 'Maternal granddaughter' })
    : pickLocaleText(locale, { zhCN: '孙女', zhTW: '孫女', enUS: 'Granddaughter' });

  if (grandchildGender === 'male') return maleLabel;
  if (grandchildGender === 'female') return femaleLabel;
  return `${maleLabel}/${femaleLabel}`;
}

function getRelationCategoryLabel(
  relationship: MemberRelationship,
  reverseRelationship: MemberRelationship | undefined,
  locale: string | undefined,
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
      return getSpouseCategoryLabel(sourceGender, targetGender, locale);
    case 'father':
    case 'mother':
    case 'parent':
      return getParentChildCategoryLabel(targetGender, sourceGender, locale);
    case 'son':
    case 'daughter':
    case 'child':
      return getParentChildCategoryLabel(sourceGender, targetGender, locale);
    case 'older_brother':
    case 'older_sister':
      return getSiblingCategoryLabel(targetGender, sourceGender, locale);
    case 'younger_brother':
    case 'younger_sister':
      return getSiblingCategoryLabel(sourceGender, targetGender, locale);
    case 'grandfather_paternal':
    case 'grandmother_paternal':
    case 'grandfather_maternal':
    case 'grandmother_maternal':
      return getGrandparentCategoryLabel(
        sourceGender,
        inferGrandparentSide(relationType, reverseRelationType),
        locale,
      );
    case 'grandson':
    case 'granddaughter':
      return getGrandparentCategoryLabel(
        targetGender,
        inferGrandparentSide(relationType, reverseRelationType),
        locale,
      );
    case 'guardian':
    case 'ward':
      return pickLocaleText(locale, { zhCN: '监护', zhTW: '監護', enUS: 'Guardianship' });
    case 'caregiver':
      return pickLocaleText(locale, { zhCN: '照护', zhTW: '照護', enUS: 'Care' });
    default:
      return getRelationCategoryFallback(relationType, locale);
  }
}

type RelationOption = { value: string; label: string };

function getRelationOptionsForRole(role: string, locale: string | undefined): RelationOption[] {
  const childOptions: RelationOption[] = [
    { value: 'father', label: '' }, { value: 'mother', label: '' },
    { value: 'older_brother', label: '' }, { value: 'older_sister', label: '' },
    { value: 'younger_brother', label: '' }, { value: 'younger_sister', label: '' },
    { value: 'grandfather_paternal', label: '' }, { value: 'grandmother_paternal', label: '' },
    { value: 'grandfather_maternal', label: '' }, { value: 'grandmother_maternal', label: '' },
    { value: 'guardian', label: '' },
  ];

  const adultOptions: RelationOption[] = [
    { value: 'husband', label: '' }, { value: 'wife', label: '' },
    { value: 'father', label: '' }, { value: 'mother', label: '' },
    { value: 'son', label: '' }, { value: 'daughter', label: '' },
    { value: 'older_brother', label: '' }, { value: 'older_sister', label: '' },
    { value: 'younger_brother', label: '' }, { value: 'younger_sister', label: '' },
    { value: 'grandfather_paternal', label: '' }, { value: 'grandmother_paternal', label: '' },
    { value: 'grandfather_maternal', label: '' }, { value: 'grandmother_maternal', label: '' },
    { value: 'grandson', label: '' }, { value: 'granddaughter', label: '' },
    { value: 'guardian', label: '' }, { value: 'ward', label: '' },
    { value: 'caregiver', label: '' },
  ];

  const elderOptions: RelationOption[] = [
    { value: 'husband', label: '' }, { value: 'wife', label: '' },
    { value: 'son', label: '' }, { value: 'daughter', label: '' },
    { value: 'grandson', label: '' }, { value: 'granddaughter', label: '' },
    { value: 'older_brother', label: '' }, { value: 'older_sister', label: '' },
    { value: 'younger_brother', label: '' }, { value: 'younger_sister', label: '' },
    { value: 'ward', label: '' },
    { value: 'caregiver', label: '' },
  ];

  switch (role) {
    case 'child': return childOptions.map(option => ({ ...option, label: getRelationLabel(option.value, locale) }));
    case 'elder': return elderOptions.map(option => ({ ...option, label: getRelationLabel(option.value, locale) }));
    default: return adultOptions.map(option => ({ ...option, label: getRelationLabel(option.value, locale) }));
  }
}

/* ---- SVG 关系图谱 ---- */
type GraphNode = { id: string; name: string; role: string; x: number; y: number; vx: number; vy: number };
type GraphEdge = { source: string; target: string; label: string; relationType: string };

function buildGraphData(
  members: Member[],
  relationships: MemberRelationship[],
  locale: string | undefined,
): { nodes: GraphNode[]; edges: GraphEdge[] } {
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
          locale,
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
  locale: string | undefined,
): string {
  // 从 selectedMember 视角: 找 selectedMember → other 的 relation_type
  const otherId = edge.source === selectedMemberId ? edge.target : edge.source;
  const rel = relationships.find(
    r => r.source_member_id === selectedMemberId && r.target_member_id === otherId,
  );
  if (rel) return getRelationLabel(rel.relation_type, locale);
  // fallback: 反向
  const revRel = relationships.find(
    r => r.source_member_id === otherId && r.target_member_id === selectedMemberId,
  );
  if (revRel) return getRelationLabel(revRel.relation_type, locale);
  return edge.label;
}

function RelationshipGraph({ members, relationships, selectedMemberId, onSelectMember }: {
  members: Member[];
  relationships: MemberRelationship[];
  selectedMemberId: string | null;
  onSelectMember: (id: string | null) => void;
}) {
  const { locale } = useI18n();
  const { nodes, edges } = useMemo(() => buildGraphData(members, relationships, locale), [members, relationships, locale]);

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
            ? getEdgeLabelForPerspective(edge, selectedMemberId, relationships, locale)
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
          {pickLocaleText(locale, {
            zhCN: '👆 已选中 ',
            zhTW: '👆 已選中 ',
            enUS: '👆 Viewing ',
          })}
          <strong>{members.find(m => m.id === selectedMemberId)?.name}</strong>
          {pickLocaleText(locale, {
            zhCN: ' 的视角，点击空白处取消',
            zhTW: ' 的視角，點擊空白處取消',
            enUS: "'s perspective. Click empty space to clear.",
          })}
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

type DynamicGraphLabelLayout = {
  id: string;
  label: string;
  width: number;
  height: number;
  anchor: DynamicGraphPoint;
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

function getGraphEdgePalette(edgeId: string) {
  const palettes = [
    '#ff6b6b',
    '#ff922b',
    '#ffd43b',
    '#69db7c',
    '#38d9a9',
    '#4dabf7',
    '#748ffc',
    '#b197fc',
    '#f06595',
    '#f783ac',
  ] as const;

  return palettes[hashGraphEdge(edgeId) % palettes.length];
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
    labelBase,
    labelNormal,
    labelAnchor: {
      x: labelBase.x + labelNormal.x * 18,
      y: labelBase.y + labelNormal.y * 18,
    },
  };
}

function doGraphLabelBoxesOverlap(a: DynamicGraphLabelLayout, b: DynamicGraphLabelLayout) {
  return Math.abs(a.anchor.x - b.anchor.x) < (a.width + b.width) / 2 + 10
    && Math.abs(a.anchor.y - b.anchor.y) < (a.height + b.height) / 2 + 8;
}

function resolveGraphLabelOverlaps(labels: Array<DynamicGraphLabelLayout & { normal: DynamicGraphPoint; base: DynamicGraphPoint }>) {
  const resolved = labels.map(label => ({ ...label, anchor: { ...label.anchor } }));

  for (let iteration = 0; iteration < 8; iteration += 1) {
    let moved = false;

    for (let i = 0; i < resolved.length; i += 1) {
      for (let j = i + 1; j < resolved.length; j += 1) {
        const current = resolved[i];
        const other = resolved[j];
        if (!doGraphLabelBoxesOverlap(current, other)) {
          continue;
        }

        const separation = 10 + iteration * 4;
        current.anchor = clampGraphPoint({
          x: current.anchor.x + current.normal.x * separation,
          y: current.anchor.y + current.normal.y * separation,
        });
        other.anchor = clampGraphPoint({
          x: other.anchor.x - other.normal.x * separation,
          y: other.anchor.y - other.normal.y * separation,
        });
        moved = true;
      }
    }

    if (!moved) {
      break;
    }
  }

  return resolved;
}

function buildDynamicGraphData(
  members: Member[],
  relationships: MemberRelationship[],
  locale: string | undefined,
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
        locale,
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
  const { locale } = useI18n();
  const { nodes, edges } = useMemo(
    () => buildDynamicGraphData(members, relationships, locale),
    [members, relationships, locale],
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
    if (nodes.length === 0 || dragState) {
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
  }, [nodes, edges, fixedNodes, dragState]);

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

  const edgeLayouts = useMemo(() => {
    const layouts = edges.map(edge => {
      const source = getPos(edge.source);
      const target = getPos(edge.target);
      const geometry = getDynamicEdgeGeometry(source, target, edge.id);
      const isHighlighted = Boolean(selectedMemberId && (edge.source === selectedMemberId || edge.target === selectedMemberId));
      const isDimmed = Boolean(selectedMemberId && !isHighlighted);
      const label = selectedMemberId && isHighlighted
        ? getEdgeLabelForPerspective(edge, selectedMemberId, relationships, locale)
        : edge.label;

      return {
        edge,
        source,
        target,
        geometry,
        palette: getGraphEdgePalette(edge.id),
        isHighlighted,
        isDimmed,
        label,
        labelWidth: Math.max(48, label.length * 16),
      };
    });

    const resolvedLabels = resolveGraphLabelOverlaps(layouts.map(layout => ({
      id: layout.edge.id,
      label: layout.label,
      width: layout.labelWidth,
      height: 24,
      anchor: layout.geometry.labelAnchor,
      base: layout.geometry.labelBase,
      normal: layout.geometry.labelNormal,
    })));

    const labelMap = new Map(resolvedLabels.map(label => [label.id, label.anchor]));
    return layouts.map(layout => ({
      ...layout,
      labelAnchor: labelMap.get(layout.edge.id) ?? layout.geometry.labelAnchor,
    }));
  }, [edges, positions, nodes, selectedMemberId, relationships]);

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
          event.preventDefault();
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
        {edgeLayouts.map(({ edge, geometry, palette, isHighlighted, isDimmed, label, labelWidth, labelAnchor }) => {
          const labelFill = `color-mix(in srgb, ${palette} 14%, var(--bg-card) 86%)`;
          const labelStroke = `color-mix(in srgb, ${palette} 36%, var(--border-light))`;
          const labelText = isHighlighted
            ? 'var(--brand-primary)'
            : `color-mix(in srgb, ${palette} 68%, var(--text-primary))`;

          return (
            <g key={edge.id}>
              <path
                d={geometry.path}
                className={`graph-edge ${isHighlighted ? 'graph-edge--highlight' : ''} ${isDimmed ? 'graph-edge--dim' : ''}`}
                style={{ stroke: palette }}
              />
              <rect
                x={labelAnchor.x - labelWidth / 2}
                y={labelAnchor.y - 12}
                width={labelWidth}
                height={24}
                rx={6}
                className={`graph-edge-label-bg ${isDimmed ? 'graph-edge-label-bg--dim' : ''}`}
                style={{ fill: labelFill, stroke: labelStroke }}
              />
              <text
                x={labelAnchor.x}
                y={labelAnchor.y + 4}
                textAnchor="middle"
                className={`graph-edge-label ${isHighlighted ? 'graph-edge-label--highlight' : ''} ${isDimmed ? 'graph-edge-label--dim' : ''}`}
                style={{ fill: labelText }}
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
                event.preventDefault();
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
          {pickLocaleText(locale, { zhCN: '重置', zhTW: '重設', enUS: 'Reset' })}
        </button>
        <span className="relationship-graph__zoom">{Math.round(viewport.scale * 100)}%</span>
      </div>
      <div className="graph-legend">
        {pickLocaleText(locale, {
          zhCN: '🔗 拖拽节点可整理图谱，双击节点可取消固定；点击成员切换关系视角，点击空白取消选中。',
          zhTW: '🔗 拖曳節點可整理圖譜，雙擊節點可取消固定；點擊成員切換關係視角，點擊空白取消選中。',
          enUS: '🔗 Drag nodes to arrange the graph. Double-click to unpin a node. Click a member to switch perspective, or click empty space to clear.',
        })}
      </div>
    </div>
  );
}

export function FamilyRelationships() {
  const { locale } = useI18n();
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
  const copy = {
    selectMembersAndType: pickLocaleText(locale, { zhCN: '请选择成员和关系类型。', zhTW: '請選擇成員和關係類型。', enUS: 'Select members and a relation type.' }),
    createSuccess: pickLocaleText(locale, {
      zhCN: '关系已创建，反向关系已自动建立。',
      zhTW: '關係已建立，反向關係也已自動建立。',
      enUS: 'Relationship created. The reverse relationship was created automatically.',
    }),
    createFailure: pickLocaleText(locale, { zhCN: '创建关系失败', zhTW: '建立關係失敗', enUS: 'Failed to create relationship' }),
    deleteSuccess: pickLocaleText(locale, { zhCN: '关系已删除。', zhTW: '關係已刪除。', enUS: 'Relationship deleted.' }),
    deleteFailure: pickLocaleText(locale, { zhCN: '删除关系失败', zhTW: '刪除關係失敗', enUS: 'Failed to delete relationship' }),
    graphLoading: pickLocaleText(locale, { zhCN: '正在加载关系数据...', zhTW: '正在載入關係資料...', enUS: 'Loading relationship data...' }),
    graphNeedMembers: pickLocaleText(locale, { zhCN: '至少需要 2 位成员才能创建关系', zhTW: '至少需要 2 位成員才能建立關係', enUS: 'At least 2 members are required before relationships can be created.' }),
    graphEmpty: pickLocaleText(locale, { zhCN: '还没有创建任何关系，请在下方添加。', zhTW: '還沒有建立任何關係，請在下方新增。', enUS: 'No relationships yet. Add one below.' }),
    addTitle: pickLocaleText(locale, { zhCN: '添加关系', zhTW: '新增關係', enUS: 'Add relationship' }),
    selectMember: pickLocaleText(locale, { zhCN: '选择成员', zhTW: '選擇成員', enUS: 'Select member' }),
    selectMemberPlaceholder: pickLocaleText(locale, { zhCN: '请选择成员', zhTW: '請選擇成員', enUS: 'Select a member' }),
    selectRelationPlaceholder: pickLocaleText(locale, { zhCN: '请选择关系', zhTW: '請選擇關係', enUS: 'Select a relationship' }),
    selectTargetPlaceholder: pickLocaleText(locale, { zhCN: '请选择目标成员', zhTW: '請選擇目標成員', enUS: 'Select a target member' }),
    targetLabel: pickLocaleText(locale, { zhCN: '关系目标', zhTW: '關係目標', enUS: 'Relationship target' }),
    addButton: pickLocaleText(locale, { zhCN: '新增关系', zhTW: '新增關係', enUS: 'Add relationship' }),
    listTitle: pickLocaleText(locale, { zhCN: '关系列表', zhTW: '關系列表', enUS: 'Relationships' }),
    deleteButton: pickLocaleText(locale, { zhCN: '删除', zhTW: '刪除', enUS: 'Delete' }),
    deletingButton: pickLocaleText(locale, { zhCN: '删除中...', zhTW: '刪除中...', enUS: 'Deleting...' }),
  };
  const memberNameMap = Object.fromEntries(members.map(member => [member.id, member.name]));
  const relationshipTypeLabel = createForm.source_member_id
    ? pickLocaleText(locale, {
      zhCN: `关系类型（${memberNameMap[createForm.source_member_id] ?? ''} 的…）`,
      zhTW: `關係類型（${memberNameMap[createForm.source_member_id] ?? ''} 的…）`,
      enUS: `Relationship type (${memberNameMap[createForm.source_member_id] ?? ''}'s ...)`,
    })
    : '';

  // 根据所选 source 成员过滤可选关系
  const sourceMember = members.find(m => m.id === createForm.source_member_id);
  const relationOptions = sourceMember ? getRelationOptionsForRole(sourceMember.role, locale) : [];

  // 根据 source 去掉 source 自己
  const targetOptions = members.filter(m => m.id !== createForm.source_member_id);

  async function handleCreateRelationship(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId || !createForm.source_member_id || !createForm.target_member_id || !createForm.relation_type) {
      setError(copy.selectMembersAndType);
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
      setStatus(copy.createSuccess);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : copy.createFailure);
    }
  }

  async function handleDelete(relationshipId: string) {
    setDeleting(relationshipId);
    try {
      setError('');
      await api.deleteMemberRelationship(relationshipId);
      await refreshWorkspace();
      setStatus(copy.deleteSuccess);
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : copy.deleteFailure);
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
            <p>{loading ? copy.graphLoading : members.length < 2 ? copy.graphNeedMembers : copy.graphEmpty}</p>
          </div>
        )}
      </Card>

      {/* 添加关系 */}
      <Card className="relation-card" style={{ marginTop: '1rem' }}>
        <h3 style={{ fontSize: 'var(--font-size-md)', fontWeight: 600, marginBottom: 'var(--spacing-md)' }}>{copy.addTitle}</h3>
        <form className="settings-form relationship-create-form" onSubmit={handleCreateRelationship}>
          <div className="form-group">
            <label>{copy.selectMember}</label>
            <select className="form-select" value={createForm.source_member_id} onChange={event => { setCreateForm(current => ({ ...current, source_member_id: event.target.value, relation_type: '', target_member_id: '' })); setStatus(''); setError(''); }}>
              <option value="">{copy.selectMemberPlaceholder}</option>
              {members.map(member => <option key={member.id} value={member.id}>{member.name}（{formatRole(member.role, locale)}）</option>)}
            </select>
          </div>
          {createForm.source_member_id && (
            <>
              <div className="form-group">
                <label>{relationshipTypeLabel}</label>
                <select className="form-select" value={createForm.relation_type} onChange={event => setCreateForm(current => ({ ...current, relation_type: event.target.value as MemberRelationship['relation_type'] }))}>
                  <option value="">{copy.selectRelationPlaceholder}</option>
                  {relationOptions.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>{copy.targetLabel}</label>
                <select className="form-select" value={createForm.target_member_id} onChange={event => setCreateForm(current => ({ ...current, target_member_id: event.target.value }))}>
                  <option value="">{copy.selectTargetPlaceholder}</option>
                  {targetOptions.map(member => <option key={member.id} value={member.id}>{member.name}（{formatRole(member.role, locale)}）</option>)}
                </select>
              </div>
            </>
          )}
          <button className="btn btn--primary" type="submit" disabled={!createForm.source_member_id || !createForm.target_member_id || !createForm.relation_type}>{copy.addButton}</button>
          {status && <div className="text-text-secondary" style={{ color: 'var(--color-success)' }}>{status}</div>}
          {error && <div className="text-text-secondary" style={{ color: 'var(--color-danger)' }}>{error}</div>}
        </form>
      </Card>

      {/* 关系列表（按成员分组） */}
      {Object.keys(groupedBySource).length > 0 && (
        <Section title={copy.listTitle}>
          {Object.entries(groupedBySource).map(([sourceId, rels]) => (
            <div key={sourceId} className="relation-group">
              <h4 className="relation-group__title">{pickLocaleText(locale, {
                zhCN: `${memberNameMap[sourceId] ?? sourceId} 的关系`,
                zhTW: `${memberNameMap[sourceId] ?? sourceId} 的關係`,
                enUS: `${memberNameMap[sourceId] ?? sourceId}'s relationships`,
              })}</h4>
              <div className="relation-list">
                {rels.map(item => {
                  const toName = memberNameMap[item.target_member_id] ?? item.target_member_id;
                  return (
                    <Card key={item.id} className="relation-card relation-card--compact">
                      <div className="relation-card__pair">
                        <span className="relation-card__label">{getRelationLabel(item.relation_type, locale)}</span>
                        <span className="relation-card__arrow">→</span>
                        <span className="relation-card__name">{toName}</span>
                      </div>
                      <button
                        className="btn btn--danger btn--small"
                        onClick={() => void handleDelete(item.id)}
                        disabled={deleting === item.id}
                      >
                        {deleting === item.id ? copy.deletingButton : copy.deleteButton}
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
