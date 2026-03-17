/**
 * AI供应商Logo组件
 * Logo来源：各平台官方品牌资源
 */
import type { SVGProps } from 'react';

type IconProps = SVGProps<SVGSVGElement>;

// OpenAI / ChatGPT
export function OpenAILogo(props: IconProps) {
  return (
    <svg viewBox="0 0 320 320" {...props}>
      <path
        fill="currentColor"
        d="M297.06 130.97c7.26-21.79 4.76-45.66-6.85-65.48-17.46-30.4-52.56-46.04-86.84-38.68C189.23 9.99 168.89-.72 147.23.03c-34.28 1.18-64.48 23.12-75.38 54.79-22.54 4.56-42.08 18.39-53.48 38.15-17.66 30.32-13.62 68.86 10.02 94.38-7.26 21.79-4.76 45.66 6.85 65.48 17.46 30.4 52.56 46.04 86.84 38.68 14.14 16.82 34.48 27.53 56.14 26.78 34.28-1.18 64.48-23.12 75.38-54.79 22.54-4.56 42.08-18.39 53.48-38.15 17.66-30.32 13.62-68.86-10.02-94.38zM165.45 299.48c-14.02.46-27.68-5.02-37.78-15.18l1.88-1.06 62.58-36.12c3.2-1.84 5.16-5.22 5.16-8.88v-88.2l26.44 15.26c.28.16.46.44.5.76v72.94c-.08 32.62-26.16 59.14-58.78 59.48zm-126.4-54.06c-7.02-12.14-9.54-26.36-7.1-40.08l1.88 1.12 62.58 36.12c3.18 1.86 7.12 1.86 10.3 0l76.4-44.12v30.52c.02.32-.12.64-.38.84l-63.24 36.5c-28.28 16.32-64.42 6.64-80.74-21.6l.3-.3zm-16.5-136.56c7-12.16 17.72-21.7 30.56-27.14v74.26c-.02 3.64 1.94 7.02 5.12 8.86l76.4 44.1-26.44 15.26c-.28.16-.6.2-.9.1l-63.26-36.52c-28.2-16.36-37.88-52.5-21.52-80.7l.04.04zm217.76 50.82l-76.4-44.12 26.44-15.24c.28-.16.6-.2.9-.1l63.26 36.5c28.26 16.34 37.94 52.52 21.58 80.74-7 12.14-17.72 21.68-30.54 27.12v-74.26c.04-3.62-1.92-6.98-5.08-8.84l-.16-.8zm26.32-39.72l-1.88-1.12-62.56-36.16c-3.18-1.84-7.12-1.84-10.3 0l-76.4 44.12v-30.52c-.02-.32.12-.64.38-.84l63.24-36.48c28.28-16.34 64.44-6.66 80.76 21.6 7 12.12 9.52 26.3 7.1 40zm-165.36 54.42l-26.44-15.26c-.28-.16-.46-.44-.5-.76V85.66c.02-32.86 26.52-59.48 59.38-59.48 13.88 0 27.32 4.88 37.98 13.78l-1.88 1.06-62.58 36.12c-3.2 1.84-5.16 5.22-5.16 8.88l-.02 88.04zm14.36-30.94l34.04-19.66 34.04 19.66v39.32l-34.04 19.66-34.04-19.66v-39.32z"
      />
    </svg>
  );
}

// Anthropic Claude
export function ClaudeLogo(props: IconProps) {
  return (
    <svg viewBox="0 0 80 80" {...props}>
      <path
        fill="currentColor"
        d="M51.2 0H28.8L0 80h20.8l4.8-13.6h28.8L59.2 80H80L51.2 0zM31.2 49.6L40 24l8.8 25.6H31.2z"
      />
    </svg>
  );
}

// Google Gemini
export function GeminiLogo(props: IconProps) {
  return (
    <svg viewBox="0 0 48 48" {...props}>
      <defs>
        <linearGradient id="geminiGradient1" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#4285F4" />
          <stop offset="50%" stopColor="#9B72CB" />
          <stop offset="100%" stopColor="#D96570" />
        </linearGradient>
        <linearGradient id="geminiGradient2" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#D96570" />
          <stop offset="50%" stopColor="#9B72CB" />
          <stop offset="100%" stopColor="#4285F4" />
        </linearGradient>
      </defs>
      <path
        fill="url(#geminiGradient1)"
        d="M24 48c0-13.255-10.745-24-24-24 13.255 0 24-10.745 24-24 0 13.255 10.745 24 24 24-13.255 0-24 10.745-24 24z"
      />
    </svg>
  );
}

// DeepSeek
export function DeepSeekLogo(props: IconProps) {
  return (
    <svg viewBox="0 0 32 32" {...props}>
      <path
        fill="currentColor"
        d="M16 0C7.163 0 0 7.163 0 16s7.163 16 16 16 16-7.163 16-16S24.837 0 16 0zm0 28c-6.627 0-12-5.373-12-12S9.373 4 16 4s12 5.373 12 12-5.373 12-12 12zm-4-8c2.209 0 4-1.791 4-4s-1.791-4-4-4-4 1.791-4 4 1.791 4 4 4zm8 0c2.209 0 4-1.791 4-4s-1.791-4-4-4-4 1.791-4 4 1.791 4 4 4z"
      />
    </svg>
  );
}

// 通义千问 Qwen
export function QwenLogo(props: IconProps) {
  return (
    <svg viewBox="0 0 32 32" {...props}>
      <defs>
        <linearGradient id="qwenGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#6366F1" />
          <stop offset="100%" stopColor="#8B5CF6" />
        </linearGradient>
      </defs>
      <circle cx="16" cy="16" r="14" fill="url(#qwenGradient)" />
      <path
        fill="white"
        d="M16 6c-5.523 0-10 4.477-10 10s4.477 10 10 10 10-4.477 10-10S21.523 6 16 6zm0 18c-4.418 0-8-3.582-8-8s3.582-8 8-8 8 3.582 8 8-3.582 8-8 8zm0-12c-2.209 0-4 1.791-4 4s1.791 4 4 4 4-1.791 4-4-1.791-4-4-4z"
      />
    </svg>
  );
}

// 智谱 GLM
export function GlmLogo(props: IconProps) {
  return (
    <svg viewBox="0 0 32 32" {...props}>
      <rect width="32" height="32" rx="6" fill="#1E40AF" />
      <path
        fill="white"
        d="M8 8h6v6H8V8zm10 0h6v6h-6V8zM8 18h6v6H8v-6zm10 0h6v6h-6v-6zm-5-5h2v2h-2v-2zm0 8h2v2h-2v-2z"
      />
    </svg>
  );
}

// SiliconFlow
export function SiliconFlowLogo(props: IconProps) {
  return (
    <svg viewBox="0 0 32 32" {...props}>
      <defs>
        <linearGradient id="siliconGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#3B82F6" />
          <stop offset="100%" stopColor="#06B6D4" />
        </linearGradient>
      </defs>
      <circle cx="16" cy="16" r="14" fill="url(#siliconGradient)" />
      <path
        fill="white"
        d="M10 12l6-4 6 4v8l-6 4-6-4v-8zm6 2l-3 2v4l3 2 3-2v-4l-3-2z"
      />
    </svg>
  );
}

// Kimi (Moonshot)
export function KimiLogo(props: IconProps) {
  return (
    <svg viewBox="0 0 32 32" {...props}>
      <rect width="32" height="32" rx="8" fill="#FF6B35" />
      <path
        fill="white"
        d="M10 10h4v12h-4V10zm8 0h4v12h-4V10zm-4 4h4v4h-4v-4z"
      />
    </svg>
  );
}

// MiniMax
export function MiniMaxLogo(props: IconProps) {
  return (
    <svg viewBox="0 0 32 32" {...props}>
      <rect width="32" height="32" rx="6" fill="#10B981" />
      <path
        fill="white"
        d="M8 8h16v2H8V8zm0 7h16v2H8v-2zm0 7h16v2H8v-2z"
      />
    </svg>
  );
}

// OpenRouter
export function OpenRouterLogo(props: IconProps) {
  return (
    <svg viewBox="0 0 32 32" {...props}>
      <circle cx="16" cy="16" r="14" fill="#6366F1" />
      <path
        fill="white"
        d="M10 12h12v2H10v-2zm0 6h12v2H10v-2zm3-3h6v2h-6v-2z"
      />
    </svg>
  );
}

// 豆包 Doubao
export function DoubaoLogo(props: IconProps) {
  return (
    <svg viewBox="0 0 32 32" {...props}>
      <rect width="32" height="32" rx="8" fill="#00D4AA" />
      <circle cx="12" cy="13" r="3" fill="white" />
      <circle cx="20" cy="13" r="3" fill="white" />
      <path
        fill="white"
        d="M10 20c0 0 3 4 6 4s6-4 6-4"
        stroke="white"
        strokeWidth="2"
        fill="none"
        strokeLinecap="round"
      />
    </svg>
  );
}

// BytePlus / VolcEngine
export function BytePlusLogo(props: IconProps) {
  return (
    <svg viewBox="0 0 32 32" {...props}>
      <rect width="32" height="32" rx="6" fill="#FF4D4F" />
      <path
        fill="white"
        d="M12 8h8v2h-8V8zm-4 4h16v2H8v-2zm2 4h12v8H10v-8zm4 2v4h4v-4h-4z"
      />
    </svg>
  );
}

// Default/Generic AI
export function DefaultAiLogo(props: IconProps) {
  return (
    <svg viewBox="0 0 32 32" {...props}>
      <circle cx="16" cy="16" r="14" fill="#94A3B8" />
      <path
        fill="white"
        d="M16 8c-4.418 0-8 3.582-8 8s3.582 8 8 8 8-3.582 8-8-3.582-8-8-8zm0 14c-3.314 0-6-2.686-6-6s2.686-6 6-6 6 2.686 6 6-2.686 6-6 6zm0-10c-2.209 0-4 1.791-4 4s1.791 4 4 4 4-1.791 4-4-1.791-4-4-4z"
      />
    </svg>
  );
}

// Logo映射表
export const AI_PROVIDER_LOGO_MAP: Record<string, React.FC<IconProps>> = {
  chatgpt: OpenAILogo,
  openai: OpenAILogo,
  claude: ClaudeLogo,
  anthropic: ClaudeLogo,
  gemini: GeminiLogo,
  google: GeminiLogo,
  deepseek: DeepSeekLogo,
  qwen: QwenLogo,
  glm: GlmLogo,
  zhipu: GlmLogo,
  siliconflow: SiliconFlowLogo,
  kimi: KimiLogo,
  moonshot: KimiLogo,
  minimax: MiniMaxLogo,
  openrouter: OpenRouterLogo,
  doubao: DoubaoLogo,
  'doubao-coding': DoubaoLogo,
  byteplus: BytePlusLogo,
  'byteplus-coding': BytePlusLogo,
  volcengine: BytePlusLogo,
};

export function getAiProviderLogo(adapterCode: string): React.FC<IconProps> {
  return AI_PROVIDER_LOGO_MAP[adapterCode] || DefaultAiLogo;
}
