// Portable helpers for optional Node adapters; no host-specific lookup paths.
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');

function loadDependency(name, directory) {
  if (directory) {
    const exact = path.join(path.resolve(directory), name);
    if (!fs.existsSync(exact)) throw new Error(`Missing ${name} in --node-modules directory. Supply a directory containing ${name}, or use another renderer.`);
    return require(exact);
  }
  const projectRequire = createRequire(path.join(process.cwd(), 'package.json'));
  for (const resolver of [projectRequire, require]) {
    let resolved;
    try {resolved = resolver.resolve(name);} catch (error) {
      if (error.code === 'MODULE_NOT_FOUND') continue;
      throw error;
    }
    return require(resolved); // Preserve native library/version errors after resolution.
  }
  throw new Error(`Missing optional dependency ${name}. Use a project that has it installed, --node-modules DIR, or another renderer. No packages were installed.`);
}

function sameFile(first, second) {
  if (path.resolve(first) === path.resolve(second)) return true;
  if (!fs.existsSync(first) || !fs.existsSync(second)) return false;
  if (fs.realpathSync(first) === fs.realpathSync(second)) return true;
  const a = fs.statSync(first), b = fs.statSync(second);
  return a.ino !== 0 && a.dev === b.dev && a.ino === b.ino;
}

module.exports = {loadDependency, sameFile};
