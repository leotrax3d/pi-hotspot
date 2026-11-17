"""Public identity, local DNS name and TLS identity."""
import ipaddress
import re
import unicodedata
from urllib.parse import quote


def domain(value):
 if not isinstance(value,str) or value!=value.strip() or any(x in value for x in '/:@?#\\'):
  raise ValueError('Ungültige Portal-Domain')
 try:value=value.encode('idna').decode('ascii').lower()
 except UnicodeError:raise ValueError('Ungültige Portal-Domain')
 labels=value.split('.')
 if len(value)>253 or len(labels)<2 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',x) for x in labels):
  raise ValueError('Domain erforderlich, z.B. wlan.lan')
 try:ipaddress.ip_address(value)
 except ValueError:return value
 raise ValueError('Portal-Domain darf keine IP-Adresse sein')


def identity(c):
 return {'brand_name':c.get('brand_name','SchülerWLAN'),
         'portal_domain':domain(c.get('portal_domain',c.get('hostname','pi-hotspot')+'.local'))}


def portal_url(c,secure=False):
 return ('https' if secure else 'http')+'://'+identity(c)['portal_domain']+'/'


def certificate_names(c):
 names=[identity(c)['portal_domain'],c['hostname']+'.local']
 return ','.join('DNS:'+n for n in dict.fromkeys(names))+',IP:'+str(ipaddress.ip_interface(c['guest']).ip)


def otp_uri(c,secret):
 issuer=identity(c)['brand_name']
 return 'otpauth://totp/'+quote(issuer+':admin',safe='')+'?secret='+quote(secret)+'&issuer='+quote(issuer,safe='')


def name_slug(name):
 name=name.lower().translate(str.maketrans({'ä':'ae','ö':'oe','ü':'ue','ß':'ss'}))
 name=unicodedata.normalize('NFKD',name).encode('ascii','ignore').decode()
 slug=re.sub(r'[^a-z0-9]+','-',name).strip('-') or 'wlan'
 if not slug[0].isalpha():slug='wlan-'+slug
 return slug[:63].rstrip('-')


def renamed_config(previous,incoming):
 updated={**previous,**incoming}
 old=identity(previous)['brand_name'];new=updated.get('brand_name',old)
 if new==old:return updated
 if not isinstance(new,str) or not new.strip():raise ValueError('Name fehlt')
 for key in ('ssid','title','description','accept_text','terms'):
  value=updated.get(key,'')
  if isinstance(value,str):updated[key]=re.sub(re.escape(old),lambda _:new,value,flags=re.I)
 slug=name_slug(new);old_slug=name_slug(old)
 old_host=previous.get('hostname','pi-hotspot')
 if updated.get('hostname')==old_host and old_host in ('pi-hotspot',old_slug):updated['hostname']=slug
 old_domain=identity(previous)['portal_domain']
 if updated.get('portal_domain',old_domain)==old_domain:
  updated['portal_domain']='.'.join(slug if label in ('pi-hotspot',old_slug,old_host) else label for label in old_domain.split('.'))
 return updated
