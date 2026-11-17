import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'qspot'))
import network
import daemon
from common import DEFAULT, validate
import activity_log


class PiNetworkTests(unittest.TestCase):
 def test_interface_validation(self):
  import platform_config
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'platform.json'
   path.write_text(json.dumps({'uplink':'eth0;reboot'}))
   with patch.object(platform_config,'PATH',path),self.assertRaises(ValueError):platform_config.load()

 def test_firewall_enforces_bypass_and_killswitch(self):
  c=copy.deepcopy(DEFAULT);c['vpn']='both';c['vpn_bypass']=['02:00:00:00:00:01']
  with patch('network.vpn_dns',return_value=['10.64.0.1']),patch('network.nft') as nft,patch('network.run',side_effect=lambda *a,**k:'[]' if a[0]=='ip' else ''):
   network.base(c)
  text=nft.call_args.args[0]
  self.assertIn('ether saddr != @vpn_bypass meta mark set 177',text)
  self.assertIn('ether saddr != @vpn_bypass oifname != "qspot-wg" drop',text)
  self.assertIn('02:00:00:00:00:01',text)
  self.assertIn('meta nfproto ipv6 drop',text)

 def test_policy_route_fails_closed_without_tunnel(self):
  c=copy.deepcopy(DEFAULT);c['vpn']='both';c['vpn_server']='test'
  with tempfile.TemporaryDirectory() as temp:
   state=Path(temp);(state/'vpn').mkdir();(state/'vpn'/'test.json').write_text('{}')
   calls=[]
   def run(*args,**kwargs):
    calls.append(args)
    if args[:4]==('ip','link','add','qspot-wg'):raise ValueError('module unavailable')
    return ''
   with patch.object(network,'STATE',state),patch('network.policy_routing',return_value=True),patch('network.run',side_effect=run),self.assertRaises(ValueError):network.vpn(c)
   self.assertIn(('ip','route','add','unreachable','default','table','177','metric','32767'),calls)
   self.assertIn(('ip','rule','add','pref','177','fwmark','177','lookup','177'),calls)

 def test_device_preferences_persist_without_network_restart(self):
  c=copy.deepcopy(DEFAULT);c['vpn']='both'
  mac='02:00:00:00:00:01'
  with patch('daemon.config',return_value=c),patch('daemon.rows',return_value=[]),patch('daemon.atomic') as atomic,patch('daemon.network.sync_bypass') as sync:
   daemon.dispatch({'method':'device_vpn','mac':mac,'enabled':False})
   self.assertIn(mac,atomic.call_args.args[1]['vpn_bypass'])
   sync.assert_called_once()

 def test_config_rejects_hostapd_and_mac_injection(self):
  for key,value in [('ap_password','abcdefgh\ninterface=eth0'),('vpn_bypass',['00:00:00:00:00:00;flush ruleset']),('dns_retention_hours',0)]:
   c=copy.deepcopy(DEFAULT);c[key]=value
   with self.assertRaises(ValueError):validate(c)

 def test_single_radio_requires_supported_uplink_channel(self):
  with patch.dict(network.PLATFORM,{'mode':'single'}),patch('network.run',return_value='channel 36 (5180 MHz)'),self.assertRaises(ValueError):network.radio_channel(DEFAULT)
  with patch.dict(network.PLATFORM,{'mode':'single'}),patch('network.run',return_value='channel 6 (2437 MHz)'):
   self.assertEqual(network.radio_channel(DEFAULT),(6,'g'))

 def test_dns_disabled_clears_retained_data(self):
  with tempfile.TemporaryDirectory() as temp:
   store=Path(temp)/'events.json';raw=Path(temp)/'queries.log'
   store.write_text('[{"domain":"example.org"}]');raw.write_text('private history')
   with patch.object(activity_log,'STORE',store),patch.object(activity_log,'RAW',raw):activity_log.maintain(DEFAULT,True)
   self.assertFalse(store.exists());self.assertEqual(raw.read_text(),'')

 def test_unlimited_defaults(self):
  self.assertEqual(DEFAULT['profiles']['standard']['bytes'],0)
  self.assertEqual(DEFAULT['profiles']['standard']['seconds'],0)


if __name__=='__main__':unittest.main()
