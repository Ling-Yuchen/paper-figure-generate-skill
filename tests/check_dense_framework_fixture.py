#!/usr/bin/env python3
"""Checks for the dense fixture, using its graph and fresh browser report.

Checks centerlines and text bounds, not arbitrary SVG or an aesthetic score.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def check(folder):
    ns='{http://www.w3.org/2000/svg}'
    source=folder/'framework.svg';root=ET.parse(source).getroot()
    graph=json.loads((folder/'graph.json').read_text(encoding='utf-8'))
    report=json.loads((folder/'qa/framework-geometry.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(source.read_bytes()).hexdigest()==report['source_sha256'],'Stale measurements'
    assert report['status']=='pass'
    ids={e.get('id'):e for e in root.iter() if e.get('id')}
    parents={c:p for p in root.iter() for c in p}
    nodes=graph['nodes'];segments=[]
    center_errors=[]
    for measured in report['modules']:
        bs=[c['box'] for c in measured['children']];b=measured['box']
        dx=(min(c['x'] for c in bs)+max(c['x']+c['w'] for c in bs))/2-b['x']-b['w']/2
        dy=(min(c['y'] for c in bs)+max(c['y']+c['h'] for c in bs))/2-b['y']-b['h']/2
        assert abs(dx)<=.1 and abs(dy)<=.1,(measured['id'],'content centering',dx,dy)
        center_errors.append(max(abs(dx),abs(dy)))
    title_count=0
    for panel in [e for e in ids.values() if e.get('id').startswith('panel-')]:
        title=panel.find(ns+'text');boundary=panel.find(ns+'rect')
        b=next(t['box'] for t in report['textBoxes'] if t['parent']==panel.get('id') and t['text']==title.text)
        dx=b['x']+b['w']/2-float(boundary.get('x'))-float(boundary.get('width'))/2
        dy=b['y']+b['h']/2-float(boundary.get('y'))-28
        assert abs(dx)<=.1 and abs(dy)<=.1,(panel.get('id'),'title centering',dx,dy)
        title_count+=1
    def hits(a,b,box,pad=0):
        x,y,w,h=box;l,t,r,bt=x-pad,y-pad,x+w+pad,y+h+pad
        if a[0]==b[0]:return l<a[0]<r and max(min(a[1],b[1]),t)<min(max(a[1],b[1]),bt)
        assert a[1]==b[1]
        return t<a[1]<bt and max(min(a[0],b[0]),l)<min(max(a[0],b[0]),r)
    def box(e):return [float(e.get(k)) for k in ['x','y','width','height']]
    def inside(b,outer,pad=0):
        x,y,w,h=b;l,t,ww,hh=outer
        return x>=l+pad-.01 and y>=t+pad-.01 and x+w<=l+ww-pad+.01 and y+h<=t+hh-pad+.01
    for name,node in nodes.items():
        group=ids['module-'+name]
        assert parents[group].get('id')=='panel-'+node['parent']
        assert inside(node['box'],box(ids['panel-'+node['parent']].find(ns+'rect')),10),(name,'parent bounds')
    for edge in graph['edges']:
        path=ids['edge-'+edge['id']].get('d')
        numbers=list(map(float,re.findall(r'-?\d+(?:\.\d+)?',path)))
        points=[list(p) for p in zip(numbers[::2],numbers[1::2])]
        assert points==edge['points']
        assert points[0]==nodes[edge['source']]['ports'][edge['source_port']]
        assert points[-1]==nodes[edge['target']]['ports'][edge['target_port']]
        for a,b in zip(points,points[1:]):
            for name,node in nodes.items():assert not hits(a,b,node['box']),(edge['id'],'node collision',name)
            for t in report['textBoxes']:
                assert not hits(a,b,[t['box'][k] for k in ['x','y','w','h']],3),(edge['id'],'text proximity',t['text'])
            segments.append((edge['id'],a,b))
    def crossing(a,b,c,d):
        av=a[0]==b[0];cv=c[0]==d[0]
        if av and cv:return a[0]==c[0] and max(min(a[1],b[1]),min(c[1],d[1]))<=min(max(a[1],b[1]),max(c[1],d[1]))
        if not av and not cv:return a[1]==c[1] and max(min(a[0],b[0]),min(c[0],d[0]))<=min(max(a[0],b[0]),max(c[0],d[0]))
        if not av:return crossing(c,d,a,b)
        return min(c[0],d[0])<=a[0]<=max(c[0],d[0]) and min(a[1],b[1])<=c[1]<=max(a[1],b[1])
    for (n,a,b),(other,c,d) in itertools.combinations(segments,2):
        if n!=other:assert not crossing(a,b,c,d),(n,other,'crossing')
    for t in report['textBoxes']:
        b=[t['box'][k] for k in ['x','y','w','h']]
        assert inside(b,[0,0,1800,1090]),('canvas text',t['text'])
        ancestor=ids.get(t['parent'])
        while ancestor is not None and not ancestor.get('id','').startswith(('module-','panel-')):
            ancestor=parents.get(ancestor)
        parent_id=ancestor.get('id','') if ancestor is not None else ''
        if parent_id.startswith('module-'):
            node=nodes[parent_id[7:]]
            # Tight scientific labels are checked separately from zero-padding glyph envelopes.
            assert inside(b,node['box'],2),(t['text'],'operator text padding')
        elif parent_id.startswith('panel-'):
            panel=ids[parent_id];assert inside(b,box(panel.find(ns+'rect'))),(t['text'],'panel caption')
            for rule in panel.findall(ns+'path'):
                if re.fullmatch(r'M [\d.]+ [\d.]+ H [\d.]+',rule.get('d','')):
                    xx,yy,end=map(float,re.findall(r'[\d.]+',rule.get('d')))
                    assert not hits([xx,yy],[end,yy],b,3),(t['text'],'divider collision')
    # Captions may be wider than a glyph; check actual text overlaps, not glyph boxes alone.
    for a,b in itertools.combinations(report['textBoxes'],2):
        p,q=a['box'],b['box']
        assert not (max(p['x'],q['x'])<min(p['x']+p['w'],q['x']+q['w'])-.01 and max(p['y'],q['y'])<min(p['y']+p['h'],q['y']+q['h'])-.01),('text overlap',a['text'],b['text'])
    for ref in graph['symbol_references']:
        assert ref['source'] in nodes and ref['target'] in nodes
        assert ref['symbol'].strip()
    return {'status':'pass','nodes':len(nodes),'edges':len(graph['edges']),'segments':len(segments),'text_boxes':len(report['textBoxes']),'symbol_references':len(graph['symbol_references']),
            'centered_node_groups':len(center_errors),'centered_title_regions':title_count,'maximum_node_center_error':max(center_errors),'centering_tolerance_root_units':.1,
            'scope':'Actual path/port agreement, node parents, centerline obstacles/crossings, text containment/overlap and dividers; reference targets. Symbol meaning, visible port silhouettes, grid intentional overlap, stroke/marker envelopes and density additionally require visual review.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path);a=p.parse_args();r=check(a.folder)
    (a.folder/'mechanism-check.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8');print(json.dumps(r))
