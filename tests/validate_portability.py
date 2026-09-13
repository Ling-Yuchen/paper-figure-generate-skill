#!/usr/bin/env python3
"""Portable regression suite. Python 3.9+; Node/browser tests are optional.

Run --help. No downloads, global changes, or dependency on project tmp/ artifacts.
"""
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from unittest import SkipTest

SOURCE = Path(__file__).resolve().parents[1]
NS = 'http://www.w3.org/2000/svg'


def fixture(origin=False, prefix=False, variant='normal'):
    vx, vy = (100, 50) if origin else (0, 0)
    x, y = vx + 40, vy + 50
    transform = f'translate({x} {y})' + (' rotate(15)' if variant == 'rotated' else '')
    module = 'plain' if variant == 'unmarked' else 'module-a'
    boundary = '<rect width="220" height="140" rx="8" data-role="node-boundary" fill="#E8EFF5"/>'
    if variant == 'circle':
        boundary = '<circle cx="110" cy="70" r="65" data-role="node-boundary" fill="#E8EFF5"/>'
    child_x = 210 if variant == 'overflow' else 30
    children = f'<text x="{child_x}" y="65" font-size="24" fill="#29323A">Input &amp; state</text><path d="M 30 90 H 160" stroke="#607F98"/>'
    if variant == 'empty': children = ''
    if variant == 'active': children += '<script>throw new Error("must not execute")</script>'
    if variant == 'external': children += '<image href="https://example.invalid/icon.png" x="30" y="100" width="20" height="20"/>'
    source = f'<svg xmlns="{NS}" viewBox="{vx} {vy} 600 300" width="180mm" height="90mm" font-family="sans-serif"><title>Portable SVG fixture</title><rect x="{vx}" y="{vy}" width="600" height="300" fill="white"/><g id="{module}" transform="{transform}">{boundary}{children}</g></svg>'
    if prefix:
        source = source.replace('xmlns=', 'xmlns:s=')
        source = re.sub(r'<(/?)(svg|title|rect|g|text|path|circle|image|script)(?=[\s>])', r'<\1s:\2', source)
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, help='New empty directory to retain artifacts; otherwise use a temporary directory.')
    parser.add_argument('--node', help='Node executable; otherwise search PATH.')
    parser.add_argument('--node-modules', type=Path, help='Optional directory containing real sharp/playwright packages.')
    parser.add_argument('--browser', help='Optional installed Chromium-family executable for browser integration tests.')
    args = parser.parse_args()
    temporary = None
    if args.work_dir:
        work = args.work_dir.resolve()
        if work.exists() and any(work.iterdir()): parser.error('--work-dir must be absent or empty.')
        work.mkdir(parents=True, exist_ok=True)
    else:
        temporary = tempfile.TemporaryDirectory(prefix='paper-figure-portability-')
        work = Path(temporary.name)
    root = work/'relocated skill 图'
    cwd = work/'independent project 空格'
    cwd.mkdir()
    root.mkdir()
    for name in ['SKILL.md', 'LICENSE', 'README.md']:
        if (SOURCE/name).exists(): shutil.copy2(SOURCE/name, root/name)
    for name in ['scripts', 'references', 'icons', 'tests']:
        shutil.copytree(SOURCE/name, root/name, ignore=shutil.ignore_patterns('__pycache__', '.DS_Store'))
    env = dict(os.environ)
    for key in list(env):
        if key == 'NODE_PATH' or key.startswith('FIGURE_'): env.pop(key)
    env['PYTHONIOENCODING'] = 'utf-8'
    node = args.node or shutil.which('node')
    if node:
        node = shutil.which(node) or str(Path(node).resolve())
    results = []

    def case(name, fn, available=True):
        if not available:
            results.append({'name': name, 'status': 'skip', 'reason': 'Optional executable/dependency not supplied.'}); return
        try:
            fn()
            results.append({'name': name, 'status': 'pass'})
        except SkipTest as exc:
            results.append({'name': name, 'status': 'skip', 'reason': str(exc)})
        except Exception as exc:
            results.append({'name': name, 'status': 'fail', 'detail': str(exc)})

    def run(command, expected=0, where=cwd, timeout=75):
        p = subprocess.run([str(v) for v in command], cwd=where, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
        assert p.returncode == expected, f'exit={p.returncode}, expected={expected}; stdout={p.stdout[-1800:]}; stderr={p.stderr[-1200:]}'
        return p

    def write(name, value):
        target = cwd/name; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(value, encoding='utf-8'); return target

    def link(source, alias, kind):
        try:
            if kind == 'symlink': alias.symlink_to(source)
            elif kind == 'hardlink': os.link(source, alias)
        except OSError as exc:
            if exc.errno in {errno.EPERM, errno.EACCES, errno.ENOTSUP, errno.ENOSYS} or getattr(exc, 'winerror', None) == 1314:
                raise SkipTest(f'{kind} unavailable on this filesystem or permission profile: {exc}') from exc
            raise

    valid = write('source input.svg', fixture())
    checker = root/'scripts/check_svg.py'

    def inspect_documents():
        for f in [root/'SKILL.md', *(root/'references').glob('*.md')]:
            source = f.read_text(encoding='utf-8')
            assert all(line == line.rstrip() for line in source.splitlines()), f.name
            for ref in re.findall(r'\]\(([^)]+)\)', source):
                relative, _, anchor = ref.partition('#')
                target = (f.parent/relative).resolve()
                assert target.is_relative_to(root), f'Outside-package link: {ref}'
                assert target.exists(), f'Missing: {ref}'
                if anchor:
                    headings = [re.sub(r'[^\w\- ]', '', line.lstrip('#').strip().lower()).replace(' ', '-') for line in target.read_text(encoding='utf-8').splitlines() if line.startswith('#')]
                    assert anchor in headings, ref
        for f in [root/'SKILL.md', *(root/'references').glob('*.md'), *(root/'scripts').glob('*')]:
            if f.is_file():
                assert not re.search(r'/Users/|/Applications/|/opt/homebrew|\.codex/|load_workspace_dependencies|view_image|tmp/(?:framework|skill)-trial', f.read_text(encoding='utf-8')), f'Host/history coupling: {f.name}'
    case('package relocation, local links, anchors and host-path scan', inspect_documents)
    case('Python-only structural check from unrelated Unicode cwd', lambda: run([sys.executable, checker, valid]))
    case('help without optional dependencies', lambda: run([sys.executable, checker, '--help']))
    case('nested report directory', lambda: run([sys.executable, checker, valid, '--output', cwd/'new/report/result.json']))

    body = '<rect id="r" width="10" height="10"/>'
    wrap = lambda s: f'<svg xmlns="{NS}" viewBox="0 0 100 100" width="100" height="100">{s}</svg>'
    structural = [
        ('duplicate IDs', body+body, 1), ('missing local target', body+'<use href="#no"/>', 1),
        ('local external icon', body+'<image href="icons/a.svg"/>', 1),
        ('remote fill', '<rect width="10" height="10" fill="url(https://example.invalid/g)"/>', 1),
        ('namespace URI is not a resource dependency', body, 0),
        ('empty namespace graphic', '<rect xmlns="" width="10" height="10"/>', 1),
        ('foreign namespace mixed with valid vector', body+'<x:path xmlns:x="urn:other"/>', 2),
        ('stylesheet needs review', body+'<style>rect{fill:red}</style>', 2),
        ('escaped paint requires review', '<rect width="10" height="10" fill="u\\72l(other.svg)"/>', 2),
        ('local gradient reference', '<defs><linearGradient id="g"/></defs><rect width="10" height="10" fill="url(#g)"/>', 0),
        ('event handler', '<rect width="10" height="10" onload="run()"/>', 1),
        ('script element', body+'<script/>', 1),
    ]
    for index, (name, body, code) in enumerate(structural):
        source = write(f'structural/{index}.svg', wrap(body))
        case('structure: '+name, lambda p=source, c=code: run([sys.executable, checker, p], c))
    for name, source in [('malformed XML', '<svg>'), ('DTD', '<!DOCTYPE svg>'+wrap('<rect/>'))]:
        source_path = write(f'structural/{name}.svg', source)
        case('structure: '+name, lambda p=source_path: run([sys.executable, checker, p], 1))
    case('missing input has structured error', lambda: run([sys.executable, checker, cwd/'absent.svg'], 1))

    def protect_output(alias_kind):
        source = write(f'protect/{alias_kind}.svg', fixture())
        alias = source if alias_kind == 'same' else source.with_suffix('.json')
        link(source, alias, alias_kind)
        before = source.read_bytes()
        run([sys.executable, checker, source, '--output', alias], 1)
        assert source.read_bytes() == before
    for kind in ['same', 'symlink', 'hardlink']:
        case('checker preserves input via '+kind, lambda k=kind: protect_output(k))

    def doc_example():
        code = re.findall(r'```python\n(.*?)```', (root/'references/toolchain.md').read_text(encoding='utf-8'), re.S)[0]
        write('build_from_docs.py', code)
        run([sys.executable, cwd/'build_from_docs.py'])
        run([sys.executable, checker, cwd/'figure.svg'])
    case('executable documentation example without Node or desktop tools', doc_example)
    def packaged_icons():
        for f in (root/'icons').glob('*.svg'):
            ET.parse(f)
            run([sys.executable,checker,f])
    case('all packaged icons parse and pass standalone structural checks', packaged_icons)

    def complex_fixture():
        out=cwd/'new framework'
        run([sys.executable,root/'tests/build_framework_fixture.py','--output-dir',out])
        run([sys.executable,checker,out/'framework.svg'])
        graph=json.loads((out/'graph.json').read_text(encoding='utf-8'))
        assert len(graph['nodes'])==11 and len(graph['edges'])==12
    case('complex framework generation with relocated embedded icons',complex_fixture)

    def dense_fixture():
        out=cwd/'dense mechanism'
        run([sys.executable,root/'tests/build_dense_framework_fixture.py','--output-dir',out])
        run([sys.executable,checker,out/'framework.svg'])
        graph=json.loads((out/'graph.json').read_text(encoding='utf-8'))
        assert len(graph['nodes'])==48 and len(graph['edges'])==42
        assert all(r['source'] in graph['nodes'] and r['target'] in graph['nodes'] for r in graph['symbol_references'])
    case('dense mechanism generation and shared-reference targets after relocation',dense_fixture)

    if node:
        render = root/'scripts/render_png.cjs'; browser_script = root/'scripts/export_browser.cjs'
        for f in (root/'scripts').glob('*.cjs'):
            case('Node syntax: '+f.name, lambda f=f: run([node, '--check', f]))
        for f in [render, browser_script]:
            case('Node help without libraries: '+f.name, lambda f=f: run([node, f, '--help']))
        for index, flags in enumerate([[], ['--width', '0'], ['--width','100','--width-mm','180'], ['--width','100','--dpi','NaN'], ['--width','50','--unknown','x']]):
            case('PNG invalid arguments '+str(index), lambda flags=flags: run([node, render, valid, cwd/'bad.png', *flags], 1))
        empty = cwd/'empty dependencies'; empty.mkdir()
        for f, tail, dependency in [(render, [valid,cwd/'none.png','--width','100'], 'sharp'), (browser_script, [valid,'--out-dir',cwd/'none','--width-mm','90'], 'playwright')]:
            def absent(f=f, tail=tail, dependency=dependency):
                p=run([node,f,*tail,'--node-modules',empty],1);assert 'Missing '+dependency in p.stderr
            case('explicit missing dependency: '+dependency, absent)
        def dependency_resolution():
            project = cwd/'different project'; package = project/'node_modules/sharp'; package.mkdir(parents=True)
            (package/'index.js').write_text('module.exports={marker:"project-local"};', encoding='utf-8')
            support = root/'scripts/node_support.cjs'
            expression = 'const s=require(process.argv[1]); console.log(s.loadDependency("sharp").marker)'
            p=run([node,'-e',expression,support],where=project);assert p.stdout.strip()=='project-local'
            (package/'index.js').write_text('throw new Error("broken project dependency");', encoding='utf-8')
            p=run([node,'-e',expression,support],1,where=project);assert 'broken project dependency' in p.stderr
        case('project-local module lookup and dependency error preservation',dependency_resolution)
        for kind in ['same','symlink','hardlink']:
            def protect_png(kind=kind):
                source=write('png-protect/'+kind+'.svg',fixture());out=source if kind=='same' else source.with_suffix('.png')
                link(source,out,kind)
                run([node,render,source,out,'--width','100'],1);assert source.read_text(encoding='utf-8')==fixture()
            case('PNG preserves source via '+kind,protect_png)
        def protect_browser():
            source=write('source.pdf',fixture())
            run([node,browser_script,source,'--out-dir',cwd,'--width-mm','90'],1)
            assert source.read_text(encoding='utf-8')==fixture()
        case('browser output cannot overwrite input',protect_browser)
        real_modules = args.node_modules.resolve() if args.node_modules else None
        sharp_available = real_modules and (real_modules/'sharp').is_dir()
        for width in [90,180]:
            def sharp_test(width=width):
                target=cwd/f'png-{width}.png'
                run([node,render,valid,target,'--width-mm',width,'--dpi','300','--node-modules',real_modules])
                data=target.read_bytes();assert data[:8]==b'\x89PNG\r\n\x1a\n'
                actual=int.from_bytes(data[16:20],'big');assert actual==round(width/25.4*300)
            case('real Sharp relocated rendering '+str(width)+'mm',sharp_test,bool(sharp_available))
        browser_available = bool(args.browser and real_modules and (real_modules/'playwright').is_dir())
        for name, variant, origin, prefix, expected in [
            ('plain','normal',False,False,0),('nonzero origin','normal',True,False,0),
            ('XML namespace prefix','normal',False,True,0),('overflow','overflow',False,False,1),
            ('no marker convention','unmarked',False,False,2),('rotated module','rotated',False,False,2),
            ('nonrectangular module','circle',False,False,2),('empty module','empty',False,False,2),
            ('active SVG rejected','active',False,False,1),('external resource flagged','external',False,False,2),
        ]:
            def browser_test(name=name,variant=variant,origin=origin,prefix=prefix,expected=expected):
                source=write('browser fixtures/'+name+'.svg',fixture(origin,prefix,variant))
                out=cwd/'browser outputs'/name
                run([node,browser_script,source,'--out-dir',out,'--width-mm','90','--padding','10',
                     '--node-modules',real_modules,'--browser',args.browser],expected)
                if variant=='active':assert not out.exists();return
                report=json.loads((out/(name+'-geometry.json')).read_text(encoding='utf-8'))
                assert report['source_sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
                assert report['export_complete'] and report['target_mm']=={'width':90,'height':45}
                assert report['status']=={0:'pass',1:'fail',2:'needs-review'}[expected]
                if expected==0:
                    box=report['modules'][0]['box'];assert abs(box['x']-(140 if origin else 40))<.1
                assert (out/(name+'.pdf')).read_bytes().startswith(b'%PDF')
            case('real browser: '+name,browser_test,browser_available)
        def dense_rendered():
            out=cwd/'dense mechanism'
            source=out/'framework.svg'
            export=[node,browser_script,source,'--out-dir',out/'qa','--width-mm','180','--padding','0',
                    '--node-modules',real_modules,'--browser',args.browser]
            run(export)
            run([sys.executable,root/'tests/center_dense_framework_fixture.py',out])
            # The old geometry must be rejected after any source mutation.
            stale=run([sys.executable,root/'tests/check_dense_framework_fixture.py',out],1)
            assert 'Stale measurements' in stale.stderr
            run(export)
            run([sys.executable,root/'tests/check_dense_framework_fixture.py',out])
            report=json.loads((out/'mechanism-check.json').read_text(encoding='utf-8'))
            assert report['centered_node_groups']==48 and report['centered_title_regions']==6
            assert report['maximum_node_center_error']<=.1
        case('dense real render, measured centering, stale report rejection and graph QA',dense_rendered,browser_available)
    else:
        results.append({'name':'Node and browser tests','status':'skip','reason':'Node not available.'})
    summary={'host_platform':sys.platform,'python_version':sys.version.split()[0],
             'work_dir':str(work),'results':results,
             'totals':{s:sum(r['status']==s for r in results) for s in ['pass','fail','skip']},
             'scope':'Relocated package, unrelated Unicode cwd, NODE_PATH/FIGURE_* removed. Actual OS recorded above; other operating systems are not thereby certified.'}
    (work/'validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    for r in results:
        if r['status']!='pass':print(json.dumps(r,ensure_ascii=False))
    print(json.dumps(summary['totals']))
    print('Report:',work/'validation.json')
    failed=summary['totals']['fail']
    if temporary:temporary.cleanup()
    raise SystemExit(bool(failed))


if __name__=='__main__': main()
