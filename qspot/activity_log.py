"""Bounded local DNS events. Query logs are kept out of the system journal."""
import datetime
import json
import re
import time
from pathlib import Path
from common import STATE, atomic

RAW=Path('/run/qspot-dns-guest/queries.log')
STORE=STATE/'dns-events.json'
LAST=0
PATTERN=re.compile(r'query\[[^]]+\]\s+(\S+)\s+from\s+([0-9.]+)')


def maintain(c, force=False):
 global LAST
 now=time.time()
 if not force and now-LAST<30:return
 LAST=now
 if not c.get('dns_logging') or c.get('features',{}).get('pihole',False):
  STORE.unlink(missing_ok=True)
  if RAW.exists():
   with RAW.open('r+') as f:f.truncate(0)
  return
 cutoff=now-c.get('dns_retention_hours',24)*3600
 events=json.loads(STORE.read_text()) if STORE.exists() else []
 if RAW.exists():
  with RAW.open('r+') as f:
   # dnsmasq keeps the descriptor open; truncate in place rather than unlink.
   size=f.seek(0,2);f.seek(max(0,size-1024*1024));lines=f.read().splitlines();f.seek(0);f.truncate()
  for line in lines:
   match=PATTERN.search(line)
   if not match:continue
   domain,ip=match.groups();domain=domain.lower().rstrip('.')
   if domain.endswith(('.lan','.local','in-addr.arpa','ip6.arpa')) or len(domain)>253:continue
   try:
    date=datetime.datetime.strptime(str(datetime.datetime.now().year)+' '+line[:15],'%Y %b %d %H:%M:%S')
    stamp=date.timestamp()
    if stamp>now+86400:stamp=date.replace(year=date.year-1).timestamp()
   except ValueError:continue
   events.append({'time':stamp,'ip':ip,'domain':domain})
 unique={(e['time'],e['ip'],e['domain']):e for e in events if cutoff<=e['time']<=now+60}
 atomic(STORE,sorted(unique.values(),key=lambda e:e['time'])[-2000:])


def activity(c,devices,hours=24):
 maintain(c,True)
 retention=c.get('dns_retention_hours',24)
 hours=max(1,min(retention,int(hours)));cutoff=time.time()-hours*3600
 macs={}
 for item in devices:macs.setdefault(item['ip'],item['mac'])
 events=json.loads(STORE.read_text()) if STORE.exists() else []
 events=[{**e,'mac':macs.get(e['ip'],'')} for e in reversed(events) if e['time']>=cutoff]
 counts={}
 for e in events:counts[e['domain']]=counts.get(e['domain'],0)+1
 return {'events':events,'top':[{'domain':d,'count':n} for d,n in sorted(counts.items(),key=lambda x:-x[1])[:12]],
         'hours':hours,'retention_hours':retention,'total':len(events),'enabled':c.get('dns_logging',False)}


def clear():
 STORE.unlink(missing_ok=True)
 if RAW.exists():
  with RAW.open('r+') as f:f.truncate(0)
