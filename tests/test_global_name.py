import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'qspot'))
from common import DEFAULT,validate
from branding import renamed_config


class GlobalNameTests(unittest.TestCase):
 def test_one_name_updates_network_identity_and_all_portal_texts(self):
  old=copy.deepcopy(DEFAULT);old['description']='SchülerWLAN Chat';old['terms']='SchülerWLAN Regeln'
  result=validate(renamed_config(old,{**old,'brand_name':'Campus Nord'}))
  self.assertEqual(result['ssid'],'Campus Nord')
  self.assertEqual(result['hostname'],'campus-nord')
  self.assertEqual(result['portal_domain'],'campus-nord.local')
  self.assertEqual(result['description'],'Campus Nord Chat')
  self.assertEqual(result['terms'],'Campus Nord Regeln')
  self.assertNotIn('SchülerWLAN',result['title'])

 def test_custom_values_and_explicit_domain_edits_survive(self):
  old={**copy.deepcopy(DEFAULT),'ssid':'Guest Network','hostname':'router-east','portal_domain':'login.school.lan'}
  result=renamed_config(old,{**old,'brand_name':'Campus','portal_domain':'custom.school.lan'})
  self.assertEqual(result['ssid'],'Guest Network')
  self.assertEqual(result['hostname'],'router-east')
  self.assertEqual(result['portal_domain'],'custom.school.lan')

 def test_special_characters_are_literal_and_slug_is_valid(self):
  old={**copy.deepcopy(DEFAULT),'brand_name':'A+B','ssid':'A+B','title':'A+B WLAN','hostname':'a-b','portal_domain':'a-b.local'}
  result=validate(renamed_config(old,{**old,'brand_name':'3D Schüler'}))
  self.assertEqual(result['title'],'3D Schüler WLAN')
  self.assertEqual(result['hostname'],'wlan-3d-schueler')
