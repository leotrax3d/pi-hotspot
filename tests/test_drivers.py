import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('pi_drivers',Path(__file__).resolve().parents[1]/'installer/drivers.py')
drivers=importlib.util.module_from_spec(spec);spec.loader.exec_module(drivers)


class DriverTests(unittest.TestCase):
 def test_unknown_generic_disk_is_not_assumed_to_be_wifi(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)/'usb';net=Path(temp)/'net';device=root/'1-1';device.mkdir(parents=True);net.mkdir()
   for name,value in {'idVendor':'1111','idProduct':'1111','product':'Disk','busnum':'1','devnum':'2'}.items():(device/name).write_text(value)
   found=drivers.inventory(root,net)
   self.assertEqual(found[0]['family'],'')
   (device/'product').write_text('UGREEN AX900')
   self.assertEqual(drivers.inventory(root,net)[0]['family'],'aic8800')

 def test_firmware_device_identification(self):
  self.assertIn('a69c:8d80',drivers.AIC_IDS)
  self.assertIn('a69c:8d81',drivers.AIC_IDS)
  self.assertEqual(len(drivers.REVISION),40)

 def test_existing_working_devices_need_no_install(self):
  device={'family':'aic8800','id':'a69c:8d81','interfaces':['wlan1']}
  with patch.object(drivers,'inventory',return_value=[device]),patch.object(drivers,'command') as command:
   self.assertEqual(drivers.prepare(lambda *a:True,lambda *a,**k:''),[device])
  command.assert_not_called()

 def test_dkms_has_bounded_parallelism_and_rebuild(self):
  config=drivers.dkms_config()
  self.assertIn('AUTOINSTALL="yes"',config)
  self.assertIn('make -j2',config)
  self.assertIn('aic_load_fw',config)
  self.assertIn('aic8800_fdrv',config)

 def test_patch_failures_are_not_ignored(self):
  with tempfile.TemporaryDirectory() as temp:
   repo=Path(temp);folder=repo/'debian/patches';folder.mkdir(parents=True)
   (folder/'series').write_text('test.patch\n');(folder/'test.patch').write_text('src/USB/test.c')
   with patch.object(drivers,'command',side_effect=RuntimeError('bad patch')),self.assertRaises(RuntimeError):drivers.apply_usb_patches(repo)
