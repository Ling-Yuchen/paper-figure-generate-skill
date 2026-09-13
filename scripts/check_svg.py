#!/usr/bin/env python3
"""Conservative structural checks for generated, static SVG figures.

No third-party dependencies. This is not a sanitizer, layout checker, or full
CSS parser. Exit 0: supported checks pass; 1: errors; 2: manual review required.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

SVG = 'http://www.w3.org/2000/svg'
URL = re.compile(r'url\(\s*([\'"]?)(.*?)\1\s*\)', re.I | re.S)
GRAPHICS = {'path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'text', 'use'}
SUPPORTED = GRAPHICS | {'svg', 'g', 'defs', 'title', 'desc', 'metadata', 'tspan', 'symbol', 'marker', 'clipPath', 'mask', 'linearGradient', 'radialGradient', 'stop', 'pattern', 'image', 'style'}


def check(path):
    errors, review, refs = [], [], []
    report = {'file': str(path), 'errors': errors, 'manual_review': review,
              'limits': 'Static XML/reference checks only; geometry, glyphs, semantics and visual quality require rendered inspection.'}
    try:
        source = path.read_text(encoding='utf-8')
    except (OSError, UnicodeError) as exc:
        errors.append(str(exc))
        return report
    if re.search(r'<!\s*(DOCTYPE|ENTITY)\b', source, re.I):
        errors.append('DTD/entity declarations are unsupported; remove them before parsing.')
        return report
    if re.search(r'<\?xml-stylesheet\b', source, re.I):
        errors.append('XML stylesheet processing instruction is an external dependency risk.')
    try:
        root = ET.fromstring(source)
    except ET.ParseError as exc:
        errors.append(f'Invalid XML: {exc}')
        return report
    if root.tag != f'{{{SVG}}}svg':
        errors.append('Root must be svg in the SVG namespace.')
    try:
        box = [float(n) for n in re.split(r'[\s,]+', root.get('viewBox', '').strip())]
        if len(box) != 4 or not all(math.isfinite(n) for n in box) or min(box[2:]) <= 0:
            raise ValueError
    except ValueError:
        errors.append('viewBox must contain four finite numbers with positive width and height.')
    for dimension in ('width', 'height'):
        if not re.fullmatch(r'(?:\d+(?:\.\d*)?|\.\d+)(?:px|mm|cm|in|pt|pc)?', root.get(dimension, '')):
            review.append(f'Explicit absolute {dimension} is missing or unsupported; verify export size.')
        elif float(re.match(r'[\d.]+', root.get(dimension)).group()) <= 0:
            errors.append(f'{dimension} must be positive.')
    ids = Counter(e.get('id') for e in root.iter() if e.get('id'))
    errors.extend(f'Duplicate ID: {key}' for key, count in ids.items() if count > 1)

    def reference(value, context, allow_image=False):
        value = value.strip()
        if value.startswith('#') and len(value) > 1:
            refs.append((value[1:], context))
        elif allow_image and re.match(r'^data:image/(png|jpeg|webp);base64,', value, re.I):
            review.append(f'{context}: embedded raster image; verify necessity and content.')
        else:
            errors.append(f'{context}: external or unsupported reference: {value[:120]}')

    counts = Counter()
    for elem in root.iter():
        tag = elem.tag.rsplit('}', 1)[-1]
        context = elem.get('id') or tag
        if not elem.tag.startswith(f'{{{SVG}}}'):
            review.append(f'{context}: non-SVG namespace; content is not verified as an SVG graphic.')
            continue
        counts[tag] += 1
        if tag in {'script', 'foreignObject', 'animate', 'animateTransform', 'set'}:
            errors.append(f'{context}: active/foreign content is unsupported.')
        elif tag not in SUPPORTED:
            review.append(f'{context}: unsupported element {tag}; inspect renderer behavior.')
        css = []
        if tag == 'style':
            css.append(''.join(elem.itertext()))
            review.append(f'{context}: stylesheet requires CSS-aware review (selectors, imports, escapes).')
        for key, value in elem.attrib.items():
            attr = key.rsplit('}', 1)[-1]
            if attr.lower().startswith('on'):
                errors.append(f'{context}: event handler {attr} is unsupported.')
            if key == '{http://www.w3.org/XML/1998/namespace}base':
                errors.append(f'{context}: xml:base changes resource resolution.')
            if attr == 'href':
                reference(value, context, tag == 'image')
            if attr in {'aria-labelledby', 'aria-describedby'}:
                refs.extend((ref, context) for ref in value.split())
            if attr == 'style' or 'url' in value.lower() or (attr in {'fill', 'stroke', 'filter', 'clip-path', 'mask', 'marker-start', 'marker-mid', 'marker-end'} and ('\\' in value or '/*' in value)):
                css.append(value)
        for value in css:
            if re.search(r'@import|@font-face', value, re.I):
                errors.append(f'{context}: imported styles/fonts require removal or explicit embedding review.')
            if '\\' in value or '/*' in value:
                review.append(f'{context}: escaped/commented CSS requires a CSS parser.')
            matches = list(URL.finditer(value))
            if len(matches) != len(re.findall(r'url\s*\(', value, re.I)):
                review.append(f'{context}: unparsed CSS url expression.')
            for match in matches:
                reference(match.group(2), context)
    errors.extend(f'{context}: missing fragment target #{ref}' for ref, context in refs if ref not in ids)
    if not sum(counts[tag] for tag in GRAPHICS):
        errors.append('No editable vector/text elements found.')
    report.update({'id_count': len(ids), 'reference_count': len(refs), 'text_count': counts['text'],
                   'image_count': counts['image'], 'element_counts': dict(counts)})
    report['errors'] = list(dict.fromkeys(errors))
    report['manual_review'] = list(dict.fromkeys(review))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('svg', type=Path)
    parser.add_argument('--output', type=Path, help='Also save the JSON report.')
    args = parser.parse_args()
    if args.output and (args.svg.resolve() == args.output.resolve() or
                       (args.svg.exists() and args.output.exists() and args.svg.samefile(args.output))):
        parser.exit(1, 'Output report must differ from the input SVG, including file aliases.\n')
    result = check(args.svg)
    result['status'] = 'fail' if result['errors'] else 'needs-review' if result['manual_review'] else 'pass'
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + '\n', encoding='utf-8')
        except OSError as exc:
            parser.exit(1, f'Cannot write report: {exc}\n')
    print(rendered)
    raise SystemExit(1 if result['errors'] else 2 if result['manual_review'] else 0)
