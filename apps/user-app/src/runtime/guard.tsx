import { PropsWithChildren, useEffect, useMemo, useRef } from 'react';
import { Button, Text, View } from '@tarojs/components';
import Taro, { useRouter } from '@tarojs/taro';
import { AppShellPage } from '../components/AppShellPage';
import { useAuthContext } from './auth';
import { AppLayoutShell } from './h5-shell';
import { useOptionalHouseholdContext } from './household';
import { useOptionalSetupContext } from './setup';

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
const IS_H5 = process.env.TARO_ENV === 'h5';

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
    // H5 下某些场景 reLaunch 会拒绝，退回 redirectTo
  }

  try {
    await Taro.redirectTo({ url });
  } catch {
    // 最后兜底，不再继续抛异常打断渲染
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
          message: '检测到当前账号还没有可用家庭，正在进入初始化向导...',
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
      message: '登录态正常，正在进入主页...',
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

  if (guardResult.kind === 'ready') {
    if (IS_H5 && props.mode === 'protected') {
      return <AppLayoutShell>{props.children}</AppLayoutShell>;
    }
    return <>{props.children}</>;
  }

  if (IS_H5) {
    const isBusyState = guardResult.kind !== 'error';
    return (
      <div className="setup-guard">
        <div
          className={`setup-guard__content ${
            guardResult.kind === 'error' ? 'setup-guard__content--error' : 'setup-guard__content--loading'
          }`.trim()}
        >
          {isBusyState ? (
            <div className="setup-guard__visual" aria-hidden="true">
              <div className="setup-guard__halo" />
              <div className="setup-guard__spinner">
                <span className="setup-guard__spinner-core" />
              </div>
              <div className="setup-guard__dots">
                <span className="setup-guard__dot" />
                <span className="setup-guard__dot" />
                <span className="setup-guard__dot" />
              </div>
            </div>
          ) : null}
          <h2>{guardResult.kind === 'error' ? '运行时壳初始化失败' : '正在校验访问资格'}</h2>
          <span className="setup-guard__eyebrow">
            {guardResult.kind === 'error' ? '页面初始化失败' : '正在准备页面'}
          </span>
          <p className="setup-guard__message">{guardResult.message}</p>
          {isBusyState ? (
            <p className="setup-guard__hint">正在同步登录、家庭与初始化上下文，请稍候片刻。</p>
          ) : null}
          {guardResult.kind === 'error' && guardResult.onRetry ? (
            <div className="setup-guard__actions">
              <button className="btn btn--primary" type="button" onClick={() => guardResult.onRetry?.()}>
              重试
              </button>
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <AppShellPage>
      <View
        style={{
          minHeight: '60vh',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          gap: '16px',
          padding: '24px',
        }}
      >
        <Text style={{ fontSize: '28px', color: '#1f2937', lineHeight: '1.7' }}>
          {guardResult.message}
        </Text>
        {guardResult.kind === 'error' && guardResult.onRetry ? (
          <Button onClick={() => guardResult.onRetry?.()}>重试</Button>
        ) : null}
      </View>
    </AppShellPage>
  );
}
