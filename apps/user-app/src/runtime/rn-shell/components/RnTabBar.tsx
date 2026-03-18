/**
 * RnTabBar - 底部导航栏
 *
 * 使用 Taro 路由跳转，读取当前路由高亮对应 tab。
 */
import { View, Pressable, StyleSheet } from 'react-native';
import Taro, { useRouter } from '@tarojs/taro';
import { rnSemanticTokens, rnFoundationTokens, rnComponentTokens } from '../tokens';
import { useI18n } from '../../h5-shell/i18n/I18nProvider';
import { RnText } from './RnText';

interface TabItem {
  key: string;
  labelKey: string;
  icon: string;
  url: string;
}

const TABS: TabItem[] = [
  { key: 'home', labelKey: 'nav.home', icon: '🏠', url: '/pages/home/index' },
  { key: 'assistant', labelKey: 'nav.assistant', icon: '💬', url: '/pages/assistant/index' },
  { key: 'family', labelKey: 'nav.family', icon: '👨‍👩‍👧‍👦', url: '/pages/family/index' },
  { key: 'memories', labelKey: 'nav.memories', icon: '📝', url: '/pages/memories/index' },
  { key: 'settings', labelKey: 'nav.settings', icon: '⚙️', url: '/pages/settings/index' },
];

export function RnTabBar() {
  const { t } = useI18n();
  const router = useRouter();
  const currentPath = router.path || '';

  function handlePress(url: string) {
    if (currentPath === url) return;
    void Taro.switchTab({ url }).catch(() => {
      void Taro.navigateTo({ url });
    });
  }

  return (
    <View style={[styles.container, rnComponentTokens.shadow.md]}>
      {TABS.map((tab) => {
        const isActive = currentPath.includes(tab.key);
        return (
          <Pressable
            key={tab.key}
            style={styles.tab}
            onPress={() => handlePress(tab.url)}
          >
            <RnText style={styles.tabIcon}>{tab.icon}</RnText>
            <RnText
              variant="caption"
              style={[
                styles.tabLabel,
                { color: isActive ? rnSemanticTokens.nav.textActive : rnSemanticTokens.nav.text },
              ]}
            >
              {t(tab.labelKey)}
            </RnText>
            {isActive ? <View style={styles.indicator} /> : null}
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    backgroundColor: rnSemanticTokens.surface.shell,
    borderTopWidth: 1,
    borderTopColor: rnSemanticTokens.border.subtle,
    paddingBottom: 20, // safe area approximation
    paddingTop: rnFoundationTokens.spacing.sm,
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: rnFoundationTokens.spacing.xs,
  },
  tabIcon: {
    fontSize: 20,
    marginBottom: 2,
  },
  tabLabel: {
    fontSize: rnFoundationTokens.fontSize.xs,
    fontWeight: '500',
  },
  indicator: {
    position: 'absolute',
    top: 0,
    width: 20,
    height: 3,
    borderRadius: 1.5,
    backgroundColor: rnSemanticTokens.action.primary,
  },
});
