/**
 * RnInput - 文本输入组件
 */
import { useState } from 'react';
import { TextInput, StyleSheet, type TextInputProps } from 'react-native';
import { rnSemanticTokens, rnComponentTokens } from '../tokens';

interface RnInputProps extends Omit<TextInputProps, 'onChangeText'> {
  value: string;
  onInput: (text: string) => void;
}

export function RnInput({ value, onInput, style, ...rest }: RnInputProps) {
  const [focused, setFocused] = useState(false);

  return (
    <TextInput
      value={value}
      onChangeText={onInput}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
      placeholderTextColor={rnSemanticTokens.text.tertiary}
      style={[
        styles.input,
        focused && styles.inputFocused,
        style,
      ]}
      {...rest}
    />
  );
}

const styles = StyleSheet.create({
  input: {
    minHeight: rnComponentTokens.input.minHeight,
    borderRadius: rnComponentTokens.input.borderRadius,
    borderWidth: rnComponentTokens.input.borderWidth,
    borderColor: rnComponentTokens.input.borderColor,
    backgroundColor: rnComponentTokens.input.backgroundColor,
    color: rnComponentTokens.input.color,
    fontSize: rnComponentTokens.input.fontSize,
    paddingHorizontal: rnComponentTokens.input.paddingHorizontal,
    paddingVertical: rnComponentTokens.input.paddingVertical,
  },
  inputFocused: {
    borderColor: rnSemanticTokens.action.primary,
    backgroundColor: rnSemanticTokens.surface.shell,
  },
});
