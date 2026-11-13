"""Three-field Chinese nameplate generator. Units: mm."""
from pathlib import Path
from datetime import datetime
from zipfile import ZipFile, ZIP_DEFLATED
import argparse, json, re, io
from functools import lru_cache
import xml.etree.ElementTree as ET
import numpy as np
import manifold3d as md
import trimesh
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from PIL import Image, ImageDraw

HERE=Path(__file__).resolve().parent
FONT_FILES={'微软雅黑粗体':'msyhbd.ttc','微软雅黑':'msyh.ttc','楷体':'simkai.ttf','华文楷体':'STKAITI.TTF','宋体':'simsun.ttc','黑体':'simhei.ttf','华文行楷（行书风格）':'STXINGKA.TTF','华文仿宋':'STFANGSO.TTF'}
DEFAULT_FONT='微软雅黑粗体'
def available_fonts():return [name for name,file in FONT_FILES.items() if (Path('C:/Windows/Fonts')/file).is_file()]
@lru_cache(maxsize=16)
def load_font(name):
    if name not in FONT_FILES:raise ValueError('未知字体：'+name)
    path=Path('C:/Windows/Fonts')/FONT_FILES[name]
    if not path.is_file():raise ValueError('本机未安装字体：'+name)
    return TTFont(str(path),fontNumber=0)
FONT=load_font(DEFAULT_FONT)
GLYPHS=FONT.getGlyphSet(); CMAP=FONT.getBestCmap()
def select_font(name):
    global FONT,GLYPHS,CMAP
    FONT=load_font(name);GLYPHS=FONT.getGlyphSet();CMAP=FONT.getBestCmap()
C='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
P='http://schemas.microsoft.com/3dmanufacturing/production/2015/06'
ET.register_namespace('',C);ET.register_namespace('p',P)

class Pen(BasePen):
    def __init__(self):super().__init__(GLYPHS);self.contours=[];self.points=[]
    def _moveTo(self,p):self.points=[np.array(p,float)]
    def _lineTo(self,p):self.points.append(np.array(p,float))
    def _qCurveToOne(self,b,c):
        a=self.points[-1];b=np.array(b);c=np.array(c)
        self.points.extend((1-t)**2*a+2*(1-t)*t*b+t*t*c for t in np.linspace(0,1,20)[1:])
    def _curveToOne(self,b,c,d):
        a=self.points[-1];b=np.array(b);c=np.array(c);d=np.array(d)
        self.points.extend((1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d for t in np.linspace(0,1,24)[1:])
    def _closePath(self):
        if len(self.points)>2:self.contours.append(np.array(self.points))
        self.points=[]
    def _endPath(self):self._closePath()

def resolve_fonts(font_name=DEFAULT_FONT):
    result=[font_name]*3 if isinstance(font_name,str) else list(font_name)
    if len(result)!=3:raise ValueError('请分别指定顶部、姓名和底部三种字体。')
    for f in result:load_font(f)
    return result

def validate(top,name,bottom,font_name=DEFAULT_FONT):
    fonts=resolve_fonts(font_name)
    top=''.join(top.split());name=''.join(name.split())
    columns=re.split(r'[\s/／|｜]+',bottom.strip()) if bottom.strip() else []
    if not 1<=len(top)<=5:raise ValueError('顶部小字请输入 1～5 个字。')
    if not 1<=len(name)<=5:raise ValueError('姓名请输入 1～5 个字，空格不计入字数。')
    if not 1<=len(columns)<=2 or any(not 1<=len(s)<=4 for s in columns):raise ValueError('底部请输入 1～2 列，每列 1～4 字；两列用空格分隔。')
    for text,f in zip([top,name,''.join(columns)],fonts):
        select_font(f)
        for ch in text:
            if ord(ch) not in CMAP:raise ValueError(f'{f} 不支持字符：{ch}')
            p=Pen();GLYPHS[CMAP[ord(ch)]].draw(p)
            if not p.contours:raise ValueError(f'字符没有可打印轮廓：{ch}')
    return top,name,columns

def glyph(ch,size,x,y):
    p=Pen();GLYPHS[CMAP[ord(ch)]].draw(p)
    pts=np.vstack(p.contours);lo=pts.min(axis=0);hi=pts.max(axis=0)
    scale=size/max(hi-lo)
    return md.CrossSection([(q-(lo+hi)/2)*scale+[x,y] for q in p.contours],md.FillRule.NonZero)

def make(top,name,bottom,font_name=DEFAULT_FONT):
    top,name,cols=validate(top,name,bottom,font_name)
    fonts=dict(zip(['top','name','bottom'],resolve_fonts(font_name)))
    letters=md.CrossSection();layout=[]
    def put(ch,s,x,y,region):
        nonlocal letters
        select_font(fonts[region])
        letters=letters+glyph(ch,s,x,y);layout.append(dict(char=ch,size_mm=s,x=x,y=y,region=region))
    # Top lettering is closer to the name; the upper band holds a strap slot.
    top_size,top_pitch=(2.9,3.35) if len(top)==5 else (3.5,4.1)
    for i,ch in enumerate(top):put(ch,top_size,10+(i-(len(top)-1)/2)*top_pitch,32.8,'top')
    name_size,pitch={1:(5,5.5),2:(5,7),3:(5,5.5),4:(3.7,4.1),5:(2.9,3.35)}[len(name)]
    for i,ch in enumerate(name):put(ch,name_size,10+(i-(len(name)-1)/2)*pitch,26.3,'name')
    for j,col in enumerate(cols):
        x=10 if len(cols)==1 else (5.7 if j==0 else 14.3)
        for i,ch in enumerate(col):put(ch,4.62,x,12+(len(col)-1)*2.5-i*5,'bottom')
    base=md.CrossSection.square([16,36],True).offset(2,circular_segments=96).translate([10,20]).extrude(2.4)
    slot=md.CrossSection.square([9,0.001],True).offset(1,circular_segments=64).translate([10,37.3])
    base=base-slot.extrude(4).translate([0,0,-.5])
    # Embedded lettering: replace the top 0.4 mm of the base, then rise 0.6 mm.
    base=base-letters.extrude(1.2).translate([0,0,2.0])
    text=letters.extrude(1.0).translate([0,0,2.0])
    meshes=[]
    for s in [base,text]:
        s=s.scale([1.25,1.25,1])
        r=s.to_mesh();m=trimesh.Trimesh(np.asarray(r.vert_properties)[:,:3],np.asarray(r.tri_verts),process=True)
        assert m.is_watertight and m.is_winding_consistent and m.volume>0
        meshes.append(m)
    for item in layout:
        for key in ['size_mm','x','y']:item[key]*=1.25
    return meshes,dict(top=top,name=name,bottom_columns_left_to_right=cols,layout=layout,dimensions_mm=[25,50,3.0],base_height_mm=2.4,text_start_z_mm=2.0,text_embedded_mm=.4,text_raised_mm=.6,fonts=fonts,slot_mm={'width':13.75,'height':2.50125,'center':[12.5,46.625],'through_base':True})

def palette(base_color,text_color):
    colors=[base_color,text_color]
    if any(not isinstance(c,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',c) for c in colors):
        raise ValueError('颜色格式应为 #RRGGBB。')
    return [c.upper() for c in colors]

def preview(meshes,base_color='#294F74',text_color='#F4B435'):
    base_color,text_color=palette(base_color,text_color)
    im=Image.new('RGB',(360,660),'#edf0f5');d=ImageDraw.Draw(im)
    for m,color,z in [(meshes[0],base_color,2.4),(meshes[1],text_color,3.0)]:
        for tri in m.triangles:
            if np.all(abs(tri[:,2]-z)<.0001):d.polygon([(30+float(v[0])*12,630-float(v[1])*12) for v in tri],fill=color)
    return im

def meta(parent,key,value):
    n=parent.find(f"metadata[@key='{key}']")
    if n is None:n=ET.SubElement(parent,'metadata',key=key)
    n.set('value',str(value))

def export(top,name,bottom,out=None,base_color='#294F74',text_color='#F4B435',font_name=DEFAULT_FONT):
    colors=palette(base_color,text_color)
    meshes,record=make(top,name,bottom,font_name)
    folder=Path(out) if out else HERE/'output'/(datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'_'+record['name'])
    folder.mkdir(parents=True,exist_ok=True)
    with ZipFile(HERE/'assets/template.3mf') as z:files={n:z.read(n) for n in z.namelist() if not n.endswith('.gcode')}
    root=ET.fromstring(files['3D/3dmodel.model']);native=ET.fromstring(files['3D/Objects/object_1.model']);cfg=ET.fromstring(files['Metadata/model_settings.config'])
    total=0
    for i,m in enumerate(meshes,1):
        center=m.bounds.mean(axis=0);obj=native.find(f'{{{C}}}resources/{{{C}}}object[@id="{i}"]')
        obj.remove(obj.find(f'{{{C}}}mesh'));me=ET.SubElement(obj,f'{{{C}}}mesh');vs=ET.SubElement(me,f'{{{C}}}vertices');fs=ET.SubElement(me,f'{{{C}}}triangles')
        for v in m.vertices-center:ET.SubElement(vs,f'{{{C}}}vertex',**{k:f'{float(a):.10g}' for k,a in zip('xyz',v)})
        for face in m.faces:ET.SubElement(fs,f'{{{C}}}triangle',**{f'v{j+1}':str(int(a)) for j,a in enumerate(face)})
        comp=root.find(f'.//{{{C}}}component[@objectid="{i}"]');comp.set('transform','1 0 0 0 1 0 0 0 1 '+' '.join(map(str,center)))
        part=cfg.find(f'object/part[@id="{i}"]');meta(part,'matrix',f'1 0 0 {center[0]} 0 1 0 {center[1]} 0 0 1 {center[2]} 0 0 0 1')
        for k,v in zip('xyz',center):meta(part,'source_offset_'+k,v)
        part.find('mesh_stat').set('face_count',str(len(m.faces)));total+=len(m.faces)
    cfg.find('object/metadata[@face_count]').set('face_count',str(total))
    meta(cfg.find('object'),'name','Custom three zone nameplate')
    settings=json.loads((HERE/'assets/p2s_02_pla_settings.json').read_text(encoding='utf-8'))
    for k,v in list(settings.items()):
        if isinstance(v,list) and len(v)==3:settings[k]=v[:2]
    settings.update(filament_colour=['#294F74','#F4B435'],default_filament_colour=['#294F74','#F4B435'],filament_self_index=['1','2'],filament_settings_id=['Generic PLA @BBL P2S 0.2 nozzle']*2,enable_support='0',layer_height='0.1',initial_layer_print_height='0.1',enable_prime_tower='1',flush_volumes_matrix=['0','140','140','0'],flush_volumes_vector=['140']*4,inherits_group=['']*4,different_settings_to_system=[settings['different_settings_to_system'][0],'','',''],wipe_tower_x=['140'],wipe_tower_y=['140'])
    for n,tree in [('3D/3dmodel.model',root),('3D/Objects/object_1.model',native),('Metadata/model_settings.config',cfg)]:files[n]=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
    files['Metadata/project_settings.config']=json.dumps(settings).encode()
    settings['filament_colour']=colors
    settings['default_filament_colour']=colors
    files['Metadata/project_settings.config']=json.dumps(settings).encode()
    pic=preview(meshes,*colors);pic.save(folder/'preview.png')
    for n in list(files):
        if n.endswith('.png'):
            b=io.BytesIO();pic.resize((256,256)).save(b,format='PNG');files[n]=b.getvalue()
    path=folder/'nameplate.3mf'
    with ZipFile(path,'w',ZIP_DEFLATED) as z:
        for n,data in files.items():z.writestr(n,data)
    with ZipFile(path) as z:assert z.testzip() is None
    record.update(project_version='2.2',printer='P2S 0.2mm',material='PLA',watertight=True,parts=2,base_color=colors[0],text_color=colors[1])
    (folder/'input.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    return path

if __name__=='__main__':
    p=argparse.ArgumentParser(description='三个参数：顶部、姓名、底部（双列用空格）')
    p.add_argument('top');p.add_argument('name');p.add_argument('bottom');p.add_argument('--out');p.add_argument('--font',default=DEFAULT_FONT,choices=available_fonts())
    p.add_argument('--top-font',choices=available_fonts());p.add_argument('--name-font',choices=available_fonts());p.add_argument('--bottom-font',choices=available_fonts())
    a=p.parse_args()
    try:print(export(a.top,a.name,a.bottom,a.out,font_name=[a.top_font or a.font,a.name_font or a.font,a.bottom_font or a.font]))
    except ValueError as e:p.error(str(e))
