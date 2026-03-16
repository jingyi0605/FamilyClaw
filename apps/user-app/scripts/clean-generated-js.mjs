import fs from 'node:fs';
import path from 'node:path';

const projectRoot = path.resolve(process.cwd());
const targetRoots = ['src', 'config'];
const sourceExtensions = ['.ts', '.tsx', '.mts', '.cts'];
const ignoredSuffixes = ['.test.js', '.spec.js'];

function shouldIgnore(filePath) {
  return ignoredSuffixes.some(suffix => filePath.endsWith(suffix));
}

function hasTypedSource(filePath) {
  const parsed = path.parse(filePath);
  return sourceExtensions.some(extension => fs.existsSync(path.join(parsed.dir, `${parsed.name}${extension}`)));
}

function walk(dirPath, foundFiles) {
  const entries = fs.readdirSync(dirPath, { withFileTypes: true });
  for (const entry of entries) {
    const entryPath = path.join(dirPath, entry.name);
    if (entry.isDirectory()) {
      walk(entryPath, foundFiles);
      continue;
    }

    if (!entry.isFile() || !entry.name.endsWith('.js')) {
      continue;
    }

    foundFiles.push(entryPath);
  }
}

const deletedFiles = [];

for (const targetRoot of targetRoots) {
  const absoluteRoot = path.join(projectRoot, targetRoot);
  if (!fs.existsSync(absoluteRoot)) {
    continue;
  }

  const candidateFiles = [];
  walk(absoluteRoot, candidateFiles);

  for (const candidateFile of candidateFiles) {
    if (shouldIgnore(candidateFile)) {
      continue;
    }

    if (!hasTypedSource(candidateFile)) {
      continue;
    }

    fs.rmSync(candidateFile);
    deletedFiles.push(path.relative(projectRoot, candidateFile));
  }
}

if (deletedFiles.length === 0) {
  console.log('[clean-generated-js] 没有发现需要清理的历史 JS 产物。');
} else {
  console.log('[clean-generated-js] 已清理以下历史 JS 产物：');
  for (const deletedFile of deletedFiles) {
    console.log(`- ${deletedFile}`);
  }
}
