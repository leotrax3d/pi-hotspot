"""DHCP-reported names, without DNS probes or per-device subprocesses."""
import ipaddress
import re
import time
from pathlib import Path

LEASES=Path('/run/qspot-dns-guest/leases')
MAC=re.compile(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}')
_key=None
_entries=[]


def leases():
 global _key,_entries
 try:
  stat=LEASES.stat();key=(str(LEASES),stat.st_mtime_ns,stat.st_size)
  if key!=_key:
   entries=[]
   with LEASES.open(encoding='utf-8',errors='replace') as file:text=file.read(262144)
   for line in text.splitlines():
    fields=line.split()
    if len(fields)<4:continue
    expiry,mac,ip,hostname=fields[:4];mac=mac.lower()
    try:expiry=int(expiry);ip=str(ipaddress.IPv4Address(ip))
    except ValueError:continue
    if not MAC.fullmatch(mac) or expiry<0:continue
    name='' if hostname=='*' else ''.join(ch for ch in hostname if ch.isprintable())[:253]
    entries.append({'expires':expiry,'mac':mac,'ip':ip,'hostname':name})
   _entries=entries;_key=key
 except OSError:return []
 now=time.time()
 return [{k:v for k,v in item.items() if k!='expires'} for item in _entries if not item['expires'] or item['expires']>now]


def hostnames():return {(item['mac'],item['ip']):item['hostname'] for item in leases()}
