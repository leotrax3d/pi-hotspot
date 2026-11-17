"""Private Pi-hole v6 API adapter. No sessions or credentials leave this module."""
import datetime
import ipaddress
import json
import re
import threading
import time
import socket
import struct
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, build_opener, ProxyHandler
from common import STATE, atomic

IMAGE='docker.io/pihole/pihole:2026.11.0'
PORT=5354
API='http://127.0.0.1:8081/api'
LOCK=threading.RLock()
SID=''
CACHE=None
UNTIL=0
LAST_HEALTH=0
ROUTED=None
PURGED=0
LAST_SAMPLE=0
RECONCILED=False
OPENER=build_opener(ProxyHandler({}))

def daily_sample():
 """Only aggregate counts persist; no clients or domains in this daily counter."""
 path=STATE/'pihole-counts.json'
 day=datetime.date.today().isoformat()
 previous=json.loads(path.read_text()) if path.exists() else {}
 sample=request('/stats/summary').get('queries',{})
 total=int(sample.get('total',0));blocked=int(sample.get('blocked',0))
 same=previous.get('day')==day
 # FTL's rolling totals can decrease when it restarts/purges/expires history.
 added=max(0,total-previous.get('sample_total',0)) if same else 0
 denied=max(0,blocked-previous.get('sample_blocked',0)) if same else 0
 result={'day':day,'total':(previous.get('total',0) if same else 0)+added,
         'blocked':(previous.get('blocked',0) if same else 0)+denied,
         'sample_total':total,'sample_blocked':blocked}
 if result!=previous:atomic(path,result)
 return result

def enabled(c):return c.get('features',{}).get('pihole',False)

def request(path, payload=None, method=None, retry=True):
 global SID
 if not SID and path!='/auth':
  result=request('/auth',{'password':(STATE/'pihole-password').read_text().strip()},retry=False)
  SID=result.get('session',{}).get('sid','')
  if not SID:raise ValueError('DNS-Schutz: Anmeldung fehlgeschlagen')
 headers={'Content-Type':'application/json'}
 if SID:headers['sid']=SID
 req=Request(API+path,data=None if payload is None else json.dumps(payload).encode(),headers=headers,method=method)
 try:
  with OPENER.open(req,timeout=2) as response:
   raw=response.read(2*1024*1024)
   return json.loads(raw) if raw else {}
 except HTTPError as error:
  if error.code==401 and retry and path!='/auth':
   SID='';return request(path,payload,method,False)
  raise ValueError('DNS-Schutz: Aktion fehlgeschlagen') from None
 except (OSError,URLError,ValueError):raise ValueError('DNS-Schutz nicht erreichbar') from None

def invalidate():
 global CACHE,UNTIL
 CACHE=None;UNTIL=0

def domain(value):
 from branding import domain as check
 value=check(str(value).strip().rstrip('.'))
 if '.' not in value:raise ValueError('Domain erforderlich')
 return value

def view(c):
 global CACHE,UNTIL
 if not enabled(c):return {'installed':False,'available':False}
 with LOCK:
  if CACHE is not None and time.monotonic()<UNTIL:return CACHE
  result={'installed':True,'available':False,'logging':c.get('dns_logging',False),'devices':{},'events':[]}
  try:
   blocking=request('/dns/blocking')
   clients=request('/clients').get('clients',[])
   result.update(available=True,blocking=blocking.get('blocking'),timer=blocking.get('timer'),
                 devices={x['client'].lower():bool(x.get('groups')) for x in clients})
   daily=STATE/'pihole-counts.json'
   counts=json.loads(daily.read_text()) if daily.exists() else {}
   result.update(blocked_today=counts.get('blocked',0),ratio=round(100*counts.get('blocked',0)/counts['total'],1) if counts.get('total') else 0)
   if c.get('dns_logging'):
    cutoff=time.time()-c.get('dns_retention_hours',24)*3600
    queries=request('/queries?'+urlencode({'length':200,'from':cutoff})).get('queries',[])
    result['events']=[{'time':x['time'],'domain':x['domain'],'ip':x.get('client',{}).get('ip',''),
                       'status':x['status']} for x in queries if x['time']>=cutoff][:200]
  except (ValueError,OSError,KeyError,TypeError):result.update(available=False,error='DNS-Schutz nicht erreichbar')
  CACHE=result;UNTIL=time.monotonic()+5
  return result

def action(c,d):
 if not enabled(c):raise ValueError('DNS-Schutz nicht installiert')
 with LOCK:
  kind=d.get('operation')
  if kind=='blocking':
   if type(d.get('enabled')) is not bool:raise ValueError('Ungültiger Zustand')
   request('/dns/blocking',{'blocking':d['enabled'],'timer':None})
   atomic(STATE/'pihole-control.json',{'blocking':d['enabled'],'pause_until':0})
  elif kind=='pause':
   request('/dns/blocking',{'blocking':False,'timer':300})
   atomic(STATE/'pihole-control.json',{'blocking':True,'pause_until':time.time()+300})
  elif kind=='domain':
   name=domain(d.get('domain',''));mode=d.get('mode')
   if mode not in ('allow','deny'):raise ValueError('Ungültige Regel')
   from branding import identity
   if name in (identity(c)['portal_domain'],c['hostname']+'.local'):raise ValueError('Lokale Domain geschützt')
   other='deny' if mode=='allow' else 'allow'
   # Replacing the opposite rule prevents an allow rule silently overriding deny.
   existing=request('/domains/'+other+'/exact/'+quote(name,safe='')).get('domains',[])
   if existing:request('/domains/'+other+'/exact/'+quote(name,safe=''),method='DELETE')
   current=request('/domains/'+mode+'/exact/'+quote(name,safe='')).get('domains',[])
   if not current:request('/domains/'+mode+'/exact',{'domain':name,'enabled':True,'groups':[0],'comment':''})
  elif kind=='device':
   mac=str(d.get('mac','')).lower()
   if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}',mac) or type(d.get('enabled')) is not bool:raise ValueError('Ungültiges Gerät')
   target='/clients/'+quote(mac,safe='')
   existing=request(target).get('clients',[])
   payload={'groups':[0] if d['enabled'] else [],'comment':''}
   if existing:request(target,payload,'PUT')
   else:request('/clients',{'client':mac,**payload})
  else:raise ValueError('Unbekannte DNS-Aktion')
  invalidate()
  return True

def environment(c, upstreams):
 from branding import identity
 addr=str(ipaddress.ip_interface(c['guest']).ip)
 hosts=[f'{addr} {name}' for name in dict.fromkeys((identity(c)['portal_domain'],c['hostname']+'.local'))]
 return {'FTLCONF_dns_port':str(PORT),'FTLCONF_dns_listeningMode':'LOCAL',
  'FTLCONF_dns_upstreams':';'.join(upstreams),'FTLCONF_dns_hosts':';'.join(hosts),
  'FTLCONF_dhcp_active':'false','FTLCONF_ntp_ipv4_active':'false','FTLCONF_ntp_ipv6_active':'false',
  'FTLCONF_ntp_sync_active':'false','FTLCONF_webserver_port':'127.0.0.1:8081',
  'FTLCONF_webserver_api_password':(STATE/'pihole-password').read_text().strip(),
  'FTLCONF_dns_queryLogging':'false','FTLCONF_database_maxDBdays':'0','FTLCONF_database_DBimport':'false',
  'FTLCONF_misc_privacylevel':'0' if c.get('dns_logging') else '3',
  'FTLCONF_webserver_api_maxHistory':str(min(86400,c.get('dns_retention_hours',24)*3600)),
  'FTLCONF_files_log_dnsmasq':'/dev/null','FTLCONF_files_log_ftl':'/dev/null','FTLCONF_files_log_webserver':'/dev/null',
  'FTLCONF_dns_blocking_active':'true'}

def configure(c,upstreams):
 """Root-owned desired environment; blocking state is API-writable, never frozen by env."""
 from common import run
 path=STATE/'pihole.env'
 if not enabled(c):
  if path.exists():run('systemctl','stop','qspot-pihole',check=False)
  return
 values=environment(c,upstreams)
 del values['FTLCONF_dns_blocking_active']
 text=''.join(k+'='+v+'\n' for k,v in values.items())
 changed=not path.exists() or path.read_text()!=text
 if changed:
  path.write_text(text);path.chmod(0o600)
  global SID,RECONCILED,PURGED
  SID='';RECONCILED=False;PURGED=0;invalidate()
  run('systemctl','restart','qspot-pihole',check=False)
 else:run('systemctl','start','qspot-pihole',check=False)

def maintain(c):
 """Only local DNS remains during FTL failure. No public fallback resolver."""
 global LAST_HEALTH,ROUTED,PURGED,RECONCILED,SID,LAST_SAMPLE
 if not enabled(c):return
 now=time.monotonic()
 if now-LAST_HEALTH<5:return
 LAST_HEALTH=now
 from common import run
 alive=False
 try:
  current=request('/dns/blocking')
  if now-LAST_SAMPLE>=30:
   daily_sample();LAST_SAMPLE=now
  control=STATE/'pihole-control.json'
  desired=json.loads(control.read_text()) if control.exists() else {'blocking':True,'pause_until':0}
  remaining=max(0,desired['pause_until']-time.time())
  expected=False if remaining else desired['blocking']
  if not RECONCILED or (current.get('blocking')=='enabled')!=expected:
   request('/dns/blocking',{'blocking':expected,'timer':remaining or None})
   RECONCILED=True
  # FTL retains RAM history for up to 24 h. Purge the entire RAM history at
  # shorter intervals so even a 1 h policy cannot retain older hidden queries.
  # No persistent query database or plaintext query log is ever enabled.
  interval=min(86400,c.get('dns_retention_hours',24)*3600)-10
  if not PURGED or now-PURGED>=interval:
   request('/action/flush/logs',{},'POST');PURGED=now;invalidate()
   counts_path=STATE/'pihole-counts.json'
   if counts_path.exists():
    counts=json.loads(counts_path.read_text());counts.update(sample_total=0,sample_blocked=0);atomic(counts_path,counts)
  alive=dns_alive(c)
 except (ValueError,OSError):pass
 if not alive:RECONCILED=False;SID=''
 if not alive and PURGED and now-PURGED>=min(86400,c.get('dns_retention_hours',24)*3600)-5:
  # An unavailable API must not defeat the retention deadline.
  run('systemctl','restart','qspot-pihole',check=False);PURGED=0
 target=PORT if alive else 53
 if target!=ROUTED:
  run('nft','-f','-',input=f'flush chain inet qspot guest_dns\nadd rule inet qspot guest_dns meta l4proto {{ tcp, udp }} redirect to :{target}\n')
  # Existing DNS conntrack entries otherwise retain their previous destination.
  run('conntrack','-D','-p','udp','--dport','53',check=False)
  run('conntrack','-D','-p','tcp','--dport','53',check=False)
  ROUTED=target

def reset_route():
 global ROUTED,LAST_HEALTH
 ROUTED=None;LAST_HEALTH=0

def dns_alive(c):
 from branding import identity
 name=identity(c)['portal_domain']
 labels=b''.join(bytes([len(x)])+x.encode('ascii') for x in name.split('.'))+b'\0'
 packet=struct.pack('!HHHHHH',43210,256,1,0,0,0)+labels+struct.pack('!HH',1,1)
 with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
  sock.settimeout(.5);sock.connect(('127.0.0.1',PORT));sock.send(packet)
  reply=sock.recv(4096)
 return len(reply)>=12 and reply[:2]==packet[:2] and (reply[3]&15)==0 and int.from_bytes(reply[6:8],'big')>0
