import Taro, { ENV_TYPE } from '@tarojs/taro';
import { AppPlatformTarget } from '@familyclaw/user-core';

export function getPlatformTarget(): AppPlatformTarget {
  const env = Taro.getEnv();

  if (env === ENV_TYPE.WEB) {
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

  if (env === ENV_TYPE.RN) {
    const systemInfo = Taro.getSystemInfoSync();
    const platform = systemInfo.platform === 'android' ? 'rn-android' : 'rn-ios';

    return {
      platform,
      runtime: 'rn',
      supports_push: true,
      supports_file_picker: true,
      supports_camera: true,
      supports_share: true,
      supports_deeplink: true,
    };
  }

  if (env === ENV_TYPE.HARMONY || env === ENV_TYPE.HARMONYHYBRID) {
    return {
      platform: 'harmony',
      runtime: 'harmony',
      supports_push: true,
      supports_file_picker: true,
      supports_camera: true,
      supports_share: true,
      supports_deeplink: true,
    };
  }

  return {
    platform: 'harmony',
    runtime: 'harmony',
    supports_push: true,
    supports_file_picker: true,
    supports_camera: true,
    supports_share: true,
    supports_deeplink: true,
  };
}
