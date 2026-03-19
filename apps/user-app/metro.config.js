const path = require('node:path')
const { getDefaultConfig, mergeConfig } = require('@react-native/metro-config')
const { getMetroConfig } = require('@tarojs/rn-supporter')

const projectRoot = __dirname
const workspaceRoot = path.resolve(projectRoot, '../..')
const sharedPackagesRoot = path.join(workspaceRoot, 'packages')
const sharedPackagePaths = [
  path.join(sharedPackagesRoot, 'user-core'),
  path.join(sharedPackagesRoot, 'user-platform'),
  path.join(sharedPackagesRoot, 'user-ui'),
]

/**
 * Metro configuration
 * https://facebook.github.io/metro/docs/configuration
 *
 * @type {import('metro-config').MetroConfig}
 */
const config = {
  watchFolders: sharedPackagePaths,
  resolver: {
    unstable_enableSymlinks: true,
    nodeModulesPaths: [
      path.join(projectRoot, 'node_modules'),
      path.join(workspaceRoot, 'node_modules'),
    ],
    extraNodeModules: {
      '@familyclaw/user-core': sharedPackagePaths[0],
      '@familyclaw/user-platform': sharedPackagePaths[1],
      '@familyclaw/user-ui': sharedPackagePaths[2],
      'h5-shell': path.join(projectRoot, 'src/runtime/h5-shell'),
    },
  },
}

module.exports = (async function () {
  return mergeConfig(getDefaultConfig(projectRoot), await getMetroConfig(), config)
})()
