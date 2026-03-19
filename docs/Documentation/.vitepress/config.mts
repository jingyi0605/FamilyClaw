import { defineConfig } from 'vitepress'

function normalizeBase(rawBase?: string) {
  if (!rawBase) {
    return '/'
  }

  let normalized = rawBase.trim()

  if (!normalized) {
    return '/'
  }

  if (!normalized.startsWith('/')) {
    normalized = `/${normalized}`
  }

  if (!normalized.endsWith('/')) {
    normalized = `${normalized}/`
  }

  return normalized
}

function createThemeConfig(options: {
  nav: Array<{ text: string; link: string }>
  sidebar: Record<string, Array<{ text: string; items: Array<{ text: string; link: string }> }>>
  outlineLabel: string
  prevLabel: string
  nextLabel: string
  lastUpdatedText: string
  sidebarMenuLabel: string
  returnToTopLabel: string
  darkModeSwitchLabel: string
  lightModeSwitchTitle: string
  darkModeSwitchTitle: string
  langMenuLabel: string
  footerMessage: string
}) {
  return {
    nav: options.nav,
    sidebar: options.sidebar,
    outline: {
      level: [2, 3],
      label: options.outlineLabel
    },
    search: {
      provider: 'local'
    },
    docFooter: {
      prev: options.prevLabel,
      next: options.nextLabel
    },
    lastUpdated: {
      text: options.lastUpdatedText
    },
    sidebarMenuLabel: options.sidebarMenuLabel,
    returnToTopLabel: options.returnToTopLabel,
    darkModeSwitchLabel: options.darkModeSwitchLabel,
    lightModeSwitchTitle: options.lightModeSwitchTitle,
    darkModeSwitchTitle: options.darkModeSwitchTitle,
    langMenuLabel: options.langMenuLabel,
    footer: {
      message: options.footerMessage,
      copyright: 'Copyright © 2026 FamilyClaw'
    }
  }
}

const zhThemeConfig = createThemeConfig({
  nav: [
    { text: '快速开始', link: '/快速开始/文档总览' },
    { text: '安装部署', link: '/安装部署/概览' },
    { text: '使用指南', link: '/使用指南/仪表盘' },
    { text: '开发文档', link: '/开发文档/环境准备' },
    { text: '沟通交流', link: '/沟通交流/官方网站' }
  ],
  sidebar: {
    '/快速开始/': [
      {
        text: '快速开始',
        items: [
          { text: '文档总览', link: '/快速开始/文档总览' },
          { text: '产品概览', link: '/快速开始/产品概览' },
          { text: '快速启动', link: '/快速开始/快速启动' },
          { text: '核心功能', link: '/快速开始/核心功能' }
        ]
      }
    ],
    '/安装部署/': [
      {
        text: '安装部署',
        items: [
          { text: '概览', link: '/安装部署/概览' },
          { text: 'Docker安装', link: '/安装部署/Docker安装' },
          { text: '源码安装', link: '/安装部署/源码安装' },
          { text: 'NAS部署', link: '/安装部署/NAS部署' },
          { text: 'Ubuntu部署', link: '/安装部署/Ubuntu部署' },
          { text: 'Windows部署', link: '/安装部署/Windows部署' }
        ]
      }
    ],
    '/使用指南/': [
      {
        text: '使用指南',
        items: [
          { text: '仪表盘', link: '/使用指南/仪表盘' },
          { text: '家庭', link: '/使用指南/家庭' },
          { text: '对话', link: '/使用指南/对话' },
          { text: '记忆', link: '/使用指南/记忆' },
          { text: '设置', link: '/使用指南/设置' }
        ]
      }
    ],
    '/开发文档/': [
      {
        text: '开发文档',
        items: [
          { text: '环境准备', link: '/开发文档/环境准备' },
          { text: '后端开发', link: '/开发文档/后端开发' },
          { text: '插件开发', link: '/开发文档/插件开发' }
        ]
      },
      {
        text: '插件开发专题',
        items: [
          { text: '插件规范', link: '/开发文档/插件规范' },
          { text: '目录结构', link: '/开发文档/目录结构' },
          { text: '字段规范', link: '/开发文档/字段规范' },
          { text: '对接方式', link: '/开发文档/对接方式' },
          { text: '实例插件', link: '/开发文档/实例插件' },
          { text: '插件提交', link: '/开发文档/插件提交' }
        ]
      }
    ],
    '/沟通交流/': [
      {
        text: '沟通交流',
        items: [
          { text: '官方网站', link: '/沟通交流/官方网站' },
          { text: 'QQ群', link: '/沟通交流/QQ群' },
          { text: '微信群', link: '/沟通交流/微信群' },
          { text: 'Discord', link: '/沟通交流/Discord' }
        ]
      }
    ]
  },
  outlineLabel: '本页目录',
  prevLabel: '上一页',
  nextLabel: '下一页',
  lastUpdatedText: '最后更新',
  sidebarMenuLabel: '目录',
  returnToTopLabel: '回到顶部',
  darkModeSwitchLabel: '切换主题',
  lightModeSwitchTitle: '切换到浅色模式',
  darkModeSwitchTitle: '切换到深色模式',
  langMenuLabel: '语言',
  footerMessage: '文档源文件保存在仓库内，站点只是展示层。'
})

const enThemeConfig = createThemeConfig({
  nav: [
    { text: 'Getting Started', link: '/en/getting-started/docs-overview' },
    { text: 'Installation', link: '/en/installation-deployment/overview' },
    { text: 'User Guide', link: '/en/user-guide/dashboard' },
    { text: 'Developer Docs', link: '/en/developer-docs/environment-setup' },
    { text: 'Community', link: '/en/community/official-website' }
  ],
  sidebar: {
    '/en/getting-started/': [
      {
        text: 'Getting Started',
        items: [
          { text: 'Docs Overview', link: '/en/getting-started/docs-overview' },
          { text: 'Product Overview', link: '/en/getting-started/product-overview' },
          { text: 'Quick Start', link: '/en/getting-started/quick-start' },
          { text: 'Core Features', link: '/en/getting-started/core-features' }
        ]
      }
    ],
    '/en/installation-deployment/': [
      {
        text: 'Installation & Deployment',
        items: [
          { text: 'Overview', link: '/en/installation-deployment/overview' },
          { text: 'Docker Installation', link: '/en/installation-deployment/docker-installation' },
          { text: 'Source Installation', link: '/en/installation-deployment/source-installation' },
          { text: 'NAS Deployment', link: '/en/installation-deployment/nas-deployment' },
          { text: 'Ubuntu Deployment', link: '/en/installation-deployment/ubuntu-deployment' },
          { text: 'Windows Deployment', link: '/en/installation-deployment/windows-deployment' }
        ]
      }
    ],
    '/en/user-guide/': [
      {
        text: 'User Guide',
        items: [
          { text: 'Dashboard', link: '/en/user-guide/dashboard' },
          { text: 'Households', link: '/en/user-guide/households' },
          { text: 'Conversations', link: '/en/user-guide/conversations' },
          { text: 'Memory', link: '/en/user-guide/memory' },
          { text: 'Settings', link: '/en/user-guide/settings' }
        ]
      }
    ],
    '/en/developer-docs/': [
      {
        text: 'Developer Docs',
        items: [
          { text: 'Environment Setup', link: '/en/developer-docs/environment-setup' },
          { text: 'Backend Development', link: '/en/developer-docs/backend-development' },
          { text: 'Plugin Development', link: '/en/developer-docs/plugin-development' }
        ]
      },
      {
        text: 'Plugin Topics',
        items: [
          { text: 'Plugin Specification', link: '/en/developer-docs/plugin-specification' },
          { text: 'Directory Structure', link: '/en/developer-docs/plugin-directory-structure' },
          { text: 'Field Specification', link: '/en/developer-docs/plugin-fields' },
          { text: 'Integration Flow', link: '/en/developer-docs/plugin-integration' },
          { text: 'Example Plugin', link: '/en/developer-docs/plugin-example' },
          { text: 'Plugin Submission', link: '/en/developer-docs/plugin-submission' }
        ]
      }
    ],
    '/en/community/': [
      {
        text: 'Community',
        items: [
          { text: 'Official Website', link: '/en/community/official-website' },
          { text: 'QQ Group', link: '/en/community/qq-group' },
          { text: 'WeChat Group', link: '/en/community/wechat-group' },
          { text: 'Discord', link: '/en/community/discord' }
        ]
      }
    ]
  },
  outlineLabel: 'On this page',
  prevLabel: 'Previous',
  nextLabel: 'Next',
  lastUpdatedText: 'Last updated',
  sidebarMenuLabel: 'Menu',
  returnToTopLabel: 'Back to top',
  darkModeSwitchLabel: 'Appearance',
  lightModeSwitchTitle: 'Switch to light theme',
  darkModeSwitchTitle: 'Switch to dark theme',
  langMenuLabel: 'Languages',
  footerMessage: 'Source files live in the repository; this site is only the presentation layer.'
})

// 先把路由和栏目稳定下来，后面补正文时不需要反复改导航。
export default defineConfig({
  base: normalizeBase(process.env.DOCS_BASE),
  lang: 'zh-CN',
  title: 'FamilyClaw 文档中心',
  description: 'FamilyClaw 项目快速开始、安装部署、使用指南、开发文档与沟通交流。',
  cleanUrls: true,
  lastUpdated: true,
  themeConfig: zhThemeConfig,
  locales: {
    root: {
      label: '简体中文',
      lang: 'zh-CN',
      link: '/'
    },
    en: {
      label: 'English',
      lang: 'en-US',
      link: '/en/',
      title: 'FamilyClaw Docs',
      description: 'FamilyClaw getting started, installation, user guide, developer docs, and community.',
      themeConfig: enThemeConfig
    }
  }
})
