import {
  DEFAULT_LOCALE_ID,
  buildLocaleDefinitions,
  formatLocaleOptionLabel as formatSharedLocaleOptionLabel,
  getLocaleDefinition as getSharedLocaleDefinition,
  resolveSupportedLocale,
} from '@familyclaw/user-core';
import { useHouseholdContext } from './familyRuntime';

type FamilyMessageKey =
  | 'nav.family'
  | 'family.overview'
  | 'family.rooms'
  | 'family.members'
  | 'family.relationships'
  | 'family.name'
  | 'family.timezone'
  | 'family.language'
  | 'family.mode'
  | 'family.privacy'
  | 'family.services'
  | 'room.devices'
  | 'room.active'
  | 'room.idle'
  | 'room.sensitive'
  | 'member.atHome'
  | 'member.away'
  | 'member.resting'
  | 'member.edit'
  | 'member.preferences'
  | 'common.save'
  | 'common.cancel'
  | 'common.edit';

const FAMILY_MESSAGES: Record<'zh-CN' | 'en-US', Record<FamilyMessageKey, string>> = {
  'zh-CN': {
    'nav.family': '家庭',
    'family.overview': '家庭概览',
    'family.rooms': '房间',
    'family.members': '成员',
    'family.relationships': '关系',
    'family.name': '家庭名称',
    'family.timezone': '时区',
    'family.language': '默认语言',
    'family.mode': '家庭模式',
    'family.privacy': '隐私模式',
    'family.services': '已开启的服务',
    'room.devices': '个设备',
    'room.active': '活跃',
    'room.idle': '空闲',
    'room.sensitive': '隐私区域',
    'member.atHome': '在家',
    'member.away': '外出',
    'member.resting': '休息中',
    'member.edit': '编辑',
    'member.preferences': '偏好',
    'common.save': '保存',
    'common.cancel': '取消',
    'common.edit': '编辑',
  },
  'en-US': {
    'nav.family': 'Family',
    'family.overview': 'Overview',
    'family.rooms': 'Rooms',
    'family.members': 'Members',
    'family.relationships': 'Relationships',
    'family.name': 'Family Name',
    'family.timezone': 'Timezone',
    'family.language': 'Default Language',
    'family.mode': 'Family Mode',
    'family.privacy': 'Privacy Mode',
    'family.services': 'Active Services',
    'room.devices': 'devices',
    'room.active': 'Active',
    'room.idle': 'Idle',
    'room.sensitive': 'Private Area',
    'member.atHome': 'At Home',
    'member.away': 'Away',
    'member.resting': 'Resting',
    'member.edit': 'Edit',
    'member.preferences': 'Preferences',
    'common.save': 'Save',
    'common.cancel': 'Cancel',
    'common.edit': 'Edit',
  },
};

let currentLocaleDefinitions = buildLocaleDefinitions([]);

export function formatLocaleOptionLabel(definition: { id: string; nativeLabel: string }) {
  return formatSharedLocaleOptionLabel(definition);
}

export function listLocaleDefinitions() {
  return currentLocaleDefinitions;
}

export function getLocaleLabel(locale: string | null | undefined) {
  if (!locale) {
    return '-';
  }
  const definition = getSharedLocaleDefinition(currentLocaleDefinitions, locale);
  return definition ? formatLocaleOptionLabel(definition) : locale;
}

export function useI18n() {
  const { currentHousehold, locale, locales } = useHouseholdContext();
  currentLocaleDefinitions = buildLocaleDefinitions(locales);
  const localeId = resolveSupportedLocale(currentHousehold?.locale ?? locale, currentLocaleDefinitions, DEFAULT_LOCALE_ID);
  const dictionary = FAMILY_MESSAGES[localeId === 'en-US' ? 'en-US' : 'zh-CN'];

  return {
    locale: localeId,
    t: (key: FamilyMessageKey) => dictionary[key] ?? key,
  };
}
