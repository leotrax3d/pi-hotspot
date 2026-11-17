#!/usr/bin/python3
"""Offline encrypted restore. Validates all data before stopping services."""
import base64, getpass, hashlib, ipaddress, json, os, re, sqlite3, subprocess, sys
from pathlib import Path
sys.path.insert(0,'/opt/qspot/qspot')
from common import atomic, validate, STATE
from network import import_wireguard
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
if os.geteuid()!=0: raise SystemExit('sudo erforderlich')
raw=base64.b64decode(Path(sys.argv[1]).read_text(),validate=True)
if raw[:6]!=b'QSPOT1':raise SystemExit('Unbekanntes Sicherungsformat')
password=getpass.getpass('Sicherungspasswort: ')
key=hashlib.scrypt(password.encode(),salt=raw[6:22],n=16384,r=8,p=1,dklen=32)
data=json.loads(AESGCM(key).decrypt(raw[22:34],raw[34:],b'QSpot backup v1'))
config=validate(data['config'])
vpns={}
for name,v in data['vpn'].items():
 if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',name):raise ValueError('Ungültiger VPN-Name')
 text=f'[Interface]\nPrivateKey={v["private"]}\nAddress={",".join(v["addresses"])}\n[Peer]\nPublicKey={v["public"]}\nEndpoint={v["endpoint"]}\nAllowedIPs=0.0.0.0/0\n'
 vpns[name]=import_wireguard(text)
for s in data['sessions']:
 if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}',s['mac']) or not 1<=int(s['id'])<=60000 or not 0<=int(s['used'])<=10**16:raise ValueError('Ungültige Sitzung')
 ipaddress.IPv4Address(s['ip'])
for c in data['codes']:
 if not re.fullmatch(r'[0-9a-f]{64}',c['digest']) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',c['profile']):raise ValueError('Ungültiger Code')
for b in data['blocked']:
 if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}',b['mac']):raise ValueError('Ungültige Sperre')
if config['vpn']!='off' and config['vpn_server'] not in vpns:raise ValueError('VPN-Konfiguration fehlt')
subprocess.run(['systemctl','stop','qspot-net','qspot-web'],check=True)
backup=Path('/var/backups/qspot/before-restore');backup.mkdir(exist_ok=True,mode=0o700)
import shutil
for name in ('config.json','router.sqlite'):
 shutil.copy2(STATE/name,backup/name)
shutil.copytree(STATE/'vpn',backup/'vpn',dirs_exist_ok=True)
try:
 db=sqlite3.connect(STATE/'router.sqlite')
 with db:
  db.execute('DELETE FROM sessions');db.execute('DELETE FROM codes');db.execute('DELETE FROM blocked')
  for c in data['codes']:db.execute('INSERT INTO codes VALUES(?,?,?,?,?,?,?,?)',tuple(c[k] for k in ('id','digest','label','profile','expires','duration','first','revoked')))
  for s in data['sessions']:db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,0,0,?,?)',(s['id'],s['mac'],s['ip'],s['profile'],s['code_id'],s['started'],s['used'],'Aus Sicherung wiederhergestellt; erneut anmelden'))
  for b in data['blocked']:db.execute('INSERT INTO blocked VALUES(?)',(b['mac'],))
 db.close();atomic(STATE/'config.json',config)
 for name,v in vpns.items():atomic(STATE/'vpn'/f'{name}.json',v)
 subprocess.run(['systemctl','start','qspot-net','qspot-web'],check=True)
 print('Wiederhergestellt. Bestehendes Adminpasswort bleibt erhalten. Sitzungen sind widerrufen. Vorzustand: '+str(backup))
except Exception:
 for name in ('config.json','router.sqlite'):shutil.copy2(backup/name,STATE/name)
 shutil.copytree(backup/'vpn',STATE/'vpn',dirs_exist_ok=True)
 subprocess.run(['systemctl','start','qspot-net','qspot-web'])
 raise
