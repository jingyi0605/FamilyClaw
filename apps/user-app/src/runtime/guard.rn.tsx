import { PropsWithChildren, useEffect, useMemo, useRef } from 'react';
import { View } from 'react-native';
import Taro, { useRouter } from '@tarojs/taro';
import { useAuthContext } from './auth';
import { useOptionalHouseholdContext } from './household';
import {
  RnButton,
  RnCard,
  RnPageShell,
  RnText,
  rnFoundationTokens,
} from './rn-shell';
import { useOptionalSetupContext } from './setup';
import { useOptionalUserGuideContext } from './user-guide';

type GuardMode = 'entry' | 'login' | 'protected' | 'setup';

type GuardResult =
  | { kind: 'ready' }
  | { kind: 'loading'; message: string }
  | { kind: 'redirect'; message: string; url: string }
  | { kind: 'error'; message: string; onRetry?: () => void };

const ENTRY_PAGE_URL = '/pages/entry/index';
const HOME_PAGE_URL = '/pages/home/index';
const LOGIN_PAGE_URL = '/pages/login/index';
const SETUP_PAGE_URL = '/pages/setup/index';

function normalizePath(path: string) {
  if (!path) {
    return ENTRY_PAGE_URL;
  }
  return path.startsWith('/') ? path : `/${path}`;
}

function encodeRedirect(path: string) {
  return encodeURIComponent(normalizePath(path));
}

function decodeRedirect(value?: string | string[]) {
  const raw = Array.isArray(value) ? value[0] : value;
  if (!raw) {
    return '';
  }

  try {
    return normalizePath(decodeURIComponent(raw));
  } catch {
    return HOME_PAGE_URL;
  }
}

async function replacePage(url: string) {
  try {
    await Taro.reLaunch({ url });
    return;
  } catch {
    // RN 场景下继续降级尝试 redirectTo。
  }

  try {
    await Taro.redirectTo({ url });
  } catch {
    // 最后兜底，不再抛异常打断壳层。
  }
}

function resolveGuardResult(options: {
  mode: GuardMode;
  path: string;
  redirect: string;
  authLoading: boolean;
  authenticated: boolean;
  household: ReturnType<typeof useOptionalHouseholdContext>;
  setup: ReturnType<typeof useOptionalSetupContext>;
}): GuardResult {
  const {
    mode,
    path,
    redirect,
    authLoading,
    authenticated,
    household,
    setup,
  } = options;

  if (authLoading) {
    return { kind: 'loading', message: '正在检查登录状态...' };
  }

  if (mode === 'login') {
    if (authenticated) {
      return {
        kind: 'redirect',
        message: '登录态已恢复，正在进入应用...',
        url: redirect || ENTRY_PAGE_URL,
      };
    }
    return { kind: 'ready' };
  }

  if (!authenticated) {
    return {
      kind: 'redirect',
      message: '未登录，正在跳转到登录页...',
      url: `${LOGIN_PAGE_URL}?redirect=${encodeRedirect(path)}`,
    };
  }

  if (!household || !setup) {
    return { kind: 'loading', message: '正在初始化应用上下文...' };
  }

  if (household.householdsError && !household.householdsLoading && household.households.length === 0) {
    return {
      kind: 'error',
      message: household.householdsError,
      onRetry: () => {
        void household.refreshHouseholds();
      },
    };
  }

  if (mode === 'entry') {
    if (!household.currentHouseholdId) {
      if (household.householdsLoading) {
        return { kind: 'loading', message: '正在加载家庭信息...' };
      }
      if (household.households.length === 0) {
        return {
          kind: 'redirect',
          message: '当前账号还没有可用家庭，正在进入初始化向导...',
          url: SETUP_PAGE_URL,
        };
      }
      return { kind: 'loading', message: '正在选择家庭...' };
    }

    if (setup.setupStatusLoading) {
      return { kind: 'loading', message: '正在检查初始化状态...' };
    }

    if (setup.setupStatusError) {
      return {
        kind: 'error',
        message: setup.setupStatusError,
        onRetry: () => {
          void setup.refreshSetupStatus();
        },
      };
    }

    if (setup.setupStatus?.is_required) {
      return {
        kind: 'redirect',
        message: '当前家庭尚未初始化完成，正在进入向导...',
        url: SETUP_PAGE_URL,
      };
    }

    return {
      kind: 'redirect',
      message: '登录态正常，正在进入首页...',
      url: HOME_PAGE_URL,
    };
  }

  if (!household.currentHouseholdId) {
    if (household.householdsLoading) {
      return { kind: 'loading', message: '正在加载家庭信息...' };
    }
    if (household.households.length === 0) {
      if (mode === 'setup') {
        return { kind: 'ready' };
      }
      return {
        kind: 'redirect',
        message: '当前账号还没有家庭，正在进入初始化向导...',
        url: `${SETUP_PAGE_URL}?redirect=${encodeRedirect(path)}`,
      };
    }
    return { kind: 'loading', message: '正在选择家庭...' };
  }

  if (setup.setupStatusLoading) {
    return { kind: 'loading', message: '正在检查初始化状态...' };
  }

  if (setup.setupStatusError) {
    return {
      kind: 'error',
      message: setup.setupStatusError,
      onRetry: () => {
        void setup.refreshSetupStatus();
      },
    };
  }

  if (mode === 'setup') {
    if (
      setup.setupStatus &&
      !setup.setupStatus.is_required &&
      setup.setupStatus.missing_requirements.length === 0
    ) {
      return {
        kind: 'redirect',
        message: '初始化已完成，正在回到业务页面...',
        url: redirect || HOME_PAGE_URL,
      };
    }

    return { kind: 'ready' };
  }

  if (setup.setupStatus?.is_required) {
    return {
      kind: 'redirect',
      message: '当前家庭尚未初始化完成，正在进入向导...',
      url: `${SETUP_PAGE_URL}?redirect=${encodeRedirect(path)}`,
    };
  }

  return { kind: 'ready' };
}

export function GuardedPage(props: PropsWithChildren<{ mode: GuardMode; path: string }>) {
  const router = useRouter();
  const { actor, authLoading } = useAuthContext();
  const household = useOptionalHouseholdContext();
  const setup = useOptionalSetupContext();
  const guide = useOptionalUserGuideContext();
  const setGuideCurrentRoute = guide?.setCurrentRoute;
  const latestRedirect = useRef('');

  const guardResult = useMemo(() => resolveGuardResult({
    mode: props.mode,
    path: normalizePath(props.path),
    redirect: decodeRedirect(router.params?.redirect),
    authLoading,
    authenticated: Boolean(actor?.authenticated),
    household,
    setup,
  }), [actor?.authenticated, authLoading, household, props.mode, props.path, router.params, setup]);

  useEffect(() => {
    if (guardResult.kind !== 'redirect') {
      latestRedirect.current = '';
      return;
    }

    if (latestRedirect.current === guardResult.url) {
      return;
    }

    latestRedirect.current = guardResult.url;
    void replacePage(guardResult.url);
  }, [guardResult]);

  useEffect(() => {
    if (guardResult.kind !== 'ready') {
      return;
    }

    setGuideCurrentRoute?.(props.path);
  }, [guardResult.kind, props.path, setGuideCurrentRoute]);

  if (guardResult.kind === 'ready') {
    return <>{props.children}</>;
  }

  return (
    <RnPageShell safeAreaBottom={false}>
      <RnCard
        variant="muted"
        style={{
          minHeight: 280,
          justifyContent: 'center',
          gap: rnFoundationTokens.spacing.md,
        }}
      >
        <RnText variant="title">
          {guardResult.kind === 'error' ? '页面初始化失败' : '正在校验访问资格'}
        </RnText>
        <RnText variant="body" tone="secondary">
          {guardResult.message}
        </RnText>
        {guardResult.kind === 'error' && guardResult.onRetry ? (
          <View style={{ marginTop: rnFoundationTokens.spacing.sm }}>
            <RnButton onPress={() => guardResult.onRetry?.()}>重试</RnButton>
          </View>
        ) : null}
      </RnCard>
    </RnPageShell>
  );
}
