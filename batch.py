"""One native Bambu plate with up to nine independently editable nameplates."""
from pathlib import Path
from datetime import datetime
from zipfile import ZipFile,ZIP_DEFLATED
import tempfile,copy,json,io
import xml.etree.ElementTree as E
from PIL import Image,ImageDraw
from generator import export,validate,palette,HERE,C,P
from plate_preview import render_plate,position

def validate_batch(items):
    if not 1<=len(items)<=9:raise ValueError('本盘需有 1～9 块姓名牌。')
    colors=[]
    for item in items:
        validate(*item['texts'],font_name=item['fonts'])
        for c in palette(*item['colors']):
            if c not in colors:colors.append(c)
    if len(colors)>4:raise ValueError('本盘最多使用 4 种颜色，请统一部分配色或分盘生成。')
    return colors

def export_batch(items,out=None):
    colors=validate_batch(items)
    out=Path(out) if out else HERE/'output'/('plate_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    out.mkdir(parents=True,exist_ok=True)
    overview=Image.new('RGB',(600,1080),'#edf0f5')
    with tempfile.TemporaryDirectory() as tmp:
        files=None
        for i,item in enumerate(items):
            p=export(*item['texts'],out=Path(tmp)/str(i),base_color=item['colors'][0],text_color=item['colors'][1],font_name=item['fonts'])
            with ZipFile(p) as z:one={n:z.read(n) for n in z.namelist()}
            if files is None:
                files=dict(one);root=E.fromstring(one['3D/3dmodel.model']);res=root.find(f'{{{C}}}resources');res.clear();build=root.find(f'{{{C}}}build');build.clear()
                cfg=E.fromstring(one['Metadata/model_settings.config'])
                for node in list(cfg):
                    if node.tag in ['object','assemble']:cfg.remove(node)
                plate=cfg.find('plate')
                for node in list(plate.findall('model_instance')):plate.remove(node)
                settings=json.loads(one['Metadata/project_settings.config'])
            source_root=E.fromstring(one['3D/3dmodel.model']);obj=copy.deepcopy(source_root.find(f'{{{C}}}resources/{{{C}}}object'));gid=str(100+i)
            obj.set('id',gid)
            for el in obj.iter():el.attrib.pop(f'{{{P}}}UUID',None)
            modelpath=f'3D/Objects/nameplate_{i+1}.model'
            native=E.fromstring(one['3D/Objects/object_1.model'])
            partids=[str(1000+i*2),str(1001+i*2)]
            for source,partid in zip(native.find(f'{{{C}}}resources'),partids):source.set('id',partid)
            for comp,partid in zip(obj.findall(f'.//{{{C}}}component'),partids):
                comp.set(f'{{{P}}}path','/'+modelpath);comp.set('objectid',partid)
            files[modelpath]=E.tostring(native,encoding='utf-8',xml_declaration=True);res.append(obj)
            x,y=position(i)
            builditem=E.SubElement(build,f'{{{C}}}item',objectid=gid,transform=f'1 0 0 0 1 0 0 0 1 {x} {y} 0',printable='1')
            builditem.set(f'{{{P}}}UUID',f'{int(gid):08x}-b1ec-4553-aec9-835e5b724bb4')
            sc=E.fromstring(one['Metadata/model_settings.config']);ob=copy.deepcopy(sc.find('object'));ob.set('id',gid)
            ob.find("metadata[@key='name']").set('value',f'Nameplate {i+1}')
            for part,color,partid in zip(ob.findall('part'),palette(*item['colors']),partids):
                part.set('id',partid)
                part.attrib.pop('uuid',None);part.find("metadata[@key='extruder']").set('value',str(colors.index(color)+1))
            cfg.insert(i,ob)
            inst=E.SubElement(plate,'model_instance')
            for key,value in [('object_id',gid),('instance_id','0'),('identify_id',gid)]:E.SubElement(inst,'metadata',key=key,value=value)
            im=Image.open(p.parent/'preview.png').resize((180,330));overview.paste(im,((i%3)*200+10,(i//3)*360+25))
            ImageDraw.Draw(overview).text(((i%3)*200+15,(i//3)*360+5),str(i+1),fill='black')
        n=len(colors)
        for key,value in list(settings.items()):
            if isinstance(value,list) and len(value)==2 and (key.startswith('filament_') or key in ['nozzle_temperature','nozzle_temperature_initial_layer','nozzle_temperature_range_low','nozzle_temperature_range_high','textured_plate_temp','textured_plate_temp_initial_layer','hot_plate_temp','hot_plate_temp_initial_layer','cool_plate_temp','cool_plate_temp_initial_layer','eng_plate_temp','eng_plate_temp_initial_layer','fan_max_speed','fan_min_speed','close_fan_the_first_x_layers','full_fan_speed_layer','overhang_fan_speed','overhang_fan_threshold','slow_down_for_layer_cooling','slow_down_layer_time','slow_down_min_speed','fan_cooling_layer_time','additional_cooling_fan_speed','chamber_temperature']):settings[key]=[value[0]]*n
        settings.update(filament_colour=colors,default_filament_colour=colors,filament_self_index=[str(i+1) for i in range(n)],inherits_group=['']*(n+2),different_settings_to_system=[settings['different_settings_to_system'][0]]+['']*(n+1),flush_volumes_matrix=['0' if i==j else '140' for i in range(n) for j in range(n)],flush_volumes_vector=['140']*(2*n),wipe_tower_x=['170'],wipe_tower_y=['100'],enable_prime_tower='1' if n>1 else '0')
        files['3D/3dmodel.model']=E.tostring(root,encoding='utf-8',xml_declaration=True)
        relns='http://schemas.openxmlformats.org/package/2006/relationships'
        # Bambu loads external models through package relationships, not paths alone.
        rels='<Relationships xmlns="'+relns+'">'+''.join(f'<Relationship Target="/3D/Objects/nameplate_{i+1}.model" Id="rel-{i+1}" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>' for i in range(len(items)))+'</Relationships>'
        files['3D/_rels/3dmodel.model.rels']=rels.encode()
        files['Metadata/model_settings.config']=E.tostring(cfg,encoding='utf-8',xml_declaration=True)
        files['Metadata/project_settings.config']=json.dumps(settings).encode()
        overview=render_plate(items)
        for path in list(files):
            if path.endswith('.png'):
                b=io.BytesIO();overview.resize((256,460)).save(b,format='PNG');files[path]=b.getvalue()
        output=out/'nameplates_plate.3mf'
        with ZipFile(output,'w',ZIP_DEFLATED) as z:
            for path,data in files.items():z.writestr(path,data)
    overview.save(out/'preview.png')
    (out/'templates.json').write_text(json.dumps({'version':'1.8','items':items,'colors':colors},ensure_ascii=False,indent=2),encoding='utf-8')
    return output
