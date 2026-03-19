import { promises as fs } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const EXPECTED_BUILTIN_THEME_PACK_COUNT = 8;
const repoRoot = path.resolve(__dirname, '..', '..', '..');
const builtinPluginRoot = path.join(
  repoRoot,
  'apps',
  'api-server',
  'app',
  'plugins',
  'builtin',
);
const themePluginRuntimeRoot = path.join(
  repoRoot,
  'apps',
  'user-app',
  'src',
  'runtime',
  'shared',
  'theme-plugin',
);
const bundlesRoot = path.join(themePluginRuntimeRoot, 'bundles');
const builtinIndexPath = path.join(
  themePluginRuntimeRoot,
  'builtinThemeBundleIndex.ts',
);

async function pathExists(targetPath) {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}

function normalizeString(value, fallback = '') {
  if (typeof value !== 'string') {
    return fallback;
  }
  const normalized = value.trim();
  return normalized || fallback;
}

function normalizeStringArray(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map(item => normalizeString(item))
    .filter(Boolean);
}

function parseJson(rawText) {
  return JSON.parse(rawText.replace(/^\uFEFF/, ''));
}

function isPlainObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function pushError(errors, message) {
  errors.push(`[theme-plugin] ${message}`);
}

function validateTokenMap(tokensObject, resourcePath, errors) {
  if (!isPlainObject(tokensObject)) {
    pushError(errors, `invalid token file format: ${resourcePath}`);
    return false;
  }

  const entries = Object.entries(tokensObject);
  if (!entries.length) {
    pushError(errors, `empty token file: ${resourcePath}`);
    return false;
  }

  for (const [key, value] of entries) {
    if (!normalizeString(key) || !normalizeString(value)) {
      pushError(errors, `token file must contain non-empty string pairs: ${resourcePath}`);
      return false;
    }
  }

  return true;
}

async function collectBuiltinThemePlugins() {
  const pluginEntries = [];
  const errors = [];

  if (!(await pathExists(builtinPluginRoot))) {
    throw new Error(`[theme-plugin] missing builtin plugin root: ${builtinPluginRoot}`);
  }

  const children = await fs.readdir(builtinPluginRoot, { withFileTypes: true });
  const directories = children
    .filter(item => item.isDirectory())
    .map(item => item.name)
    .sort((left, right) => left.localeCompare(right, 'en'));

  for (const directoryName of directories) {
    const pluginRoot = path.join(builtinPluginRoot, directoryName);
    const manifestPath = path.join(pluginRoot, 'manifest.json');
    if (!(await pathExists(manifestPath))) {
      continue;
    }

    const manifestRaw = await fs.readFile(manifestPath, 'utf8');
    const manifest = parseJson(manifestRaw);
    const manifestTypes = Array.isArray(manifest.types) ? manifest.types : [];
    if (!manifestTypes.includes('theme-pack')) {
      continue;
    }

    const pluginId = normalizeString(manifest.id);
    const capability = manifest.capabilities?.theme_pack ?? null;
    if (!pluginId || !isPlainObject(capability)) {
      pushError(errors, `invalid theme-pack manifest: ${manifestPath}`);
      continue;
    }

    const themeId = normalizeString(capability.theme_id);
    const displayName = normalizeString(capability.display_name, themeId);
    const description = normalizeString(capability.description);
    const resourceVersion = normalizeString(
      capability.resource_version,
      normalizeString(manifest.version, '1.0.0'),
    );
    const themeSchemaVersion = Number.isFinite(capability.theme_schema_version)
      ? capability.theme_schema_version
      : 1;
    const platformTargets = normalizeStringArray(capability.platform_targets);
    const preview = isPlainObject(capability.preview)
      ? capability.preview
      : {};
    const tokensResource = normalizeString(capability.tokens_resource ?? capability.entry_resource);

    if (!themeId) {
      pushError(errors, `missing theme_id: ${manifestPath}`);
      continue;
    }
    if (!tokensResource) {
      pushError(errors, `missing tokens_resource or entry_resource: ${manifestPath}`);
      continue;
    }

    const tokenResourcePath = path.join(pluginRoot, tokensResource);
    if (!(await pathExists(tokenResourcePath))) {
      pushError(errors, `missing theme resource file: ${tokenResourcePath}`);
      continue;
    }

    const tokenResourceRaw = await fs.readFile(tokenResourcePath, 'utf8');
    const tokenResourceJson = parseJson(tokenResourceRaw);
    const tokensObject = isPlainObject(tokenResourceJson?.tokens)
      ? tokenResourceJson.tokens
      : tokenResourceJson;

    if (!validateTokenMap(tokensObject, tokenResourcePath, errors)) {
      continue;
    }

    pluginEntries.push({
      pluginId,
      themeId,
      displayName,
      description,
      resourceVersion,
      themeSchemaVersion,
      platformTargets,
      preview,
      bundlePayload: {
        display_name: normalizeString(tokenResourceJson?.display_name, displayName),
        description: normalizeString(tokenResourceJson?.description, description),
        resource_version: normalizeString(tokenResourceJson?.resource_version, resourceVersion),
        theme_schema_version: Number.isFinite(tokenResourceJson?.theme_schema_version)
          ? tokenResourceJson.theme_schema_version
          : themeSchemaVersion,
        preview: isPlainObject(tokenResourceJson?.preview)
          ? tokenResourceJson.preview
          : preview,
        tokens: tokensObject,
      },
    });
  }

  if (pluginEntries.length !== EXPECTED_BUILTIN_THEME_PACK_COUNT) {
    pushError(
      errors,
      `builtin theme-pack count mismatch: expected ${EXPECTED_BUILTIN_THEME_PACK_COUNT}, got ${pluginEntries.length}`,
    );
  }

  const seenRegistryKeys = new Set();
  for (const entry of pluginEntries) {
    const registryKey = `${entry.pluginId}::${entry.themeId}`;
    if (seenRegistryKeys.has(registryKey)) {
      pushError(errors, `duplicate theme registry key: ${registryKey}`);
      continue;
    }
    seenRegistryKeys.add(registryKey);
  }

  if (errors.length > 0) {
    throw new Error(errors.join('\n'));
  }

  return pluginEntries;
}

function buildBundleModulePath(pluginId, themeId) {
  return path.join(bundlesRoot, pluginId, `${themeId}.ts`);
}

function renderBundleModule(bundlePayload) {
  return [
    `const bundle = ${JSON.stringify(bundlePayload, null, 2)} as const;`,
    '',
    'export default bundle;',
    '',
  ].join('\n');
}

function renderBuiltinIndex(entries) {
  const body = entries.map((entry) => {
    const modulePath = `./bundles/${entry.pluginId}/${entry.themeId}`;
    const platformTargets = JSON.stringify(entry.platformTargets, null, 2);
    return [
      '  {',
      `    plugin_id: ${JSON.stringify(entry.pluginId)},`,
      `    theme_id: ${JSON.stringify(entry.themeId)},`,
      `    display_name: ${JSON.stringify(entry.displayName)},`,
      `    description: ${JSON.stringify(entry.description)},`,
      "    source_type: 'builtin',",
      "    resource_source: 'builtin_bundle',",
      `    resource_version: ${JSON.stringify(entry.resourceVersion)},`,
      `    theme_schema_version: ${entry.themeSchemaVersion},`,
      `    platform_targets: ${platformTargets},`,
      `    preview: ${JSON.stringify(entry.preview ?? {}, null, 2)},`,
      `    bundle_module: ${JSON.stringify(modulePath)},`,
      `    load_bundle: () => import(${JSON.stringify(modulePath)}).then(module => module.default),`,
      '  },',
    ].join('\n');
  });

  return [
    "import type { BuiltinThemeBundleEntry } from './types';",
    '',
    '// Auto-generated by scripts/sync-builtin-theme-plugins.mjs. Do not edit manually.',
    'export const builtinThemeBundleIndex: BuiltinThemeBundleEntry[] = [',
    ...body,
    '];',
    '',
  ].join('\n');
}

async function writeBundlesAndIndex(entries) {
  await fs.rm(bundlesRoot, { recursive: true, force: true });
  await fs.mkdir(bundlesRoot, { recursive: true });

  for (const entry of entries) {
    const bundleFilePath = buildBundleModulePath(entry.pluginId, entry.themeId);
    await fs.mkdir(path.dirname(bundleFilePath), { recursive: true });
    await fs.writeFile(
      bundleFilePath,
      renderBundleModule(entry.bundlePayload),
      'utf8',
    );
  }

  await fs.writeFile(
    builtinIndexPath,
    renderBuiltinIndex(entries),
    'utf8',
  );
}

async function main() {
  const builtinThemePlugins = await collectBuiltinThemePlugins();
  await writeBundlesAndIndex(builtinThemePlugins);
  process.stdout.write(`synced ${builtinThemePlugins.length} builtin theme-pack bundles\n`);
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
