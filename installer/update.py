#!/usr/bin/env python3
"""Manual update with a snapshot and independent timed rollback."""
import argparse
import importlib.util
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

spec=importlib.util.spec_from_file_location('pi_setup',Path(__file__).with_name('setup.py'))
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--backup-only',action='store_true');args=parser.parse_args()
 if os.geteuid()!=0:raise ValueError('Bitte mit sudo starten')
 if args.backup_only:print(setup.backup());return
 if not setup.yes('Aktuelle main-Version nach Sicherung installieren?',False):return
 with tempfile.TemporaryDirectory(prefix='pi-hotspot-update-') as temp:
  source=Path(temp)/'source'
  setup.command('git','clone','--depth','1','https://github.com/leotrax3d/pi-hotspot.git',str(source))
  setup.command('python3','-m','compileall','-q',str(source/'qspot'),str(source/'installer'))
  saved=setup.backup();print('Sicherung:',saved)
  setup.command('systemd-run','--unit=pi-hotspot-update-rollback','--on-active=5m',
                '/usr/bin/python3',str(saved/'rollback.py'),str(saved))
  try:
   setup.command('systemctl','stop','qspot-web','qspot-net','qspot-hostapd','qspot-dns@guest')
   for name in ('qspot','system','installer'):
    destination=Path('/opt/qspot')/name
    shutil.rmtree(destination);shutil.copytree(source/name,destination,ignore=shutil.ignore_patterns('__pycache__'))
   setup.write_text('/usr/local/bin/pi-hotspot',(source/'installer'/'pi-hotspot').read_text(),0o755)
   for unit in setup.UNITS:shutil.copy2(source/'system'/unit,Path('/etc/systemd/system')/unit)
   setup.write_text('/opt/qspot/SOURCE',setup.command('git','-C',str(source),'rev-parse','HEAD',quiet=True))
   setup.command('systemctl','daemon-reload');setup.command('systemctl','start','qspot-net','qspot-web')
   setup.wait_ready()
   setup.command('systemctl','stop','pi-hotspot-update-rollback.timer')
   print('Update abgeschlossen. Konfiguration und Zugangsdaten wurden beibehalten.')
  except BaseException:
   setup.command('python3',str(saved/'rollback.py'),str(saved),check=False)
   setup.command('systemctl','stop','pi-hotspot-update-rollback.timer',check=False)
   raise


if __name__=='__main__':main()
