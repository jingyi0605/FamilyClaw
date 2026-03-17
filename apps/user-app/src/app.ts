import { Fragment, createElement, type ReactNode } from 'react';
import './app.scss';
import './runtime/h5-shell/styles/index.h5.scss';
import { AuthProvider, HouseholdProvider, SetupProvider, useAuthContext } from './runtime';
import { I18nProvider, ThemeProvider, useI18n } from './runtime/h5-shell';
import { useEffect } from 'react';
import { useHouseholdContext } from './runtime';

function AuthLocaleReset() {
  const { actor } = useAuthContext();
  const { replacePluginLocales } = useI18n();

  useEffect(() => {
    if (!actor?.authenticated) {
      replacePluginLocales([]);
    }
  }, [actor?.authenticated, replacePluginLocales]);

  return null;
}

function HouseholdLocaleSync() {
  const { locales } = useHouseholdContext();
  const { replacePluginLocales } = useI18n();

  useEffect(() => {
    replacePluginLocales(locales);
  }, [locales, replacePluginLocales]);

  return null;
}

function RuntimeProviders(props: { children?: ReactNode }) {
  const { actor } = useAuthContext();

  // 始终提供 HouseholdProvider 和 SetupProvider，以确保 setup 页面等场景可以正常使用 hooks
  // GuardedPage 会根据认证状态和业务逻辑处理重定向
  return createElement(
    HouseholdProvider,
    null,
    createElement(
      SetupProvider,
      null,
      createElement(
        ThemeProvider,
        null,
        createElement(
          Fragment,
          null,
          actor?.authenticated ? createElement(HouseholdLocaleSync, null) : null,
          props.children,
        ),
      ),
    ),
  );
}

export default function App(props: { children?: ReactNode }) {
  return createElement(
    I18nProvider,
    null,
    createElement(
      AuthProvider,
      null,
      createElement(
        Fragment,
        null,
        createElement(AuthLocaleReset, null),
        createElement(RuntimeProviders, null, props.children),
      ),
    ),
  );
}
