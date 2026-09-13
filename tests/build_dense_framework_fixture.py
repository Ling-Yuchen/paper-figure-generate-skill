#!/usr/bin/env python3
"""Hypothetical mechanism-level visual stress fixture. Python standard library.

Grids are schematic, not experimental data. This is not an automatic layout engine.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

NS='http://www.w3.org/2000/svg'
ET.register_namespace('',NS)


def build(out,icons):
    def add(p,tag,**a):return ET.SubElement(p,'{'+NS+'}'+tag,{k.replace('_','-'):str(v) for k,v in a.items()})
    def text(p,x,y,s,size=30,**a):
        e=add(p,'text',x=x,y=y,font_size=size,fill='#293841',**a);e.text=s;return e
    root=ET.Element('{'+NS+'}svg',{'viewBox':'0 0 1800 1090','width':'180mm','height':'109mm','font-family':'sans-serif'})
    add(root,'title').text='Hypothetical multi-scale cross-modal matching: mechanism-level fixture'
    add(root,'desc').text='Shared q and F feed three alignment scales. Forward and reverse refinement provide a prior. Prediction uses Z1 to Z3. Losses L1, L2, L3 and Lrec are training only. All grids are schematic.'
    add(root,'rect',width=1800,height=1090,fill='white')
    defs=add(root,'defs')
    marker=add(defs,'marker',id='arrow',viewBox='0 0 12 10',refX=12,refY=5,markerWidth=12,markerHeight=10,markerUnits='userSpaceOnUse',orient='auto')
    add(marker,'path',d='M 0 0 L 12 5 L 0 10 Z',fill='#425660')
    panels={};nodes={};edges=[];refs=[]
    def panel(name,x,y,w,h,title,fill,stroke,parent=None):
        g=add(panels[parent] if parent else root,'g',id='panel-'+name);panels[name]=g
        add(g,'rect',x=x,y=y,width=w,height=h,rx=8,fill=fill,stroke=stroke,stroke_width=2.2 if not parent else 1.6)
        text(g,x+18,y+38,title,size=34 if not parent else 30,font_weight=600)
        return g
    panel('features',24,24,1752,232,'(a) Shared representations','#FFF0E5','#B9987B')
    panel('alignment',24,280,1000,508,'(b) Multi-scale alignment','#F3EDF5','#97849F')
    panel('refinement',1048,280,728,508,'(c) Bidirectional refinement','#F4F5F1','#889780')
    panel('forward',1064,350,696,208,'Forward · init(F1:3)','#E7F3DF','#92AA7F','refinement')
    panel('reverse',1064,578,696,200,'Reverse','#E3EFF5','#87A7B6','refinement')
    panel('objectives',24,812,1752,216,'(d) Joint objectives','#E6F2F4','#709CA5')
    # Shared references use stable tensor/loss names, rather than ambiguous wire bundles.
    def node(name,parent,x,y,w,h,label,kind='op',caption=None,lines=None):
        g=add(panels[parent],'g',id='module-'+name)
        accent='#6F8590';fill='white'
        if kind=='loss':accent='#A56F73';fill='#F6DFDF'
        # For tensor/circle glyphs this invisible rect is a measurement envelope,
        # not a depicted module interface; ports below coincide with visible glyph edges.
        boundary=add(g,'rect',x=x,y=y,width=w,height=h,rx=6,fill=fill if kind in ('op','loss','input') else 'none',stroke=accent if kind in ('op','loss','input') else 'none',stroke_width=2,data_role='node-boundary')
        if kind=='tensor':
            d=12;fw=w-d;fh=h-d
            add(g,'polygon',points=f'{x},{y+d} {x+d},{y} {x+w},{y} {x+fw},{y+d}',fill='#DAE8EA',stroke=accent,stroke_width=1.2)
            add(g,'polygon',points=f'{x+fw},{y+d} {x+w},{y} {x+w},{y+fh} {x+fw},{y+h}',fill='#C3DADC',stroke=accent,stroke_width=1.2)
            add(g,'rect',x=x,y=y+d,width=fw,height=fh,fill='#F7FBFC',stroke=accent,stroke_width=1.2)
            for col in range(1,8):add(g,'path',d=f'M {x+fw*col/8} {y+d} V {y+h}',stroke='#A5B8BF',stroke_width=.8)
            for row in range(1,6):add(g,'path',d=f'M {x} {y+d+fh*row/6} H {x+fw}',stroke='#A5B8BF',stroke_width=.8)
            add(g,'rect',x=x+fw*5/8,y=y+d+fh*3/6,width=fw/8,height=fh/6,fill='#6DABC0')
        elif kind=='tokens':
            for i in range(4):
                xx=x+i*(w-16)/3
                add(g,'rect',x=xx,y=y+12,width=16,height=h-24,rx=2,fill=['#D5E5E9','#AFCAD3','#D7DDD0','#A3BBC3'][i],stroke=accent,stroke_width=1)
        elif kind=='dot':
            add(g,'circle',cx=x+w/2,cy=y+h/2,r=w/2,fill='white',stroke=accent,stroke_width=2)
            text(g,x+w/2,y+h/2+10,label,size=34,text_anchor='middle')
        elif kind=='input':
            glyph='contract' if name=='text-input' else 'vision'
            source=ET.parse(icons/(glyph+'.svg')).getroot()
            assert all(e.tag=='{'+NS+'}path' and not e.get('id') for e in source)
            holder=add(g,'g',transform=f'translate({x+w/2-20} {y+10}) scale({40/1024})')
            for path in source:
                p=deepcopy(path);p.attrib.clear();p.set('d',path.get('d'));p.set('fill','#7F8F96');holder.append(p)
            text(g,x+w/2,y+h-14,label,text_anchor='middle')
        else:
            words=lines or [label]
            step=44;start=y+h/2-(len(words)-1)*step/2+10
            for i,s in enumerate(words):text(g,x+w/2,start+i*step,s,text_anchor='middle',font_weight=600 if kind=='loss' else 400)
        if caption:
            c=text(panels[parent],x+w/2,y+h+32,caption,text_anchor='middle');c.set('data-owner',name)
        nodes[name]={'parent':parent,'box':[x,y,w,h],'kind':kind,'label':caption or label,
                     'ports':{'L':[x,y+h/2],'R':[x+w,y+h/2],'T':[x+w/2,y],'B':[x+w/2,y+h]}}
        return name
    def edge(name,a,b,points=None,ap='R',bp='L',kind='data'):
        points=points or [nodes[a]['ports'][ap],nodes[b]['ports'][bp]]
        edges.append({'id':name,'source':a,'target':b,'source_port':ap,'target_port':bp,'points':points,'kind':kind})
    # Feature pipelines: compact operators alternate with actual representations.
    left=[('text-input',48,104,'Text','input',None,None),('embed',180,120,'Embed','op',None,None),('text-enc',330,134,'','op',None,['Text','encoder']),('q-tokens',494,108,'','tokens','Q',None),('q-pool',632,106,'Pool','op',None,None),('q',768,92,'','tensor','q',None)]
    right=[('video-input',940,108,'Video','input',None,None),('video-enc',1078,128,'','op',None,['Video','encoder']),('time-enc',1236,138,'','op',None,['Time','encoder']),('clips',1404,96,'','tokens','Clips',None),('pyramid',1530,132,'','op',None,['Feature','pyramid']),('F',1680,72,'','tensor','F1:3',None)]
    for seq in [left,right]:
        for name,x,w,label,kind,caption,lines in seq:node(name,'features',x,96,w,96,label,kind,caption,lines)
        for a,b in zip(seq,seq[1:]):edge(a[0]+'-'+b[0],a[0],b[0])
    # The same local mechanism is repeated at three explicitly defined scales.
    for i,y in enumerate([360,500,640],1):
        if i>1:add(panels['alignment'],'path',d=f'M 42 {y-10} H 1006',stroke='#D5C9DB',stroke_width=1.2)
        names=[f'pair{i}',f'cos{i}',f'sim{i}',f'select{i}',f'Z{i}',f'L{i}']
        node(names[0],'alignment',48,y,124,80,'','tensor',f'q, F{i}')
        node(names[1],'alignment',206,y,60,80,'×','dot',f'Scale {i}')
        node(names[2],'alignment',300,y,110,80,'','tensor',f'S{i}')
        node(names[3],'alignment',450,y,128,80,'Select')
        node(names[4],'alignment',620,y,116,80,'','tokens',f'Z{i}')
        node(names[5],'alignment',808,y,166,80,f'L{i}','loss')
        for a,b in zip(names,names[1:]):edge(a+'-'+b,a,b,kind='train' if b==names[-1] else 'data')
        refs.extend([{'source':'q','target':names[0],'symbol':'q'},{'source':'F','target':names[0],'symbol':f'F{i}'}])
    # Paired local stages; reverse starts from the forward result.
    xs=[1080,1220,1354,1490,1628];ws=[110,104,104,104,108]
    for parent,y,labels in [('forward',424,['P0','Norm','Mix','Gate','P+']),('reverse',648,['P−','Gate','Mix','Norm','P+'])]:
        order=[]
        for j,(x,w,label) in enumerate(zip(xs,ws,labels)):
            name=f'{parent}{j}';kind='tensor' if j in (0,4) else 'op'
            node(name,parent,x,y,w,80,label if kind=='op' else '',kind,label if kind=='tensor' else None);order.append(name)
        if parent=='reverse':order.reverse()
        for a,b in zip(order,order[1:]):edge(a+'-'+b,a,b,ap='R' if parent=='forward' else 'L',bp='L' if parent=='forward' else 'R')
    edge('direction-feedback','forward4','reverse4',[[1736,464],[1748,464],[1748,688],[1736,688]],bp='R')
    refs.append({'source':'F','target':'forward0','symbol':'P0 initialized from F1:3'})
    # Prediction and loss aggregation use explicit names for shared values.
    node('fuse','objectives',48,884,140,96,'',lines=['Fuse','Z1:3'])
    node('score','objectives',224,884,108,96,'','tensor','Score')
    node('prior','objectives',376,884,140,96,'',lines=['Prior','gate'])
    node('topk','objectives',560,884,108,96,'Top-k')
    node('candidate','objectives',708,884,110,96,'','tokens','C')
    node('decode','objectives',858,884,164,96,'',lines=['Text','decoder'])
    node('Lrec','objectives',1066,884,138,96,'Lrec','loss')
    node('total','objectives',1320,884,416,96,'','loss',lines=['L = L1 + L2 + L3 + Lrec','Training only'])
    chain=['fuse','score','prior','topk','candidate','decode','Lrec','total']
    for a,b in zip(chain,chain[1:]):edge(a+'-'+b,a,b,kind='train' if b in ['decode','Lrec','total'] else 'data')
    edge('reverse-prior','reverse0','prior',[[1080,688],[1036,688],[1036,802],[446,802],[446,884]],ap='L',bp='T')
    for i in range(1,4):refs.extend([{'source':f'Z{i}','target':'fuse','symbol':f'Z{i}'},{'source':f'L{i}','target':'total','symbol':f'L{i}'}])
    layer=add(root,'g',id='relations',fill='none',stroke='#425660',stroke_width=2.8,stroke_linejoin='round')
    for e in edges:
        attrs={'id':'edge-'+e['id'],'d':'M '+' L '.join(f'{x} {y}' for x,y in e['points']),'marker_end':'url(#arrow)'}
        if e['kind']=='train':attrs['stroke_dasharray']='7 5'
        add(layer,'path',**attrs)
    legend=add(root,'g',id='legend')
    text(legend,28,1070,'q / F / Z: shared tensors',size=28)
    add(legend,'path',d='M 510 1060 H 558',stroke='#425660',stroke_width=2.8,marker_end='url(#arrow)')
    text(legend,575,1070,'Data',size=28)
    add(legend,'path',d='M 716 1060 H 764',stroke='#425660',stroke_width=2.8,stroke_dasharray='7 5',marker_end='url(#arrow)')
    text(legend,782,1070,'Training',size=28)
    text(legend,1030,1070,'×: similarity; grids are schematic',size=28)
    out.mkdir(parents=True,exist_ok=True)
    ET.ElementTree(root).write(out/'framework.svg',encoding='utf-8',xml_declaration=True)
    (out/'graph.json').write_text(json.dumps({'hypothetical':True,'nodes':nodes,'edges':edges,'symbol_references':refs},indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'nodes':len(nodes),'drawn_edges':len(edges),'symbol_references':len(refs)}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--icons',type=Path,default=Path(__file__).resolve().parents[1]/'icons');a=p.parse_args();build(a.output_dir,a.icons)
