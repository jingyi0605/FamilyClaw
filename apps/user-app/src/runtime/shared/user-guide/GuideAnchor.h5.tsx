import { useCallback, useEffect, type CSSProperties } from 'react';
import { useOptionalUserGuideContext } from '../../user-guide';
import { registerGuideAnchor, unregisterGuideAnchor } from './anchorRegistry';
import type { GuideAnchorProps } from './GuideAnchor.types';

export function GuideAnchor(props: GuideAnchorProps) {
  const guide = useOptionalUserGuideContext();

  const bindElement = useCallback((element: HTMLDivElement | null) => {
    registerGuideAnchor({
      anchorId: props.anchorId,
      route: guide?.currentRoute ?? '',
      ready: Boolean(element),
      element,
    });
  }, [guide?.currentRoute, props.anchorId]);

  useEffect(() => () => unregisterGuideAnchor(props.anchorId), [props.anchorId]);

  return (
    <div
      ref={bindElement}
      className={props.className}
      style={props.style as CSSProperties | undefined}
      data-guide-anchor={props.anchorId}
    >
      {props.children}
    </div>
  );
}
