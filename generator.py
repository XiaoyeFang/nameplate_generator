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
FONT_FILES['霞鹜文楷TC（繁体手写）']=str(HERE/'assets/fonts/LXGWWenKaiTC-Medium.ttf')
FONT_FILES['正风毛笔（繁体行书·粗体）']=str(HERE/'assets/fonts/MasaFont-Bold.ttf')
FONT_FILES['华康行楷体W5-B5（繁体行楷）']=str(HERE/'assets/fonts/DFPXingKaiW5-B5.ttf')
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
    if not 1<=len(columns)<=2 or any(not 1<=len(s)<=6 for s in columns):raise ValueError('底部请输入 1～2 列，每列 1～6 字；两列用空格分隔。')
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

def sizing(options=None):
    o=dict(width=25.,height=50.,sizes=[0.,0.,0.]);o.update(options or {})
    try:
        o['width']=float(o['width']);o['height']=float(o['height']);o['sizes']=[float(v) for v in o['sizes']]
        assert 15<=o['width']<=50 and 30<=o['height']<=100 and len(o['sizes'])==3
        assert all(np.isfinite(v) and 0<=v<=20 for v in o['sizes'])
    except (ValueError,TypeError,AssertionError):raise ValueError('宽度15～50 mm，高度30～100 mm；字号0～20 mm（0为自动）。')
    return o

def make(top,name,bottom,font_name=DEFAULT_FONT,options=None):
    top,name,cols=validate(top,name,bottom,font_name)
    fonts=dict(zip(['top','name','bottom'],resolve_fonts(font_name)))
    o=sizing(options);w,h=o['width'],o['height'];factor=min(w/25,h/50)
    defaults=[(2.9 if len(top)==5 else 3.5)*1.25,{1:5,2:5,3:5,4:3.7,5:2.9}[len(name)]*1.25,5.775]
    sizes=[v or d*factor for v,d in zip(o['sizes'],defaults)]
    if not o['sizes'][2]:
        count=max(map(len,cols));gap=.475*factor
        room=2*min(h*.3-1,h*.3575-sizes[1]/2-.8)
        sizes[2]=min(sizes[2],(room-(count-1)*gap)/count)
        if sizes[2]<=0:raise ValueError('底部没有足够空间，请增高底板或减小姓名字号。')
    letters=md.CrossSection();layout=[];boxes=[]
    def put(ch,size,x,y,region):
        nonlocal letters
        box=(x-size/2,y-size/2,x+size/2,y+size/2)
        if box[0]<1 or box[2]>w-1 or box[1]<1 or box[3]>h*.89:
            raise ValueError('文字超出安全区域，请减小字号或增大名牌。')
        if any(box[0]<b[2] and box[2]>b[0] and box[1]<b[3] and box[3]>b[1] for b in boxes):
            raise ValueError('文字区域重叠，请减小字号或增大名牌。')
        boxes.append(box);select_font(fonts[region]);letters=letters+glyph(ch,size,x,y)
        layout.append(dict(char=ch,size_mm=size,x=x,y=y,region=region))
    for text,size,cy,region,gap in [(top,sizes[0],h*.82,'top',.6),(name,sizes[1],h*.6575,'name',2.5 if len(name)==2 else .6)]:
        pitch=size+gap*factor
        for i,ch in enumerate(text):put(ch,size,w/2+(i-(len(text)-1)/2)*pitch,cy,region)
    for j,col in enumerate(cols):
        x=w/2 if len(cols)==1 else w*(.285 if j==0 else .715)
        pitch=sizes[2]+.475*factor
        for i,ch in enumerate(col):put(ch,sizes[2],x,h*.3+((len(col)-1)/2-i)*pitch,'bottom')
    base2=md.CrossSection.square([16,36],True).offset(2,circular_segments=96).translate([10,20]).scale([w/20,h/40])
    slot=md.CrossSection.square([9,.001],True).offset(1,circular_segments=64).translate([10,37.3]).scale([w/20,h/40])
    base=(base2-slot).extrude(2.4)-letters.extrude(1.2).translate([0,0,2.0])
    text=letters.extrude(1.).translate([0,0,2.0]);meshes=[]
    for solid in [base,text]:
        r=solid.to_mesh();m=trimesh.Trimesh(np.asarray(r.vert_properties)[:,:3],np.asarray(r.tri_verts),process=True)
        assert m.is_watertight and m.is_winding_consistent and m.volume>0
        meshes.append(m)
    return meshes,dict(top=top,name=name,bottom_columns_left_to_right=cols,layout=layout,dimensions_mm=[w,h,3.0],base_height_mm=2.4,text_start_z_mm=2.0,text_embedded_mm=.4,text_raised_mm=.6,fonts=fonts,options=o,font_sizes_mm=sizes,slot_mm={'width':w*.55,'height':h*2.001/40,'center':[w/2,h*.9325],'through_base':True})


def palette(base_color,text_color):
    colors=[base_color,text_color]
    if any(not isinstance(c,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',c) for c in colors):
        raise ValueError('颜色格式应为 #RRGGBB。')
    return [c.upper() for c in colors]

def preview(meshes,base_color='#294F74',text_color='#F4B435'):
    base_color,text_color=palette(base_color,text_color)
    im=Image.new('RGB',(360,660),'#edf0f5');d=ImageDraw.Draw(im)
    w,h=meshes[0].bounds[1,:2];scale=min(300/w,600/h);ox=(360-w*scale)/2;oy=(660+h*scale)/2
    for m,color,z in [(meshes[0],base_color,2.4),(meshes[1],text_color,3.0)]:
        for tri in m.triangles:
            if np.all(abs(tri[:,2]-z)<.0001):d.polygon([(ox+float(v[0])*scale,oy-float(v[1])*scale) for v in tri],fill=color)
    return im

def meta(parent,key,value):
    n=parent.find(f"metadata[@key='{key}']")
    if n is None:n=ET.SubElement(parent,'metadata',key=key)
    n.set('value',str(value))

def export(top,name,bottom,out=None,base_color='#294F74',text_color='#F4B435',font_name=DEFAULT_FONT,options=None):
    colors=palette(base_color,text_color)
    meshes,record=make(top,name,bottom,font_name,options)
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
    record.update(project_version='2.5',printer='P2S 0.2mm',material='PLA',watertight=True,parts=2,base_color=colors[0],text_color=colors[1])
    (folder/'input.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    return path

if __name__=='__main__':
    p=argparse.ArgumentParser(description='三个参数：顶部、姓名、底部（双列用空格）')
    p.add_argument('top');p.add_argument('name');p.add_argument('bottom');p.add_argument('--out');p.add_argument('--font',default=DEFAULT_FONT,choices=available_fonts())
    p.add_argument('--top-font',choices=available_fonts());p.add_argument('--name-font',choices=available_fonts());p.add_argument('--bottom-font',choices=available_fonts())
    a=p.parse_args()
    try:print(export(a.top,a.name,a.bottom,a.out,font_name=[a.top_font or a.font,a.name_font or a.font,a.bottom_font or a.font]))
    except ValueError as e:p.error(str(e))
