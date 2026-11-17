import configparser
from contextlib import closing
import importlib.util
import io
import json
import os
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'installer'))
import runtime
import recovery
import rollback
spec=importlib.util.spec_from_file_location('robust_setup',ROOT/'installer/setup.py')
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)


class InstallerRobustness(unittest.TestCase):
 def snapshot(self,directory,name='etc/hostname',link=None):
  archive=Path(directory)/'files.tar.gz'
  with tarfile.open(archive,'w:gz') as file:
   member=tarfile.TarInfo(name)
   if link is not None:member.type=tarfile.SYMTYPE;member.linkname=link;file.addfile(member)
   else:
    data=b'old-router\n';member.size=len(data);file.addfile(member,io.BytesIO(data))
  manifest={'version':2,'targets':list(rollback.ALLOWED),'present':['/etc/hostname'],'sha256':runtime.digest(archive)}
  (Path(directory)/'manifest.json').write_text(json.dumps(manifest))
  return archive

 def test_valid_backup_and_digest(self):
  with tempfile.TemporaryDirectory() as directory:
   self.snapshot(directory);data=rollback.validate_snapshot(directory)
   self.assertEqual(data['present'],['/etc/hostname'])

 def test_corruption_and_traversal_rejected_before_restore(self):
  with tempfile.TemporaryDirectory() as directory:
   archive=self.snapshot(directory);archive.write_bytes(b'corrupted')
   with self.assertRaisesRegex(ValueError,'SHA-256'):rollback.validate_snapshot(directory)
   self.snapshot(directory,'etc/hostname/../../passwd')
   with self.assertRaises(ValueError):rollback.validate_snapshot(directory)

 def test_escaping_links_fail_in_staging(self):
  with tempfile.TemporaryDirectory() as directory,tempfile.TemporaryDirectory() as staging:
   self.snapshot(directory,link='/etc/passwd')
   rollback.validate_snapshot(directory)
   with tarfile.open(Path(directory)/'files.tar.gz') as archive,self.assertRaises(tarfile.FilterError):archive.extractall(staging,filter=rollback.extraction_filter)

 def test_sqlite_snapshot_includes_wal_and_is_consistent(self):
  with tempfile.TemporaryDirectory() as directory:
   source=Path(directory)/'live.sqlite';destination=Path(directory)/'snapshot.sqlite'
   with closing(sqlite3.connect(source)) as connection:
    connection.execute('PRAGMA journal_mode=WAL');connection.execute('CREATE TABLE names(value)');connection.execute('INSERT INTO names VALUES("Laptop")');connection.commit()
    setup.sqlite_snapshot(source,destination)
   with closing(sqlite3.connect(destination)) as copy:
    self.assertEqual(copy.execute('PRAGMA integrity_check').fetchone()[0],'ok')
    self.assertEqual(copy.execute('SELECT value FROM names').fetchone()[0],'Laptop')

 def test_timeout_is_bounded_and_does_not_echo_arguments(self):
  with self.assertRaises(RuntimeError) as error:runtime.command(sys.executable,'-c','import time;time.sleep(5)','secret-value',quiet=True,timeout=.05)
  self.assertNotIn('secret-value',str(error.exception))

 def test_numeric_input_recovers_and_secret_spaces_survive(self):
  with patch('builtins.input',side_effect=['no','0','999','6']):self.assertEqual(setup.ask_int('Kanal',1,11,6),6)
  with patch('getpass.getpass',return_value='  password  '):self.assertEqual(setup.ask('Passwort',secret=True),'  password  ')

 def test_bad_uplink_rejected_before_any_network_change(self):
  with self.assertRaises(ValueError):setup.validate_uplink({'ssid':'Example','security':'WPA2/WPA3 Personal','password':'short'})

 @unittest.skipUnless(os.name=='posix','Linux file locks')
 def test_parallel_installers_are_blocked(self):
  with tempfile.TemporaryDirectory() as directory,patch.object(runtime,'LOCK',Path(directory)/'lock'):
   with runtime.exclusive():
    with self.assertRaises(ValueError):
     with runtime.exclusive():pass

 @unittest.skipUnless(os.name=='posix','Durable Linux state')
 def test_completion_clears_recovery_marker(self):
  with tempfile.TemporaryDirectory() as directory,patch.object(runtime,'STATE',Path(directory)),patch('runtime.command'):
   runtime.save(Path(directory)/'transaction.json',{'backup':'/safe/path','stage':'ready'})
   runtime.finish()
   self.assertFalse((Path(directory)/'transaction.json').exists())
   self.assertEqual(json.loads((Path(directory)/'last-operation.json').read_text())['stage'],'complete')

 @unittest.skipUnless(os.name=='posix','Linux boot identity')
 def test_boot_recovery_does_not_interrupt_live_installer(self):
  data={'boot':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'pid':os.getpid(),
        'process_start':Path(f'/proc/{os.getpid()}/stat').read_text().split(') ',1)[1].split()[19]}
  self.assertTrue(recovery.owner_alive(data));data['boot']='old-boot';self.assertFalse(recovery.owner_alive(data))

 def test_services_remain_enabled_and_retry_without_start_limit(self):
  for name in ('qspot-net.service','qspot-web.service','qspot-hostapd.service','qspot-dns@.service'):
   parser=configparser.ConfigParser(interpolation=None);parser.read(ROOT/'system'/name)
   self.assertEqual(parser['Service']['Restart'],'always')
   self.assertEqual(parser['Unit']['StartLimitIntervalSec'],'0')
   if name in ('qspot-net.service','qspot-web.service'):self.assertEqual(parser['Install']['WantedBy'],'multi-user.target')
