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
    name: '禁止 JSX/TS 里的固定 px 尺寸',
    pattern: /['"`]\d*\.?\d+px['"`]/g,
    message: '请改用 token、共享组件，避免在 JSX/TS 里直接写固定像素字符串。',
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
  console.error('[style-guard] 发现新的散装样式写法：');
  for (const item of violations) {
    console.error(`- ${item.file}:${item.line} ${item.name} -> ${item.sample}`);
    console.error(`  ${item.message}`);
  }
  process.exit(1);
}

console.log(`[style-guard] 通过，共检查 ${protectedFiles.length} 个受保护文件。`);
