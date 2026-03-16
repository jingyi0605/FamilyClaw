import path from 'node:path';

const apiProxyTarget = process.env.USER_APP_API_PROXY_TARGET ?? 'http://127.0.0.1:8000';

const workspacePackageSrcRoots = [
  'user-platform',
  'user-core',
  'user-ui',
  'user-testing',
].map(packageName => path.resolve(process.cwd(), `../../packages/${packageName}/src`));

const h5Config = {
  router: {
    mode: 'browser',
    customRoutes: {
      '/pages/home/index': ['/', '/home'],
      '/pages/entry/index': '/entry',
      '/pages/login/index': '/login',
      '/pages/setup/index': '/setup',
      '/pages/family/index': '/family',
      '/pages/assistant/index': ['/conversation', '/assistant'],
      '/pages/memories/index': '/memories',
      '/pages/settings/index': '/settings',
      '/pages/plugins/index': '/plugins',
    },
  },
  compile: {
    include: workspacePackageSrcRoots,
  },
  h5: {
    output: {
      filename: 'js/[name].[hash:8].js',
      chunkFilename: 'js/[name].[chunkhash:8].js',
    },
    devServer: {
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
          ws: true,
        },
      },
    },
  },
  devServer: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
};

export default h5Config;
