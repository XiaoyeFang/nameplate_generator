"""Local preferences, atomically saved; invalid files fall back to defaults."""
from pathlib import Path
import json
import os

PATH=Path(__file__).resolve().parent/'last_settings.json'
DEFAULTS={'texts':['北京芸奕','王珊','剑心永明 战斗不止'],'fonts':['微软雅黑粗体']*3,'colors':['#294F74','#F4B435']}

def load(path=PATH):
    result={k:list(v) if isinstance(v,list) else v for k,v in DEFAULTS.items()}
    try:
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(data,dict):return result
        if isinstance(data.get('texts'),list) and len(data['texts'])==3 and all(isinstance(v,str) for v in data['texts']):result['texts']=data['texts']
        if isinstance(data.get('font'),str):result['fonts']=[data['font']]*3
        if isinstance(data.get('fonts'),list) and len(data['fonts'])==3 and all(isinstance(v,str) for v in data['fonts']):result['fonts']=data['fonts']
        if isinstance(data.get('batch'),list):result['batch']=data['batch']
        from generator import sizing
        result['options']=sizing(data.get('options'))
        import re
        if isinstance(data.get('colors'),list) and len(data['colors'])==2 and all(isinstance(v,str) and re.fullmatch(r'#[0-9a-fA-F]{6}',v) for v in data['colors']):result['colors']=data['colors']
    except (OSError,ValueError):pass
    return result

def save(data,path=PATH):
    path=Path(path);tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(tmp,path)
