import { Fragment, createElement, type ReactNode } from 'react';
import './app.scss';
import {
  AuthProvider,
  HouseholdProvider,
  SetupProvider,
  UserGuideProvider,
  useAuthContext,
  useHouseholdContext,
} from './runtime/runtime-safe';
import { I18nProvider, useI18n } from './runtime/h5-shell/i18n/I18nProvider';
import { ThemeProvider } from './runtime/h5-shell/theme/ThemeProvider';
import { useEffect } from 'react';

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
          UserGuideProvider,
          null,
          createElement(
            Fragment,
            null,
            actor?.authenticated ? createElement(HouseholdLocaleSync, null) : null,
            props.children,
          ),
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
