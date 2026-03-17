/**
 * 通讯平台Logo组件
 * Logo来源：各平台官方品牌资源
 * - Telegram: https://telegram.org/tour/screenshots
 * - Discord: https://discord.com/branding
 * - 飞书: https://open.feishu.cn
 * - 钉钉: https://dingtalk.com
 */
import type { SVGProps } from 'react';

type IconProps = SVGProps<SVGSVGElement>;

export function TelegramLogo(props: IconProps) {
  return (
    <svg viewBox="0 0 240 240" {...props}>
      <defs>
        <linearGradient id="telegramGradient" x1="50%" y1="0%" x2="50%" y2="100%">
          <stop offset="0%" stopColor="#37AEE2" />
          <stop offset="100%" stopColor="#1E96C8" />
        </linearGradient>
      </defs>
      <circle cx="120" cy="120" r="120" fill="url(#telegramGradient)" />
      <path
        fill="#C8DAEA"
        d="M98 175c-3.9 0-3.2-1.5-4.6-5.2L82 132.2 170 80"
      />
      <path
        fill="#A9C9DD"
        d="M98 175c3 0 4.3-1.4 6-3l16-15.6-20-12"
      />
      <path
        fill="white"
        d="M100 144.4l48.4 35.7c5.5 3 9.5 1.5 10.9-5.1l19.7-92.8c2-8-3-11.6-8.4-9.3l-117.4 45.3c-7.8 3.1-7.7 7.5-1.4 9.5l30.1 9.4 69.7-43.9c3.3-2 6.3-.9 3.8 1.3"
      />
    </svg>
  );
}

export function DiscordLogo(props: IconProps) {
  return (
    <svg viewBox="0 0 127.14 96.36" {...props}>
      <path
        fill="#5865F2"
        d="M107.7,8.07A105.15,105.15,0,0,0,81.47,0a72.06,72.06,0,0,0-3.36,6.83A97.68,97.68,0,0,0,49,6.83,72.37,72.37,0,0,0,45.64,0,105.89,105.89,0,0,0,19.39,8.09C2.79,32.65-1.71,56.6.54,80.21h0A105.73,105.73,0,0,0,32.71,96.36,77.7,77.7,0,0,0,39.6,85.25a68.42,68.42,0,0,1-10.85-5.18c.91-.66,1.8-1.34,2.66-2a75.57,75.57,0,0,0,64.32,0c.87.71,1.76,1.39,2.66,2a68.68,68.68,0,0,1-10.87,5.19,77,77,0,0,0,6.89,11.1A105.25,105.25,0,0,0,126.6,80.22h0C129.24,52.84,122.09,29.11,107.7,8.07ZM42.45,65.69C36.18,65.69,31,60,31,53s5-12.74,11.43-12.74S54,46,53.89,53,48.84,65.69,42.45,65.69Zm42.24,0C78.41,65.69,73.25,60,73.25,53s5-12.74,11.44-12.74S96.23,46,96.12,53,91.08,65.69,84.69,65.69Z"
      />
    </svg>
  );
}

export function FeishuLogo(props: IconProps) {
  return (
    <svg viewBox="0 0 256 256" {...props}>
      <defs>
        <linearGradient id="feishuGradient1" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#00D6E9" />
          <stop offset="100%" stopColor="#00B4D8" />
        </linearGradient>
        <linearGradient id="feishuGradient2" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#0066FF" />
          <stop offset="100%" stopColor="#0052CC" />
        </linearGradient>
      </defs>
      <path
        fill="url(#feishuGradient1)"
        d="M128 32c-53 0-96 43-96 96s43 96 96 96 96-43 96-96-43-96-96-96zm0 168c-39.8 0-72-32.2-72-72s32.2-72 72-72 72 32.2 72 72-32.2 72-72 72z"
      />
      <path
        fill="url(#feishuGradient2)"
        d="M128 72c-30.9 0-56 25.1-56 56s25.1 56 56 56 56-25.1 56-56-25.1-56-56-56zm0 88c-17.7 0-32-14.3-32-32s14.3-32 32-32 32 14.3 32 32-14.3 32-32 32z"
      />
      <circle fill="#00D6E9" cx="128" cy="128" r="16" />
      <path
        fill="#0066FF"
        d="M96 40l16 24h32l16-24c-10-3-20.5-5-32-5s-22 2-32 5zM160 216l-16-24h-32l-16 24c10 3 20.5 5 32 5s22-2 32-5z"
      />
    </svg>
  );
}

export function DingtalkLogo(props: IconProps) {
  return (
    <svg viewBox="0 0 1024 1024" {...props}>
      <defs>
        <linearGradient id="dingtalkGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#0089FF" />
          <stop offset="100%" stopColor="#0066CC" />
        </linearGradient>
      </defs>
      <path
        fill="url(#dingtalkGradient)"
        d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm195.2 544.5c-14.5 41.5-56.5 94.5-106.5 128.5l-1.5 1-3 1.5c-11 5.5-23 8.5-35.5 8.5-20.5 0-40-7.5-55-21l-2-2c-22-21-35.5-52-35.5-85 0-12 2-24 5.5-35l1-3 2-4 1-2c5-10 12-20 20.5-28.5 32-32 78-44 120.5-33l2 .5 2 .5c3 1 6 2 9 3.5l2 1 2.5 1.5c7 4 13.5 8.5 19.5 14 8 7.5 14.5 16 19.5 25.5l1 2 1 2c8 16 12 33.5 12 51.5 0 8-1 16-3 24l-.5 2-.5 2z"
      />
      <path
        fill="white"
        d="M708.5 609c-4.5-9.5-11-18-19-25.5-6-5.5-12.5-10-19.5-14l-2.5-1.5-2-1c-3-1.5-6-2.5-9-3.5l-2-.5-2-.5c-42.5-11-88.5 1-120.5 33-8.5 8.5-15.5 18.5-20.5 28.5l-1 2-2 4-1 3c-3.5 11-5.5 23-5.5 35 0 33 13.5 64 35.5 85l2 2c15 13.5 34.5 21 55 21 12.5 0 24.5-3 35.5-8.5l3-1.5 1.5-1c50-34 92-87 106.5-128.5l.5-2 .5-2c2-8 3-16 3-24 0-18-4-35.5-12-51.5l-1-2-1-2z"
      />
      <path
        fill="white"
        d="M512 256c-141.4 0-256 114.6-256 256 0 52.5 15.8 101.3 43 141.8l-31.5 94.5 100-35.5c38.5 25 84.5 39.7 133.5 40.2h11c141.4 0 256-114.6 256-256S653.4 256 512 256z"
        opacity="0.3"
      />
    </svg>
  );
}

export const PLATFORM_LOGO_MAP: Record<string, React.FC<IconProps>> = {
  telegram: TelegramLogo,
  discord: DiscordLogo,
  feishu: FeishuLogo,
  dingtalk: DingtalkLogo,
};
