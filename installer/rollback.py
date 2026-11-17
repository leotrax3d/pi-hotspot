#!/usr/bin/env python3
"""Validate and stage a snapshot before touching the running installation."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ALLOWED={'/opt/qspot','/etc/qspot','/var/lib/qspot','/var/lib/qspot-web',
         '/etc/NetworkManager/system-connections','/etc/NetworkManager/conf.d/90-pi-hotspot.conf',
         '/etc/sysctl.d/90-pi-hotspot.conf','/etc/avahi/hosts','/etc/hostname','/etc/hosts','/usr/local/bin/pi-hotspot'}
ALLOWED.update('/etc/systemd/system/'+u for u in ('qspot-net.service','qspot-web.service','qspot-hostapd.service','qspot-dns@.service'))
MARKER=Path('/var/lib/pi-hotspot/transaction.json')


def run(*args,required=False):
 result=subprocess.run(args,check=False,capture_output=True,text=True,timeout=120)
 if required and result.returncode:raise RuntimeError('Wiederherstellung fehlgeschlagen: '+args[0])
 return result


def checksum(path):
 value=hashlib.sha256()
 with path.open('rb') as file:
  for block in iter(lambda:file.read(1024*1024),b''):value.update(block)
 return value.hexdigest()


def validate_snapshot(directory):
 directory=Path(directory)
 data=json.loads((directory/'manifest.json').read_text())
 if not isinstance(data,dict):raise ValueError('Ungültiges Sicherungsmanifest')
 targets=data.get('targets',[])
 if not isinstance(targets,list) or len(targets)!=len(set(targets)) or set(targets) not in (ALLOWED,ALLOWED-{'/etc/avahi/hosts'}):raise ValueError('Ungültiges Sicherungsmanifest')
 present=data.get('present',[])
 if not isinstance(present,list) or len(present)!=len(set(present)) or not set(present)<=set(data['targets']):raise ValueError('Ungültige Sicherungspfade')
 if set(data.get('services',{}))-{'qspot-net','qspot-web','avahi-daemon'}:raise ValueError('Ungültige Dienste')
 if set(data.get('sysctl',{}))-{'net.ipv4.ip_forward','net.ipv4.conf.all.rp_filter'}:raise ValueError('Ungültige Kernelparameter')
 import re
 for device,ident in data.get('connections',{}).items():
  if not re.fullmatch(r'[a-zA-Z0-9_-]{1,15}',device) or not re.fullmatch(r'[a-fA-F0-9-]{36}',ident):raise ValueError('Ungültige Verbindungsdaten')
 archive=directory/'files.tar.gz'
 if data.get('version',1)>=2 and (not data.get('sha256') or checksum(archive)!=data['sha256']):raise ValueError('Sicherung beschädigt: SHA-256 stimmt nicht überein')
 with tarfile.open(archive) as source:
  members=source.getmembers();names=set()
  for member in members:
   path=Path(member.name)
   if path.is_absolute() or '..' in path.parts or member.name in names:raise ValueError('Unsicherer Archivpfad')
   names.add(member.name)
   absolute='/'+member.name.rstrip('/')
   if not any(absolute==target or absolute.startswith(target+'/') for target in present):raise ValueError('Unerwarteter Archivpfad')
   if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):raise ValueError('Nicht unterstützter Archivtyp')
  if any(p.lstrip('/') not in names for p in present):raise ValueError('Unvollständige Sicherung')
  needed=sum(m.size for m in members)+64*1024**2
  if shutil.disk_usage(directory).free<needed:raise ValueError('Zu wenig Speicher für sichere Wiederherstellung')
 return data


def extraction_filter(member,destination):
 safe=tarfile.data_filter(member,destination)
 if safe is None:return None
 # Keep application ownership and restricted permissions from our local archive.
 return safe.replace(uid=member.uid,gid=member.gid,uname=member.uname,gname=member.gname,mode=member.mode&0o777)


def clear_marker(directory):
 if MARKER.exists():
  data=json.loads(MARKER.read_text())
  if Path(data.get('backup','')).resolve()==directory:
   MARKER.unlink()
   fd=os.open(MARKER.parent,os.O_DIRECTORY)
   try:os.fsync(fd)
   finally:os.close(fd)


def restore(directory,watchdog=False):
 directory=Path(directory).resolve()
 if directory.parent!=Path('/var/backups/pi-hotspot') or directory.stat().st_uid!=0 or directory.stat().st_mode&0o022:
  raise ValueError('Nur geschützte Root-Sicherungen unter /var/backups/pi-hotspot sind erlaubt')
 if watchdog:
  if not MARKER.exists():return
  marker=json.loads(MARKER.read_text())
  if Path(marker.get('backup','')).resolve()!=directory or marker.get('stage')=='complete':return
 data=validate_snapshot(directory)
 # Bad paths, links, truncated archives and full disks fail here, before services stop.
 with tempfile.TemporaryDirectory(prefix='restore-',dir=directory) as temporary:
  stage=Path(temporary)
  with tarfile.open(directory/'files.tar.gz') as archive:archive.extractall(stage,filter=extraction_filter)
  current_path=Path('/etc/qspot/platform.json')
  current=json.loads(current_path.read_text()) if current_path.exists() else {}
  for key in ('ap','uplink'):
   if key in current:
    import re
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,15}',current[key]):raise ValueError('Ungültige Schnittstelle')
  for unit in ('qspot-web','qspot-net','qspot-hostapd','qspot-dns@guest'):run('systemctl','stop',unit)
  for unit in ('qspot-web','qspot-net'):run('systemctl','disable',unit)
  run('nft','delete','table','inet','qspot')
  run('ip','rule','del','pref','177');run('ip','route','flush','table','177');run('ip','route','flush','proto','186')
  run('ip','link','del','qspot-wg')
  if current.get('mode')=='single':run('iw','dev',current['ap'],'del')
  elif current.get('ap'):
   run('ip','address','flush','dev',current['ap']);run('nmcli','device','set',current['ap'],'managed','yes')
  for name in data['targets']:
   target=Path(name);saved=stage/name.lstrip('/')
   if target.is_dir() and not target.is_symlink():shutil.rmtree(target)
   else:target.unlink(missing_ok=True)
   if name in data['present']:
    target.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(saved),str(target))
  run('systemctl','daemon-reload',required=True)
  run('nmcli','general','reload',required=True);run('nmcli','connection','reload',required=True)
  if Path('/etc/hostname').exists():run('hostnamectl','set-hostname',Path('/etc/hostname').read_text().strip(),required=True)
  for name,value in data.get('sysctl',{}).items():run('sysctl','-w',name+'='+value,required=True)
  for unit,state in data.get('services',{}).items():
   if state['enabled']:run('systemctl','enable',unit,required=True)
   if state['active'] and os.environ.get('PI_HOTSPOT_BOOT_RECOVERY')!='1':run('systemctl','start',unit,required=True)
  for device,ident in data.get('connections',{}).items():
   run('nmcli','--wait','30','connection','up','uuid',ident,'ifname',device,required=True)
 clear_marker(directory)
 print('Wiederhergestellt:',directory)


if __name__=='__main__':
 if os.geteuid()!=0:raise SystemExit('sudo erforderlich')
 restore(sys.argv[1],watchdog='--watchdog' in sys.argv[2:])
