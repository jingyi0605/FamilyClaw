/* ============================================================
 * Web 平台专用入口
 * 只导出 web 环境需要的功能，不包含 Taro 依赖
 * ============================================================ */

// 只导出 browser 和 memory storage
export { createBrowserStorageAdapter } from './storage/browser';
export { createMemoryStorage } from './storage/memory';
export type { KeyValueStorage } from './storage/types';

// 兼容别名：在 H5 环境中，Taro 存储适配器等同于浏览器存储适配器
export { createBrowserStorageAdapter as createTaroStorageAdapter } from './storage/browser';

// 实时连接（浏览器实现，无 Taro 依赖）
export {
  BOOTSTRAP_REALTIME_EVENT_TYPES,
  DISPLAY_TEXT_EVENT_TYPES,
  FORBIDDEN_TEXT_PROTOCOL_MARKERS,
  STATE_PATCH_EVENT_TYPES,
  assertBootstrapRealtimeEvent,
  buildBootstrapRealtimeUrl,
  buildConversationRealtimeUrl,
  createBrowserRealtimeClient,
  newRealtimeRequestId,
  parseBootstrapRealtimeEvent,
  createUnavailableRealtimeConnection,
  type RealtimeConnection,
  type RealtimeConnectionState,
  type BootstrapRealtimeEvent,
  type BootstrapRealtimeEventType,
  type BootstrapRealtimePayloadByType,
  type BootstrapRealtimeSessionSnapshot,
} from './realtime';

// Web 平台能力类型（本地定义，避免循环依赖）
export type WebPlatformTarget = {
  platform: 'h5';
  runtime: 'h5';
  supports_push: boolean;
  supports_file_picker: boolean;
  supports_camera: boolean;
  supports_share: boolean;
  supports_deeplink: boolean;
};

export function getPlatformTarget(): WebPlatformTarget {
  return {
    platform: 'h5',
    runtime: 'h5',
    supports_push: false,
    supports_file_picker: true,
    supports_camera: false,
    supports_share: typeof navigator !== 'undefined' && 'share' in navigator,
    supports_deeplink: true,
  };
}
