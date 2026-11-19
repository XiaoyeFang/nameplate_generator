"""Magnified plate region, using the same XY placement as batch export."""
from functools import lru_cache
from PIL import Image,ImageDraw,ImageFont
from generator import make,preview,sizing

def position(index,items=None):
    opts=[sizing(t.get('options')) for t in (items or [])]
    w=max([o['width'] for o in opts] or [25]);h=max([o['height'] for o in opts] or [50])
    count=max(1,len(opts))
    for columns in [3,4,5,6,7,8,9,2,1]:
        rows=(count+columns-1)//columns
        if min(columns,count)*(w+8)-8<=180 and rows*(h+8)-8<=230:
            return 20+(index%columns)*(w+8),20+(index//columns)*(h+8)
    raise ValueError('当前尺寸和数量无法排入本盘预留区域，请减少数量后分盘生成。')

def split_plates(items):
    plates=[];current=[]
    for item in items:
        candidate=current+[item]
        try:
            if len(candidate)>9:raise ValueError()
            position(0,candidate)
        except ValueError:
            if not current:raise
            plates.append(current);current=[item];position(0,current)
        else:current=candidate
    if current:plates.append(current)
    return plates

@lru_cache(maxsize=40)
def tile(texts,fonts,colors,width=25,height=50,sizes=(0,0,0)):
    meshes,_=make(*texts,font_name=fonts,options=dict(width=width,height=height,sizes=sizes))
    im=preview(meshes,*colors)
    scale=min(300/width,600/height);x=(360-width*scale)/2;y=(660-height*scale)/2
    return im.crop((round(x),round(y),round(x+width*scale),round(y+height*scale))).resize((round(width*2.5),round(height*2.5)),Image.Resampling.LANCZOS)

def preview_scale(groups):
    bounds=[(*position(i,items),sizing(t.get('options'))) for items in groups for i,t in enumerate(items)]
    extent_x=max([x+o['width']-20 for x,y,o in bounds] or [100])
    extent_y=max([y+o['height']-20 for x,y,o in bounds] or [180])
    return min(520/extent_x,800/extent_y)

def render_plate(items,groups=None,start_index=0):
    if len(items)>9:raise ValueError('一盘最多9块。')
    im=Image.new('RGB',(600,1000),'#edf0f5');d=ImageDraw.Draw(im)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',20)
    small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',16)
    d.text((24,12),f'本盘 {len(items)} / 9 块 · 按项目统一比例排布',font=font,fill='#243648')
    zoom=preview_scale(groups if groups is not None else [items])
    for i,item in enumerate(items):
        o=sizing(item.get('options'));w,h=o['width'],o['height'];x,y=position(i,items)
        px=40+round((x-20)*zoom);py=900-round((y-20+h)*zoom)
        im.paste(tile(tuple(item['texts']),tuple(item['fonts']),tuple(item['colors']),w,h,tuple(o['sizes'])).resize((round(w*zoom),round(h*zoom)),Image.Resampling.LANCZOS),(px,py))
        d.text((px,py-22),f'{start_index+i+1}: {w:g}×{h:g}mm',font=small,fill='#526477')
    d.text((24,950),'下方为热床前侧；编号对应项目清单。',font=small,fill='#526477')
    return im
