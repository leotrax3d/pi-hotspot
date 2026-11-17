import configparser
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('pi_setup',Path(__file__).resolve().parents[1]/'installer'/'setup.py')
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)


class InstallerTests(unittest.TestCase):
 def test_enterprise_profile_has_certificate_validation_and_no_secret_argv(self):
  with tempfile.TemporaryDirectory() as directory:
   destination=Path(directory)/'uplink.nmconnection'
   wifi={'ssid':'Example enterprise','security':'WPA2 Enterprise (PEAP/MSCHAPv2)',
         'identity':'test-user','password':'test-only-password','ca':'','domain':'radius.example.org'}
   with patch.object(setup,'Path',return_value=destination),patch.object(setup,'command') as command:
    setup.configure_uplink(wifi,{'uplink':'wlan1','mode':'dual'})
   profile=configparser.ConfigParser(interpolation=None);profile.read(destination)
   self.assertEqual(profile['802-1x']['domain-suffix-match'],'radius.example.org')
   self.assertEqual(profile['802-1x']['system-ca-certs'],'true')
   self.assertEqual(profile['802-1x']['password'],'test-only-password')
   self.assertEqual(profile['connection']['interface-name'],'wlan1')
   self.assertNotIn('test-only-password',str(command.call_args_list))
   self.assertEqual(destination.stat().st_mode&0o777,0o600)

 def test_single_radio_profile_pins_uplink_to_24ghz(self):
  with tempfile.TemporaryDirectory() as directory:
   destination=Path(directory)/'uplink.nmconnection'
   with patch.object(setup,'Path',return_value=destination),patch.object(setup,'command'):
    setup.configure_uplink({'ssid':'Example','security':'Offen'},{'uplink':'wlan0','mode':'single'})
   profile=configparser.ConfigParser();profile.read(destination)
   self.assertEqual(profile['wifi']['band'],'bg')

 def test_unsupported_platform_is_rejected_before_commands(self):
  with patch.object(setup.platform,'system',return_value='Windows'),patch.object(setup,'command') as command,self.assertRaises(ValueError):setup.preflight()
  command.assert_not_called()


if __name__=='__main__':unittest.main()
