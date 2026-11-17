"""Public identity, local DNS name and TLS identity."""
import ipaddress
import re
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
