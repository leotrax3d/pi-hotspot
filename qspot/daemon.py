import copy, hashlib, ipaddress, json, os, re, secrets, socketserver, sqlite3, threading, time
from pathlib import Path
from common import STATE, DEFAULT, atomic, run, validate
import network
from branding import identity, portal_url, renamed_config

LOCK=threading.RLock()
CONFIG=STATE/'config.json'
DB=None
START=time.monotonic()
ERROR=''
RECOVERY=[]
RECOVERY_UNTIL=0

def config():
 c=json.loads(CONFIG.read_text());return {**c,**identity(c)}

def restore_sessions(c,active):
 associated=set(network.associated())
 blocked={b['mac'] for b in rows('SELECT * FROM blocked')}
 restored=0
 for s in active:
  p=c['profiles'].get(s['profile'])
  if not p or s['mac'] not in associated or s['mac'] in blocked:continue
  if p['seconds']:
   remaining_seconds=s['started']+p['seconds']-time.time()
   if remaining_seconds<=0:continue
   deadline=time.monotonic()+remaining_seconds
  else:deadline=0
  try:
   mac,ip=peer(s['ip'])
   if mac!=s['mac']:continue
  except ValueError:
   # A dnsmasq restart used to discard its runtime leases. Only recover a
   # previous authorization when both association and current ARP still agree.
   if ipaddress.ip_address(s['ip']) not in ipaddress.ip_interface(c['guest']).network:continue
   neighbors=json.loads(run('ip','-j','neigh','show',s['ip'],'dev',network.AP))
   if not any(n.get('lladdr')==s['mac'] and 'FAILED' not in n.get('state',[]) for n in neighbors):continue
  if s['code_id']:
   codes=rows('SELECT * FROM codes WHERE id=?',(s['code_id'],))
   if not codes:continue
   v=codes[0]
   if v['revoked'] or (v['expires'] and time.time()>=v['expires']) or (v['duration'] and v['first'] and time.time()>=v['first']+v['duration']):continue
  total=DB.execute('SELECT COALESCE(SUM(used),0) FROM sessions WHERE mac=? AND profile=?',(s['mac'],s['profile'])).fetchone()[0]
  if p['bytes'] and total>=p['bytes']:continue
  network.cleanup_session(s['id'])
  network.counter_add(s['id'],s['ip'],p['bytes']-total if p['bytes'] else 0,s['used'])
  network.device_limit(s['ip'],p,s['id']+100,c)
  network.authorize(s['mac'],s['ip'],10)
  sql('UPDATE sessions SET active=1,deadline=?,reason=? WHERE id=?',(deadline,'',s['id']))
  restored+=1
 return restored

def set_vpn(c,enabled,server=None):
 if (STATE/'pending.json').exists():raise ValueError('Netzwerkänderung zuerst bestätigen')
 available=sorted(p.stem for p in (STATE/'vpn').glob('*.json'))
 server=server or c.get('vpn_server') or (available[0] if available else '')
 if enabled and not c.get('features',{}).get('vpn',True):raise ValueError('VPN wurde bei der Installation abgewählt')
 if enabled and server not in available:raise ValueError('Zuerst einen Mullvad-Server importieren')
 updated={**c,'vpn':'both' if enabled else 'off','vpn_server':server}
 active=rows('SELECT * FROM sessions WHERE active=1')
 for s in active:
  s['used']=max(s['used'],network.bytes_used(s['id']))
  sql('UPDATE sessions SET used=? WHERE id=?',(s['used'],s['id']))
 def apply(cfg):
  network.base(cfg);network.vpn(cfg);network.dns(cfg);network.shaping(cfg)
  for b in rows('SELECT * FROM blocked'):network.nft(f'add element inet qspot blocked {{ {b["mac"]} }}')
  for s in active:
   p=cfg['profiles'].get(s['profile'])
   if not p:continue
   total=DB.execute('SELECT COALESCE(SUM(used),0) FROM sessions WHERE mac=? AND profile=?',(s['mac'],s['profile'])).fetchone()[0]
   remaining=max(1,p['bytes']-total) if p['bytes'] else 0
   network.counter_add(s['id'],s['ip'],remaining,s['used'])
   network.device_limit(s['ip'],p,s['id']+100,cfg)
   network.authorize(s['mac'],s['ip'],10)
 try:apply(updated)
 except Exception:
  apply(c);raise
 atomic(CONFIG,updated)
 return {'enabled':enabled,'server':server}
def rows(sql,args=()): return [dict(r) for r in DB.execute(sql,args).fetchall()]
def sql(query,args=()):
 cur=DB.execute(query,args); DB.commit(); return cur
def peer(ip):
 ip=str(ipaddress.IPv4Address(ip)); net=ipaddress.ip_interface(config()['guest']).network
 if ipaddress.ip_address(ip) not in net: raise ValueError('Nur Gäste im Hotspot können sich freischalten')
 leases=Path('/run/qspot-dns-guest/leases')
 if not leases.exists(): raise ValueError('Keine DHCP-Zuordnung gefunden')
 for line in leases.read_text().splitlines():
  v=line.split()
  if len(v)>=3 and v[2]==ip and re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}',v[1]):
   # Verify the current neighbour, rather than trusting a browser-supplied MAC.
   n=json.loads(run('ip','-j','neigh','show',ip,'dev',network.AP))
   if not any(x.get('lladdr')==v[1] and 'FAILED' not in x.get('state',[]) for x in n): raise ValueError('Gerätezuordnung noch nicht verfügbar; erneut versuchen')
   return v[1],ip
 raise ValueError('DHCP-Gerät nicht gefunden')

def end(s,reason):
 used=max(s['used'],network.bytes_used(s['id']))
 sql('UPDATE sessions SET active=0,reason=?,used=? WHERE id=?',(reason,used,s['id']))
 network.revoke(s['mac'],s['ip'])
 network.cleanup_session(s['id'])

def activate(ip,code=None):
 c=config(); mac,ip=peer(ip)
 if rows('SELECT * FROM blocked WHERE mac=?',(mac,)): raise ValueError('Dieses Gerät ist gesperrt')
 current=rows('SELECT * FROM sessions WHERE mac=? AND active=1',(mac,))
 if current: return session_view(current[0])
 voucher=None
 if code:
  if c['portal_mode']=='accept': raise ValueError('Codezugang ist deaktiviert')
  digest=hashlib.sha256(code.strip().upper().encode()).hexdigest()
  found=rows('SELECT * FROM codes WHERE digest=? AND revoked=0',(digest,))
  if not found: raise ValueError('Code ungültig oder widerrufen')
  voucher=found[0]
  if voucher['expires'] and (time.time()<1735689600 or time.time()>=voucher['expires']): raise ValueError('Code abgelaufen oder Systemzeit nicht verlässlich')
  if voucher['duration'] and voucher['first'] and time.time()>=voucher['first']+voucher['duration']: raise ValueError('Nutzungsdauer des Codes abgelaufen')
  name=voucher['profile']
 else:
  if c['portal_mode']=='code': raise ValueError('Zugangscode erforderlich')
  name=c['default_profile']
 p=c['profiles'].get(name)
 if p is None: raise ValueError('Profil existiert nicht mehr')
 if voucher:
  devices=rows('SELECT DISTINCT mac FROM sessions WHERE code_id=?',(voucher['id'],))
  if p['devices'] and mac not in [x['mac'] for x in devices] and len(devices)>=p['devices']: raise ValueError('Gerätelimit dieses Codes erreicht')
  active=rows('SELECT id FROM sessions WHERE code_id=? AND active=1',(voucher['id'],))
  if p['concurrent'] and len(active)>=p['concurrent']: raise ValueError('Zu viele gleichzeitige Sitzungen')
 # A profile quota persists across reconnects for the same randomized MAC.
 used=sum(x['used'] for x in rows('SELECT used FROM sessions WHERE mac=? AND profile=?',(mac,name)))
 if p['bytes'] and used>=p['bytes']: raise ValueError('Datenvolumen aufgebraucht')
 ident=sql('INSERT INTO sessions(mac,ip,profile,code_id,started,deadline,active,used,reason) VALUES(?,?,?,?,?,?,0,0,?)',
  (mac,ip,name,voucher['id'] if voucher else None,time.time(),time.monotonic()+p['seconds'] if p['seconds'] else 0,'wird eingerichtet')).lastrowid
 if ident>60000: raise ValueError('Sitzungstabelle muss gewartet werden')
 try:
  network.counter_add(ident,ip,(p['bytes']-used) if p['bytes'] else 0)
  network.device_limit(ip,p,ident+100,c)
  network.authorize(mac,ip,10)
  sql('UPDATE sessions SET active=1,reason=? WHERE id=?',('',ident))
  if voucher and not voucher['first']: sql('UPDATE codes SET first=? WHERE id=?',(time.time(),voucher['id']))
 except Exception:
  network.revoke(mac,ip); raise
 return session_view(rows('SELECT * FROM sessions WHERE id=?',(ident,))[0])

def session_view(s,c=None,names=None):
 c=c or config()
 p=c['profiles'].get(s['profile'],{})
 if names is None:
  from device_names import hostnames
  names=hostnames()
 return {**s,'hostname':names.get((s['mac'],s['ip']),''),'remaining_seconds':max(0,int(s['deadline']-time.monotonic())) if s['deadline'] else None,'limit_bytes':p.get('bytes',0),'vpn':c['vpn']!='off' and s['mac'] not in c.get('vpn_bypass',[])}

def tick():
 global ERROR, RECOVERY
 while True:
  try:
   with LOCK:
    c=config()
    if RECOVERY and time.monotonic()<RECOVERY_UNTIL:
     restore_sessions(c,RECOVERY)
     live={s['id'] for s in rows('SELECT id FROM sessions WHERE active=1')}
     RECOVERY=[s for s in RECOVERY if s['id'] not in live]
    from activity_log import maintain
    maintain(c)
    if c['vpn']!='off' and not Path('/sys/class/net/qspot-wg').exists():
     network.vpn(c);network.dns(c);network.shaping(c)
    for s in rows('SELECT * FROM sessions WHERE active=1'):
     used=network.bytes_used(s['id']); sql('UPDATE sessions SET used=? WHERE id=?',(used,s['id']))
     p=c['profiles'].get(s['profile'])
     reason=''
     if p is None: reason='Profil gelöscht'
     elif s['deadline'] and time.monotonic()>=s['deadline']: reason='Sitzung abgelaufen'
     elif p['bytes']:
      total=DB.execute('SELECT COALESCE(SUM(used),0) FROM sessions WHERE mac=? AND profile=?',(s['mac'],s['profile'])).fetchone()[0]
      if total>=p['bytes'] or network.exhausted(s['id']): reason='Datenvolumen aufgebraucht'
     if s['code_id']:
      v=rows('SELECT * FROM codes WHERE id=?',(s['code_id'],))[0]
      if v['revoked'] or (v['expires'] and time.time()>=v['expires']) or (v['duration'] and v['first'] and time.time()>=v['first']+v['duration']): reason='Code abgelaufen oder widerrufen'
     if reason: end(s,reason)
     else:
      # Renew short kernel leases; if this daemon dies, access expires in 10 s.
      network.nft(f'destroy element inet qspot allowed {{ {s["mac"]} . {s["ip"]} }}\ndestroy element inet qspot online {{ {s["ip"]} }}\nadd element inet qspot allowed {{ {s["mac"]} . {s["ip"]} timeout 10s }}\nadd element inet qspot online {{ {s["ip"]} timeout 10s }}')
    status=status_data()
    public={'time':time.time(),'uptime':time.monotonic()-START,'guests':status['connected_guests'],'vpn':status['vpn'],'internet':status['internet'],'host_connected':status['host_connected'],'matrix':c['matrix'],'setup':not (Path('/var/lib/qspot-web/auth.json')).exists(),'error':ERROR}
    test=Path('/run/qspot/matrix-test.json')
    if test.exists():
     data=json.loads(test.read_text())
     if data['expires']>time.time():public['matrix_test']=data
    atomic('/run/qspot/status.json',public,0o644)
   ERROR=''
  except Exception as e:
   ERROR=type(e).__name__+': '+str(e)
   # Never leave a stale matrix-ready status on errors.
   try: atomic('/run/qspot/status.json',{'time':time.time(),'error':ERROR,'matrix':config()['matrix']},0o644)
   except Exception: pass
  time.sleep(2)

LAST={}
def status_data():
 c=config(); now=time.monotonic(); rates={}
 from device_names import hostnames
 names=hostnames()
 for dev in (network.WAN,network.AP,'qspot-wg'):
  path=Path('/sys/class/net')/dev/'statistics'
  if not path.exists(): continue
  rx=int((path/'rx_bytes').read_text()); tx=int((path/'tx_bytes').read_text()); old=LAST.get(dev,(rx,tx,now))
  rates[dev]={'rx_bytes':rx,'tx_bytes':tx,'rx_Bps':int((rx-old[0])/max(.1,now-old[2])),'tx_Bps':int((tx-old[1])/max(.1,now-old[2]))}; LAST[dev]=(rx,tx,now)
 mem={}
 for l in Path('/proc/meminfo').read_text().splitlines():
  k,v=l.split(':',1); mem[k]=int(v.strip().split()[0])*1024
 stat=os.statvfs('/')
 handshake=run('wg','show','qspot-wg','latest-handshakes',check=False).split()
 stamp=int(handshake[-1]) if handshake and handshake[-1].isdigit() else 0
 connected=(Path('/sys/class/net')/network.WAN/'operstate').read_text().strip()=='up'
 internet=run('nmcli','-t','-f','CONNECTIVITY','general',check=False)=='full'
 host=run('iw','dev',network.WAN,'link',check=False)
 stations=network.associated()
 started=Path('/run/qspot/vpn-started')
 connecting=started.exists() and time.time()-float(started.read_text())<30
 return {'connected_guests':len(stations),'associated_macs':stations,'host_connected':connected,'internet':internet,'host':host,'rates':rates,'vpn':('off' if c['vpn']=='off' else 'connected' if stamp and time.time()-stamp<180 else 'connecting' if connecting else 'blocked'),'vpn_global':False,'vpn_enabled':c['vpn']!='off','features':c.get('features',{}),'uplink_interface':network.WAN,'network_mode':network.PLATFORM['mode'],'vpn_handshake':stamp,'cpu_load':os.getloadavg()[0],'ram_total':mem['MemTotal'],'ram_available':mem['MemAvailable'],'disk_free':stat.f_bavail*stat.f_frsize,'temperature_c':int(Path('/sys/class/thermal/thermal_zone0/temp').read_text())/1000,'error':ERROR,'uptime':int(now-START),'sessions':[session_view(s,c,names) for s in rows('SELECT * FROM sessions ORDER BY id DESC LIMIT 200')],'codes':rows('SELECT id,label,profile,expires,duration,first,revoked FROM codes ORDER BY id DESC'),'blocked':rows('SELECT * FROM blocked'),'pending':(STATE/'pending.json').exists() or (STATE/'wifi-pending.json').exists(),'vpn_servers':[p.stem for p in (STATE/'vpn').glob('*.json')]}

def web_activity(hours=24):
 from activity_log import activity
 return activity(config(), rows('SELECT ip,mac FROM sessions ORDER BY id DESC'), hours)


def dispatch(d):
 method=d['method']; c=config()
 if method=='config': return c
 if method=='matrix_test':
  mode=int(d['mode'])
  if not 0<=mode<=6:raise ValueError('Unbekanntes Matrixsymbol')
  atomic('/run/qspot/matrix-test.json',{'mode':mode,'expires':time.time()+8},0o644)
  return True
 if method=='matrix_config':
  c['matrix']=d['matrix'];validate(c);atomic(CONFIG,c);return True
 if method=='status': return status_data()
 if method=='web_activity': return web_activity(d.get('hours',24))
 if method=='clear_web_activity':
  from activity_log import clear
  clear();return True
 if method=='portal':
  visible={k:c[k] for k in ('title','description','accept_text','terms','portal_mode')}
  visible.update(identity(c))
  visible['features']=c.get('features',{})
  if c.get('dns_logging'):visible['terms']+=' DNS-Domains werden lokal bis zu '+str(c.get('dns_retention_hours',24))+' Stunden gespeichert. Keine vollständigen HTTPS-Adressen.'
  visible['portal_url']=portal_url(c)
  try:
   mac,ip=peer(d['ip']); s=rows('SELECT * FROM sessions WHERE mac=? ORDER BY id DESC LIMIT 1',(mac,)); visible['session']=session_view(s[0]) if s else None
  except ValueError: visible['session']=None
  return visible
 if method=='activate': return activate(d['ip'],d.get('code'))
 if method=='codes':
  if d['profile'] not in c['profiles']: raise ValueError('Unbekanntes Profil')
  count=int(d.get('count',1)); expires=int(d.get('expires',0)); duration=int(d.get('duration',0))
  if not 1<=count<=500 or min(expires,duration)<0: raise ValueError('Ungültige Codeparameter')
  generated=[]
  for _ in range(count):
   code=secrets.token_hex(10).upper(); digest=hashlib.sha256(code.encode()).hexdigest(); label=code[-4:]
   ident=sql('INSERT INTO codes(digest,label,profile,expires,duration,first,revoked) VALUES(?,?,?,?,?,0,0)',(digest,label,d['profile'],expires,duration)).lastrowid
   generated.append({'id':ident,'code':code})
  return generated
 if method=='revoke_code':
  ident=int(d['id']); sql('UPDATE codes SET revoked=1 WHERE id=?',(ident,))
  for s in rows('SELECT * FROM sessions WHERE code_id=? AND active=1',(ident,)): end(s,'Code widerrufen')
  return True
 if method=='delete_code':
  ident=int(d['id'])
  if rows('SELECT * FROM sessions WHERE code_id=? AND active=1',(ident,)): raise ValueError('Zuerst widerrufen')
  sql('DELETE FROM codes WHERE id=?',(ident,)); return True
 if method=='end':
  for s in rows('SELECT * FROM sessions WHERE id=? AND active=1',(int(d['id']),)): end(s,'Administrativ beendet')
  return True
 if method=='block':
  mac=d['mac'].lower()
  if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}',mac): raise ValueError('Ungültige MAC-Adresse')
  sql('INSERT OR IGNORE INTO blocked VALUES(?)',(mac,)); network.nft(f'add element inet qspot blocked {{ {mac} }}')
  for s in rows('SELECT * FROM sessions WHERE mac=? AND active=1',(mac,)): end(s,'Gerät gesperrt')
  return True
 if method=='unblock':
  mac=d['mac'].lower()
  if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}',mac): raise ValueError('Ungültige MAC-Adresse')
  network.run('nft','delete','element','inet','qspot','blocked','{',mac,'}',check=False); sql('DELETE FROM blocked WHERE mac=?',(mac,)); return True
 if method=='unblock_all':
  network.nft('flush set inet qspot blocked');sql('DELETE FROM blocked');return True
 if method=='clear_devices':
  active=rows('SELECT * FROM sessions WHERE active=1')
  sql("UPDATE sessions SET active=0,reason='Alle Freigaben gelöscht'")
  network.nft('flush set inet qspot allowed\nflush set inet qspot online\nflush chain inet qspot accounting\nflush chain inet qspot quotas')
  for s in active:
   network.revoke(s['mac'],s['ip']);network.cleanup_session(s['id'])
  objects=json.loads(run('nft','-j','list','table','inet','qspot'))
  for obj in objects['nftables']:
   for kind,prefix in [('counter','s'),('quota','q')]:
    value=obj.get(kind,{})
    if re.fullmatch(prefix+r'\d+',value.get('name','')):run('nft','delete',kind,'inet','qspot',value['name'],check=False)
  sql('DELETE FROM sessions');return True
 if method in ('scan','wifi_connect') and network.PLATFORM['mode']=='lan':raise ValueError('Internet-Uplink ist LAN; Netzwerkmodus per CLI ?ndern')
 if method=='scan':
  run('nmcli','device','wifi','rescan',check=False)
  return run('nmcli','-t','-f','SSID,SIGNAL,FREQ,SECURITY','device','wifi','list','--rescan','no')
 if method=='wifi_list': return run('nmcli','-t','-f','NAME,UUID,TYPE,AUTOCONNECT,AUTOCONNECT-PRIORITY','connection','show')
 if method=='wifi_connect':
  if (STATE/'wifi-pending.json').exists(): raise ValueError('Den letzten WLAN-Wechsel zuerst bestätigen')
  ssid=d['ssid']; password=d.get('password',''); hidden=d.get('hidden',False)
  security=d.get('security','wpa-psk' if password else 'none')
  if security not in ('wpa-psk','sae','none'): raise ValueError('Sicherheitsart nicht unterstützt')
  if security=='wpa-psk' and not (8<=len(password)<=63 or re.fullmatch(r'[a-fA-F0-9]{64}',password)): raise ValueError('WPA2-Passwort: 8–63 Zeichen oder 64 Hex-Zeichen erforderlich')
  if security=='sae' and not 1<=len(password)<=63: raise ValueError('WPA3-Passwort erforderlich')
  if not isinstance(ssid,str) or not 1<=len(ssid.encode())<=32 or '\n' in ssid: raise ValueError('Ungültige SSID')
  # Credentials are supplied through a root-only connection file, never argv.
  import configparser, uuid
  ident=str(uuid.uuid4()); p=Path('/run/qspot/connect.nmconnection')
  parser=configparser.ConfigParser(interpolation=None)
  parser['connection']={'id':identity(c)['brand_name']+'-'+ssid,'uuid':ident,'type':'wifi','autoconnect':'true','autoconnect-priority':str(max(-999,min(999,int(d.get('priority',0)))))}
  parser['connection']['interface-name']=network.WAN
  parser['wifi']={'ssid':ssid,'mode':'infrastructure','powersave':'2','hidden':'true' if hidden else 'false'}
  parser['ipv4']={'method':'auto'}; parser['ipv6']={'method':'auto'}
  if security!='none': parser['wifi-security']={'key-mgmt':security,'psk':password}
  with p.open('w') as f: os.chmod(p,0o600); parser.write(f,space_around_delimiters=False)
  target=Path('/etc/NetworkManager/system-connections')/(ident+'.nmconnection'); os.replace(p,target)
  previous=run('nmcli','-g','GENERAL.CON-UUID','device','show',network.WAN)
  if re.fullmatch(r'[a-f0-9-]{36}',previous):
   atomic(STATE/'wifi-pending.json',{'previous':previous,'new':ident})
   run('systemd-run','--collect','--unit=qspot-wifi-rollback','--on-active=120s','--timer-property=AccuracySec=1s','/usr/bin/python3','/opt/qspot/qspot/wifi_rollback.py')
  run('nmcli','connection','load',str(target))
  try:
   run('nmcli','--wait','25','connection','up','uuid',ident,timeout=30)
   validate(c,json.loads(run('ip','-j','route','show','table','main')))
   network.update_local(c); network.dns(c)
   if network.PLATFORM['mode']=='single':network.setup(c)
  except Exception:
   if (STATE/'wifi-pending.json').exists():
    run('nmcli','--wait','20','connection','up','uuid',previous,timeout=25,check=False)
    (STATE/'wifi-pending.json').unlink()
    run('systemctl','stop','qspot-wifi-rollback.timer',check=False)
   raise ValueError('Host-WLAN konnte nicht verbunden werden. SSID, Sicherheitsart und Passwort prüfen; vorheriges Netz wurde erneut angefordert.')
  return True
 if method=='wifi_priority':
  ident=d['uuid']
  if not re.fullmatch(r'[a-f0-9-]{36}',ident): raise ValueError('Ungültige UUID')
  run('nmcli','connection','modify','uuid',ident,'connection.autoconnect-priority',str(max(-999,min(999,int(d['priority']))))); return True
 if method=='vpn_import':
  name=d['name']
  if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',name): raise ValueError('Ungültiger Servername')
  atomic(STATE/'vpn'/f'{name}.json',network.import_wireguard(d['text'])); return True
 if method=='device_vpn':
  mac=str(d.get('mac','')).lower()
  if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}',mac) or type(d.get('enabled')) is not bool:raise ValueError('Ungültige Geräteauswahl')
  if c['vpn']=='off':raise ValueError('Zuerst VPN global aktivieren')
  values=set(c.get('vpn_bypass',[]))
  if d['enabled']:values.discard(mac)
  else:values.add(mac)
  updated={**c,'vpn_bypass':sorted(values)};validate(updated)
  network.sync_bypass(updated);atomic(CONFIG,updated)
  for s in rows('SELECT * FROM sessions WHERE mac=?',(mac,)):
   run('conntrack','-D','-s',s['ip'],check=False);run('conntrack','-D','-d',s['ip'],check=False)
  return True
 if method=='vpn_toggle':
  if type(d.get('enabled')) is not bool:raise ValueError('VPN-Zustand fehlt')
  return set_vpn(c,d['enabled'],d.get('server'))
 if method=='apply':
  if (STATE/'pending.json').exists(): raise ValueError('Vorherige Änderung zuerst bestätigen oder zurückrollen')
  new=validate(renamed_config(c,d['config']),json.loads(run('ip','-j','route','show','table','main')))
  atomic(STATE/'previous.json',c)
  atomic(STATE/'pending.json',{'deadline':time.time()+120})
  run('systemd-run','--unit=qspot-rollback','--on-active=120s','/usr/bin/python3','/opt/qspot/qspot/rollback.py')
  for s in rows('SELECT * FROM sessions WHERE active=1'): end(s,'Konfiguration geändert')
  atomic(CONFIG,new)
  try: network.setup(new)
  except Exception:
   atomic(CONFIG,c); network.setup(c); raise
  return {'confirm_within_seconds':120}
 if method=='confirm':
  (STATE/'pending.json').unlink(missing_ok=True)
  run('systemctl','stop','qspot-rollback.timer',check=False); run('systemctl','reset-failed','qspot-rollback.service',check=False)
  (STATE/'wifi-pending.json').unlink(missing_ok=True)
  run('systemctl','stop','qspot-wifi-rollback.timer',check=False)
  run('hostnamectl','set-hostname',c['hostname']); return True
 if method=='rollback':
  if (STATE/'pending.json').exists():
   atomic(CONFIG,json.loads((STATE/'previous.json').read_text())); (STATE/'pending.json').unlink(); network.setup(config())
  return True
 if method=='backup':
  return {'config':c,'codes':rows('SELECT * FROM codes'),'sessions':rows('SELECT * FROM sessions'),'blocked':rows('SELECT * FROM blocked'),'vpn':{p.stem:json.loads(p.read_text()) for p in (STATE/'vpn').glob('*.json')}}
 if method=='restart':
  service=d['service']
  if service not in ('qspot-hostapd','qspot-dns@guest','qspot-dns@usb'): raise ValueError('Dienst nicht freigegeben')
  run('systemctl','restart',service); return True
 if method=='reboot': run('systemd-run','--on-active=3s','systemctl','reboot'); return True
 if method=='logs': return run('journalctl','-u','qspot-net','-u','qspot-hostapd','-u','qspot-dns@guest','--no-pager','-n','100')
 raise ValueError('Unbekannte Aktion')

class Handler(socketserver.StreamRequestHandler):
 def handle(self):
  try:
   raw=self.rfile.readline(1024*1024+1)
   if len(raw)>1024*1024: raise ValueError('Anfrage zu groß')
   with LOCK: result={'result':dispatch(json.loads(raw))}
  except Exception as e: result={'error':str(e)}
  self.wfile.write(json.dumps(result).encode()+b'\n')

def main():
 global DB, RECOVERY, RECOVERY_UNTIL
 os.umask(0o077); STATE.mkdir(exist_ok=True); (STATE/'vpn').mkdir(exist_ok=True)
 if not CONFIG.exists(): atomic(CONFIG,DEFAULT)
 if (STATE/'pending.json').exists():
  atomic(CONFIG,json.loads((STATE/'previous.json').read_text())); (STATE/'pending.json').unlink()
 if (STATE/'wifi-pending.json').exists():
  previous=json.loads((STATE/'wifi-pending.json').read_text())['previous']
  run('nmcli','--wait','20','connection','up','uuid',previous,timeout=25,check=False)
  (STATE/'wifi-pending.json').unlink()
 DB=sqlite3.connect(STATE/'router.sqlite',check_same_thread=False); DB.row_factory=sqlite3.Row
 DB.executescript('''CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY,mac TEXT,ip TEXT,profile TEXT,code_id INTEGER,started REAL,deadline REAL,active INTEGER,used INTEGER,reason TEXT);
 CREATE TABLE IF NOT EXISTS codes(id INTEGER PRIMARY KEY,digest TEXT UNIQUE,label TEXT,profile TEXT,expires INTEGER,duration INTEGER,first REAL,revoked INTEGER);
 CREATE TABLE IF NOT EXISTS blocked(mac TEXT PRIMARY KEY);''')
 boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 marker=STATE/'session-boot'
 same_boot=marker.exists() and marker.read_text().strip()==boot
 recover=rows('SELECT * FROM sessions WHERE active=1') if same_boot else []
 sql("UPDATE sessions SET active=0,reason='Systemdienst neu gestartet' WHERE active=1")
 Path('/run/qspot').mkdir(exist_ok=True)
 network.setup(validate(config(),json.loads(run('ip','-j','route','show','table','main'))))
 restore_sessions(config(),recover)
 live={s['id'] for s in rows('SELECT id FROM sessions WHERE active=1')}
 RECOVERY=[s for s in recover if s['id'] not in live]
 RECOVERY_UNTIL=time.monotonic()+60
 marker.write_text(boot)
 for b in rows('SELECT * FROM blocked'): network.nft(f'add element inet qspot blocked {{ {b["mac"]} }}')
 sock='/run/qspot/control.sock'; Path(sock).unlink(missing_ok=True)
 server=socketserver.ThreadingUnixStreamServer(sock,Handler)
 import grp
 os.chown(sock,0,grp.getgrnam('qspot').gr_gid); os.chmod(sock,0o660)
 threading.Thread(target=tick,daemon=True).start()
 server.serve_forever()
if __name__=='__main__': main()
