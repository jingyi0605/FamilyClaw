import {
  Bell,
  Bot,
  Globe,
  HeartHandshake,
  KeyRound,
  Link as LinkIcon,
  MessageCircle,
  Palette,
  Puzzle,
  Tag as TagIcon,
} from 'lucide-react';
import Taro from '@tarojs/taro';
import type { ReactNode } from 'react';
import { useMemo } from 'react';
import { useI18n } from '../../runtime/h5-shell';
import { useAuthContext } from '../../runtime/auth';

type SettingsNavKey =
  | 'appearance'
  | 'ai'
  | 'accounts'
  | 'language'
  | 'notifications'
  | 'accessibility'
  | 'version-management'
  | 'integrations'
  | 'channel-access'
  | 'plugins';

type SettingsNavItem = {
  key: SettingsNavKey;
  labelKey: string;
  descKey: string;
  url: string;
  icon: ReactNode;
  adminOnly?: boolean;
};

const settingsItems: SettingsNavItem[] = [
  {
    key: 'appearance',
    labelKey: 'settings.nav.appearance.label',
    descKey: 'settings.nav.appearance.desc',
    url: '/pages/settings/index?section=appearance',
    icon: <Palette size={20} />,
  },
  {
    key: 'language',
    labelKey: 'settings.nav.language.label',
    descKey: 'settings.nav.language.desc',
    url: '/pages/settings/index?section=language',
    icon: <Globe size={20} />,
  },
  {
    key: 'notifications',
    labelKey: 'settings.nav.notifications.label',
    descKey: 'settings.nav.notifications.desc',
    url: '/pages/settings/index?section=notifications',
    icon: <Bell size={20} />,
  },
  {
    key: 'accessibility',
    labelKey: 'settings.nav.accessibility.label',
    descKey: 'settings.nav.accessibility.desc',
    url: '/pages/settings/index?section=accessibility',
    icon: <HeartHandshake size={20} />,
  },
  {
    key: 'ai',
    labelKey: 'settings.nav.ai.label',
    descKey: 'settings.nav.ai.desc',
    url: '/pages/settings/ai/index',
    icon: <Bot size={20} />,
    adminOnly: true,
  },
  {
    key: 'accounts',
    labelKey: 'settings.nav.accounts.label',
    descKey: 'settings.nav.accounts.desc',
    url: '/pages/settings/accounts/index',
    icon: <KeyRound size={20} />,
    adminOnly: true,
  },
  {
    key: 'integrations',
    labelKey: 'settings.nav.integrations.label',
    descKey: 'settings.nav.integrations.desc',
    url: '/pages/settings/integrations/index',
    icon: <LinkIcon size={20} />,
    adminOnly: true,
  },
  {
    key: 'channel-access',
    labelKey: 'settings.nav.channelAccess.label',
    descKey: 'settings.nav.channelAccess.desc',
    url: '/pages/settings/channel-access/index',
    icon: <MessageCircle size={20} />,
    adminOnly: true,
  },
  {
    key: 'plugins',
    labelKey: 'settings.nav.plugins.label',
    descKey: 'settings.nav.plugins.desc',
    url: '/pages/plugins/index',
    icon: <Puzzle size={20} />,
    adminOnly: true,
  },
  {
    key: 'version-management',
    labelKey: 'settings.nav.versionManagement.label',
    descKey: 'settings.nav.versionManagement.desc',
    url: '/pages/settings/index?section=version-management',
    icon: <TagIcon size={20} />,
    adminOnly: true,
  },
];

async function openPage(url: string) {
  try {
    await Taro.redirectTo({ url });
    return;
  } catch {
    // 当前页或栈受限时，退化到 navigateTo。
  }

  try {
    await Taro.navigateTo({ url });
    return;
  } catch {
    // 最后兜底直接重启到目标页。
  }

  await Taro.reLaunch({ url }).catch(() => undefined);
}

export function SettingsNav(props: { activeKey: SettingsNavKey }) {
  const { t } = useI18n();
  const { actor } = useAuthContext();

  const isAdmin = actor?.member_role === 'admin';

  const visibleItems = useMemo(() => {
    return settingsItems.filter((item) => !item.adminOnly || isAdmin);
  }, [isAdmin]);

  return (
    <nav className="memory-main-tabs" role="tablist" aria-label={t('settings.title')}>
      {visibleItems.map((item) => {
        const isActive = props.activeKey === item.key;
        return (
          <button
            key={item.key}
            type="button"
            className={`memory-main-tab ${isActive ? 'memory-main-tab--active' : ''}`}
            onClick={() => void openPage(item.url)}
          >
            <span className="settings-tab__icon">{item.icon}</span>
            <span className="settings-tab__label">{t(item.labelKey)}</span>
          </button>
        );
      })}
    </nav>
  );
}

export type { SettingsNavKey };
