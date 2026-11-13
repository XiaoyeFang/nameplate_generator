"""Magnified plate region, using the same XY placement as batch export."""
from functools import lru_cache
from PIL import Image,ImageDraw,ImageFont
from generator import make,preview

def position(index):return 40+(index%3)*35,35+(index//3)*60

@lru_cache(maxsize=40)
def tile(texts,fonts,colors):
    meshes,_=make(*texts,font_name=fonts)
    # Remove the single-card preview's 2 mm visual border, keep the actual mesh.
    return preview(meshes,*colors).crop((30,30,330,630)).resize((125,250),Image.Resampling.LANCZOS)

def render_plate(items):
    if len(items)>9:raise ValueError('一盘最多9块。')
    im=Image.new('RGB',(600,1000),'#edf0f5');d=ImageDraw.Draw(im)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',20)
    small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',16)
    d.text((24,12),f'本盘 {len(items)} / 9 块 · 姓名牌区域放大',font=font,fill='#243648')
    for i in range(9):
        x,y=position(i)
        px=60+int((x-40)*5);py=80+int((155-y)*5)
        d.rounded_rectangle((px-7,py-7,px+132,py+257),radius=10,outline='#c4cbd4',width=2)
        d.text((px,py-32),f'{i+1:02d}',font=small,fill='#526477')
        if i<len(items):
            item=items[i];im.paste(tile(tuple(item['texts']),tuple(item['fonts']),tuple(item['colors'])),(px,py))
        else:d.text((px+20,py+105),'空位',font=font,fill='#97a2ad')
    d.text((24,950),'下方为热床前侧；编号对应本盘清单。',font=small,fill='#526477')
    return im
