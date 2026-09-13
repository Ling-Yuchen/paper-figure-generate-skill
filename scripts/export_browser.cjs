#!/usr/bin/env node
// Requires playwright and an installed Chromium-family browser.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {loadDependency, sameFile} = require('./node_support.cjs');

function bounded(promise, stage, milliseconds = 30000) {
  let timer;
  return Promise.race([promise, new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`Timed out during ${stage}`)), milliseconds);
  })]).finally(() => clearTimeout(timer));
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--help')) {
    console.log('Usage: node export_browser.cjs input.svg --out-dir DIR --width-mm N [--browser EXECUTABLE | --channel NAME] [--padding 16] [--node-modules DIR]');
    console.log('Writes PDF, browser PNG and geometry JSON. Exit 0: measured checks pass; 1: error/violation; 2: coverage needs review.');
    return;
  }
  const [input, ...rest] = args;
  if (!input || rest.length % 2) throw new Error('Use --help for the argument format.');
  const options = {};
  for (let i = 0; i < rest.length; i += 2) {
    const key = rest[i];
    if (!['--out-dir', '--width-mm', '--browser', '--channel', '--padding', '--node-modules'].includes(key) || key in options) throw new Error(`Unknown or repeated option: ${key}`);
    if (!rest[i + 1] || rest[i + 1].startsWith('--')) throw new Error(`${key} requires a value.`);
    options[key] = rest[i + 1];
  }
  const widthMm = Number(options['--width-mm']);
  const padding = Number(options['--padding'] ?? 16);
  if (!options['--out-dir'] || !Number.isFinite(widthMm) || widthMm <= 0 || !Number.isFinite(padding) || padding < 0) throw new Error('--out-dir, positive --width-mm, and nonnegative --padding required.');
  if (options['--channel'] && options['--browser']) throw new Error('Choose --browser or --channel, not both.');
  const directory = path.resolve(options['--out-dir']);
  const stem = path.join(directory, path.basename(input, path.extname(input)));
  for (const suffix of ['.pdf', '-browser.png', '-geometry.json']) {
    if (sameFile(input, stem + suffix)) throw new Error('An output would overwrite the source, including a file alias.');
  }
  const svg = fs.readFileSync(input, 'utf8');
  if (/<!\s*(DOCTYPE|ENTITY)\b/i.test(svg)) throw new Error('SVG DTD/entity declarations are unsupported.');
  const sourceHash = crypto.createHash('sha256').update(svg).digest('hex');
  const {chromium} = loadDependency('playwright', options['--node-modules']);
  const executablePath = options['--browser'] || (!options['--channel'] && process.env.FIGURE_BROWSER);
  const browser = await chromium.launch({headless: true,
    ...(executablePath ? {executablePath} : {}), ...(options['--channel'] ? {channel: options['--channel']} : {})});
  try {
    // The SVG should already have passed check_svg.py. Rendering needs no network.
    const page = await browser.newPage({serviceWorkers: 'block'});
    page.setDefaultTimeout(30000);
    let blockedResources = 0;
    await page.route('**/*', route => {blockedResources++; return route.abort();});
    await bounded(page.setContent('<!doctype html><html><head><title>Paper figure</title><style>html,body{margin:0;padding:0}body>svg{display:block}</style></head><body></body></html>'), 'page loading');
    const canvas = await bounded(page.evaluate(source => {
      const parsed = new DOMParser().parseFromString(source, 'image/svg+xml');
      if (parsed.querySelector('parsererror')) throw new Error('Invalid SVG XML.');
      const root = parsed.documentElement;
      if (root.localName !== 'svg' || root.namespaceURI !== 'http://www.w3.org/2000/svg') throw new Error('Expected an SVG root in the SVG namespace.');
      for (const element of [root, ...root.querySelectorAll('*')]) {
        if (['script','foreignObject','animate','animateTransform','set'].includes(element.localName) || [...element.attributes].some(a => /^on/i.test(a.localName)))
          throw new Error('Active or foreign SVG content is unsupported.');
      }
      const v = root.viewBox.baseVal;
      if (!(v.width > 0 && v.height > 0) || ![v.x,v.y,v.width,v.height].every(Number.isFinite)) throw new Error('A finite positive viewBox is required.');
      const canvas = {x: v.x, y: v.y, width: v.width, height: v.height};
      root.style.width = `${v.width}px`;
      root.style.height = `${v.height}px`;
      document.body.replaceChildren(document.importNode(root, true));
      document.title = root.querySelector('title')?.textContent || 'Paper figure';
      return canvas;
    }, svg), 'SVG parsing');
    const heightMm = widthMm * canvas.height / canvas.width;
    await page.setViewportSize({width: Math.ceil(canvas.width), height: Math.ceil(canvas.height)});
    await bounded(page.addStyleTag({content: `@page{size:${widthMm}mm ${heightMm}mm;margin:0} @media print{body>svg{width:${widthMm}mm!important;height:${heightMm}mm!important}}`}), 'print styling');
    await bounded(page.evaluate(() => document.fonts.ready), 'font loading');
    const report = await bounded(page.evaluate(({canvas, padding}) => {
      const root = document.querySelector('body > svg');
      const frame = root.getBoundingClientRect();
      // All measurements are converted back to root viewBox coordinates.
      const bounds = e => {
        const r = e.getBoundingClientRect();
        return {x: canvas.x + (r.x - frame.x) * canvas.width / frame.width,
          y: canvas.y + (r.y - frame.y) * canvas.height / frame.height,
          w: r.width * canvas.width / frame.width, h: r.height * canvas.height / frame.height};
      };
      const violations = [], manualReview = [], modules = [], textBoxes = [];
      const all = [...root.querySelectorAll('g')].filter(g => g.id.startsWith('module-'));
      if (!all.length) manualReview.push('No module-* groups; module containment was not measured.');
      for (const group of all) {
        const boundary = [...group.children].find(e => e.getAttribute('data-role') === 'node-boundary');
        if (!boundary) {manualReview.push(`${group.id}: missing direct node-boundary child.`); continue;}
        const matrix = boundary.getCTM();
        if (boundary.localName !== 'rect' || !matrix || Math.abs(matrix.b) > .00001 || Math.abs(matrix.c) > .00001) {
          manualReview.push(`${group.id}: non-rectangular or rotated boundary; containment not measured.`); continue;
        }
        const box = bounds(boundary);
        if (!(box.w > 0 && box.h > 0)) {manualReview.push(`${group.id}: empty/hidden boundary; containment not measured.`); continue;}
        const children = [...group.children].filter(e => !['node-boundary', 'port-connection'].includes(e.getAttribute('data-role')) && !['title','desc','defs','metadata'].includes(e.localName))
          .map(e => ({id: e.id || e.textContent.trim() || e.localName, tag: e.localName, box: bounds(e)}));
        if (!children.length) manualReview.push(`${group.id}: no ordinary content to measure.`);
        for (const child of children) {
          const b = child.box;
          if (b.x < box.x + padding - .01 || b.y < box.y + padding - .01 || b.x + b.w > box.x + box.w - padding + .01 || b.y + b.h > box.y + box.h - padding + .01)
            violations.push({module: group.id, child: child.id, issue: `content clearance < ${padding} root SVG units`, box: b});
        }
        modules.push({id: group.id, box, children});
      }
      for (const t of root.querySelectorAll('text')) textBoxes.push({id: t.id || t.textContent, parent: t.parentElement.id, text: t.textContent, box: bounds(t)});
      return {violations, manual_review: manualReview, modules, textBoxes};
    }, {canvas, padding}), 'content measurement');
    if (blockedResources) report.manual_review.push(`${blockedResources} external resource request(s) blocked; check standalone rendering.`);
    const screenshot = await bounded(page.screenshot(), 'screenshot');
    const pdf = await bounded(page.pdf({preferCSSPageSize: true, printBackground: true, displayHeaderFooter: false}), 'PDF export');
    const result = {source: path.resolve(input), source_sha256: sourceHash, canvas,
      target_mm: {width: widthMm, height: heightMm}, padding_root_units: padding,
      browser_version: browser.version(), export_complete: true,
      status: report.violations.length ? 'fail' : report.manual_review.length ? 'needs-review' : 'pass', ...report,
      limits: 'Axis-aligned module bounding boxes and all text boxes only. Root SVG units; port-connection paths excluded. This does not check topology, glyph intersections, marker/stroke envelopes, aesthetic quality or rotated/non-rectangular containment.'};
    fs.mkdirSync(directory, {recursive: true});
    fs.writeFileSync(`${stem}-browser.png`, screenshot);
    fs.writeFileSync(`${stem}.pdf`, pdf);
    fs.writeFileSync(`${stem}-geometry.json`, JSON.stringify(result, null, 2) + '\n');
    console.log(JSON.stringify({pdf: `${stem}.pdf`, report: `${stem}-geometry.json`,
      measured_modules: report.modules.length, violations: report.violations, manual_review: report.manual_review}, null, 2));
    process.exitCode = report.violations.length ? 1 : report.manual_review.length ? 2 : 0;
  } finally {await browser.close();}
}
main().catch(error => {console.error(error.message); process.exitCode = 1;});
