import { Fragment, createElement, type ReactNode } from 'react';
import './app.scss';
import { useEffect } from 'react';
import { AuthProvider, HouseholdProvider, SetupProvider, UserGuideProvider, useAuthContext, useHouseholdContext } from './runtime/index.rn';
import { I18nProvider, ThemeProvider, useI18n } from './runtime/h5-shell/index.rn';

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
