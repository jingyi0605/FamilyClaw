const apiProxyTarget = process.env.USER_APP_API_PROXY_TARGET ?? 'http://127.0.0.1:8000';

const h5Config = {
  router: {
    mode: 'browser',
    customRoutes: {
      '/pages/home/index': ['/', '/home'],
      '/pages/entry/index': '/entry',
      '/pages/login/index': '/login',
      '/pages/setup/index': '/setup',
      '/pages/family/index': '/family',
      '/pages/assistant/index': '/assistant',
      '/pages/memories/index': '/memories',
      '/pages/settings/index': '/settings',
      '/pages/plugins/index': '/plugins',
    },
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
