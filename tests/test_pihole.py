import copy
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'qspot'))
import pihole
import network
from common import DEFAULT,validate

class PiHoleTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.state=Path(self.temp.name);self.patch=patch.object(pihole,'STATE',self.state);self.patch.start();self.addCleanup(self.patch.stop)
  (self.state/'pihole-password').write_text('private-test-password')
  self.c=copy.deepcopy(DEFAULT);self.c['features']['pihole']=True
  pihole.SID='';pihole.RECONCILED=False;pihole.PURGED=0;pihole.invalidate();pihole.reset_route()

 def test_optional_and_validated(self):
  self.assertFalse(pihole.enabled(DEFAULT));validate(self.c)
  self.assertFalse(pihole.view(DEFAULT)['installed'])

 def test_environment_does_not_freeze_blocking_and_disables_disk_history(self):
  with patch('common.run'):
   pihole.configure(self.c,['10.64.0.1'])
  text=(self.state/'pihole.env').read_text()
  self.assertNotIn('dns_blocking_active',text)
  self.assertIn('FTLCONF_database_maxDBdays=0',text)
  self.assertIn('FTLCONF_misc_privacylevel=3',text)
  self.assertIn('127.0.0.1:8081',text)
  self.assertIn(self.c['portal_domain'],text)
  self.assertNotIn('1.1.1.1',text)

 def test_pause_is_fixed_and_durable(self):
  with patch('pihole.request') as api,patch('pihole.atomic',side_effect=lambda p,d:p.write_text(json.dumps(d))):
   pihole.action(self.c,{'operation':'pause','timer':99999})
  self.assertEqual(api.call_args.args,('/dns/blocking',{'blocking':False,'timer':300}))
  self.assertGreater(json.loads((self.state/'pihole-control.json').read_text())['pause_until'],time.time())

 def test_mac_filter_selection(self):
  with patch('pihole.request',return_value={'clients':[]}) as api:
   pihole.action(self.c,{'operation':'device','mac':'02:00:00:00:00:01','enabled':False})
  self.assertEqual(api.call_args.args,('/clients',{'client':'02:00:00:00:00:01','groups':[],'comment':''}))
  with self.assertRaises(ValueError):pihole.action(self.c,{'operation':'device','mac':'bad','enabled':True})

 def test_domain_validation_and_local_domain_protection(self):
  for name in ('https://example.com/a',self.c['portal_domain'],'a\nserver=1.1.1.1'):
   with self.assertRaises(ValueError):pihole.action(self.c,{'operation':'domain','domain':name,'mode':'deny'})
  with patch('pihole.request',return_value={'domains':[]}) as api:
   pihole.action(self.c,{'operation':'domain','domain':'Example.org','mode':'deny'})
  self.assertIn(unittest.mock.call('/domains/deny/exact',{'domain':'example.org','enabled':True,'groups':[0],'comment':''}),api.call_args_list)

 def test_outage_routes_only_to_local_dns_then_recovers(self):
  with patch('pihole.request',side_effect=ValueError('unavailable')),patch('common.run') as run:
   pihole.maintain(self.c)
  self.assertIn('redirect to :53',run.call_args_list[0].kwargs['input'])
  pihole.LAST_HEALTH=0
  with patch('pihole.request',return_value={'blocking':'enabled'}),patch('pihole.daily_sample'),patch('pihole.dns_alive',return_value=True),patch('common.run') as run:
   pihole.maintain(self.c)
  self.assertIn('redirect to :5354',run.call_args_list[0].kwargs['input'])

 def test_logging_off_returns_no_queries_or_credentials_and_cache_is_shared(self):
  with patch('pihole.request',side_effect=[{'blocking':'enabled','sid':'secret'},{'clients':[]}]) as api:
   first=pihole.view(self.c);second=pihole.view(self.c)
  self.assertEqual(api.call_count,2);self.assertIs(first,second)
  self.assertNotIn('secret',json.dumps(first));self.assertEqual(first['events'],[])

 def test_dhcp_fallback_has_no_external_resolver(self):
  import tempfile
  real=Path
  with tempfile.TemporaryDirectory() as temp:
   def path(value):return real(temp)/'dns.conf' if str(value)=='/run/qspot/dns-guest.conf' else real(value)
   with patch('network.Path',side_effect=path),patch('network.run',return_value='192.0.2.53'),patch('pihole.configure'):
    network.dns(self.c)
   text=(real(temp)/'dns.conf').read_text()
  self.assertIn('dhcp-range=',text);self.assertIn('no-resolv',text);self.assertNotIn('server=',text)

 def test_expired_pause_resumes_on_new_process(self):
  (self.state/'pihole-control.json').write_text(json.dumps({'blocking':True,'pause_until':time.time()-5}))
  with patch('pihole.request',return_value={'blocking':'disabled'}) as api,patch('pihole.daily_sample'),patch('pihole.dns_alive',return_value=True),patch('common.run'):
   pihole.maintain(self.c)
  self.assertIn(unittest.mock.call('/dns/blocking',{'blocking':True,'timer':None}),api.call_args_list)

 def test_retention_purges_memory_without_disk_database(self):
  self.c['dns_logging']=True;self.c['dns_retention_hours']=1
  pihole.PURGED=time.monotonic()-3600
  with patch('pihole.request',return_value={'blocking':'enabled'}) as api,patch('pihole.daily_sample'),patch('pihole.dns_alive',return_value=True),patch('common.run'):
   pihole.maintain(self.c)
  self.assertIn(unittest.mock.call('/action/flush/logs',{},'POST'),api.call_args_list)

if __name__=='__main__':unittest.main()
