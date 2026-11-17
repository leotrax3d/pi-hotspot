"""Root-owned certificate and local name files, updated with configuration."""
import ipaddress
import json
import re
from pathlib import Path
from common import run
from branding import certificate_names, identity

TLS=Path('/etc/qspot/tls')


def apply(c):
 hostfile=Path('/etc/hosts');text=hostfile.read_text()
 updated=re.sub(r'^127\.0\.1\.1\s+.*$',lambda _: '127.0.1.1\t'+c['hostname'],text,flags=re.M)
 if not re.search(r'^127\.0\.1\.1\s',updated,re.M):updated+='\n127.0.1.1\t'+c['hostname']+'\n'
 if updated!=text:hostfile.write_text(updated)
 run('hostnamectl','set-hostname',c['hostname'])
 desired=certificate_names(c)
 marker=TLS/'identity.json'
 if not marker.exists() or json.loads(marker.read_text()).get('names')!=desired:
  key=TLS/'key.next.pem';cert=TLS/'cert.next.pem'
  run('openssl','req','-x509','-newkey','rsa:3072','-sha256','-nodes','-days','365',
      '-keyout',str(key),'-out',str(cert),'-subj','/CN='+identity(c)['portal_domain'],
      '-addext','subjectAltName='+desired,timeout=60)
  import grp,os
  for p in (key,cert):os.chown(p,0,grp.getgrnam('qspot').gr_gid);p.chmod(0o640)
  key.replace(TLS/'key.pem');cert.replace(TLS/'cert.pem')
  marker.write_text(json.dumps({'names':desired}));marker.chmod(0o600)
 hosts=Path('/etc/avahi/hosts')
 if hosts.exists():
  text=re.sub(r'\n?# pi-hotspot begin\n.*?# pi-hotspot end\n?','\n',hosts.read_text(),flags=re.S)
  name=identity(c)['portal_domain']
  if name.endswith('.local') and name!=c['hostname']+'.local':
   text+='\n# pi-hotspot begin\n'+str(ipaddress.ip_interface(c['guest']).ip)+' '+name+'\n# pi-hotspot end\n'
  hosts.write_text(text)
  run('systemctl','reload','avahi-daemon',check=False)
