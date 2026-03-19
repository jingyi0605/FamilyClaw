import { useEffect } from 'react';
import { View, StyleSheet, type StyleProp, type ViewStyle } from 'react-native';
import { useOptionalUserGuideContext } from '../../user-guide';
import { registerGuideAnchor, unregisterGuideAnchor } from './anchorRegistry';
import type { GuideAnchorProps } from './GuideAnchor.types';

export function GuideAnchor(props: GuideAnchorProps) {
  const guide = useOptionalUserGuideContext();
  const isActive = guide?.currentStep?.anchor_id === props.anchorId && guide.session?.status === 'showing';

  useEffect(() => {
    registerGuideAnchor({
      anchorId: props.anchorId,
      route: guide?.currentRoute ?? '',
      ready: false,
    });

    return () => unregisterGuideAnchor(props.anchorId);
  }, [guide?.currentRoute, props.anchorId]);

  return (
    <View
      onLayout={() => {
        registerGuideAnchor({
          anchorId: props.anchorId,
          route: guide?.currentRoute ?? '',
          ready: true,
        });
      }}
      style={[
        styles.container,
        props.style as StyleProp<ViewStyle>,
        isActive ? styles.active : null,
      ]}
    >
      {props.children}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderRadius: 20,
  },
  active: {
    borderWidth: 2,
    borderColor: '#f58a3a',
    backgroundColor: 'rgba(245, 138, 58, 0.08)',
  },
});
