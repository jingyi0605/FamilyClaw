export type DocLocale = 'zh' | 'en'

type TranslationPair = {
  zh: string
  en: string
}

type SectionFallback = {
  zhPrefix: string
  enPrefix: string
  zh: string
  en: string
}

// 这份映射只负责“确实存在对应译文”的页面。
// 没有成对翻译的页面，后面会走分区兜底，至少保证不会跳 404。
const TRANSLATION_PAIRS: TranslationPair[] = [
  { zh: 'index.md', en: 'en/index.md' },
  { zh: '快速开始/文档总览.md', en: 'en/getting-started/docs-overview.md' },
  { zh: '快速开始/产品概览.md', en: 'en/getting-started/product-overview.md' },
  { zh: '快速开始/快速启动.md', en: 'en/getting-started/quick-start.md' },
  { zh: '快速开始/核心功能.md', en: 'en/getting-started/core-features.md' },
  { zh: '安装部署/概览.md', en: 'en/installation-deployment/overview.md' },
  { zh: '安装部署/Docker安装.md', en: 'en/installation-deployment/docker-installation.md' },
  { zh: '安装部署/源码安装.md', en: 'en/installation-deployment/source-installation.md' },
  { zh: '安装部署/NAS部署.md', en: 'en/installation-deployment/nas-deployment.md' },
  { zh: '安装部署/Ubuntu部署.md', en: 'en/installation-deployment/ubuntu-deployment.md' },
  { zh: '安装部署/Windows部署.md', en: 'en/installation-deployment/windows-deployment.md' },
  { zh: '使用指南/首次登录与初始化.md', en: 'en/user-guide/first-login-and-setup.md' },
  { zh: '使用指南/仪表盘.md', en: 'en/user-guide/dashboard.md' },
  { zh: '使用指南/家庭.md', en: 'en/user-guide/households.md' },
  { zh: '使用指南/对话.md', en: 'en/user-guide/conversations.md' },
  { zh: '使用指南/记忆.md', en: 'en/user-guide/memory.md' },
  { zh: '使用指南/设置.md', en: 'en/user-guide/settings.md' },
  { zh: '使用指南/插件.md', en: 'en/user-guide/plugins.md' },
  { zh: '开发文档/环境准备.md', en: 'en/developer-docs/environment-setup.md' },
  { zh: '开发文档/后端开发.md', en: 'en/developer-docs/backend-development.md' },
  { zh: '开发文档/插件开发.md', en: 'en/developer-docs/plugin-development.md' },
  { zh: '开发文档/插件规范.md', en: 'en/developer-docs/plugin-specification.md' },
  { zh: '开发文档/目录结构.md', en: 'en/developer-docs/plugin-directory-structure.md' },
  { zh: '开发文档/字段规范.md', en: 'en/developer-docs/plugin-fields.md' },
  { zh: '开发文档/对接方式.md', en: 'en/developer-docs/plugin-integration.md' },
  { zh: '开发文档/实例插件.md', en: 'en/developer-docs/plugin-example.md' },
  { zh: '开发文档/插件提交.md', en: 'en/developer-docs/plugin-submission.md' },
  { zh: '沟通交流/官方网站.md', en: 'en/community/official-website.md' },
  { zh: '沟通交流/QQ群.md', en: 'en/community/qq-group.md' },
  { zh: '沟通交流/微信群.md', en: 'en/community/wechat-group.md' },
  { zh: '沟通交流/Discord.md', en: 'en/community/discord.md' }
]

// 某些中文开发文档还没有英文版。
// 这类页面切语言时，回退到对应英文分区首页，而不是构造一个不存在的 URL。
const SECTION_FALLBACKS: SectionFallback[] = [
  {
    zhPrefix: '快速开始/',
    enPrefix: 'en/getting-started/',
    zh: '快速开始/文档总览.md',
    en: 'en/getting-started/docs-overview.md'
  },
  {
    zhPrefix: '安装部署/',
    enPrefix: 'en/installation-deployment/',
    zh: '安装部署/概览.md',
    en: 'en/installation-deployment/overview.md'
  },
  {
    zhPrefix: '使用指南/',
    enPrefix: 'en/user-guide/',
    zh: '使用指南/首次登录与初始化.md',
    en: 'en/user-guide/first-login-and-setup.md'
  },
  {
    zhPrefix: '开发文档/',
    enPrefix: 'en/developer-docs/',
    zh: '开发文档/环境准备.md',
    en: 'en/developer-docs/environment-setup.md'
  },
  {
    zhPrefix: '沟通交流/',
    enPrefix: 'en/community/',
    zh: '沟通交流/官方网站.md',
    en: 'en/community/official-website.md'
  }
]

const zhToEnMap = new Map(TRANSLATION_PAIRS.map((pair) => [pair.zh, pair.en]))
const enToZhMap = new Map(TRANSLATION_PAIRS.map((pair) => [pair.en, pair.zh]))

function normalizeRelativePath(relativePath: string) {
  return relativePath.replace(/\\/g, '/').replace(/^\/+/, '')
}

function findSectionFallback(relativePath: string, targetLocale: DocLocale) {
  return SECTION_FALLBACKS.find((section) =>
    targetLocale === 'en'
      ? relativePath.startsWith(section.zhPrefix)
      : relativePath.startsWith(section.enPrefix)
  )
}

export function getDocLocale(relativePath: string): DocLocale {
  return normalizeRelativePath(relativePath).startsWith('en/') ? 'en' : 'zh'
}

export function getLocaleLabel(locale: DocLocale) {
  return locale === 'en' ? 'English' : '简体中文'
}

export function relativePathToLink(relativePath: string) {
  const normalized = normalizeRelativePath(relativePath)

  if (normalized === 'index.md') {
    return '/'
  }

  const withoutIndex = normalized.replace(/(^|\/)index\.md$/, '$1')
  const withoutExt = withoutIndex.replace(/\.md$/, '')
  const link = withoutExt.startsWith('/') ? withoutExt : `/${withoutExt}`

  return link || '/'
}

export function getAlternateRelativePath(
  relativePath: string,
  targetLocale: DocLocale
) {
  const normalized = normalizeRelativePath(relativePath)
  const currentLocale = getDocLocale(normalized)

  if (currentLocale === targetLocale) {
    return normalized
  }

  const exactMatch =
    targetLocale === 'en' ? zhToEnMap.get(normalized) : enToZhMap.get(normalized)

  if (exactMatch) {
    return exactMatch
  }

  const sectionFallback = findSectionFallback(normalized, targetLocale)
  if (sectionFallback) {
    return targetLocale === 'en' ? sectionFallback.en : sectionFallback.zh
  }

  return targetLocale === 'en' ? 'en/index.md' : 'index.md'
}

export function getAlternateLink(relativePath: string, targetLocale: DocLocale) {
  return relativePathToLink(getAlternateRelativePath(relativePath, targetLocale))
}
