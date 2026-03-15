import { ReactNode, createElement } from 'react';
import './app.scss';
import { AppRuntimeProvider } from './runtime';

export default function App(props: { children?: unknown }) {
  return createElement(AppRuntimeProvider, null, props.children as ReactNode);
}
