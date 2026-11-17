import json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'qspot'))
tmp=tempfile.TemporaryDirectory();os.environ['QSPOT_WEB_STATE']=tmp.name
import web
class WebTests(unittest.TestCase):
 def setUp(self):
  self.client=web.app.test_client();self.base='https://qspot.lan'
 def test_authentication_and_csrf(self):
  self.assertEqual(self.client.get('/api/admin/status',base_url=self.base).status_code,401)
  csrf=self.client.get('/api/auth',base_url=self.base).json['csrf']
  data={'token':(Path(tmp.name)/'setup-token').read_text(),'password':'unique-test-password-4'}
  self.assertEqual(self.client.post('/api/setup',base_url=self.base,json=data).status_code,403)
  self.assertEqual(self.client.post('/api/setup',base_url=self.base,json=data,headers={'X-CSRF-Token':csrf}).status_code,200)
  csrf=self.client.get('/api/auth',base_url=self.base).json['csrf']
  self.assertEqual(self.client.get('/api/admin/sessions',base_url=self.base).status_code,200)
  self.assertEqual(self.client.post('/api/admin/action',base_url=self.base,json={'method':'arbitrary_shell'},headers={'X-CSRF-Token':csrf}).status_code,400)
  self.assertEqual(self.client.post('/api/logout',base_url=self.base,json={},headers={'X-CSRF-Token':csrf}).status_code,200)
  self.assertEqual(self.client.get('/api/admin/sessions',base_url=self.base).status_code,401)
 def test_https_required(self):
  csrf=self.client.get('/api/auth',base_url=self.base).json['csrf']
  self.assertEqual(self.client.post('/api/login',json={'password':'whatever'},headers={'X-CSRF-Token':csrf}).status_code,400)
 def test_captive_browser_null_origin(self):
  import re
  original=web.rpc
  web.rpc=lambda *a,**k:{'active':1}
  try:
   page=self.client.get('/',base_url='http://10.77.0.1',environ_overrides={'REMOTE_ADDR':'10.77.0.52'}).text
   token=re.search(r'name="portal_token" value="([^"]+)"',page).group(1)
   r=self.client.post('/portal/activate',base_url='http://10.77.0.1',data={'accepted':'yes','portal_token':token},headers={'Origin':'null'},environ_overrides={'REMOTE_ADDR':'10.77.0.52'})
   self.assertEqual(r.status_code,303)
   r=self.client.post('/portal/activate',base_url='http://10.77.0.1',data={'accepted':'yes','portal_token':token},environ_overrides={'REMOTE_ADDR':'10.77.0.53'})
   self.assertEqual(r.status_code,400)
  finally:web.rpc=original
if __name__=='__main__':unittest.main()
