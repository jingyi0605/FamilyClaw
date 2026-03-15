export type LoginLocaleId = 'zh-CN' | 'en-US';

export type LoginMessageKey =
  | 'login.welcome'
  | 'login.subtitle'
  | 'login.feature1'
  | 'login.feature2'
  | 'login.feature3'
  | 'login.title'
  | 'login.formSubtitle'
  | 'login.username'
  | 'login.usernamePlaceholder'
  | 'login.password'
  | 'login.passwordPlaceholder'
  | 'login.loggingIn'
  | 'login.submit'
  | 'login.footer';

export const loginMessages: Record<LoginLocaleId, Record<LoginMessageKey, string>> = {
  'zh-CN': {
    'login.welcome': '欢迎来到智能家庭空间',
    'login.subtitle': '一个温暖、智能、关怀的家庭助手，让每一天都充满可能',
    'login.feature1': '智能对话助手',
    'login.feature2': '家庭记忆中心',
    'login.feature3': '隐私安全保障',
    'login.title': '登录',
    'login.formSubtitle': '使用您的家庭账号进入',
    'login.username': '用户名',
    'login.usernamePlaceholder': '请输入用户名',
    'login.password': '密码',
    'login.passwordPlaceholder': '请输入密码',
    'login.loggingIn': '登录中...',
    'login.submit': '进入家庭空间',
    'login.footer': '让科技温暖每个家庭',
  },
  'en-US': {
    'login.welcome': 'Welcome to Your Smart Home',
    'login.subtitle': 'A warm, intelligent family assistant that makes every day possible',
    'login.feature1': 'Smart Conversation',
    'login.feature2': 'Family Memories',
    'login.feature3': 'Privacy & Security',
    'login.title': 'Sign In',
    'login.formSubtitle': 'Enter with your family account',
    'login.username': 'Username',
    'login.usernamePlaceholder': 'Enter your username',
    'login.password': 'Password',
    'login.passwordPlaceholder': 'Enter your password',
    'login.loggingIn': 'Signing in...',
    'login.submit': 'Enter Home',
    'login.footer': 'Technology that warms every family',
  },
};
