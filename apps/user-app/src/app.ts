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

  if (!actor?.authenticated) {
    return createElement(Fragment, null, props.children);
  }

  return createElement(
    HouseholdProvider,
    null,
    createElement(
      Fragment,
      null,
      createElement(HouseholdLocaleSync, null),
      createElement(SetupProvider, null, props.children),
    ),
  );
}

export default function App(props: { children?: ReactNode }) {
  return createElement(
    ThemeProvider,
    null,
    createElement(
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
    ),
  );
}
