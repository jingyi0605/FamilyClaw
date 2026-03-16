import {
  Bell,
  Bot,
  Globe,
  HeartHandshake,
  Link as LinkIcon,
  MessageCircle,
  Palette,
  Puzzle,
} from 'lucide-react';
import Taro from '@tarojs/taro';
import type { ReactNode } from 'react';
import { useI18n } from '../../runtime/h5-shell';

type SettingsNavKey =
  | 'appearance'
  | 'ai'
  | 'language'
  | 'notifications'
  | 'accessibility'
  | 'integrations'
  | 'channel-access'
  | 'plugins';

type SettingsNavItem = {
  key: SettingsNavKey;
  labelKey: string;
  descKey: string;
  url: string;
  icon: ReactNode;
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
    key: 'ai',
    labelKey: 'settings.nav.ai.label',
    descKey: 'settings.nav.ai.desc',
    url: '/pages/settings/ai/index',
    icon: <Bot size={20} />,
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
    key: 'integrations',
    labelKey: 'settings.nav.integrations.label',
    descKey: 'settings.nav.integrations.desc',
    url: '/pages/settings/integrations/index',
    icon: <LinkIcon size={20} />,
  },
  {
    key: 'channel-access',
    labelKey: 'settings.nav.channelAccess.label',
    descKey: 'settings.nav.channelAccess.desc',
    url: '/pages/settings/channel-access/index',
    icon: <MessageCircle size={20} />,
  },
  {
    key: 'plugins',
    labelKey: 'settings.nav.plugins.label',
    descKey: 'settings.nav.plugins.desc',
    url: '/pages/plugins/index',
    icon: <Puzzle size={20} />,
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

  return (
    <nav className="settings-tabs" role="tablist">
      <div className="settings-tabs__scroll">
        {settingsItems.map((item) => {
          const isActive = props.activeKey === item.key;
          return (
            <button
              key={item.key}
              type="button"
              className={`settings-tab ${isActive ? 'settings-tab--active' : ''}`}
              onClick={() => void openPage(item.url)}
            >
              <span className="settings-tab__icon">{item.icon}</span>
              <span className="settings-tab__label">{t(item.labelKey)}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}

export type { SettingsNavKey };
