"""Raspberry Pi router plane. Commands are passed as argv, never to a shell."""
import functools, ipaddress, json, os, re, shutil, time
from pathlib import Path
from common import run, STATE
from platform_config import load
from branding import identity

PLATFORM=load()
AP=PLATFORM['ap']
WAN=PLATFORM['uplink']

@functools.cache
def policy_routing():
 return bool(run('ip','-4','rule','list',check=False))

def vpn_dns(c):
 if c['vpn']=='off':return []
 name=c['vpn_server']
 if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',name):raise ValueError('VPN-Server auswählen')
 data=json.loads((STATE/'vpn'/f'{name}.json').read_text())
 return [str(ipaddress.IPv4Address(ip)) for ip in data.get('dns',['10.64.0.1'])]

def associated():
 text=run('iw','dev',AP,'station','dump',check=False)
 # Some AP drivers omit the associated field; station entries are then accepted.
 return [m.group(1) for m in re.finditer(r'Station ([0-9a-f:]{17})[^\n]*\n(.*?)(?=\nStation |\Z)',text,re.S)
         if not re.search(r'(?:associated|authorized):\s+no',m.group(2))]

def nft(script):return run('nft','-f','-',input=script)

def sync_bypass(c):
 values=', '.join(c.get('vpn_bypass',[]))
 nft('flush set inet qspot vpn_bypass\n'+(f'add element inet qspot vpn_bypass {{ {values} }}' if values else ''))

def base(c):
 import pihole
 pihole.reset_route()
 subnet=str(ipaddress.ip_interface(c['guest']).network)
 addresses=[str(ipaddress.ip_interface(c['guest']).ip)]
 for d in json.loads(run('ip','-j','-4','address','show')):
  addresses.extend(a['local'] for a in d.get('addr_info',[]) if a['family']=='inet')
 pre='delete table inet qspot\n' if run('nft','list','table','inet','qspot',check=False) else ''
 bypass=', '.join(c.get('vpn_bypass',[]))
 bypass_elements=f'elements = {{ {bypass} }};' if bypass else ''
 mark=f'iifname "{AP}" ether saddr != @vpn_bypass meta mark set 177' if c['vpn']!='off' else 'counter'
 kill=f'iifname "{AP}" ether saddr != @vpn_bypass oifname != "qspot-wg" drop' if c['vpn']!='off' else ''
 # Permit only local and tunnel DNS; VPN clients never inherit upstream DNS.
 protect='ip daddr { '+', '.join(vpn_dns(c))+' } oifname != "qspot-wg" reject' if c['vpn']!='off' else 'counter'
 nft(pre+f'''table inet qspot {{
 set allowed {{ type ether_addr . ipv4_addr; flags timeout; }}
 set online {{ type ipv4_addr; flags timeout; }}
 set blocked {{ type ether_addr; }}
 set vpn_bypass {{ type ether_addr; {bypass_elements} }}
 set localaddrs {{ type ipv4_addr; elements = {{ {', '.join(sorted(set(addresses)))} }}; }}
 chain mark_vpn {{ type filter hook prerouting priority mangle; policy accept; {mark}; }}
 chain input {{ type filter hook input priority -30; policy accept;
  iifname != "lo" tcp dport 8081 drop
  iifname != {{ "lo", "{AP}" }} udp dport 5354 drop
  iifname != {{ "lo", "{AP}" }} tcp dport 5354 drop
  iifname "{AP}" meta nfproto ipv6 drop
  iifname "{AP}" ether saddr @blocked drop
  iifname "{AP}" udp dport {{ 53, 67, 5353, 5354 }} accept
  iifname "{AP}" tcp dport {{ 53, 80, 443, 8080, 8443, 5354 }} accept
  iifname "{AP}" ip protocol icmp accept
  iifname "{AP}" drop
 }}
 chain forward {{ type filter hook forward priority -30; policy accept;
  iifname "{AP}" meta nfproto ipv6 drop
  oifname "{AP}" meta nfproto ipv6 drop
  iifname "{AP}" ether saddr @blocked drop
  iifname "{AP}" ether saddr . ip saddr != @allowed drop
  oifname "{AP}" ip daddr != @online drop
  iifname "{AP}" oifname "{AP}" drop
  iifname "{AP}" ip daddr {{ 0.0.0.0/8,10.0.0.0/8,100.64.0.0/10,127.0.0.0/8,169.254.0.0/16,172.16.0.0/12,192.168.0.0/16,224.0.0.0/4 }} drop
  {kill}
  iifname "{AP}" oifname {{ "{WAN}", "qspot-wg" }} accept
  oifname "{AP}" ct state established,related accept
  iifname "{AP}" drop
  oifname "{AP}" drop
 }}
 chain accounting {{ type filter hook forward priority -25; policy accept; }}
 chain quotas {{ type filter hook forward priority -26; policy accept; }}
 chain output {{ type filter hook output priority -30; policy accept; {protect}; }}
 chain guest_dns {{ meta l4proto {{ tcp, udp }} redirect to :53; }}
 chain portal_redirect {{ type nat hook prerouting priority dstnat; policy accept;
  ip daddr @localaddrs tcp dport 443 redirect to :8443
  ip daddr @localaddrs tcp dport 80 redirect to :8080
  iifname "{AP}" udp dport 53 jump guest_dns
  iifname "{AP}" tcp dport 53 jump guest_dns
  iifname "{AP}" ether saddr . ip saddr @allowed return
  iifname "{AP}" tcp dport 80 redirect to :8080
 }}
 chain source_nat {{ type nat hook postrouting priority srcnat; policy accept;
  ip saddr {subnet} oifname {{ "{WAN}", "qspot-wg" }} masquerade
 }}
}}''')

def radio_channel(c):
 if PLATFORM['mode']!='single':return c['channel'],'g'
 text=run('iw','dev',WAN,'info')
 match=re.search(r'channel (\d+) \((\d+) MHz\)',text)
 if not match:raise ValueError('Im Ein-Adapter-Modus muss zuerst der WLAN-Uplink verbunden sein')
 channel,freq=map(int,match.groups())
 # Initial concurrent implementation is limited to non-DFS 2.4 GHz.
 if freq>=3000 or channel not in range(1,12):
  raise ValueError('Experimenteller Ein-Adapter-Modus benötigt einen 2,4-GHz-Uplink auf Kanal 1–11')
 return channel,'g'

def setup(c):
 base(c)
 from identity_files import apply
 apply(c)
 run('sysctl','-w','net.ipv4.ip_forward=1')
 run('sysctl','-w','net.ipv4.conf.all.rp_filter=2')
 if PLATFORM['mode']=='single' and not Path('/sys/class/net/'+AP).exists():
  run('iw','dev',WAN,'interface','add',AP,'type','__ap')
 run('nmcli','device','set',AP,'managed','no')
 run('iw','dev',AP,'set','power_save','off',check=False)
 run('sysctl','-w',f'net.ipv6.conf.{AP}.disable_ipv6=1')
 run('ip','address','flush','dev',AP)
 run('ip','address','add',c['guest'],'dev',AP)
 run('ip','link','set',AP,'up')
 channel,mode=radio_channel(c)
 text=f'interface={AP}\ndriver=nl80211\nssid={c["ssid"]}\ncountry_code={c["country"]}\nhw_mode={mode}\nchannel={channel}\nieee80211n=1\nwmm_enabled=1\nap_isolate=1\nauth_algs=1\nctrl_interface=/run/qspot/hostapd\n'
 if c.get('ap_password'):
  text+='wpa=2\nwpa_key_mgmt=WPA-PSK\nrsn_pairwise=CCMP\nwpa_passphrase='+c['ap_password']+'\n'
 private=Path('/run/qspot/hostapd.conf');private.write_text(text);private.chmod(0o600)
 run('systemctl','restart','qspot-hostapd.service')
 start_guest_services(c)

def start_guest_services(c):
 # DHCP and the local portal must remain available during an uplink/VPN outage.
 try:vpn(c)
 except (ValueError,OSError):
  run('ip','link','del','qspot-wg',check=False)
 dns(c);shaping(c)

def dns(c):
 import pihole
 hostdns=run('nmcli','-g','IP4.DNS','device','show',WAN,check=False).splitlines()
 hostdns=[x for x in hostdns if re.fullmatch(r'\d+\.\d+\.\d+\.\d+',x)] or ['1.1.1.1']
 servers=[ip+('@qspot-wg' if Path('/sys/class/net/qspot-wg').exists() else '') for ip in vpn_dns(c)] if c['vpn']!='off' else hostdns
 ip=ipaddress.ip_interface(c['guest']);net=ip.network
 cfg=f'interface={AP}\nbind-dynamic\nexcept-interface=lo\nlisten-address={ip.ip}\nno-resolv\ndomain-needed\nbogus-priv\nlog-async=25\ndhcp-authoritative\ndhcp-range={net.network_address+20},{net.network_address+220},255.255.255.0,1h\ndhcp-option=3,{ip.ip}\ndhcp-option=6,{ip.ip}\ndhcp-leasefile=/run/qspot-dns-guest/leases\ndhcp-option=114,http://{ip.ip}/captive-api\n'
 cfg+=''.join(f'host-record={name},{ip.ip}\n' for name in dict.fromkeys((identity(c)['portal_domain'],c['hostname']+'.local')))
 if not pihole.enabled(c):cfg+=''.join('server='+s+'\n' for s in servers)
 if c.get('dns_logging') and not pihole.enabled(c):cfg+='log-queries=extra\nlog-facility=/run/qspot-dns-guest/queries.log\n'
 Path('/run/qspot/dns-guest.conf').write_text(cfg)
 Path('/run/qspot/dns-guest.conf').chmod(0o644)
 run('dnsmasq','--test','--conf-file=/run/qspot/dns-guest.conf')
 run('systemctl','restart','qspot-dns@guest.service')
 pihole.configure(c,[s.split('@')[0] for s in servers])

def update_local(c):
 addresses=[str(ipaddress.ip_interface(c['guest']).ip)]
 for d in json.loads(run('ip','-j','-4','address','show')):
  addresses.extend(a['local'] for a in d.get('addr_info',[]) if a['family']=='inet')
 nft('flush set inet qspot localaddrs\nadd element inet qspot localaddrs { '+', '.join(sorted(set(addresses)))+' }')

def vpn(c):
 if not policy_routing():raise ValueError('Dieser Pi-Kernel unterstützt kein Policy-Routing')
 run('ip','rule','del','pref','177',check=False)
 run('ip','route','flush','table','177',check=False)
 run('ip','route','flush','proto','186',check=False)
 run('ip','link','del','qspot-wg',check=False)
 if c['vpn']=='off':return
 # Unreachable blocks further rule fall-through even when the interface disappears.
 run('ip','route','add','unreachable','default','table','177','metric','32767')
 run('ip','rule','add','pref','177','fwmark','177','lookup','177')
 server=c['vpn_server']
 if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',server):raise ValueError('VPN-Server auswählen')
 data=json.loads((STATE/'vpn'/f'{server}.json').read_text())
 run('ip','link','add','qspot-wg','type','wireguard')
 private=Path('/run/qspot/wg.conf')
 private.write_text(f'[Interface]\nPrivateKey = {data["private"]}\n[Peer]\nPublicKey = {data["public"]}\nEndpoint = {data["endpoint"]}\nAllowedIPs = 0.0.0.0/0\nPersistentKeepalive = 25\n');private.chmod(0o600)
 try:run('wg','setconf','qspot-wg',str(private))
 finally:private.unlink(missing_ok=True)
 for addr in data['addresses']:
  if ipaddress.ip_interface(addr).version==4:run('ip','address','add',addr,'dev','qspot-wg')
 run('ip','link','set','qspot-wg','mtu','1380','up')
 Path('/run/qspot/vpn-started').write_text(str(time.time()))
 run('ip','route','add','default','dev','qspot-wg','table','177','metric','10')
 for address in vpn_dns(c):run('ip','route','replace',address+'/32','dev','qspot-wg','proto','186')


def shaping(c):
 for module in ('sch_htb','cls_u32','sch_fq_codel'): run('modprobe',module)
 for kind,dev in [('guest',AP),('usb','pi-unused')]:
  if not Path('/sys/class/net/'+dev).exists(): continue
  limit=c[('global_' if kind=='guest' else 'usb_')+'down_kbit'] or 1000000
  run('tc','qdisc','del','dev',dev,'root',check=False)
  run('tc','qdisc','add','dev',dev,'root','handle','1:','htb','default','2')
  run('tc','class','replace','dev',dev,'parent','1:','classid','1:1','htb','rate',str(limit)+'kbit','ceil',str(limit)+'kbit')
  run('tc','class','replace','dev',dev,'parent','1:1','classid','1:2','htb','rate','1kbit','ceil',str(limit)+'kbit')
  run('tc','qdisc','replace','dev',dev,'parent','1:2','handle','20:','fq_codel')
 for dev in (WAN,'qspot-wg'):
  if not Path('/sys/class/net/'+dev).exists(): continue
  run('tc','qdisc','del','dev',dev,'root',check=False)
  run('tc','qdisc','add','dev',dev,'root','handle','1:','htb','default','2')
  run('tc','class','replace','dev',dev,'parent','1:','classid','1:1','htb','rate','1000000kbit','ceil','1000000kbit')
  run('tc','class','replace','dev',dev,'parent','1:1','classid','1:2','htb','rate','1kbit','ceil','1000000kbit')
  run('tc','qdisc','replace','dev',dev,'parent','1:2','handle','20:','fq_codel')
  for kind,group in [('guest','10'),('usb','20')]:
   limit=c[('global_' if kind=='guest' else 'usb_')+'up_kbit'] or 1000000
   run('tc','class','replace','dev',dev,'parent','1:1','classid','1:'+group,'htb','rate','1kbit','ceil',str(limit)+'kbit')
   if kind=='usb':
    run('tc','qdisc','replace','dev',dev,'parent','1:20','handle','30:','fq_codel')
    run('tc','filter','replace','dev',dev,'protocol','ip','parent','1:','prio','5','u32','match','ip','src',str(ipaddress.ip_interface(c['usb']).network),'flowid','1:20')

def device_limit(ip, profile, ident, c):
 uplink=WAN  # Shaping is applied on both paths for per-device VPN selection.
 for iface,direction,match,parent in [(AP,'down','dst','1:1'),(uplink,'up','src','1:10')]+([('qspot-wg','up','src','1:10')] if Path('/sys/class/net/qspot-wg').exists() else []):
  global_limit=c['global_'+direction+'_kbit'] or 1000000
  limit=min(profile[direction+'_kbit'] or global_limit,global_limit)
  rate=1
  cls=f'1:{ident:x}'
  run('tc','class','replace','dev',iface,'parent',parent,'classid',cls,'htb','rate',str(rate)+'kbit','ceil',str(limit)+'kbit','quantum','1514')
  run('tc','qdisc','replace','dev',iface,'parent',cls,'handle',f'{ident:x}:','fq_codel')
  run('tc','filter','replace','dev',iface,'protocol','ip','parent','1:','prio',str(ident),'u32','match','ip',match,ip+'/32','flowid',cls)

def authorize(mac, ip, seconds):
 seconds=max(1,min(int(seconds),86400))
 nft(f'add element inet qspot allowed {{ {mac} . {ip} timeout {seconds}s }}\nadd element inet qspot online {{ {ip} timeout {seconds}s }}')
def revoke(mac,ip):
 run('nft','delete','element','inet','qspot','allowed','{',mac,'.',ip,'}',check=False)
 run('nft','delete','element','inet','qspot','online','{',ip,'}',check=False)
 run('conntrack','-D','-s',ip,check=False); run('conntrack','-D','-d',ip,check=False)
def cleanup_session(ident):
 j=json.loads(run('nft','-j','list','table','inet','qspot'))
 for item in j['nftables']:
  rule=item.get('rule'); names=(f'"s{ident}"',f'"q{ident}"')
  if rule and any(n in json.dumps(rule.get('expr',[])) for n in names):
   run('nft','delete','rule','inet','qspot',rule['chain'],'handle',str(rule['handle']))
 for kind,prefix in [('counter','s'),('quota','q')]: run('nft','delete',kind,'inet','qspot',f'{prefix}{ident}',check=False)
 for dev in (AP,WAN,'qspot-wg'):
  if Path('/sys/class/net/'+dev).exists():
   run('tc','filter','del','dev',dev,'parent','1:','prio',str(ident+100),check=False)
   run('tc','class','del','dev',dev,'classid',f'1:{ident+100:x}',check=False)
def counter_add(ident,ip,remaining=0,used=0):
 # Per-session counters live before the forward filter, including upload/download.
 nft(f'add counter inet qspot s{ident} {{ packets 0 bytes {int(used)}; }}\nadd rule inet qspot accounting ip saddr {ip} counter name s{ident}\nadd rule inet qspot accounting ip daddr {ip} counter name s{ident}')
 if remaining:
  nft(f'add quota inet qspot q{ident} {{ over {int(remaining)} bytes; }}\nadd rule inet qspot quotas ip saddr {ip} quota name q{ident} drop\nadd rule inet qspot quotas ip daddr {ip} quota name q{ident} drop')
def exhausted(ident):
 try:
  j=json.loads(run('nft','-j','list','quota','inet','qspot',f'q{ident}'))
  q=next(x['quota'] for x in j['nftables'] if 'quota' in x)
  return q['used']>=q['bytes']
 except Exception:return False
def bytes_used(ident):
 try:
  j=json.loads(run('nft','-j','list','counter','inet','qspot',f's{ident}'))
  return next(x['counter']['bytes'] for x in j['nftables'] if 'counter' in x)
 except Exception: return 0

def import_wireguard(text):
 fields={}; section=''
 permitted={'Interface':{'PrivateKey','Address','DNS','MTU'},'Peer':{'PublicKey','Endpoint','AllowedIPs','PersistentKeepalive'}}
 for line in text.splitlines():
  line=line.split('#',1)[0].strip()
  if not line: continue
  if line.startswith('[') and line.endswith(']'):
   section=line[1:-1]
   if section not in permitted or section in fields: raise ValueError('Genau ein Interface und Peer erforderlich')
   fields[section]={}; continue
  if '=' not in line or section not in permitted: raise ValueError('Ungültige WireGuard-Datei')
  k,v=map(str.strip,line.split('=',1))
  if k not in permitted[section] or k in fields[section]: raise ValueError('Nicht erlaubtes WireGuard-Feld: '+k)
  fields[section][k]=v
 i=fields.get('Interface',{}); p=fields.get('Peer',{})
 import base64
 for k in (i.get('PrivateKey',''),p.get('PublicKey','')):
  if len(base64.b64decode(k,validate=True))!=32: raise ValueError('Ungültiger WireGuard-Schlüssel')
 endpoint=p.get('Endpoint','')
 if not re.fullmatch(r'(?:[a-zA-Z0-9.-]+|\[[0-9a-fA-F:]+\]):[0-9]{1,5}',endpoint): raise ValueError('Ungültiger Endpunkt')
 if not 1<=int(endpoint.rsplit(':',1)[1])<=65535: raise ValueError('Ungültiger Port')
 addresses=[str(ipaddress.ip_interface(a.strip())) for a in i.get('Address','').split(',')]
 if not any(ipaddress.ip_interface(a).version==4 for a in addresses): raise ValueError('IPv4-Adresse erforderlich')
 allowed=[str(ipaddress.ip_network(a.strip())) for a in p.get('AllowedIPs','').split(',')]
 if '0.0.0.0/0' not in allowed: raise ValueError('Volltunnel-Konfiguration erforderlich')
 dns=[str(ipaddress.ip_address(a.strip())) for a in i.get('DNS','10.64.0.1').split(',')]
 dns=[a for a in dns if ipaddress.ip_address(a).version==4]
 if not dns:raise ValueError('IPv4-DNS-Adresse erforderlich')
 return {'private':i['PrivateKey'],'public':p['PublicKey'],'endpoint':endpoint,'addresses':addresses,'dns':dns}
