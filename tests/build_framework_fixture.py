#!/usr/bin/env python3
"""Build a hypothetical framework for visual regression; Python standard library.

This is a bounded example, not an automatic layout engine or a paper template.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
INK = '#29323A'
COLORS = [('input',32,240,'Inputs','#E8EFF5','#607F98'),
          ('encode',296,432,'Representation','#E7EFE9','#68816F'),
          ('decide',752,360,'Decision','#EEEAF3','#847696'),
          ('execute',1136,432,'Execution','#F3EBDD','#9A8055')]


def build(out, icons, wireframe=False):
    def add(parent, tag, **attrs):
        return ET.SubElement(parent, '{'+NS+'}'+tag, {k.replace('_','-'):str(v) for k,v in attrs.items()})
    def label(parent, x, y, value, size=34, **attrs):
        el=add(parent,'text',x=x,y=y,font_size=size,fill=INK,**attrs);el.text=value;return el
    root=ET.Element('{'+NS+'}svg', {'viewBox':'0 0 1600 932','width':'180mm','height':'104.85mm','font-family':'sans-serif'})
    add(root,'title').text='Hypothetical GUI agent framework — visual validation fixture'
    add(root,'desc').text='Two parallel encoders, feature fusion, planning, tool execution, conditional retry and a shared state store.'
    defs=add(root,'defs')
    marker=add(defs,'marker',id='arrow',viewBox='0 0 12 10',refX=12,refY=5,markerWidth=12,markerHeight=10,markerUnits='userSpaceOnUse',orient='auto')
    add(marker,'path',d='M 0 0 L 12 5 L 0 10 Z',fill=INK)
    add(root,'rect',width=1600,height=932,fill='white')
    panels={}
    for name,x,w,title,bg,accent in COLORS:
        g=add(root,'g',id='panel-'+name);panels[name]=g
        add(g,'rect',x=x,y=80,width=w,height=580,rx=8,fill='white' if wireframe else bg,stroke=accent,stroke_width=2)
        label(g,x+w/2,128,title,font_weight=600,text_anchor='middle')
        add(g,'path',d=f'M {x+16} 150 H {x+w-16}',stroke=accent,stroke_width=2)
    nodes={}
    icon_map={}
    def icon(g,name,x,y,color,size=56):
        if wireframe:return
        # These fixture icons were inspected: path-only SVGs, no internal IDs or references.
        source=ET.parse(icons/(name+'.svg')).getroot()
        assert all(e.tag=='{'+NS+'}path' and not e.get('id') for e in source), 'Fixture expects path-only icons.'
        box=list(map(float,source.get('viewBox').split()));scale=size/max(box[2:])
        holder=add(g,'g',transform=f'translate({x} {y}) scale({scale}) translate({-box[0]} {-box[1]})')
        for child in source:
            item=deepcopy(child)
            for key in list(item.attrib):
                if key not in {'d','fill','stroke','fill-rule','clip-rule','stroke-width'}:del item.attrib[key]
            if item.get('fill')!='none':item.set('fill',color)
            if item.get('stroke') not in (None,'none'):item.set('stroke',color)
            holder.append(item)
        icon_map[name]='icons/'+name+'.svg'
    def node(name,panel,x,y,w,h,title,glyph=None,layout='stack'):
        color=next((row[5] for row in COLORS if row[0]==panel),'#707D86')
        g=add(panels[panel] if panel in panels else root,'g',id='module-'+name)
        add(g,'rect',x=x,y=y,width=w,height=h,rx=8,fill='white',stroke=color,stroke_width=2,data_role='node-boundary')
        if layout=='stack':
            if glyph:icon(g,glyph,x+w/2-28,y+16,color)
            label(g,x+w/2,y+h-28,title,text_anchor='middle')
        elif layout=='row':
            if glyph:icon(g,glyph,x+24,y+(h-56)/2,color)
            label(g,x+108,y+h/2+12,title)
        else:label(g,x+w/2,y+52,title,text_anchor='middle')
        nodes[name]={'parent':panel,'box':[x,y,w,h]}
        return g
    node('task','input',52,184,200,140,'Task','contract')
    node('screen','input',52,408,200,140,'Screen','vision')
    node('text','encode',320,184,190,140,'Text enc.','contract')
    node('ui','encode',320,408,190,140,'UI enc.','ground')
    fusion=node('fusion','encode',554,294,150,170,'Fusion',layout='custom')
    if not wireframe:
        for row in range(3):
            for col in range(3):
                add(fusion,'rect',x=581+col*32,y=369+row*21,width=24,height=12,rx=2,fill=['#ACC1B2','#68816F','#CEDBD1'][col])
    node('planner','decide',776,184,312,140,'Planner','plan','row')
    node('check','decide',776,408,312,140,'Check','vision','row')
    node('tools','execute',1160,184,384,140,'Tools','verify','row')
    node('observed','execute',1160,408,234,140,'New UI','vision')
    node('done','execute',1414,408,130,140,'Done','commit')
    memory=node('memory','shared',32,716,1536,132,'Shared state',layout='custom')
    # Replace the centered label with a compact left title, then actual memory contents.
    list(memory)[1].set('x','174');list(memory)[1].set('y','794')
    icon(memory,'history',376,752,'#707D86')
    label(memory,462,794,'History')
    icon(memory,'vision',970,752,'#707D86')
    label(memory,1056,794,'Current state')
    edges=add(root,'g',id='relations',fill='none',stroke=INK,stroke_width=3,stroke_linejoin='round')
    records=[]
    def edge(name,source,target,points,kind='data'):
        attrs={'id':'edge-'+name,'d':'M '+' L '.join(f'{x} {y}' for x,y in points),'marker_end':'url(#arrow)'}
        if kind!='data':attrs['stroke_dasharray']='8 6'
        add(edges,'path',**attrs)
        records.append({'id':name,'source':source,'target':target,'kind':kind,'points':points})
    edge('task-text','task','text',[(252,254),(320,254)])
    edge('screen-ui','screen','ui',[(252,478),(320,478)])
    edge('text-fusion','text','fusion',[(510,254),(532,254),(532,340),(554,340)])
    edge('ui-fusion','ui','fusion',[(510,478),(532,478),(532,417),(554,417)])
    edge('fusion-plan','fusion','planner',[(704,379),(740,379),(740,254),(776,254)])
    edge('plan-tools','planner','tools',[(1088,254),(1160,254)])
    edge('tools-observe','tools','observed',[(1352,324),(1352,408)])
    edge('observe-check','observed','check',[(1160,478),(1088,478)])
    edge('retry','check','planner',[(932,408),(932,324)],'condition')
    edge('pass','check','done',[(1008,548),(1008,612),(1479,612),(1479,548)],'condition')
    edge('read','memory','planner',[(730,716),(730,686),(762,686),(762,300),(776,300)],'state')
    edge('update','check','memory',[(888,548),(888,716)],'state')
    labels=add(root,'g',id='edge-labels')
    for x,y,text in [(954,379,'Retry'),(1216,588,'Pass'),(644,696,'Read'),(914,696,'Update')]:label(labels,x,y,text,size=30)
    legend=add(root,'g',id='legend')
    add(legend,'path',d='M 350 880 H 400',stroke=INK,stroke_width=3,marker_end='url(#arrow)')
    label(legend,416,890,'Data',size=30)
    add(legend,'path',d='M 690 880 H 740',stroke=INK,stroke_width=3,stroke_dasharray='8 6',marker_end='url(#arrow)')
    label(legend,756,890,'Condition / state access',size=30)
    out.mkdir(parents=True,exist_ok=True)
    stem='framework-wireframe' if wireframe else 'framework'
    ET.ElementTree(root).write(out/(stem+'.svg'),encoding='utf-8',xml_declaration=True)
    if not wireframe:
        (out/'graph.json').write_text(json.dumps({'hypothetical':True,'nodes':nodes,'edges':records,'icons':icon_map},indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--icons',type=Path,default=Path(__file__).resolve().parents[1]/'icons')
    p.add_argument('--wireframe',action='store_true')
    args=p.parse_args();build(args.output_dir,args.icons,args.wireframe)
