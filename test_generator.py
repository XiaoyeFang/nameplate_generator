import unittest
import tempfile
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET
import numpy as np
import trimesh
from generator import validate,make,export,C,P

class GeneratorTests(unittest.TestCase):
    def test_batch_more_than_four_colors(self):
        import json
        from batch import export_batch
        colors=['#112233','#223344','#334455','#445566','#556677','#667788']
        items=[dict(texts=['北京','王珊','剑心'],fonts=['楷体']*3,colors=colors[i:i+2]) for i in range(0,6,2)]
        with tempfile.TemporaryDirectory() as tmp:
            path=export_batch(items,tmp)
            with ZipFile(path) as z:
                cfg=json.loads(z.read('Metadata/project_settings.config'))
                self.assertEqual(cfg['filament_colour'],colors)
                self.assertEqual(len(cfg['filament_settings_id']),6)
                self.assertEqual(len(cfg['flush_volumes_matrix']),36)
                self.assertEqual(len(cfg['different_settings_to_system']),8)
                model=ET.fromstring(z.read('Metadata/model_settings.config'))
                self.assertEqual([p.find("metadata[@key='extruder']").get('value') for o in model.findall('object') for p in o.findall('part')],['1','2','3','4','5','6'])

    def test_bottom_five_and_six_characters(self):
        for text in ['一二三四五','一二三四五六','一二三四五六 七八九十一二']:
            meshes,r=make('北京','王珊',text,options=dict(width=30,height=60))
            bottom=[v for v in r['layout'] if v['region']=='bottom']
            self.assertEqual(len(bottom),len(text.replace(' ','')))
            self.assertTrue(all(v['y']-v['size_mm']/2>=1-1e-6 for v in bottom))
            self.assertTrue(all(m.is_watertight for m in meshes))
        with self.assertRaises(ValueError):make('北京','王珊','一二三四五六七')
        with self.assertRaises(ValueError):make('北京','王珊','一二三四五六',options=dict(sizes=[0,0,10]))

    def test_tall_nameplates_and_plate_bounds(self):
        from plate_preview import position
        for height in [80,100]:
            meshes,r=make('北京','王珊','一二三四五六',options=dict(height=height))
            self.assertAlmostEqual(meshes[0].bounds[1,1],height)
            items=[{'options':dict(width=25,height=height)}]*9
            points=[position(i,items) for i in range(9)]
            self.assertEqual(len(set(points)),9)
            for x,y in points:
                self.assertLessEqual(x+25,200)
                self.assertLessEqual(y+height,250)
        with self.assertRaises(ValueError):position(0,[{'options':dict(width=50,height=100)}]*9)

    def test_multiplate_preview_same_scale(self):
        from plate_preview import split_plates,render_plate
        item=dict(texts=['北京','王珊','剑心'],fonts=['楷体']*3,colors=['#294F74','#F4B435'])
        groups=split_plates([item]*10)
        first=np.asarray(render_plate(groups[0],groups))
        second=np.asarray(render_plate(groups[1],groups,start_index=9))
        color=np.array([41,79,116])
        # First object remains identical in size and position on each page.
        a=np.all(first==color,axis=2);b=np.all(second==color,axis=2)
        ys,xs=np.where(b);self.assertGreater(len(xs),0)
        self.assertTrue(np.array_equal(a[ys.min():ys.max()+1,xs.min():xs.max()+1],b[ys.min():ys.max()+1,xs.min():xs.max()+1]))

    def test_custom_dimensions_and_font_sizes(self):
        opts=dict(width=30,height=60,sizes=[4,6,7])
        meshes,r=make('北京','王珊','剑心永明',options=opts)
        self.assertTrue(np.allclose(meshes[0].bounds,[[0,0,0],[30,60,2.4]],atol=.0001))
        self.assertEqual(r['font_sizes_mm'],[4,6,7])
        self.assertEqual(r['dimensions_mm'],[30,60,3.0])
        with self.assertRaises(ValueError):make('北京芸奕馆','王珊','剑心永明',options=dict(sizes=[15,6,7]))
        from plate_preview import position
        items=[{'options':opts}]*9
        self.assertEqual(position(8,items),(96,156))
        from generator import sizing
        for bad in [dict(width=0),dict(height=101),dict(sizes=[float('nan'),0,0])]:
            with self.assertRaises(ValueError):sizing(bad)

    def test_region_fonts_and_long_names(self):
        fonts=['宋体','楷体','华文行楷（行书风格）']
        for name in ['一二三四','一二三四五']:
            meshes,r=make('北京芸奕馆',name,'剑心永明',fonts)
            self.assertEqual(list(r['fonts'].values()),fonts)
            self.assertTrue(all(p['x']-p['size_mm']/2>0 and p['x']+p['size_mm']/2<25 for p in r['layout']))
            self.assertTrue(all(m.is_watertight for m in meshes))
    def test_preference_font_migration(self):
        import json,preferences
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'prefs.json';p.write_text(json.dumps({'font':'楷体'}),encoding='utf-8')
            self.assertEqual(preferences.load(p)['fonts'],['楷体']*3)
            new=preferences.load(p);new['fonts']=['宋体','楷体','华文行楷（行书风格）'];preferences.save(new,p)
            self.assertEqual(preferences.load(p),new)
    def test_custom_colors_saved_and_previewed(self):
        import json
        from generator import preview
        m,_=make('北京','王珊','剑心')
        im=preview(m,'#112233','#abcdef')
        pixels=set(im.getdata())
        self.assertIn((17,34,51),pixels);self.assertIn((171,205,239),pixels)
        with tempfile.TemporaryDirectory() as tmp:
            p=export('北京','王珊','剑心',tmp,base_color='#112233',text_color='#abcdef')
            with ZipFile(p) as z:
                cfg=json.loads(z.read('Metadata/project_settings.config'))
                self.assertEqual(cfg['filament_colour'],['#112233','#ABCDEF'])
                self.assertEqual(cfg['printer_settings_id'],'Bambu Lab P2S 0.2 nozzle')
                self.assertEqual(cfg['nozzle_diameter'],['0.2'])
                for key in ['top_surface_pattern','bottom_surface_pattern','internal_solid_infill_pattern','sparse_infill_pattern']:
                    self.assertEqual(cfg[key],'octagramspiral')
                    self.assertIn(key,cfg['different_settings_to_system'][0].split(';'))
                self.assertEqual(cfg['print_compatible_printers'],['Bambu Lab P2S 0.2 nozzle'])
                self.assertEqual(cfg['layer_height'],'0.1')
                self.assertEqual(cfg['initial_layer_print_height'],'0.1')
                self.assertEqual(cfg['outer_wall_line_width'],'0.22')
                self.assertEqual(cfg['filament_max_volumetric_speed'],['1.6','1.6'])
            self.assertEqual(json.loads((Path(tmp)/'input.json').read_text(encoding='utf-8'))['text_color'],'#ABCDEF')
    def test_slot_is_open_and_top_text_clear(self):
        import manifold3d as md
        meshes,r=make('北京芸奕','王珊','我最牛逼')
        m=meshes[0];s=md.Manifold(md.Mesh(np.asarray(m.vertices,np.float32),np.asarray(m.faces,np.uint32)))
        probe=md.Manifold.cube([8,1,2.4],True).translate([12.5,46.625,1.2])
        self.assertAlmostEqual((s^probe).volume(),0,places=5)
        self.assertEqual(len(s.decompose()),1)
        top=[p for p in r['layout'] if p['region']=='top']
        self.assertTrue(all(p['y']+p['size_mm']/2<45.374375 for p in top))
        self.assertTrue(all(p['y']-p['size_mm']/2>37.5 for p in top))
    def test_limits_and_missing_glyph(self):
        for args in [('北京芸奕多字','王珊','剑心'),('北京','一二三四五六','剑心'),('北京','王珊','一二三四五六七'),('北京','王珊','一 二 三'),('','王珊','剑心'),('北京','王珊','😀')]:
            with self.assertRaises(ValueError):validate(*args)
    def test_name_space_and_columns(self):
        a,ra=make('北京芸奕','王珊','我最牛逼');b,rb=make('北京芸奕','王 珊','我最牛逼')
        self.assertEqual(ra,rb)
        self.assertTrue(all(p['x']==12.5 for p in ra['layout'] if p['region']=='bottom'))
        _,r=make('北京芸奕','王小珊','剑心永明 战斗不止')
        self.assertEqual(r['bottom_columns_left_to_right'],['剑心永明','战斗不止'])
        xs=sorted(set(p['x'] for p in r['layout'] if p['region']=='bottom'))
        self.assertAlmostEqual(sum(xs),25)
        self.assertEqual(len([p for p in r['layout'] if p['region']=='name']),3)
    def test_export_restores_mesh_and_color(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=export('北京芸奕','王珊','剑心永明 战斗不止',tmp)
            with ZipFile(path) as z:
                root=ET.fromstring(z.read('3D/3dmodel.model'));settings=ET.fromstring(z.read('Metadata/model_settings.config'));native=ET.fromstring(z.read('3D/Objects/object_1.model'))
                self.assertEqual([p.find("metadata[@key='extruder']").get('value') for p in settings.findall('object/part')],['1','2'])
                bounds=[]
                for comp in root.findall(f'.//{{{C}}}component'):
                    obj=native.find(f'{{{C}}}resources/{{{C}}}object[@id="{comp.get("objectid")}"]')
                    v=np.array([[float(a.get(k)) for k in 'xyz'] for a in obj.findall(f'.//{{{C}}}vertex')]);f=np.array([[int(a.get(k)) for k in ['v1','v2','v3']] for a in obj.findall(f'.//{{{C}}}triangle')])
                    t=np.array(list(map(float,comp.get('transform').split()))).reshape(4,3)
                    m=trimesh.Trimesh(v@t[:3]+t[3],f,process=True)
                    self.assertTrue(m.is_watertight);bounds.append(m.bounds)
                self.assertTrue(np.allclose(bounds[0],[[0,0,0],[25,50,2.4]],atol=.0001))
                self.assertAlmostEqual(bounds[1][0,2],2.0,places=4)
                self.assertAlmostEqual(bounds[1][1,2],3.0,places=4)
                self.assertTrue(np.all(bounds[1][0,:2]>0) and np.all(bounds[1][1,:2]<[25,50]))

if __name__=='__main__':unittest.main()
