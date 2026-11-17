#!/usr/bin/env python3
"""Interactive Raspberry Pi installer. No third-party Python dependencies."""
import argparse
import configparser
import sqlite3
import ssl
from contextlib import closing
from urllib.request import urlopen
import copy
import getpass
import ipaddress
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time
import uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'qspot'))
sys.path.insert(0,str(ROOT/'installer'))
from common import DEFAULT, atomic, password_hash, validate, rpc
from branding import certificate_names, identity
from drivers import prepare as prepare_drivers
import runtime

PACKAGES=['iw','hostapd','dnsmasq-base','nftables','wireguard-tools','iproute2',
          'conntrack','python3-flask','python3-cryptography','openssl',
          'avahi-daemon','network-manager','rfkill','ca-certificates','git']
UNITS=['qspot-net.service','qspot-web.service','qspot-hostapd.service','qspot-dns@.service']
TARGETS=['/opt/qspot','/etc/qspot','/var/lib/qspot','/var/lib/qspot-web',
         '/etc/NetworkManager/system-connections','/etc/NetworkManager/conf.d/90-pi-hotspot.conf',
         '/etc/sysctl.d/90-pi-hotspot.conf','/etc/avahi/hosts','/etc/hostname','/etc/hosts','/usr/local/bin/pi-hotspot']+['/etc/systemd/system/'+u for u in UNITS]


command=runtime.command


def ask(label,default=None,secret=False):
 suffix=f' [{default}]' if default is not None and not secret else ''
 value=(getpass.getpass if secret else input)(label+suffix+': ')
 if not secret:value=value.strip()
 return value or (default if default is not None else '')


def ask_int(label,minimum,maximum,default):
 while True:
  value=ask(label,str(default))
  if value.isdecimal() and minimum<=int(value)<=maximum:return int(value)
  print(f'{minimum}–{maximum}')


def validate_uplink(wifi):
 if wifi is None:return
 ssid=wifi.get('ssid','')
 if not isinstance(ssid,str) or not 1<=len(ssid.encode())<=32 or any(ord(ch)<32 for ch in ssid):raise ValueError('Ungültige Uplink-SSID')
 security=wifi.get('security');password=wifi.get('password','')
 if security=='WPA2/WPA3 Personal':
  if not (8<=len(password)<=63 or re.fullmatch(r'[a-fA-F0-9]{64}',password)):raise ValueError('WLAN-Passwort: 8–63 Zeichen oder 64 Hex-Zeichen')
 elif security=='WPA2 Enterprise (PEAP/MSCHAPv2)':
  from branding import domain
  domain(wifi.get('domain',''))
  if not wifi.get('identity') or not password:raise ValueError('Enterprise-Zugangsdaten fehlen')
  if wifi.get('ca'):ssl.create_default_context(cafile=wifi['ca'])
 elif security!='Offen':raise ValueError('Unbekannte WLAN-Sicherheitsart')


def yes(label,default=True):
 while True:
  value=ask(label+' (j/n)','j' if default else 'n').lower()
  if value in ('j','ja','y','yes'):return True
  if value in ('n','nein','no'):return False


def choose(label,items,default=0):
 if not items:raise ValueError('Keine passenden Schnittstellen gefunden: '+label)
 print('\n'+label)
 for i,value in enumerate(items,1):print(f'  {i}. {value}')
 while True:
  value=ask('Auswahl',str(default+1))
  if value.isdigit() and 1<=int(value)<=len(items):return items[int(value)-1]


def preflight(allow_installed=False):
 if platform.system()!='Linux' or platform.machine() not in ('aarch64','arm64'):
  raise ValueError('Erforderlich: Raspberry Pi OS Lite 64 Bit (aarch64)')
 release=Path('/etc/os-release').read_text()
 if not re.search(r'^VERSION_ID="?(12|13)"?$',release,re.M):
  raise ValueError('Unterstützte Basis: Raspberry Pi OS Bookworm (12) oder Trixie (13)')
 modelpath=Path('/proc/device-tree/model')
 model=modelpath.read_text().rstrip('\0') if modelpath.exists() else ''
 if not re.search(r'Raspberry Pi (3 Model B|4 Model B|5 Model B)',model):
  raise ValueError('Zielhardware: Raspberry Pi 3B/3B+, 4B oder 5B')
 for executable in ('nmcli','iw','ip','systemctl'):
  if not shutil.which(executable):raise ValueError(executable+' fehlt. Bitte ein frisches Raspberry Pi OS Lite verwenden.')
 if command('systemctl','is-active','NetworkManager',check=False,quiet=True)!='active':
  raise ValueError('NetworkManager muss aktiv sein')
 if Path('/var/lib/qspot/config.json').exists() and not allow_installed:
  raise ValueError('Bereits installiert. Updates: sudo pi-hotspot update; neu konfigurieren: sudo pi-hotspot configure')
 if not hasattr(tarfile,'data_filter'):raise ValueError('Python-Sicherheitsupdates fehlen (tarfile.data_filter)')
 if shutil.disk_usage('/').free<1024**3:raise ValueError('Mindestens 1 GB freier Speicher erforderlich')
 if os.statvfs('/').f_flag&os.ST_RDONLY:raise ValueError('Root-Dateisystem ist schreibgesch?tzt')
 if (runtime.STATE/'transaction.json').exists():raise ValueError('Offene Wiederherstellung: sudo pi-hotspot recover')
 return model


def collect(existing=None,old_platform=None,existing_auth=None):
 c={**copy.deepcopy(DEFAULT),**(existing or {})}
 c['features']={**DEFAULT['features'],**c.get('features',{})}
 old_platform=old_platform or {}
 names=[p.name for p in Path('/sys/class/net').iterdir() if p.name not in ('lo','qspot-ap','qspot-wg')]
 radios=[n for n in names if (Path('/sys/class/net')/n/'phy80211').exists()]
 mode=choose('Internetquelle',['LAN','WLAN mit separatem Hotspot-Adapter','WLAN + Hotspot auf einem Adapter (experimentell)'],default={'lan':0,'dual':1,'single':2}.get(old_platform.get('mode'),0))
 mode={'LAN':'lan','WLAN mit separatem Hotspot-Adapter':'dual','WLAN + Hotspot auf einem Adapter (experimentell)':'single'}[mode]
 uplink=choose('Uplink-Schnittstelle',[n for n in names if n not in radios] if mode=='lan' else radios)
 radio=choose('Hotspot-WLAN-Adapter',[n for n in radios if mode!='dual' or n!=uplink]) if mode!='single' else uplink
 p={'mode':mode,'uplink':uplink,'radio':radio,'ap':'qspot-ap' if mode=='single' else radio}
 caps=command('iw','phy','phy'+(Path('/sys/class/net')/radio/'phy80211'/'index').read_text().strip(),'info',quiet=True)
 if not re.search(r'^\s*\* AP\s*$',caps,re.M):raise ValueError('Der gewählte Treiber meldet keinen AP-Modus')
 if mode=='single':
  print('Experimentell: AP+STA muss vom Treiber gleichzeitig unterstützt werden. Nur 2,4 GHz, gleicher Kanal. Uplink-Kanalwechsel kann den Hotspot unterbrechen.')
  if 'valid interface combinations' not in caps or 'managed' not in caps:
   raise ValueError('Treiber meldet keine gleichzeitigen Interface-Kombinationen')
 c['hostname']=ask('Lokaler Hostname',c['hostname'])
 c['brand_name']=ask('Anzeigename',c['brand_name'])
 c['portal_domain']=ask('Portal-Domain',c.get('portal_domain',c['hostname']+'.local'))
 c['ssid']=ask('Hotspot-Name',c['ssid'] if existing else c['brand_name'])
 c['channel']=ask_int('Hotspot-Kanal',1,11,c['channel'])
 c['guest']=ask('Hotspot-IP mit /24',c['guest'])
 access_default=(3 if c['portal_mode']=='code' else 0) if c.get('ap_password') else (2 if c['portal_mode']=='code' else 1)
 access=choose('Hotspot-Zugang',['WLAN-Passwort + Portal','Offenes WLAN + Portal','Offenes WLAN + Voucher','WLAN-Passwort + Voucher'],default=access_default if existing else 0)
 if access.startswith('WLAN-Passwort'):
  c['ap_password']=ask('Hotspot-Passwort (8–63 ASCII-Zeichen)',default=c.get('ap_password','') if existing else None,secret=True)
  if not c['ap_password']:raise ValueError('Hotspot-Passwort fehlt')
 else:c['ap_password']=''
 c['portal_mode']='code' if 'Voucher' in access else 'both' if yes('Zusätzlich Voucher im Portal anbieten?',c['portal_mode']=='both' if existing else False) else 'accept'
 if not existing:c['terms']='Nutze den Zugang verantwortungsbewusst. '+('Die WLAN-Funkstrecke ist unverschlüsselt; nutze HTTPS.' if not c['ap_password'] else 'Die WLAN-Funkstrecke ist mit WPA2 geschützt.')
 c['title']=ask('Titel im Portal',c['title'] if existing else c['brand_name'])
 for key,label in [('chat','Chat mit Wort- und Linkfilter'),('singleplayer','Singleplayer-Games'),('multiplayer','Multiplayer-Games mit Lobbys'),('vpn','Mullvad/WireGuard-Unterstützung')]:
  c['features'][key]=yes(label+' installieren?',c['features'][key])
 c['dns_logging']=yes('DNS-Domain-Logs aktivieren?',c['dns_logging'])
 if c['dns_logging']:c['dns_retention_hours']=ask_int('Aufbewahrung (Stunden)',1,168,c['dns_retention_hours'])
 wifi=None
 if mode!='lan' and yes('WLAN-Uplink jetzt konfigurieren?',existing is None):
  security=choose('Sicherheit des Internet-WLANs',['WPA2/WPA3 Personal','WPA2 Enterprise (PEAP/MSCHAPv2)','Offen'])
  wifi={'ssid':ask('SSID des Internet-WLANs'),'security':security,'password':'','identity':'','ca':'','domain':''}
  if security!='Offen':wifi['password']=ask('WLAN-Zugangspasswort',secret=True)
  if 'Enterprise' in security:
   wifi['identity']=ask('Enterprise-Benutzername')
   wifi['ca']=ask('Pfad zum CA-Zertifikat (leer = System-Zertifikate)')
   wifi['domain']=ask('Server-Domain zur Zertifikatsprüfung (z.B. radius.example.org)')
   if not wifi['identity'] or not re.fullmatch(r'[A-Za-z0-9.-]+',wifi['domain']):raise ValueError('Benutzername und vertrauenswürdige Server-Domain erforderlich')
   if wifi['ca'] and not Path(wifi['ca']).is_file():raise ValueError('CA-Datei nicht gefunden')
 vpn=None
 if not c['features']['vpn']:c['vpn']='off'
 if c['features']['vpn']:
  path=ask('Pfad zur Mullvad-WireGuard-.conf (leer = später im Dashboard importieren)')
  if path:
   from network import import_wireguard
   vpn=import_wireguard(Path(path).read_text());c['vpn_server']='mullvad'
   c['vpn']='both' if yes('VPN nach der Installation einschalten?',False) else 'off'
 password=ask('Admin-Passwort (leer = beibehalten)' if existing_auth else 'Neues Admin-Passwort (mindestens 8 Zeichen)',secret=True)
 if not password and existing_auth:auth=existing_auth
 else:
  if password!=ask('Admin-Passwort wiederholen',secret=True):raise ValueError('Passwörter stimmen nicht überein')
  auth={'password':password_hash(password),'totp':''}
 validate_uplink(wifi)
 if existing:
  from branding import renamed_config
  c=renamed_config(existing,c)
 for key in ('uplink','radio'):
  address=Path('/sys/class/net')/p[key]/'address'
  if address.exists():p[key+'_mac']=address.read_text().strip()
 routes=json.loads(command('ip','-j','-4','route','show','table','main',quiet=True))
 validate(c,routes)
 return c,p,wifi,vpn,auth


def backup():
 base=Path('/var/backups/pi-hotspot')
 target=base/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
 target.mkdir(parents=True,mode=0o700);target.chmod(0o700)
 present=[p for p in TARGETS if Path(p).exists()]
 services={u:{'enabled':command('systemctl','is-enabled',u,check=False,quiet=True)=='enabled','active':command('systemctl','is-active',u,check=False,quiet=True)=='active'} for u in ('qspot-net','qspot-web','avahi-daemon')}
 sysctls={k:command('sysctl','-n',k,check=False,quiet=True) for k in ('net.ipv4.ip_forward','net.ipv4.conf.all.rp_filter')}
 active=json.loads(command('ip','-j','link','show',quiet=True))
 connections={}
 for device in active:
  if device['ifname'] in ('lo','qspot-ap','qspot-wg') or device['ifname'].startswith(('veth','docker','br-')):continue
  ident=command('nmcli','-g','GENERAL.CON-UUID','device','show',device['ifname'],check=False,quiet=True)
  if re.fullmatch(r'[a-fA-F0-9-]{36}',ident):connections[device['ifname']]=ident
 database=Path('/var/lib/qspot/router.sqlite');snapshot=target/'router.snapshot.sqlite'
 try:
  if database.exists():
   sqlite_snapshot(database,snapshot)
   snapshot.chmod(0o600)
  with tarfile.open(target/'files.tar.gz','w:gz') as archive:
   for path in present:
    archive.add(path,arcname=path.lstrip('/'),filter=lambda m:None if m.name in ('var/lib/qspot/router.sqlite','var/lib/qspot/router.sqlite-wal','var/lib/qspot/router.sqlite-shm','var/lib/qspot/router.sqlite-journal') else m)
   if snapshot.exists():archive.add(snapshot,arcname='var/lib/qspot/router.sqlite')
  (target/'files.tar.gz').chmod(0o600)
  atomic(target/'manifest.json',{'version':2,'present':present,'targets':TARGETS,'services':services,'sysctl':sysctls,'connections':connections,'sha256':runtime.digest(target/'files.tar.gz')})
  shutil.copy2(ROOT/'installer'/'rollback.py',target/'rollback.py')
  from rollback import validate_snapshot
  validate_snapshot(target)
 finally:snapshot.unlink(missing_ok=True)
 return target


def sqlite_snapshot(database,destination):
 with closing(sqlite3.connect(Path(database).as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(destination)) as dest:src.backup(dest)


def write_text(path,text,mode=0o644):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text);path.chmod(mode)


def wait_ready(seconds=90):
 for unit in ('qspot-net','qspot-web','avahi-daemon'):
  if command('systemctl','is-enabled',unit,check=False,quiet=True)!='enabled':raise RuntimeError('Autostart fehlt: '+unit)
 deadline=time.monotonic()+seconds
 while time.monotonic()<deadline:
  units=('qspot-net','qspot-web','qspot-hostapd','qspot-dns@guest')
  if all(command('systemctl','is-active',u,check=False,quiet=True)=='active' for u in units):
   try:
    status=rpc('status')
    if not status.get('error'):
     context=ssl.create_default_context(cafile='/etc/qspot/tls/cert.pem');context.check_hostname=False
     with urlopen('https://127.0.0.1:8443/api/auth',context=context,timeout=3) as response:
      if json.load(response).get('setup'):raise ValueError('Admin-Zugang fehlt')
     with urlopen('https://127.0.0.1:8443/admin',context=context,timeout=3) as response:
      if response.status==200:return
   except (ValueError,OSError):pass
  time.sleep(2)
 raise RuntimeError('Dienste wurden nicht rechtzeitig bereit; Diagnose: journalctl -u qspot-net')


def configure_uplink(wifi,p):
 if wifi is None:return
 validate_uplink(wifi)
 parser=configparser.ConfigParser(interpolation=None)
 ident=str(uuid.uuid4())
 parser['connection']={'id':'pi-hotspot-uplink','uuid':ident,'type':'wifi','interface-name':p['uplink'],'autoconnect':'true','autoconnect-priority':'100'}
 parser['wifi']={'ssid':wifi['ssid'],'mode':'infrastructure','powersave':'2'}
 if p['mode']=='single':parser['wifi']['band']='bg'
 parser['ipv4']={'method':'auto'};parser['ipv6']={'method':'auto'}
 if 'Personal' in wifi['security']:
  parser['wifi-security']={'key-mgmt':'wpa-psk','psk':wifi['password']}
 elif 'Enterprise' in wifi['security']:
  parser['wifi-security']={'key-mgmt':'wpa-eap'}
  parser['802-1x']={'eap':'peap;','identity':wifi['identity'],'password':wifi['password'],'phase2-auth':'mschapv2','domain-suffix-match':wifi['domain']}
  if wifi['ca']:
   shutil.copy2(wifi['ca'],'/etc/qspot/uplink-ca.pem');parser['802-1x']['ca-cert']='/etc/qspot/uplink-ca.pem'
  else:parser['802-1x']['system-ca-certs']='true'
 target=Path('/etc/NetworkManager/system-connections/pi-hotspot-uplink.nmconnection')
 with target.open('w') as f:
  os.chmod(target,0o600);parser.write(f,space_around_delimiters=False)
 command('nmcli','connection','load',str(target))
 command('nmcli','--wait','45','connection','up','uuid',ident)


def install(c,p,wifi,vpn,auth):
 import grp
 if not (ROOT/'qspot/static/app/index.html').is_file():raise ValueError('Weboberfläche fehlt im Installationspaket')
 saved=backup();print('Sicherung:',saved)
 runtime.begin(saved,'install',ROOT)
 committed=False
 try:
  runtime.stage('Pakete installieren')
  if command('dpkg','--audit',quiet=True):command('dpkg','--configure','-a',timeout=1800)
  runtime.apt('update');runtime.apt('install','-y','--no-install-recommends',*PACKAGES)
  for module in ('wireguard','sch_htb','cls_u32','sch_fq_codel'):command('modprobe',module)
  runtime.stage('Dienste anhalten')
  command('systemctl','stop','qspot-web','qspot-net','qspot-hostapd','qspot-dns@guest',check=False)
  if command('id','-u','qspot',check=False,quiet=True)=='':
   command('useradd','--system','--home-dir','/var/lib/qspot-web','--shell','/usr/sbin/nologin','qspot')
  runtime.stage('Dateien und Zugang einrichten')
  for directory in ('/opt/qspot','/etc/qspot/tls','/var/lib/qspot','/var/lib/qspot/vpn','/var/lib/qspot-web'):
   Path(directory).mkdir(parents=True,exist_ok=True)
  for name in ('qspot','system','installer'):
   if (ROOT/name).resolve()!=(Path('/opt/qspot')/name).resolve():shutil.copytree(ROOT/name,Path('/opt/qspot')/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
  if (ROOT/'install.sh').resolve()!=Path('/opt/qspot/install.sh'):shutil.copy2(ROOT/'install.sh','/opt/qspot/install.sh')
  write_text('/opt/qspot/SOURCE',command('git','-C',str(ROOT),'rev-parse','HEAD',check=False,quiet=True) or 'archive-main')
  write_text('/usr/local/bin/pi-hotspot',(ROOT/'installer'/'pi-hotspot').read_text(),0o755)
  os.chmod('/var/lib/qspot',0o700);os.chmod('/var/lib/qspot/vpn',0o700)
  atomic('/etc/qspot/platform.json',p)
  atomic('/var/lib/qspot/config.json',c)
  if vpn:atomic('/var/lib/qspot/vpn/mullvad.json',vpn)
  atomic('/var/lib/qspot-web/auth.json',auth)
  qgid=grp.getgrnam('qspot').gr_gid
  shutil.chown('/var/lib/qspot-web',user='qspot',group='qspot');os.chmod('/var/lib/qspot-web',0o700)
  shutil.chown('/var/lib/qspot-web/auth.json',user='qspot',group='qspot')
  command('openssl','req','-x509','-newkey','rsa:3072','-sha256','-nodes','-days','365',
          '-keyout','/etc/qspot/tls/key.pem','-out','/etc/qspot/tls/cert.pem','-subj','/CN='+c['hostname']+'.local',
          '-addext','subjectAltName='+certificate_names(c))
  atomic('/etc/qspot/tls/identity.json',{'names':certificate_names(c)})
  for name in ('key.pem','cert.pem'):
   path=Path('/etc/qspot/tls')/name;os.chown(path,0,qgid);path.chmod(0o640)
  for unit in UNITS:shutil.copy2(ROOT/'system'/unit,Path('/etc/systemd/system')/unit)
  write_text('/etc/NetworkManager/conf.d/90-pi-hotspot.conf',f'[keyfile]\nunmanaged-devices=interface-name:{p["ap"]}\n')
  write_text('/etc/sysctl.d/90-pi-hotspot.conf','net.ipv4.ip_forward=1\nnet.ipv4.conf.all.rp_filter=2\n')
  runtime.stage('Netzwerk einrichten')
  command('rfkill','unblock','wifi')
  command('nmcli','general','reload');configure_uplink(wifi,p)
  defaults=json.loads(command('ip','-j','-4','route','show','default','dev',p['uplink'],quiet=True))
  if not defaults:raise RuntimeError('Der gewählte Uplink hat keine IPv4-Standardroute')
  ident=command('nmcli','-g','GENERAL.CON-UUID','device','show',p['uplink'],check=False,quiet=True)
  if re.fullmatch(r'[a-fA-F0-9-]{36}',ident):command('nmcli','connection','modify','uuid',ident,'connection.autoconnect','yes')
  command('hostnamectl','set-hostname',c['hostname'])
  hosts=Path('/etc/hosts').read_text()
  hosts=re.sub(r'^127\.0\.1\.1\s+.*$', '127.0.1.1\t'+c['hostname'],hosts,flags=re.M)
  if not re.search(r'^127\.0\.1\.1\s',hosts,re.M):hosts+='\n127.0.1.1\t'+c['hostname']+'\n'
  write_text('/etc/hosts',hosts)
  runtime.stage('Autostart und Dienste pr?fen')
  command('systemctl','daemon-reload');command('systemctl','enable','qspot-net','qspot-web','avahi-daemon')
  command('systemctl','restart','avahi-daemon');command('systemctl','start','qspot-net','qspot-web')
  wait_ready()
  runtime.finish();committed=True
  print('\nBereit: https://'+c['portal_domain']+'/admin')
  print('Hotspot: '+c['ssid']+' | IP: '+str(ipaddress.ip_interface(c['guest']).ip))
  print('Lokales selbstsigniertes Zertifikat: Fingerabdruck am Pi prüfen und im Browser vertrauen.')
  command('openssl','x509','-in','/etc/qspot/tls/cert.pem','-noout','-fingerprint','-sha256')
  print('Sicherung/Rückkehr: sudo python3 '+str(saved/'rollback.py')+' '+str(saved))
 except BaseException:
  if committed:raise
  print('Installation fehlgeschlagen; vorherige Konfiguration wird wiederhergestellt.',file=sys.stderr)
  result=command('python3',str(saved/'rollback.py'),str(saved),check=False)
  if result==0:command('systemctl','stop','pi-hotspot-transaction-rollback.timer',check=False)
  else:print('Automatische Wiederherstellung fehlgeschlagen. Sicherung: '+str(saved),file=sys.stderr)
  raise


def main():
 parser=argparse.ArgumentParser(description='pi-hotspot: interaktive Raspberry-Pi-Einrichtung')
 parser.add_argument('--check',action='store_true',help='Nur Hardware und Betriebssystem prüfen')
 parser.add_argument('--reconfigure',action='store_true',help='Bestehende Installation neu konfigurieren')
 args=parser.parse_args()
 os.umask(0o022)
 if os.geteuid()!=0:raise ValueError('Bitte mit sudo starten')
 if args.reconfigure:
  print('Neu-Konfiguration fragt Einstellungen vollständig neu ab; bisherige Daten werden vorher gesichert.')
  if not Path('/var/lib/qspot/config.json').exists():raise ValueError('Noch nicht installiert')
  model=preflight(allow_installed=True)
 else:model=preflight()
 print('pi-hotspot | '+model)
 if args.check:return
 prepare_drivers(yes,choose)
 old=json.loads(Path('/var/lib/qspot/config.json').read_text()) if args.reconfigure else None
 old_platform=json.loads(Path('/etc/qspot/platform.json').read_text()) if args.reconfigure else None
 old_auth=json.loads(Path('/var/lib/qspot-web/auth.json').read_text()) if args.reconfigure and Path('/var/lib/qspot-web/auth.json').exists() else None
 c,p,wifi,vpn,auth=collect(old,old_platform,old_auth)
 print('\nZusammenfassung (keine Passwörter):')
 print(json.dumps({'plattform':p,'hotspot':c['ssid'],'zugang':c['portal_mode'],
                   'funktionen':c['features'],'dns_logs':c['dns_logging'],
                   'aufbewahrung_stunden':c['dns_retention_hours'],'vpn_start':c['vpn'],
                   'verwaltung':c['portal_domain'],'name':c['brand_name'],'datenvolumen':'unbegrenzt'},ensure_ascii=False,indent=2))
 print('Richtet Pakete, NetworkManager, Hotspot, DHCP/DNS, Firewall, Dienste und lokalen Admin ein. Netzwerk/SSH kann kurz unterbrochen werden.')
 if not yes('Diese Konfiguration nach Sicherung anwenden?',False):print('Abgebrochen.');return
 install(c,p,wifi,vpn,auth)


if __name__=='__main__':
 try:
  with runtime.exclusive():main()
 except (ValueError,RuntimeError,OSError,KeyboardInterrupt,EOFError,tarfile.TarError) as e:
  print('Fehler: '+str(e),file=sys.stderr);sys.exit(1)
