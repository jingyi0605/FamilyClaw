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

// 先把路由和栏目稳定下来，后面补正文时不需要反复改导航。
export default defineConfig({
  base: normalizeBase(process.env.DOCS_BASE),
  lang: 'zh-CN',
  title: 'FamilyClaw 文档中心',
  description: 'FamilyClaw 项目安装、使用、开发与运维文档',
  cleanUrls: true,
  lastUpdated: true,
  themeConfig: {
    nav: [
      { text: '开始这里', link: '/开始这里/文档总览' },
      { text: '安装部署', link: '/安装部署/环境要求' },
      { text: '使用指南', link: '/使用指南/用户快速上手' },
      { text: '开发指南', link: '/开发指南/开发环境准备' },
      { text: '运维排障', link: '/运维与排障/日志与诊断' },
      { text: '参考资料', link: '/参考资料/配置参考' },
      { text: '文档规范', link: '/文档规范/文档图片与排版约定' },
      { text: '存量资料', link: '/存量资料/现有文档入口' }
    ],
    sidebar: {
      '/开始这里/': [
        {
          text: '开始这里',
          items: [
            { text: '文档总览', link: '/开始这里/文档总览' },
            { text: '完整文档目录与写作计划', link: '/开始这里/完整文档目录与写作计划' },
            { text: '快速开始', link: '/开始这里/快速开始' }
          ]
        }
      ],
      '/安装部署/': [
        {
          text: '安装部署',
          items: [
            { text: '环境要求', link: '/安装部署/环境要求' },
            { text: '本地安装', link: '/安装部署/本地安装' },
            { text: '生产部署', link: '/安装部署/生产部署' },
            { text: '配置说明', link: '/安装部署/配置说明' }
          ]
        }
      ],
      '/使用指南/': [
        {
          text: '使用指南',
          items: [
            { text: '用户快速上手', link: '/使用指南/用户快速上手' },
            { text: '家庭与成员管理', link: '/使用指南/家庭与成员管理' },
            { text: 'AI 配置与插件使用', link: '/使用指南/AI配置与插件使用' },
            { text: '常见操作', link: '/使用指南/常见操作' }
          ]
        }
      ],
      '/开发指南/': [
        {
          text: '开发指南',
          items: [
            { text: '开发环境准备', link: '/开发指南/开发环境准备' },
            { text: '仓库结构说明', link: '/开发指南/仓库结构说明' },
            { text: '前端开发', link: '/开发指南/前端开发' },
            { text: '后端开发', link: '/开发指南/后端开发' },
            { text: '插件开发', link: '/开发指南/插件开发' },
            { text: '测试与提交流程', link: '/开发指南/测试与提交流程' },
            { text: '文档发布', link: '/开发指南/文档发布' }
          ]
        }
      ],
      '/运维与排障/': [
        {
          text: '运维与排障',
          items: [
            { text: '日志与诊断', link: '/运维与排障/日志与诊断' },
            { text: '常见故障排查', link: '/运维与排障/常见故障排查' },
            { text: '升级与回滚', link: '/运维与排障/升级与回滚' }
          ]
        }
      ],
      '/参考资料/': [
        {
          text: '参考资料',
          items: [
            { text: '配置参考', link: '/参考资料/配置参考' },
            { text: '接口参考', link: '/参考资料/接口参考' },
            { text: '术语表', link: '/参考资料/术语表' }
          ]
        }
      ],
      '/文档规范/': [
        {
          text: '文档规范',
          items: [
            { text: '文档图片与排版约定', link: '/文档规范/文档图片与排版约定' },
            { text: '文档编写模板说明', link: '/文档规范/文档编写模板说明' },
            { text: '文档治理规范', link: '/文档规范/文档治理规范' }
          ]
        }
      ],
      '/存量资料/': [
        {
          text: '存量资料',
          items: [
            { text: '现有文档入口', link: '/存量资料/现有文档入口' }
          ]
        }
      ]
    },
    outline: {
      level: [2, 3],
      label: '本页目录'
    },
    search: {
      provider: 'local'
    },
    docFooter: {
      prev: '上一页',
      next: '下一页'
    },
    lastUpdated: {
      text: '最后更新'
    },
    sidebarMenuLabel: '目录',
    returnToTopLabel: '回到顶部',
    darkModeSwitchLabel: '切换主题',
    lightModeSwitchTitle: '切换到浅色模式',
    darkModeSwitchTitle: '切换到深色模式',
    footer: {
      message: '文档源文件保存在仓库内，站点只是展示层。',
      copyright: 'Copyright © 2026 FamilyClaw'
    }
  }
})
