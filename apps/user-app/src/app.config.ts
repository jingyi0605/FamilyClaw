export default {
  animation: false,
  pages: [
    'pages/entry/index',
    'pages/login/index',
    'pages/setup/index',
    'pages/home/index',
  ],
  subPackages: [
    {
      root: 'pages/family',
      pages: ['index'],
    },
    {
      root: 'pages/assistant',
      pages: ['index'],
    },
    {
      root: 'pages/memories',
      pages: ['index'],
    },
    {
      root: 'pages/settings',
      pages: ['index', 'ai/index', 'accounts/index', 'integrations/index', 'channel-access/index'],
    },
    {
      root: 'pages/plugins',
      pages: ['index'],
    },
  ],
  window: {
    navigationBarTitleText: 'FamilyClaw',
    navigationBarBackgroundColor: '#ffffff',
    navigationBarTextStyle: 'black',
    backgroundColor: '#f5f6f8',
    backgroundTextStyle: 'light',
  },
};
