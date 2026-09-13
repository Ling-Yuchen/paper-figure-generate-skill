#!/usr/bin/env python3
"""Center this fixture's node contents and 56-unit title regions from fresh measurements.

Standard library only. Requires export_browser.cjs's geometry report, not a
particular browser/font installation. This is a fixture adapter, not a general
SVG layout engine; nested panel bodies retain their planned grid/routing areas.
"""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

NS = '{http://www.w3.org/2000/svg}'
ET.register_namespace('', NS[1:-1])


def center(folder):
    source = folder / 'framework.svg'
    report = json.loads((folder / 'qa/framework-geometry.json').read_text(encoding='utf-8'))
    assert report['source_sha256'] == hashlib.sha256(source.read_bytes()).hexdigest(), 'Stale measurements'
    root = ET.parse(source).getroot()
    ids = {e.get('id'): e for e in root.iter() if e.get('id')}
    changes = []
    for m in report['modules']:
        group = ids[m['id']]
        boxes = [c['box'] for c in m['children']]
        assert boxes, m['id']
        left = min(b['x'] for b in boxes); right = max(b['x'] + b['w'] for b in boxes)
        top = min(b['y'] for b in boxes); bottom = max(b['y'] + b['h'] for b in boxes)
        b = m['box']
        dx = b['x'] + b['w'] / 2 - (left + right) / 2
        dy = b['y'] + b['h'] / 2 - (top + bottom) / 2
        content = group.find(NS + "g[@data-role='centered-content']")
        if content is None:
            content = ET.Element(NS + 'g', {'id': 'content-' + m['id'][7:], 'data-role': 'centered-content'})
            for child in list(group):
                if child.get('data-role') not in ('node-boundary', 'port-connection') and child.tag not in [NS + t for t in ('title', 'desc', 'defs', 'metadata')]:
                    group.remove(child); content.append(child)
            group.append(content)
        if abs(dx) + abs(dy) > .00001:
            content.set('transform', f'translate({dx:.6f} {dy:.6f}) ' + content.get('transform', ''))
        changes.append({'id': m['id'], 'dx': dx, 'dy': dy})
    for group in [g for g in root.iter(NS + 'g') if g.get('id', '').startswith('panel-')]:
        boundary = group.find(NS + 'rect'); title = group.find(NS + 'text')
        measured = next(t['box'] for t in report['textBoxes'] if t['parent'] == group.get('id') and t['text'] == title.text)
        dx = float(boundary.get('x')) + float(boundary.get('width')) / 2 - measured['x'] - measured['w'] / 2
        dy = float(boundary.get('y')) + 28 - measured['y'] - measured['h'] / 2
        title.set('transform', f'translate({dx:.6f} {dy:.6f}) ' + title.get('transform', ''))
        changes.append({'id': group.get('id') + '-title', 'dx': dx, 'dy': dy})
    ET.ElementTree(root).write(source, encoding='utf-8', xml_declaration=True)
    (folder / 'centering-adjustments.json').write_text(json.dumps({'measured_source_sha256': report['source_sha256'], 'adjustments': changes}, indent=2) + '\n', encoding='utf-8')
    print('Centered node contents and panel titles. Re-render before checking.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    center(parser.parse_args().folder)
