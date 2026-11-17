import sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'qspot'))
import device_names


class DeviceNameTests(unittest.TestCase):
 def test_lease_names_are_bound_to_mac_and_ip(self):
  with tempfile.TemporaryDirectory() as directory:
   lease=Path(directory)/'leases'
   lease.write_text(f'{int(time.time())+3600} 02:00:00:00:00:01 10.77.0.20 School-Laptop *\n0 02:00:00:00:00:02 10.77.0.21 * *\n')
   with patch.object(device_names,'LEASES',lease):names=device_names.hostnames()
   self.assertEqual(names[('02:00:00:00:00:01','10.77.0.20')],'School-Laptop')
   self.assertEqual(names[('02:00:00:00:00:02','10.77.0.21')],'')
   self.assertNotIn(('02:00:00:00:00:01','10.77.0.21'),names)

 def test_expiry_is_checked_even_when_file_is_cached(self):
  with tempfile.TemporaryDirectory() as directory:
   lease=Path(directory)/'leases';lease.write_text('2000 02:00:00:00:00:01 10.77.0.20 Laptop *\n')
   with patch.object(device_names,'LEASES',lease),patch('device_names.time.time',return_value=1000):self.assertEqual(len(device_names.leases()),1)
   with patch.object(device_names,'LEASES',lease),patch('device_names.time.time',return_value=3000):self.assertEqual(device_names.leases(),[])

 def test_missing_or_malformed_leases_are_harmless(self):
  with tempfile.TemporaryDirectory() as directory:
   lease=Path(directory)/'leases'
   with patch.object(device_names,'LEASES',lease):self.assertEqual(device_names.hostnames(),{})
   lease.write_text('bad line\n0 not-a-mac 10.77.0.20 Host *\n0 02:00:00:00:00:01 invalid Host *\n')
   with patch.object(device_names,'LEASES',lease):self.assertEqual(device_names.hostnames(),{})
