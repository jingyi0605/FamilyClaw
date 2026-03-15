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
  label: string;
  desc: string;
  url: string;
  icon: ReactNode;
};

const settingsItems: SettingsNavItem[] = [
  {
    key: 'appearance',
    label: '外观主题',
    desc: '切换主题并预览当前风格',
    url: '/pages/settings/index?section=appearance',
    icon: <Palette size={20} />,
  },
  {
    key: 'ai',
    label: 'AI 配置',
    desc: '管理提供商、管家和 Agent',
    url: '/pages/settings/ai/index',
    icon: <Bot size={20} />,
  },
  {
    key: 'language',
    label: '语言与地区',
    desc: '调整界面语言和时区',
    url: '/pages/settings/index?section=language',
    icon: <Globe size={20} />,
  },
  {
    key: 'notifications',
    label: '通知偏好',
    desc: '管理免打扰和提醒范围',
    url: '/pages/settings/index?section=notifications',
    icon: <Bell size={20} />,
  },
  {
    key: 'accessibility',
    label: '长辈友好',
    desc: '切换更大字号和更高对比',
    url: '/pages/settings/index?section=accessibility',
    icon: <HeartHandshake size={20} />,
  },
  {
    key: 'integrations',
    label: '设备与集成',
    desc: '管理 Home Assistant 和设备同步',
    url: '/pages/settings/integrations/index',
    icon: <LinkIcon size={20} />,
  },
  {
    key: 'channel-access',
    label: '通讯平台接入',
    desc: '接入 Telegram、Discord 等外部平台',
    url: '/pages/settings/channel-access/index',
    icon: <MessageCircle size={20} />,
  },
  {
    key: 'plugins',
    label: '插件管理',
    desc: '查看和管理已安装插件',
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
  return (
    <nav className="settings-nav">
      {settingsItems.map((item) => {
        const isActive = props.activeKey === item.key;

        return (
          <button
            key={item.key}
            type="button"
            className={`settings-nav__item ${isActive ? 'settings-nav__item--active' : ''}`}
            aria-current={isActive ? 'page' : undefined}
            onClick={() => void openPage(item.url)}
          >
            <span className="settings-nav__icon">{item.icon}</span>
            <div className="settings-nav__text">
              <span className="settings-nav__label">{item.label}</span>
              <span className="settings-nav__desc">{item.desc}</span>
            </div>
          </button>
        );
      })}
    </nav>
  );
}

export type { SettingsNavKey };
