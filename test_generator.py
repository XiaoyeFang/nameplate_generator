import unittest
import tempfile
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET
import numpy as np
import trimesh
from generator import validate,make,export,C,P

class GeneratorTests(unittest.TestCase):
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
        for args in [('北京芸奕多字','王珊','剑心'),('北京','一二三四五六','剑心'),('北京','王珊','一二三四五'),('北京','王珊','一 二 三'),('','王珊','剑心'),('北京','王珊','😀')]:
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
