import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'qspot'))
from common import DEFAULT,validate
from branding import domain,identity,certificate_names,otp_uri


class BrandingTests(unittest.TestCase):
 def test_domain_validation(self):
  for invalid in ('https://portal.lan','portal.lan/path','portal.lan:443','portal.lan\nserver=evil','127.0.0.1','localhost','-foo.lan','foo..lan','foo.lan?x',' foo.lan'):
   with self.subTest(invalid=invalid),self.assertRaises(ValueError):domain(invalid)
  self.assertEqual(domain('Schüler.lan'),'xn--schler-5ya.lan')

 def test_branding_is_backwards_compatible(self):
  self.assertEqual(identity({'hostname':'old-router'})['portal_domain'],'old-router.local')
  c=copy.deepcopy(DEFAULT);c['brand_name']='Campus';c['portal_domain']='login.campus.lan'
  validate(c)
  self.assertIn('DNS:login.campus.lan',certificate_names(c))
  self.assertIn('DNS:pi-hotspot.local',certificate_names(c))
  self.assertIn('Campus',otp_uri(c,'TEST'))

 def test_brand_control_characters_rejected(self):
  c=copy.deepcopy(DEFAULT);c['brand_name']='Hello\nWorld'
  with self.assertRaises(ValueError):validate(c)

 def test_portal_uses_configured_domain_and_escapes_name(self):
  import web
  c={**copy.deepcopy(DEFAULT),'brand_name':'Campus <Test>','portal_domain':'login.campus.lan','ap_password':'not-public-secret'}
  with patch('web.rpc',return_value=c):
   client=web.app.test_client()
   result=client.get('/',base_url='http://probe.example')
   self.assertEqual(result.status_code,302)
   self.assertEqual(result.location,'http://login.campus.lan/')
   page=client.get('/',base_url='http://login.campus.lan')
   self.assertEqual(page.status_code,200)
   self.assertIn('Campus &lt;Test&gt;',page.text)
   self.assertNotIn('schuelerwlan.lan',page.text)
   public=client.get('/api/branding').json
   self.assertEqual(set(public),{'brand_name','portal_domain'})
   self.assertNotIn('not-public-secret',str(public))
