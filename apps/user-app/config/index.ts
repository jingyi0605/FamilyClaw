import path from 'node:path';
import { defineConfig } from '@tarojs/cli';
import h5Config from './platform/h5';
import rnConfig from './platform/rn';
import harmonyConfig from './platform/harmony';

function resolveTaroEnv() {
  const envFromProcess = process.env.TARO_ENV;
  if (envFromProcess) {
    return envFromProcess.replace('harmony-cpp', 'harmony_cpp');
  }

  const typeArg = process.argv.find(arg => arg.startsWith('--type'));
  if (!typeArg) {
    return 'h5';
  }

  if (typeArg.includes('=')) {
    return (typeArg.split('=')[1] ?? 'h5').replace('harmony-cpp', 'harmony_cpp');
  }

  const typeIndex = process.argv.indexOf(typeArg);
  return (process.argv[typeIndex + 1] ?? 'h5').replace('harmony-cpp', 'harmony_cpp');
}

export default defineConfig(async merge => {
  const taroEnv = resolveTaroEnv();
  const workspacePackageSrcRoots = [
    'user-platform',
    'user-core',
    'user-ui',
  ].map(packageName => path.resolve(process.cwd(), `../../packages/${packageName}/src`));

  const workspacePackageEntries = {
    '@familyclaw/user-core': path.resolve(process.cwd(), '../../packages/user-core/src/index.ts'),
    '@familyclaw/user-ui': path.resolve(process.cwd(), '../../packages/user-ui/src/index.ts'),
    '@familyclaw/user-platform/web': path.resolve(process.cwd(), '../../packages/user-platform/src/index.web.ts'),
    '@familyclaw/user-platform': path.resolve(
      process.cwd(),
      taroEnv === 'h5' ? '../../packages/user-platform/src/index.web.ts' : '../../packages/user-platform/src/index.ts',
    ),
  } as const;

  const baseConfig = {
    projectName: 'familyclaw-user-app',
    date: '2026-03-15',
    designWidth: 750,
    deviceRatio: {
      640: 2.34 / 2,
      750: 1,
      375: 2,
      828: 1.81 / 2,
    },
    sourceRoot: 'src',
    outputRoot: 'dist',
    framework: 'react',
    compiler: {
      type: 'webpack5',
      prebundle: {
        enable: false,
      },
    },
    plugins: taroEnv === 'harmony_cpp' ? ['@tarojs/plugin-platform-harmony-cpp'] : [],
    alias: {
      '@': path.resolve(process.cwd(), 'src'),
      ...workspacePackageEntries,
    },
    appPath: taroEnv === 'rn' ? 'src/app.rn.ts' : 'src/app.ts',
    modifyWebpackChain(chain: any) {
      if (taroEnv !== 'h5') {
        return;
      }

      chain.resolve.symlinks(false);
      chain.resolve.extensions.clear();
      ['.h5.tsx', '.h5.ts', '.h5.jsx', '.h5.js', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.vue'].forEach((extension: string) => {
        chain.resolve.extensions.add(extension);
      });

      Object.entries(workspacePackageEntries).forEach(([packageName, packageEntry]) => {
        chain.resolve.alias.set(`${packageName}$`, packageEntry);
      });

      const scriptRule = chain.module.rule('script');
      workspacePackageSrcRoots.forEach(packageSrcRoot => {
        scriptRule.include.add(packageSrcRoot);
      });
    },
  };

  if (taroEnv === 'h5') {
    return merge(baseConfig, { h5: h5Config });
  }

  if (taroEnv === 'rn') {
    return merge(baseConfig, { rn: rnConfig });
  }

  if (taroEnv === 'harmony_cpp') {
    return merge(baseConfig, { harmony: harmonyConfig });
  }

  return baseConfig;
});
