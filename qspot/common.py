import base64, hashlib, hmac, ipaddress, json, os, re, secrets, socket, subprocess, time
from pathlib import Path

STATE = Path(os.environ.get('QSPOT_STATE', '/var/lib/qspot'))
DEFAULT = {
 'hostname':'pi-hotspot', 'ssid':'SchülerWLAN', 'channel':6, 'country':'DE',
 'brand_name':'SchülerWLAN', 'portal_domain':'pi-hotspot.local',
 'guest':'10.77.0.1/24', 'usb':'10.78.0.1/24', 'portal_mode':'both',
 'title':'Willkommen im SchülerWLAN', 'description':'',
 'accept_text':'Ich akzeptiere die Nutzungsbedingungen.', 'terms':'Offenes WLAN: Die Funkstrecke ist unverschlüsselt. Nutze HTTPS.',
 'profiles':{'standard':{'down_kbit':0,'up_kbit':0,'seconds':0,'bytes':0,'devices':0,'concurrent':0}},
 'default_profile':'standard', 'global_down_kbit':0, 'global_up_kbit':0,
 'usb_down_kbit':0,'usb_up_kbit':0, 'vpn':'off','vpn_server':'',
 'ap_password':'', 'vpn_bypass':[], 'dns_logging':False, 'dns_retention_hours':24,
 'features':{'chat':True,'singleplayer':True,'multiplayer':True,'vpn':True,'pihole':False},
 'onboarding_complete':True,
 'matrix':{'enabled':False,'brightness':2,'reduce_motion':False,'night_start':'22:00','night_end':'07:00','timezone':'Europe/Berlin'},
}
def atomic(path, obj, mode=0o600):
 path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_name(path.name+'.new')
 with open(tmp,'w') as f:
  os.chmod(tmp,mode); json.dump(obj,f,ensure_ascii=False); f.flush(); os.fsync(f.fileno())
 os.replace(tmp,path)
 fd=os.open(path.parent,os.O_DIRECTORY); os.fsync(fd); os.close(fd)

def run(*args, input=None, timeout=20, check=True):
 p=subprocess.run(args,input=input,text=True,capture_output=True,timeout=timeout)
 if check and p.returncode: raise ValueError(f'{args[0]}: Aktion fehlgeschlagen ({p.returncode})')
 return p.stdout.strip()

def validate(c, routes=()):
 from branding import domain
 c['portal_domain']=domain(c.get('portal_domain',c['hostname']+'.local'))
 brand=c.get('brand_name','SchülerWLAN')
 if not isinstance(brand,str) or not 1<=len(brand)<=48 or any(ord(x)<32 or ord(x)==127 for x in brand):raise ValueError('Anzeigename: 1–48 Zeichen')
 c['brand_name']=brand
 if c.get('ap_password') and not re.fullmatch(r'[\x20-\x7e]{8,63}',c['ap_password']):raise ValueError('Hotspot-Passwort: 8–63 druckbare ASCII-Zeichen')
 if type(c.get('dns_logging',False)) is not bool:raise ValueError('DNS-Logging muss wahr oder falsch sein')
 if type(c.get('dns_retention_hours',24)) is not int or not 1<=c.get('dns_retention_hours',24)<=168:raise ValueError('DNS-Aufbewahrung: 1–168 Stunden')
 if not isinstance(c.get('vpn_bypass',[]),list) or len(c.get('vpn_bypass',[]))>1000 or any(not isinstance(x,str) or not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}',x) for x in c.get('vpn_bypass',[])):raise ValueError('Ungültige VPN-Geräteauswahl')
 features=c.get('features',{})
 if not isinstance(features,dict) or set(features)-{'chat','singleplayer','multiplayer','vpn','pihole'} or any(type(x) is not bool for x in features.values()):raise ValueError('Ungültige Funktionsauswahl')
 if not re.fullmatch(r'[a-z][a-z0-9-]{0,61}[a-z0-9]|[a-z]', c['hostname']): raise ValueError('Ungültiger Hostname')
 if not 1<=len(c['ssid'].encode())<=32 or any(ord(x)<32 for x in c['ssid']): raise ValueError('Ungültige SSID')
 if c['country']!='DE' or c['channel'] not in range(1,12): raise ValueError('Diese Installation unterstützt DE und Kanal 1–11')
 nets=[]
 for key in ('guest','usb'):
  i=ipaddress.ip_interface(c[key])
  if i.version!=4 or i.network.prefixlen!=24 or not i.ip.is_private or i.ip in (i.network.network_address,i.network.broadcast_address): raise ValueError('Private IPv4-/24-Netze erforderlich')
  nets.append(i.network)
 if nets[0].overlaps(nets[1]): raise ValueError('Gast- und USB-Netz überschneiden sich')
 for r in routes:
  from platform_config import load
  if r.get('dev') in ('qspot-ap','usb0',load()['ap']) or r.get('dst','default')=='default': continue
  n=ipaddress.ip_network(r['dst'],strict=False)
  if n.version==4 and any(n.overlaps(x) for x in nets): raise ValueError('Netzüberschneidung mit '+str(n))
 if c['portal_mode'] not in ('both','accept','code') or c['vpn'] not in ('off','guest','usb','both'): raise ValueError('Ungültiger Modus')
 if c['default_profile'] not in c['profiles']: raise ValueError('Standardprofil fehlt')
 if not 1<=len(c['profiles'])<=100: raise ValueError('1–100 Profile erforderlich')
 for name,p in c['profiles'].items():
  if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',name): raise ValueError('Ungültiger Profilname')
  for k in ('down_kbit','up_kbit','seconds','bytes','devices','concurrent'):
   if type(p[k])!=int or not 0<=p[k]<=10**13: raise ValueError('Limits: 0 bedeutet unbegrenzt; nur positive Ganzzahlen')
 for k in ('global_down_kbit','global_up_kbit','usb_down_kbit','usb_up_kbit'):
  if type(c[k])!=int or not 0<=c[k]<=1000000: raise ValueError('Ungültiges Bandbreitenlimit')
 for k in ('title','description','accept_text','terms'):
  if not isinstance(c[k],str) or len(c[k])>10000: raise ValueError('Text zu lang')
 m=c['matrix']
 if type(m['brightness'])!=int or not 0<=m['brightness']<=7: raise ValueError('Helligkeit: 0–7')
 for k in ('night_start','night_end'):
  if not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]',m[k]): raise ValueError('Nachtzeit: HH:MM')
 return c

def password_hash(password):
 if len(password)<8: raise ValueError('Mindestens 8 Zeichen für das Adminpasswort')
 salt=secrets.token_bytes(16)
 return salt.hex()+':'+hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1).hex()
def password_ok(password, stored):
 try:
  salt,key=stored.split(':'); value=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1)
  return hmac.compare_digest(value.hex(),key)
 except (ValueError,TypeError): return False
def totp(secret, value, now=None):
 if not re.fullmatch(r'\d{6}',str(value)): return False
 counter=int((now or time.time())//30)
 for n in (-1,0,1):
  d=hmac.new(base64.b32decode(secret), (counter+n).to_bytes(8,'big'),hashlib.sha1).digest(); o=d[-1]&15
  if hmac.compare_digest(str((int.from_bytes(d[o:o+4],'big')&0x7fffffff)%1000000).zfill(6),str(value)): return True
 return False
def rpc(method, **data):
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(45); s.connect('/run/qspot/control.sock'); s.sendall(json.dumps({'method':method,**data}).encode()+b'\n')
  f=s.makefile('rb'); result=json.loads(f.readline(2*1024*1024))
  if 'error' in result: raise ValueError(result['error'])
  return result['result']
