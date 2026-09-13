#!/usr/bin/env node
// Optional Sharp adapter. Dependencies can live in the caller's project.
const fs = require('node:fs');
const path = require('node:path');
const {loadDependency, sameFile} = require('./node_support.cjs');

async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--help')) {
    console.log('Usage: node render_png.cjs input.svg output.png (--width-mm N | --width N) [--dpi 300] [--node-modules DIR]');
    return;
  }
  const [input, output, ...rest] = args;
  if (!input || !output || rest.length % 2) throw new Error('Use --help for the argument format.');
  const options = {};
  for (let i = 0; i < rest.length; i += 2) {
    const key = rest[i];
    if (!['--width-mm', '--width', '--dpi', '--node-modules'].includes(key) || key in options) throw new Error(`Unknown or repeated option: ${key}`);
    if (key === '--node-modules') {
      if (!rest[i + 1] || rest[i + 1].startsWith('--')) throw new Error('--node-modules requires a directory.');
      options[key] = rest[i + 1]; continue;
    }
    const value = Number(rest[i + 1]);
    if (!Number.isFinite(value) || value <= 0) throw new Error(`${key} must be a positive number.`);
    options[key] = value;
  }
  if (('--width-mm' in options) === ('--width' in options)) throw new Error('Specify exactly one of --width-mm or --width.');
  if (sameFile(input, output)) throw new Error('Output must differ from source, including file aliases.');
  const dpi = options['--dpi'] ?? 300;
  const width = Math.round(options['--width'] ?? options['--width-mm'] / 25.4 * dpi);
  if (width < 1) throw new Error('Computed pixel width must be at least 1.');
  const sharp = loadDependency('sharp', options['--node-modules']);
  const source = fs.readFileSync(input);
  const metadata = await sharp(source).metadata();
  if (metadata.format !== 'svg') throw new Error('Input must be an SVG document.');
  // Physical mm + DPI determine actual pixels, not only resolution metadata.
  const {data, info} = await sharp(source, {density: dpi}).resize({width})
    .withMetadata({density: dpi}).png().toBuffer({resolveWithObject: true});
  fs.mkdirSync(path.dirname(path.resolve(output)), {recursive: true});
  fs.writeFileSync(output, data);
  console.log(JSON.stringify({output: path.resolve(output), dpi, ...info}, null, 2));
}
main().catch(error => {console.error(error.message); process.exitCode = 1;});
