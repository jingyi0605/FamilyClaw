/* ============================================================
 * 瀹跺涵椤?- 鍖呭惈姒傝/鎴块棿/鎴愬憳/鍏崇郴鍥涗釜瀛愯矾鐢?
 * ============================================================ */
import { createContext, useContext, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import Taro from '@tarojs/taro';
import { getLocaleDefinition, type LocaleDefinition } from '@familyclaw/user-core';
import { DEFAULT_REGION_COUNTRY, DEFAULT_REGION_PROVIDER, RegionSelector, type RegionSelectionFormValue } from './RegionSelector';
import { PageHeader, Card, Section } from './base';
import { HouseholdDeviceDetailDialog, type DevicePageLookup } from '../device-management/HouseholdDeviceDetailDialog';
import { useHouseholdContext, useI18n } from '../../runtime';
import { getPageMessage } from '../../runtime/h5-shell/i18n/pageMessageUtils';
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

/* ---- 瀹跺涵瀛愬鑸?---- */
const familyTabs = [
  { key: 'overview' as const, hash: '#overview', labelKey: 'family.overview' as const },
  { key: 'rooms' as const, hash: '#rooms', labelKey: 'family.rooms' as const },
  { key: 'devices' as const, hash: '#devices', labelKey: 'family.devices' as const },
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

function getFamilyMessage(
  locale: string | undefined,
  key: Parameters<typeof getPageMessage>[1],
  params?: Parameters<typeof getPageMessage>[2],
) {
  return getPageMessage(locale, key, params);
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
  return value?.name ?? getFamilyMessage(locale, 'family.common.unknown');
}

function formatHomeMode(mode: ContextOverviewRead['home_mode'] | undefined, locale: string | undefined) {
  switch (mode) {
    case 'home': return getFamilyMessage(locale, 'family.mode.home');
    case 'away': return getFamilyMessage(locale, 'family.mode.away');
    case 'night': return getFamilyMessage(locale, 'family.mode.night');
    case 'sleep': return getFamilyMessage(locale, 'family.mode.sleep');
    case 'custom': return getFamilyMessage(locale, 'family.mode.custom');
    default: return '-';
  }
}

function formatPrivacyMode(mode: ContextOverviewRead['privacy_mode'] | undefined, locale: string | undefined) {
  switch (mode) {
    case 'balanced': return getFamilyMessage(locale, 'family.privacy.balanced');
    case 'strict': return getFamilyMessage(locale, 'family.privacy.strict');
    case 'care': return getFamilyMessage(locale, 'family.privacy.care');
    default: return '-';
  }
}

function formatRole(role: Member['role'], locale: string | undefined) {
  switch (role) {
    case 'admin': return getFamilyMessage(locale, 'family.role.admin');
    case 'adult': return getFamilyMessage(locale, 'family.role.adult');
    case 'child': return getFamilyMessage(locale, 'family.role.child');
    case 'elder': return getFamilyMessage(locale, 'family.role.elder');
    case 'guest': return getFamilyMessage(locale, 'family.role.guest');
  }
}

function formatDeviceType(deviceType: Device['device_type'], locale: string | undefined) {
  switch (deviceType) {
    case 'light': return getFamilyMessage(locale, 'family.devices.type.light');
    case 'ac': return getFamilyMessage(locale, 'family.devices.type.ac');
    case 'curtain': return getFamilyMessage(locale, 'family.devices.type.curtain');
    case 'speaker': return getFamilyMessage(locale, 'family.devices.type.speaker');
    case 'camera': return getFamilyMessage(locale, 'family.devices.type.camera');
    case 'sensor': return getFamilyMessage(locale, 'family.devices.type.sensor');
    case 'lock': return getFamilyMessage(locale, 'family.devices.type.lock');
  }
}

function formatDeviceStatus(status: Device['status'], locale: string | undefined) {
  switch (status) {
    case 'active': return getFamilyMessage(locale, 'family.devices.status.active');
    case 'offline': return getFamilyMessage(locale, 'family.devices.status.offline');
    case 'disabled': return getFamilyMessage(locale, 'family.devices.status.disabled');
    default: return getFamilyMessage(locale, 'family.devices.status.inactive');
  }
}

function getDeviceStatusBadge(status: Device['status']): 'success' | 'warning' | 'inactive' | 'danger' | 'secondary' {
  if (status === 'active') {
    return 'success';
  }
  if (status === 'offline') {
    return 'warning';
  }
  if (status === 'disabled') {
    return 'danger';
  }
  if (status === 'inactive') {
    return 'inactive';
  }
  return 'secondary';
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
    return getFamilyMessage(locale, 'family.preferences.empty');
  }

  const parts: string[] = [];
  if (preference.preferred_name) parts.push(getFamilyMessage(locale, 'family.preferences.preferredName', { name: preference.preferred_name }));
  if (preference.climate_preference) parts.push(getFamilyMessage(locale, 'family.preferences.temperatureSet'));
  if (preference.light_preference) parts.push(getFamilyMessage(locale, 'family.preferences.lightingSet'));
  if (preference.reminder_channel_preference) parts.push(getFamilyMessage(locale, 'family.preferences.reminderChannelSet'));
  if (preference.sleep_schedule) parts.push(getFamilyMessage(locale, 'family.preferences.sleepScheduleSet'));

  return parts.length > 0 ? parts.join(' · ') : getFamilyMessage(locale, 'family.preferences.empty');
}

function validatePhoneNumber(value: string, locale: string | undefined) {
  if (!value.trim()) {
    return '';
  }

  return /^[0-9+\-\s]{6,20}$/.test(value.trim()) ? '' : getFamilyMessage(locale, 'family.validation.phone');
}

function roleNeedsGuardian(role: Member['role']) {
  return role === 'child';
}

function getAllowedStatusOptions(role: Member['role'], locale: string | undefined) {
  if (role === 'admin') {
    return [{ value: 'active' as const, label: getFamilyMessage(locale, 'family.memberStatus.active') }];
  }

  return [
    { value: 'active' as const, label: getFamilyMessage(locale, 'family.memberStatus.active') },
    { value: 'inactive' as const, label: getFamilyMessage(locale, 'family.memberStatus.inactive') },
  ];
}

function formatMemberOptionLabel(name: string, roleLabel: string, locale: string | undefined) {
  return getFamilyMessage(locale, 'family.member.optionLabel', { name, role: roleLabel });
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
    return getFamilyMessage(locale, 'family.birthday.unset');
  }

  const birthDate = new Date(`${birthday}T00:00:00`);
  if (Number.isNaN(birthDate.getTime())) {
    return getFamilyMessage(locale, 'family.birthday.invalid');
  }

  const today = new Date();
  const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  let nextBirthday = new Date(today.getFullYear(), birthDate.getMonth(), birthDate.getDate());
  if (nextBirthday < startOfToday) {
    nextBirthday = new Date(today.getFullYear() + 1, birthDate.getMonth(), birthDate.getDate());
  }

  const diffDays = Math.round((nextBirthday.getTime() - startOfToday.getTime()) / 86400000);
  if (diffDays === 0) return getFamilyMessage(locale, 'family.birthday.today');
  if (diffDays === 1) return getFamilyMessage(locale, 'family.birthday.tomorrow');
  return getFamilyMessage(locale, 'family.birthday.inDays', { count: diffDays });
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
      ? getFamilyMessage(locale, 'family.birthday.lunarUnmatched')
      : getFamilyMessage(locale, 'family.birthday.unset');
  }

  if (days === 0) return getFamilyMessage(locale, 'family.birthday.today');
  if (days === 1) return getFamilyMessage(locale, 'family.birthday.tomorrow');
  return getFamilyMessage(locale, 'family.birthday.inDays', { count: days });
}

function getMemberRoleOptions(locale: string | undefined) {
  return [
    { value: 'admin' as const, label: getFamilyMessage(locale, 'family.role.admin') },
    { value: 'adult' as const, label: getFamilyMessage(locale, 'family.role.adult') },
    { value: 'child' as const, label: getFamilyMessage(locale, 'family.role.child') },
    { value: 'elder' as const, label: getFamilyMessage(locale, 'family.role.elder') },
    { value: 'guest' as const, label: getFamilyMessage(locale, 'family.role.guest') },
  ];
}

function getAgeGroupOptionsForRole(role: Member['role'], locale: string | undefined) {
  switch (role) {
    case 'child':
      return [
        { value: 'toddler' as const, label: getFamilyMessage(locale, 'family.ageGroup.toddler') },
        { value: 'child' as const, label: getFamilyMessage(locale, 'family.ageGroup.child') },
        { value: 'teen' as const, label: getFamilyMessage(locale, 'family.ageGroup.teen') },
      ];
    case 'elder':
      return [{ value: 'elder' as const, label: getFamilyMessage(locale, 'family.ageGroup.elder') }];
    default:
      return [{ value: 'adult' as const, label: getFamilyMessage(locale, 'family.ageGroup.adult') }];
  }
}

function formatRelationType(type: MemberRelationship['relation_type'], locale: string | undefined) {
  switch (type) {
    case 'caregiver': return getFamilyMessage(locale, 'family.relationship.caregiver');
    case 'guardian': return getFamilyMessage(locale, 'family.relationship.guardian');
    case 'parent': return getFamilyMessage(locale, 'family.relationship.parent');
    case 'child': return getFamilyMessage(locale, 'family.relationship.child');
    case 'spouse': return getFamilyMessage(locale, 'family.relationship.spouse');
  }
}

function formatVisibilityScope(scope: MemberRelationship['visibility_scope'], locale: string | undefined) {
  switch (scope) {
    case 'public': return getFamilyMessage(locale, 'family.visibility.public');
    case 'family': return getFamilyMessage(locale, 'family.visibility.family');
    case 'private': return getFamilyMessage(locale, 'family.visibility.private');
  }
}

function formatDelegationScope(scope: MemberRelationship['delegation_scope'], locale: string | undefined) {
  switch (scope) {
    case 'none': return getFamilyMessage(locale, 'family.delegation.none');
    case 'reminder': return getFamilyMessage(locale, 'family.delegation.reminder');
    case 'health': return getFamilyMessage(locale, 'family.delegation.health');
    case 'device': return getFamilyMessage(locale, 'family.delegation.device');
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

  useEffect(() => {
    void Taro.setNavigationBarTitle({ title: t('nav.family') }).catch(() => undefined);
  }, [t, locale]);

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
      .map(result => result.reason instanceof Error ? result.reason.message : getFamilyMessage(locale, 'family.loadFailed'));

    preferenceResults.forEach(result => {
      if (result.status === 'rejected') {
        errors.push(result.reason instanceof Error ? result.reason.message : getFamilyMessage(locale, 'family.preferences.loadFailed'));
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
        <PageHeader title={t('nav.family')} description={workspace.errors.length > 0 ? getFamilyMessage(locale, 'family.partialLoadFailed') : undefined} />
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
          {activeTab === 'devices' ? <FamilyDevices /> : null}
          {activeTab === 'members' ? <FamilyMembers /> : null}
          {activeTab === 'relationships' ? <FamilyRelationships /> : null}
        </div>
      </div>
    </FamilyWorkspaceContext.Provider>
  );
}

/* ---- 瀹跺涵姒傝 ---- */
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
    loading: getFamilyMessage(locale, 'family.overview.loading'),
    regionLabel: getFamilyMessage(locale, 'family.overview.regionLabel'),
    noServiceSummary: getFamilyMessage(locale, 'family.overview.noServiceSummary'),
    regionStructureTitle: getFamilyMessage(locale, 'family.overview.regionStructureTitle'),
    regionStructureIntro: getFamilyMessage(locale, 'family.overview.regionStructureIntro'),
    regionCountry: getFamilyMessage(locale, 'family.overview.regionCountry'),
    province: getFamilyMessage(locale, 'family.overview.province'),
    city: getFamilyMessage(locale, 'family.overview.city'),
    district: getFamilyMessage(locale, 'family.overview.district'),
    regionBindingStatus: getFamilyMessage(locale, 'family.overview.regionBindingStatus'),
    regionFallbackHint: getFamilyMessage(locale, 'family.overview.regionFallbackHint', { city: household?.city ?? '' }),
    regionUnconfiguredHint: getFamilyMessage(locale, 'family.overview.regionUnconfiguredHint', { city: household?.city ?? '' }),
    profileTitle: getFamilyMessage(locale, 'family.overview.profileTitle'),
    profileDesc: getFamilyMessage(locale, 'family.overview.profileDesc'),
    nameLabel: getFamilyMessage(locale, 'family.overview.nameLabel'),
    timezoneLabel: getFamilyMessage(locale, 'family.overview.timezoneLabel'),
    defaultLanguageLabel: getFamilyMessage(locale, 'family.overview.defaultLanguageLabel'),
    saveButton: getFamilyMessage(locale, 'family.overview.saveButton'),
    savingButton: getFamilyMessage(locale, 'family.overview.savingButton'),
    saveSuccess: getFamilyMessage(locale, 'family.overview.saveSuccess'),
    saveFailure: getFamilyMessage(locale, 'family.overview.saveFailure'),
  };

  const serviceSummary = [
    overview?.voice_fast_path_enabled ? getFamilyMessage(locale, 'family.overview.service.voiceFastPath') : null,
    overview?.guest_mode_enabled ? getFamilyMessage(locale, 'family.overview.service.guestMode') : null,
    overview?.child_protection_enabled ? getFamilyMessage(locale, 'family.overview.service.childProtection') : null,
    overview?.elder_care_watch_enabled ? getFamilyMessage(locale, 'family.overview.service.elderCare') : null,
  ].filter(Boolean).join(' · ');
  const regionCountryText = household?.region?.country_code === 'CN'
    ? getFamilyMessage(locale, 'family.overview.countryChina')
    : getFamilyMessage(locale, 'family.common.unknown');
  const regionStatusText = household?.region?.status === 'configured'
    ? getFamilyMessage(locale, 'family.overview.regionStatus.configured')
    : household?.region?.status === 'provider_unavailable'
      ? getFamilyMessage(locale, 'family.overview.regionStatus.providerUnavailable')
      : getFamilyMessage(locale, 'family.overview.regionStatus.needsCompletion');

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

/* ---- 鎴块棿椤?---- */
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
    nameRequired: getFamilyMessage(locale, 'family.rooms.nameRequired'),
    selectHousehold: getFamilyMessage(locale, 'family.rooms.selectHousehold'),
    createSuccess: getFamilyMessage(locale, 'family.rooms.createSuccess'),
    createToast: getFamilyMessage(locale, 'family.rooms.createToast'),
    createFailure: getFamilyMessage(locale, 'family.rooms.createFailure'),
    title: getFamilyMessage(locale, 'family.rooms.title'),
    desc: getFamilyMessage(locale, 'family.rooms.desc'),
    addButton: getFamilyMessage(locale, 'family.rooms.addButton'),
    loading: getFamilyMessage(locale, 'family.rooms.loading'),
    modalDesc: getFamilyMessage(locale, 'family.rooms.modalDesc'),
    roomName: getFamilyMessage(locale, 'family.rooms.roomName'),
    roomType: getFamilyMessage(locale, 'family.rooms.roomType'),
    privacyLevel: getFamilyMessage(locale, 'family.rooms.privacyLevel'),
    privacyPublic: getFamilyMessage(locale, 'family.rooms.privacyPublic'),
    privacyPrivate: getFamilyMessage(locale, 'family.rooms.privacyPrivate'),
    privacySensitive: getFamilyMessage(locale, 'family.rooms.privacySensitive'),
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
              <span className="meta-item">📍 {room.type}</span>
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

type FamilyDeviceFilterState = {
  roomId: string;
  deviceType: Device['device_type'] | 'all';
  status: Device['status'] | 'all';
};

export function FamilyDevices() {
  const { locale } = useI18n();
  const { rooms } = useFamilyWorkspace();
  const { currentHouseholdId } = useHouseholdContext();
  const [filters, setFilters] = useState<FamilyDeviceFilterState>({
    roomId: 'all',
    deviceType: 'all',
    status: 'all',
  });
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
  const [reloadNonce, setReloadNonce] = useState(0);

  const copy = {
    title: getFamilyMessage(locale, 'family.devices.title'),
    desc: getFamilyMessage(locale, 'family.devices.desc'),
    loading: getFamilyMessage(locale, 'family.devices.loading'),
    count: (count: number) => getFamilyMessage(locale, 'family.devices.count', { count }),
    loadFailed: getFamilyMessage(locale, 'family.devices.loadFailed'),
    roomFilter: getFamilyMessage(locale, 'family.devices.filter.room'),
    roomAll: getFamilyMessage(locale, 'family.devices.filter.roomAll'),
    typeFilter: getFamilyMessage(locale, 'family.devices.filter.type'),
    typeAll: getFamilyMessage(locale, 'family.devices.filter.typeAll'),
    statusFilter: getFamilyMessage(locale, 'family.devices.filter.status'),
    statusAll: getFamilyMessage(locale, 'family.devices.filter.statusAll'),
    emptyTitle: getFamilyMessage(locale, 'family.devices.emptyTitle'),
    emptyDesc: getFamilyMessage(locale, 'family.devices.emptyDesc'),
    emptyFilteredDesc: getFamilyMessage(locale, 'family.devices.emptyFilteredDesc'),
    noRoom: getFamilyMessage(locale, 'family.devices.noRoom'),
    controllable: getFamilyMessage(locale, 'family.devices.controllable'),
    readOnly: getFamilyMessage(locale, 'family.devices.readOnly'),
  };

  const roomNameMap = useMemo(() => (
    rooms.reduce<Record<string, string>>((acc, room) => {
      acc[room.id] = room.name;
      return acc;
    }, {})
  ), [rooms]);

  const roomOptions = useMemo(() => rooms.map(room => ({
    value: room.id,
    label: room.name,
  })), [rooms]);

  const deviceTypeOptions = useMemo(() => ([
    { value: 'light' as const, label: formatDeviceType('light', locale) },
    { value: 'ac' as const, label: formatDeviceType('ac', locale) },
    { value: 'curtain' as const, label: formatDeviceType('curtain', locale) },
    { value: 'speaker' as const, label: formatDeviceType('speaker', locale) },
    { value: 'camera' as const, label: formatDeviceType('camera', locale) },
    { value: 'sensor' as const, label: formatDeviceType('sensor', locale) },
    { value: 'lock' as const, label: formatDeviceType('lock', locale) },
  ]), [locale]);

  const statusOptions = useMemo(() => ([
    { value: 'active' as const, label: formatDeviceStatus('active', locale) },
    { value: 'offline' as const, label: formatDeviceStatus('offline', locale) },
    { value: 'inactive' as const, label: formatDeviceStatus('inactive', locale) },
    { value: 'disabled' as const, label: formatDeviceStatus('disabled', locale) },
  ]), [locale]);

  const hasActiveFilters = filters.roomId !== 'all' || filters.deviceType !== 'all' || filters.status !== 'all';
  const detailPageLookup: DevicePageLookup = (key, params) => getPageMessage(
    locale,
    key as Parameters<typeof getPageMessage>[1],
    params,
  );

  useEffect(() => {
    if (!currentHouseholdId) {
      setDevices([]);
      setError('');
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);

    void api.listDevices(currentHouseholdId, {
      room_id: filters.roomId === 'all' ? undefined : filters.roomId,
      device_type: filters.deviceType === 'all' ? undefined : filters.deviceType,
      status: filters.status === 'all' ? undefined : filters.status,
    }).then((response) => {
      if (cancelled) {
        return;
      }
      setDevices(response.items as Device[]);
      setSelectedDevice((current) => {
        if (!current) {
          return null;
        }
        return (response.items.find(item => item.id === current.id) as Device | undefined) ?? current;
      });
      setError('');
    }).catch((loadError) => {
      if (cancelled) {
        return;
      }
      setError(loadError instanceof Error ? loadError.message : copy.loadFailed);
      setDevices([]);
    }).finally(() => {
      if (!cancelled) {
        setLoading(false);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [copy.loadFailed, currentHouseholdId, filters.deviceType, filters.roomId, filters.status, reloadNonce]);

  return (
    <div className="family-devices">
      <div className="member-page-toolbar">
        <div>
          <h2 className="member-page-toolbar__title">{copy.title}</h2>
          <p className="member-page-toolbar__desc">{copy.desc}</p>
        </div>
        <div className="member-page-toolbar__summary">
          {copy.count(devices.length)}
        </div>
      </div>

      {status ? <div className="family-device-feedback family-device-feedback--success">{status}</div> : null}
      {error ? <div className="family-device-feedback family-device-feedback--error">{error}</div> : null}

      <div className="family-device-filters">
        <label className="family-device-filters__item">
          <span className="family-device-filters__label">{copy.roomFilter}</span>
          <select
            className="form-select"
            value={filters.roomId}
            onChange={(event) => setFilters(current => ({ ...current, roomId: event.target.value }))}
          >
            <option value="all">{copy.roomAll}</option>
            {roomOptions.map(option => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>

        <label className="family-device-filters__item">
          <span className="family-device-filters__label">{copy.typeFilter}</span>
          <select
            className="form-select"
            value={filters.deviceType}
            onChange={(event) => setFilters(current => ({
              ...current,
              deviceType: event.target.value as FamilyDeviceFilterState['deviceType'],
            }))}
          >
            <option value="all">{copy.typeAll}</option>
            {deviceTypeOptions.map(option => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>

        <label className="family-device-filters__item">
          <span className="family-device-filters__label">{copy.statusFilter}</span>
          <select
            className="form-select"
            value={filters.status}
            onChange={(event) => setFilters(current => ({
              ...current,
              status: event.target.value as FamilyDeviceFilterState['status'],
            }))}
          >
            <option value="all">{copy.statusAll}</option>
            {statusOptions.map(option => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
      </div>

      {loading && devices.length === 0 ? (
        <div className="family-device-feedback">{copy.loading}</div>
      ) : null}

      {!loading && devices.length === 0 ? (
        <Card className="family-device-empty">
          <div className="settings-empty-state">
            <h3>{copy.emptyTitle}</h3>
            <p>{hasActiveFilters ? copy.emptyFilteredDesc : copy.emptyDesc}</p>
          </div>
        </Card>
      ) : null}

      {devices.length > 0 ? (
        <div className="family-device-grid">
          {devices.map(device => (
            <Card
              key={device.id}
              className="family-device-card"
              onClick={() => setSelectedDevice(device)}
            >
              <div className="family-device-card__header">
                <div className="family-device-card__name-block">
                  <h3 className="family-device-card__name">{device.name}</h3>
                  <p className="family-device-card__room">{roomNameMap[device.room_id ?? ''] ?? copy.noRoom}</p>
                </div>
                <span className={`badge badge--${getDeviceStatusBadge(device.status)}`}>
                  {formatDeviceStatus(device.status, locale)}
                </span>
              </div>
              <div className="family-device-card__tags">
                <span className="badge badge--secondary">{formatDeviceType(device.device_type, locale)}</span>
                <span className={`badge badge--${device.controllable ? 'success' : 'secondary'}`}>
                  {device.controllable ? copy.controllable : copy.readOnly}
                </span>
              </div>
            </Card>
          ))}
        </div>
      ) : null}

      <HouseholdDeviceDetailDialog
        open={selectedDevice !== null}
        currentHouseholdId={currentHouseholdId}
        deviceId={selectedDevice?.id ?? null}
        deviceName={selectedDevice?.name ?? ''}
        subtitle={roomNameMap[selectedDevice?.room_id ?? ''] ?? copy.noRoom}
        page={detailPageLookup}
        fallbackStatus={selectedDevice?.status}
        fallbackControllable={selectedDevice?.controllable}
        onClose={() => setSelectedDevice(null)}
        onStatus={(message) => {
          setStatus(message);
          setError('');
          setReloadNonce(current => current + 1);
        }}
        onError={setError}
        onReload={async () => {
          setReloadNonce(current => current + 1);
        }}
        onDeleted={() => setSelectedDevice(null)}
      />
    </div>
  );
}

/* ---- 鎴愬憳椤?---- */
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
    nameRequired: getFamilyMessage(locale, 'family.members.nameRequired'),
    guardianRequired: getFamilyMessage(locale, 'family.members.guardianRequired'),
    guardianRequiredBeforeSave: getFamilyMessage(locale, 'family.members.guardianRequiredBeforeSave'),
    selectHousehold: getFamilyMessage(locale, 'family.members.selectHousehold'),
    createSuccess: getFamilyMessage(locale, 'family.members.createSuccess'),
    createToast: getFamilyMessage(locale, 'family.members.createToast'),
    createFailure: getFamilyMessage(locale, 'family.members.createFailure'),
    saveSuccess: getFamilyMessage(locale, 'family.members.saveSuccess'),
    saveToast: getFamilyMessage(locale, 'family.members.saveToast'),
    saveFailure: getFamilyMessage(locale, 'family.members.saveFailure'),
    disableConfirm: (memberName: string) => getFamilyMessage(locale, 'family.members.disableConfirm', { name: memberName }),
    disabledStatus: getFamilyMessage(locale, 'family.members.disabledStatus'),
    disabledAction: getFamilyMessage(locale, 'family.members.disabledAction'),
    enabledAction: getFamilyMessage(locale, 'family.members.enabledAction'),
    disableSuccess: getFamilyMessage(locale, 'family.members.disableSuccess'),
    enableSuccess: getFamilyMessage(locale, 'family.members.enableSuccess'),
    disableToast: getFamilyMessage(locale, 'family.members.disableToast'),
    enableToast: getFamilyMessage(locale, 'family.members.enableToast'),
    disableFailure: getFamilyMessage(locale, 'family.members.disableFailure'),
    enableFailure: getFamilyMessage(locale, 'family.members.enableFailure'),
    preferencesSaveSuccess: getFamilyMessage(locale, 'family.members.preferencesSaveSuccess'),
    preferencesSaveToast: getFamilyMessage(locale, 'family.members.preferencesSaveToast'),
    preferencesSaveFailure: getFamilyMessage(locale, 'family.members.preferencesSaveFailure'),
    title: getFamilyMessage(locale, 'family.members.title'),
    desc: getFamilyMessage(locale, 'family.members.desc'),
    addButton: getFamilyMessage(locale, 'family.members.addButton'),
    loading: getFamilyMessage(locale, 'family.members.loading'),
    lunarBirthday: getFamilyMessage(locale, 'family.members.lunarBirthday'),
    solarBirthday: getFamilyMessage(locale, 'family.members.solarBirthday'),
    birthdayUnset: getFamilyMessage(locale, 'family.birthday.unset'),
    agePending: getFamilyMessage(locale, 'family.members.agePending'),
    birthdaySoon: getFamilyMessage(locale, 'family.members.birthdaySoon'),
    nickname: getFamilyMessage(locale, 'family.members.nickname'),
    gender: getFamilyMessage(locale, 'family.members.gender'),
    genderUnset: getFamilyMessage(locale, 'family.members.genderUnset'),
    genderMale: getFamilyMessage(locale, 'family.members.genderMale'),
    genderFemale: getFamilyMessage(locale, 'family.members.genderFemale'),
    role: getFamilyMessage(locale, 'family.members.role'),
    ageGroup: getFamilyMessage(locale, 'family.members.ageGroup'),
    ageGroupAuto: getFamilyMessage(locale, 'family.members.ageGroupAuto'),
    birthday: getFamilyMessage(locale, 'family.members.birthday'),
    lunarReminder: getFamilyMessage(locale, 'family.members.lunarReminder'),
    phone: getFamilyMessage(locale, 'family.members.phone'),
    memberStatus: getFamilyMessage(locale, 'family.members.memberStatus'),
    adminStatusHint: getFamilyMessage(locale, 'family.members.adminStatusHint'),
    guardian: getFamilyMessage(locale, 'family.members.guardian'),
    guardianSelect: getFamilyMessage(locale, 'family.members.guardianSelect'),
    guardianHint: getFamilyMessage(locale, 'family.members.guardianHint'),
    modalDesc: getFamilyMessage(locale, 'family.members.modalDesc'),
    name: getFamilyMessage(locale, 'family.members.name'),
    preferredName: getFamilyMessage(locale, 'family.members.preferredName'),
    reminderNote: getFamilyMessage(locale, 'family.members.reminderNote'),
    reminderPlaceholder: getFamilyMessage(locale, 'family.members.reminderPlaceholder'),
    sleepStart: getFamilyMessage(locale, 'family.members.sleepStart'),
    sleepEnd: getFamilyMessage(locale, 'family.members.sleepEnd'),
    sleepStartPlaceholder: getFamilyMessage(locale, 'family.members.sleepStartPlaceholder'),
    sleepEndPlaceholder: getFamilyMessage(locale, 'family.members.sleepEndPlaceholder'),
  };
  const formatAgeText = (age: number | null) => age === null
    ? copy.agePending
    : getFamilyMessage(locale, 'family.members.ageYears', { age });
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
                  {member.role === 'elder' ? '👵' : member.role === 'child' ? '🧒' : member.role === 'guest' ? '🙋' : '🧑'}
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
                <span className="meta-item">🎈 {birthdayCountdown}</span>
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
                  {guardianCandidates.map(candidate => <option key={candidate.id} value={candidate.id}>{formatMemberOptionLabel(candidate.name, formatRole(candidate.role, locale), locale)}</option>)}
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
                  {guardianCandidates.map(candidate => <option key={candidate.id} value={candidate.id}>{formatMemberOptionLabel(candidate.name, formatRole(candidate.role, locale), locale)}</option>)}
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
              <input className="form-input" value={preferencesDraft.sleep_start} onChange={event => setPreferencesDraft(current => ({ ...current, sleep_start: event.target.value }))} placeholder={copy.sleepStartPlaceholder} />
            </div>
            <div className="form-group">
              <label>{copy.sleepEnd}</label>
              <input className="form-input" value={preferencesDraft.sleep_end} onChange={event => setPreferencesDraft(current => ({ ...current, sleep_end: event.target.value }))} placeholder={copy.sleepEndPlaceholder} />
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

/* ---- 鍏崇郴椤?---- */

/* 鍏崇郴涓枃鏍囩 */
const RELATION_LABELS: Record<string, Parameters<typeof getPageMessage>[1]> = {
  husband: 'family.relation.label.husband',
  wife: 'family.relation.label.wife',
  spouse: 'family.relation.label.spouse',
  father: 'family.relation.label.father',
  mother: 'family.relation.label.mother',
  parent: 'family.relation.label.parent',
  son: 'family.relation.label.son',
  daughter: 'family.relation.label.daughter',
  child: 'family.relation.label.child',
  older_brother: 'family.relation.label.olderBrother',
  older_sister: 'family.relation.label.olderSister',
  younger_brother: 'family.relation.label.youngerBrother',
  younger_sister: 'family.relation.label.youngerSister',
  grandfather_paternal: 'family.relation.label.grandfatherPaternal',
  grandmother_paternal: 'family.relation.label.grandmotherPaternal',
  grandfather_maternal: 'family.relation.label.grandfatherMaternal',
  grandmother_maternal: 'family.relation.label.grandmotherMaternal',
  grandson: 'family.relation.label.grandson',
  granddaughter: 'family.relation.label.granddaughter',
  guardian: 'family.relation.label.guardian',
  ward: 'family.relation.label.ward',
  caregiver: 'family.relation.label.caregiver',
};
const RELATION_CATEGORY_LABELS: Record<string, Parameters<typeof getPageMessage>[1]> = {
  husband: 'family.relation.category.fallback.spouse',
  wife: 'family.relation.category.fallback.spouse',
  spouse: 'family.relation.category.fallback.spouse',
  father: 'family.relation.category.fallback.parentChild',
  mother: 'family.relation.category.fallback.parentChild',
  parent: 'family.relation.category.fallback.parentChild',
  son: 'family.relation.category.fallback.parentChild',
  daughter: 'family.relation.category.fallback.parentChild',
  child: 'family.relation.category.fallback.parentChild',
  older_brother: 'family.relation.category.fallback.siblings',
  older_sister: 'family.relation.category.fallback.siblings',
  younger_brother: 'family.relation.category.fallback.siblings',
  younger_sister: 'family.relation.category.fallback.siblings',
  grandfather_paternal: 'family.relation.category.fallback.grandparentGrandchild',
  grandmother_paternal: 'family.relation.category.fallback.grandparentGrandchild',
  grandfather_maternal: 'family.relation.category.fallback.maternalGrandchild',
  grandmother_maternal: 'family.relation.category.fallback.maternalGrandchild',
  grandson: 'family.relation.category.fallback.grandson',
  granddaughter: 'family.relation.category.fallback.granddaughter',
  guardian: 'family.relation.category.fallback.guardianship',
  ward: 'family.relation.category.fallback.guardianship',
  caregiver: 'family.relation.category.fallback.care',
};
function getRelationLabel(relationType: string, locale: string | undefined) {
  const label = RELATION_LABELS[relationType];
  return label ? getFamilyMessage(locale, label) : relationType;
}
function getRelationCategoryFallback(relationType: string, locale: string | undefined) {
  const label = RELATION_CATEGORY_LABELS[relationType];
  return label ? getFamilyMessage(locale, label) : relationType;
}
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
  if (firstGender === 'male' && secondGender === 'male') return getFamilyMessage(locale, 'family.relation.category.husbands');
  if (firstGender === 'female' && secondGender === 'female') return getFamilyMessage(locale, 'family.relation.category.wives');
  if (
    (firstGender === 'male' && secondGender === 'female')
    || (firstGender === 'female' && secondGender === 'male')
  ) {
    return getFamilyMessage(locale, 'family.relation.category.marriedCouple');
  }
  return getFamilyMessage(locale, 'family.relation.category.partners');
}

function getParentChildCategoryLabel(parentGender: Member['gender'], childGender: Member['gender'], locale: string | undefined) {
  if (parentGender === 'male') {
    if (childGender === 'male') return getFamilyMessage(locale, 'family.relation.category.fatherSon');
    if (childGender === 'female') return getFamilyMessage(locale, 'family.relation.category.fatherDaughter');
    return getFamilyMessage(locale, 'family.relation.category.fatherChild');
  }

  if (parentGender === 'female') {
    if (childGender === 'male') return getFamilyMessage(locale, 'family.relation.category.motherSon');
    if (childGender === 'female') return getFamilyMessage(locale, 'family.relation.category.motherDaughter');
    return getFamilyMessage(locale, 'family.relation.category.motherChild');
  }

  if (childGender === 'male') return getFamilyMessage(locale, 'family.relation.category.parentSon');
  if (childGender === 'female') return getFamilyMessage(locale, 'family.relation.category.parentDaughter');
  return getFamilyMessage(locale, 'family.relation.category.parentChild');
}

function getSiblingCategoryLabel(olderGender: Member['gender'], youngerGender: Member['gender'], locale: string | undefined) {
  if (olderGender === 'male') {
    if (youngerGender === 'male') return getFamilyMessage(locale, 'family.relation.category.brothers');
    if (youngerGender === 'female') return getFamilyMessage(locale, 'family.relation.category.brotherAndSister');
    return getFamilyMessage(locale, 'family.relation.category.siblings');
  }

  if (olderGender === 'female') {
    if (youngerGender === 'male') return getFamilyMessage(locale, 'family.relation.category.sisterAndBrother');
    if (youngerGender === 'female') return getFamilyMessage(locale, 'family.relation.category.sisters');
    return getFamilyMessage(locale, 'family.relation.category.siblings');
  }

  if (youngerGender === 'male') return getFamilyMessage(locale, 'family.relation.category.siblings');
  if (youngerGender === 'female') return getFamilyMessage(locale, 'family.relation.category.siblings');
  return getFamilyMessage(locale, 'family.relation.category.handFoot');
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
    ? getFamilyMessage(locale, 'family.relation.category.maternalGrandson')
    : getFamilyMessage(locale, 'family.relation.category.grandson');
  const femaleLabel = side === 'maternal'
    ? getFamilyMessage(locale, 'family.relation.category.maternalGranddaughter')
    : getFamilyMessage(locale, 'family.relation.category.granddaughter');

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
      return getFamilyMessage(locale, 'family.relation.category.fallback.guardianship');
    case 'caregiver':
      return getFamilyMessage(locale, 'family.relation.category.fallback.care');
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

/* ---- SVG 鍏崇郴鍥捐氨 ---- */
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

  // 鍘婚噸: 瀵逛簬 A鈫払 鍜?B鈫扐 杩欑鍙屽悜鍏崇郴锛屽彧淇濈暀涓€鏉¤竟
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
  // 浠?selectedMember 瑙嗚: 鎵?selectedMember 鈫?other 鐨?relation_type
  const otherId = edge.source === selectedMemberId ? edge.target : edge.source;
  const rel = relationships.find(
    r => r.source_member_id === selectedMemberId && r.target_member_id === otherId,
  );
  if (rel) return getRelationLabel(rel.relation_type, locale);
  // fallback: 鍙嶅悜
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

  // 绠€鍗曠殑鍔涘鍚戞ā鎷?
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({});

  useEffect(() => {
    if (nodes.length === 0) return;

    const simNodes = nodes.map(n => ({ ...n }));
    const nodeMap = Object.fromEntries(simNodes.map(n => [n.id, n]));

    let frame: number;
    let iterations = 0;
    const maxIterations = 120;

    function tick() {
      // 鍔涘鍚戣绠?
      for (const node of simNodes) {
        node.vx *= 0.85;
        node.vy *= 0.85;
      }

      // 鎺掓枼鍔?
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

      // 寮曞姏 (杩炵嚎鐨?
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

      // 灞呬腑鍔?
      for (const node of simNodes) {
        node.vx += (250 - node.x) * 0.005;
        node.vy += (220 - node.y) * 0.005;
      }

      // 鏇存柊浣嶇疆
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
      case 'child': return '🧒';
      case 'guest': return '🙋';
      default: return '🧑';
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

        {/* 杩炵嚎 */}
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

        {/* 鑺傜偣 */}
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
          {getFamilyMessage(locale, 'family.graph.selectedPrefix')}
          <strong>{members.find(m => m.id === selectedMemberId)?.name}</strong>
          {getFamilyMessage(locale, 'family.graph.selectedSuffix')}
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
      case 'elder': return '👴';
      case 'child': return '🧒';
      case 'guest': return '👤';
      default: return '👤';
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
          +
        </button>
        <button className="relationship-graph__toolbtn" type="button" onClick={() => zoomGraph(viewport.scale * 0.9)}>
          -
        </button>
        <button className="relationship-graph__toolbtn relationship-graph__toolbtn--wide" type="button" onClick={resetViewport}>
          {getFamilyMessage(locale, 'family.graph.reset')}
        </button>
        <span className="relationship-graph__zoom">{Math.round(viewport.scale * 100)}%</span>
      </div>
      <div className="graph-legend">
        {getFamilyMessage(locale, 'family.graph.legend')}
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
    selectMembersAndType: getFamilyMessage(locale, 'family.relationships.selectMembersAndType'),
    createSuccess: getFamilyMessage(locale, 'family.relationships.createSuccess'),
    createFailure: getFamilyMessage(locale, 'family.relationships.createFailure'),
    deleteSuccess: getFamilyMessage(locale, 'family.relationships.deleteSuccess'),
    deleteFailure: getFamilyMessage(locale, 'family.relationships.deleteFailure'),
    graphLoading: getFamilyMessage(locale, 'family.relationships.graphLoading'),
    graphNeedMembers: getFamilyMessage(locale, 'family.relationships.graphNeedMembers'),
    graphEmpty: getFamilyMessage(locale, 'family.relationships.graphEmpty'),
    addTitle: getFamilyMessage(locale, 'family.relationships.addTitle'),
    selectMember: getFamilyMessage(locale, 'family.relationships.selectMember'),
    selectMemberPlaceholder: getFamilyMessage(locale, 'family.relationships.selectMemberPlaceholder'),
    selectRelationPlaceholder: getFamilyMessage(locale, 'family.relationships.selectRelationPlaceholder'),
    selectTargetPlaceholder: getFamilyMessage(locale, 'family.relationships.selectTargetPlaceholder'),
    targetLabel: getFamilyMessage(locale, 'family.relationships.targetLabel'),
    addButton: getFamilyMessage(locale, 'family.relationships.addButton'),
    listTitle: getFamilyMessage(locale, 'family.relationships.listTitle'),
    deleteButton: getFamilyMessage(locale, 'family.relationships.deleteButton'),
    deletingButton: getFamilyMessage(locale, 'family.relationships.deletingButton'),
  };
  const memberNameMap = Object.fromEntries(members.map(member => [member.id, member.name]));
  const relationshipTypeLabel = createForm.source_member_id
    ? getFamilyMessage(locale, 'family.relationships.typeLabel', { name: memberNameMap[createForm.source_member_id] ?? '' })
    : '';

  const sourceMember = members.find(m => m.id === createForm.source_member_id);
  const relationOptions = sourceMember ? getRelationOptionsForRole(sourceMember.role, locale) : [];

  // 鏍规嵁 source 鍘绘帀 source 鑷繁
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

  // 鎸?source 鍒嗙粍
  const groupedBySource = useMemo(() => {
    const groups: Record<string, MemberRelationship[]> = {};
    for (const rel of relationships) {
      (groups[rel.source_member_id] ??= []).push(rel);
    }
    return groups;
  }, [relationships]);

  return (
    <div className="family-relationships">
      {/* 鍏崇郴鍥捐氨 */}
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

      {/* 娣诲姞鍏崇郴 */}
      <Card className="relation-card" style={{ marginTop: '1rem' }}>
        <h3 style={{ fontSize: 'var(--font-size-md)', fontWeight: 600, marginBottom: 'var(--spacing-md)' }}>{copy.addTitle}</h3>
        <form className="settings-form relationship-create-form" onSubmit={handleCreateRelationship}>
          <div className="form-group">
            <label>{copy.selectMember}</label>
            <select className="form-select" value={createForm.source_member_id} onChange={event => { setCreateForm(current => ({ ...current, source_member_id: event.target.value, relation_type: '', target_member_id: '' })); setStatus(''); setError(''); }}>
              <option value="">{copy.selectMemberPlaceholder}</option>
              {members.map(member => <option key={member.id} value={member.id}>{formatMemberOptionLabel(member.name, formatRole(member.role, locale), locale)}</option>)}
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
                  {targetOptions.map(member => <option key={member.id} value={member.id}>{formatMemberOptionLabel(member.name, formatRole(member.role, locale), locale)}</option>)}
                </select>
              </div>
            </>
          )}
          <button className="btn btn--primary" type="submit" disabled={!createForm.source_member_id || !createForm.target_member_id || !createForm.relation_type}>{copy.addButton}</button>
          {status && <div className="text-text-secondary" style={{ color: 'var(--color-success)' }}>{status}</div>}
          {error && <div className="text-text-secondary" style={{ color: 'var(--color-danger)' }}>{error}</div>}
        </form>
      </Card>

      {/* 鍏崇郴鍒楄〃锛堟寜鎴愬憳鍒嗙粍锛?*/}
      {Object.keys(groupedBySource).length > 0 && (
        <Section title={copy.listTitle}>
          {Object.entries(groupedBySource).map(([sourceId, rels]) => (
            <div key={sourceId} className="relation-group">
              <h4 className="relation-group__title">{getFamilyMessage(locale, 'family.relationships.groupTitle', { name: memberNameMap[sourceId] ?? sourceId })}</h4>
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

