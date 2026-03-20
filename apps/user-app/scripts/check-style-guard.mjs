import { readFileSync } from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const appRoot = path.resolve(import.meta.dirname, '..');

const protectedFiles = [
  'src/components/AppUi.tsx',
  'src/components/AppShellPage.tsx',
  'src/components/AuthShellPage.tsx',
  'src/components/MainShellPage.tsx',
  'src/components/FeaturePlaceholder.tsx',
  'src/runtime/guard.tsx',
  'src/pages/login/index.tsx',
  'src/pages/settings/SettingsPageShell.tsx',
  'src/pages/settings/index.tsx',
  'src/pages/settings/ai/index.tsx',
  'src/pages/settings/components/AiProviderConfigPanel.tsx',
  'src/pages/settings/components/AiProviderEditorDialog.tsx',
  'src/pages/settings/components/AiProviderSelectDialog.tsx',
  'src/pages/settings/components/aiProviderCatalog.ts',
  'src/pages/setup/SimpleAiProviderSetup.tsx',
  'src/pages/family/base.tsx',
  'src/pages/setup/base.tsx',
  'src/pages/home/page.h5.tsx',
  'src/pages/assistant/index.h5.tsx',
];

const rules = [
  {
    name: '禁止手写 rem',
    pattern: /(?<![\w-])\d*\.?\d+rem\b/g,
    message: '请改用 token、共享组件，或在样式文件里继续走设计稿 px + Taro 换算链路。',
  },
  {
    name: '禁止在 JSX/TS 里写固定 px',
    pattern: /['"`]\d*\.?\d+px['"`]/g,
    message: '请改用 token、共享组件，避免在 JSX/TS 里直接写死像素字符串。',
  },
  {
    name: '禁止把 AI 供应商 Logo 映射写回核心',
    pattern: /\bAI_PROVIDER_LOGO_MAP\b|\bgetAiProviderLogo\b/g,
    message: 'AI 供应商 Logo 必须来自插件 branding，不能回到核心映射表。',
  },
  {
    name: '禁止把供应商说明文案 key 映射写回核心',
    pattern: /settings\.ai\.provider\.adapter\./g,
    message: 'AI 供应商说明文案必须来自插件 branding 或插件资源，不能再按 adapter_code 写核心映射。',
  },
  {
    name: '禁止按 model_name 字段名硬编码模型发现',
    pattern: /field\.key\s*===\s*['"]model_name['"]/g,
    message: '模型发现必须走插件声明的 action 和 model_discovery，不能按字段名硬编码。',
  },
  {
    name: '禁止在 AI 设置页里从 plugin registry 重建 provider adapter',
    pattern: /\bbuildRegistryAdapter\b|capabilities\.ai_provider/g,
    message: 'AI 设置页只能消费 /provider-adapters 返回的插件契约，不能再从 PluginRegistryItem 重建 provider adapter。',
  },
];

function getLineNumber(source, index) {
  return source.slice(0, index).split('\n').length;
}

const violations = [];

for (const relativePath of protectedFiles) {
  const absolutePath = path.join(appRoot, relativePath);
  const source = readFileSync(absolutePath, 'utf8');

  for (const rule of rules) {
    const matches = [...source.matchAll(rule.pattern)];
    for (const match of matches) {
      violations.push({
        file: relativePath,
        line: getLineNumber(source, match.index ?? 0),
        name: rule.name,
        sample: match[0],
        message: rule.message,
      });
    }
  }
}

if (violations.length > 0) {
  console.error('[style-guard] 发现新的受保护代码回退写法:');
  for (const item of violations) {
    console.error(`- ${item.file}:${item.line} ${item.name} -> ${item.sample}`);
    console.error(`  ${item.message}`);
  }
  process.exit(1);
}

console.log(`[style-guard] 通过，共检查 ${protectedFiles.length} 个受保护文件。`);
