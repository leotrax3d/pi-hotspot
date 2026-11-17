#!/usr/bin/env python3
"""Restore a root-owned installation snapshot. Usable without the application."""
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path


def run(*args):
 return subprocess.run(args,check=False,capture_output=True,text=True)


def restore(directory):
 directory=Path(directory).resolve()
 if directory.parent!=Path('/var/backups/pi-hotspot') or directory.stat().st_uid!=0:
  raise ValueError('Nur lokale Root-Sicherungen unter /var/backups/pi-hotspot sind erlaubt')
 data=json.loads((directory/'manifest.json').read_text())
 targets=data['targets']
 allowed={'/opt/qspot','/etc/qspot','/var/lib/qspot','/var/lib/qspot-web',
          '/etc/NetworkManager/system-connections','/etc/NetworkManager/conf.d/90-pi-hotspot.conf',
          '/etc/sysctl.d/90-pi-hotspot.conf','/etc/avahi/hosts','/etc/hostname','/etc/hosts','/usr/local/bin/pi-hotspot'}
 allowed.update('/etc/systemd/system/'+u for u in ('qspot-net.service','qspot-web.service','qspot-hostapd.service','qspot-dns@.service'))
 if set(targets) not in (allowed,allowed-{'/etc/avahi/hosts'}):raise ValueError('Ungültiges Sicherungsmanifest')
 p=Path('/etc/qspot/platform.json')
 current=json.loads(p.read_text()) if p.exists() else {}
 for unit in ('qspot-web','qspot-net','qspot-hostapd','qspot-dns@guest'):
  run('systemctl','stop',unit)
 for unit in ('qspot-web','qspot-net'):run('systemctl','disable',unit)
 run('nft','delete','table','inet','qspot')
 run('ip','rule','del','pref','177');run('ip','route','flush','table','177');run('ip','route','flush','proto','186')
 run('ip','link','del','qspot-wg')
 if current.get('mode')=='single':run('iw','dev',current['ap'],'del')
 elif current.get('ap'):
  run('ip','address','flush','dev',current['ap'])
  run('nmcli','device','set',current['ap'],'managed','yes')
 for name in targets:
  path=Path(name)
  if path.is_dir() and not path.is_symlink():shutil.rmtree(path)
  else:path.unlink(missing_ok=True)
 with tarfile.open(directory/'files.tar.gz') as archive:
  # Archives originate locally; validate paths before restoring root-owned files.
  for member in archive.getmembers():
   absolute='/'+member.name
   if '..' in Path(member.name).parts or not any(absolute==t or absolute.startswith(t+'/') for t in targets):
    raise ValueError('Unerwarteter Archivpfad')
  archive.extractall('/',filter='fully_trusted')
 run('systemctl','daemon-reload');run('nmcli','general','reload');run('nmcli','connection','reload')
 if Path('/etc/hostname').exists():run('hostnamectl','set-hostname',Path('/etc/hostname').read_text().strip())
 for name,value in data.get('sysctl',{}).items():run('sysctl','-w',name+'='+value)
 for unit,state in data.get('services',{}).items():
  if state['enabled']:run('systemctl','enable',unit)
  if state['active']:run('systemctl','start',unit)
 print('Vorherige Konfiguration wiederhergestellt:',directory)


if __name__=='__main__':
 if os.geteuid()!=0:raise SystemExit('Bitte mit sudo starten')
 restore(sys.argv[1])
