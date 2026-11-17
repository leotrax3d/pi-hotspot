"""Real official-image/API/DNS integration check, on an isolated Linux CI runner."""
import copy,json,os,socket,struct,subprocess,sys,tempfile,time,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'qspot'))
import pihole
from common import DEFAULT
ENGINE=os.environ.get('PI_HOTSPOT_CONTAINER_ENGINE','docker')

def run(*args):
 if args[0]=='docker':args=(ENGINE,*args[1:])
 return subprocess.run(args,check=True,capture_output=True,text=True).stdout.strip()

def dataplane(c,state):
 """Real Linux netns: source identity, filtering and local-only outage DNS."""
 import network
 namespace='pi-hotspot-test';ap='ph-test-ap';peer='ph-test-peer'
 fallback=None
 try:
  run('ip','netns','add',namespace)
  run('ip','link','add',ap,'type','veth','peer','name',peer)
  run('ip','link','set',peer,'netns',namespace)
  run('ip','addr','add','10.77.0.1/24','dev',ap);run('ip','link','set',ap,'up')
  run('ip','netns','exec',namespace,'ip','link','set','lo','up')
  run('ip','netns','exec',namespace,'ip','link','set',peer,'address','02:00:00:00:00:01')
  run('ip','netns','exec',namespace,'ip','addr','add','10.77.0.2/24','dev',peer)
  run('ip','netns','exec',namespace,'ip','link','set',peer,'up')
  def apply_nft(script):
   subprocess.run(['nft','-f','-'],input=script,text=True,check=True)
  network.nft=apply_nft
  network.AP=ap;network.WAN='eth0';network.base(c)
  conf=state/'fallback.conf'
  conf.write_text('interface='+ap+'\nbind-interfaces\nlisten-address=10.77.0.1\nno-resolv\nno-hosts\nhost-record='+c['portal_domain']+',10.77.0.1\nlog-facility=/dev/null\n')
  fallback=subprocess.Popen(['dnsmasq','--no-daemon','--conf-file='+str(conf)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  time.sleep(.3)
  assert fallback.poll() is None
  def query(name):
   code="import socket,struct,json;name="+repr(name)+";labels=b''.join(bytes([len(x)])+x.encode() for x in name.split('.'))+b'\\0';packet=struct.pack('!HHHHHH',43210,256,1,0,0,0)+labels+struct.pack('!HH',1,1);s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.settimeout(3);s.sendto(packet,('10.77.0.1',53));data=s.recv(4096);print(json.dumps({'rcode':data[3]&15,'answers':int.from_bytes(data[6:8],'big'),'ip':socket.inet_ntoa(data[-4:])}))"
   return json.loads(run('ip','netns','exec',namespace,'python3','-c',code))
  pihole.request('/domains/deny/exact',{'domain':c['portal_domain'],'enabled':True,'groups':[0],'comment':'integration-test'})
  pihole.LAST_HEALTH=0;pihole.maintain(c)
  assert query(c['portal_domain'])['ip']=='10.77.0.1'
  # The MAC-based group bypass applies to this real Ethernet peer.
  assert query('blocked.test')['ip']=='192.0.2.5'
  pihole.action(c,{'operation':'device','mac':'02:00:00:00:00:01','enabled':True})
  time.sleep(.5)
  blocked=query('blocked.test');assert blocked['ip']=='0.0.0.0' or blocked['rcode']==3,blocked
  for _ in range(10):
   query('blocked.test')
   seen=pihole.request('/queries?length=50')['queries']
   if any(x.get('client',{}).get('ip')=='10.77.0.2' for x in seen):break
   time.sleep(.3)
  assert any(x.get('client',{}).get('ip')=='10.77.0.2' for x in seen),'Client address was lost'
  run('systemctl','stop','qspot-pihole-test')
  pihole.LAST_HEALTH=0;pihole.maintain(c)
  assert query(c['portal_domain'])['ip']=='10.77.0.1'
  external=query('unfiltered.example');assert external['answers']==0,external
  run('systemctl','start','qspot-pihole-test')
  for _ in range(30):
   try:
    pihole.LAST_HEALTH=0;pihole.maintain(c)
    if pihole.ROUTED==pihole.PORT:break
   except (ValueError,OSError):pass
   time.sleep(1)
  assert pihole.ROUTED==pihole.PORT
  assert query(c['portal_domain'])['ip']=='10.77.0.1'
  assert pihole.request('/clients')['clients'][0]['groups']==[0]
  # Logging is off by default in production: MAC filters must still work.
  run('systemctl','stop','qspot-pihole-test')
  environment=state/'pihole.env'
  environment.write_text(environment.read_text().replace('FTLCONF_misc_privacylevel=0\n','FTLCONF_misc_privacylevel=3\n'))
  c['dns_logging']=False;pihole.invalidate();pihole.LAST_HEALTH=0;pihole.reset_route()
  run('systemctl','start','qspot-pihole-test')
  for _ in range(30):
   try:
    pihole.LAST_HEALTH=0;pihole.maintain(c)
    if pihole.ROUTED==pihole.PORT:break
   except (ValueError,OSError):pass
   time.sleep(1)
  assert query('blocked.test')['ip']=='0.0.0.0'
  pihole.action(c,{'operation':'device','mac':'02:00:00:00:00:01','enabled':False})
  assert query('blocked.test')['ip']=='192.0.2.5'
  assert pihole.view(c)['events']==[]
  assert pihole.request('/queries?length=50')['queries']==[]
  print('Linux namespaces: real MAC selection, source identity, DNS redirect, filtered outage and restart recovery: OK')
 finally:
  if fallback:fallback.terminate();fallback.wait(timeout=5)
  subprocess.run(['nft','delete','table','inet','qspot'],capture_output=True)
  subprocess.run(['ip','link','del',ap],capture_output=True)
  subprocess.run(['ip','netns','del',namespace],capture_output=True)

with tempfile.TemporaryDirectory() as temp:
 state=Path(temp);pihole.STATE=state
 (state/'pihole-password').write_text('integration-test-only-password')
 c=copy.deepcopy(DEFAULT);c['features']['pihole']=True;c['dns_logging']=True
 env=pihole.environment(c,['192.0.2.1']);env.pop('FTLCONF_dns_blocking_active')
 env['FTLCONF_dns_port']='5354';env['FTLCONF_webserver_port']='127.0.0.1:8081'
 env['FTLCONF_misc_dnsmasq_lines']='address=/blocked.test/192.0.2.5'
 path=state/'pihole.env';path.write_text(''.join(k+'='+v+'\n' for k,v in env.items()))
 (state/'pihole').mkdir()
 pihole.API='http://127.0.0.1:8081/api';pihole.PORT=5354
 run('docker','pull',pihole.IMAGE)
 manifest=json.loads(run(ENGINE,'manifest','inspect',pihole.IMAGE))
 assert any(x.get('platform',{}).get('architecture')=='arm64' for x in manifest.get('manifests',[])),'Official image has no ARM64 build'
 name='pi-hotspot-integration'
 unit=Path('/etc/systemd/system/qspot-pihole-test.service')
 try:
  if ENGINE=='podman':
   run('nft','add','table','inet','qspot')
   text=(Path(__file__).resolve().parents[1]/'system/qspot-pihole.service').read_text().replace('qspot-pihole',name).replace('/var/lib/qspot',str(state))
   unit.write_text(text)
   run('systemctl','daemon-reload');run('systemctl','enable','--now','qspot-pihole-test')
   assert run('systemctl','is-enabled','qspot-pihole-test')=='enabled'
  else:run('docker','run','-d','--name',name,'--network','host','--env-file',str(path),'--log-driver','none','-v',str(state/'pihole')+':/etc/pihole',pihole.IMAGE)
  for _ in range(90):
   try:
    if pihole.dns_alive(c):pihole.request('/dns/blocking');break
   except (ValueError,OSError):pass
   time.sleep(1)
  else:raise RuntimeError('Official Pi-hole image did not become ready')
  pihole.action(c,{'operation':'domain','domain':'blocked.test','mode':'deny'})
  pihole.action(c,{'operation':'pause'})
  assert pihole.request('/dns/blocking')['blocking']=='disabled'
  assert 290<pihole.request('/dns/blocking')['timer']<=300
  pihole.action(c,{'operation':'blocking','enabled':True})
  assert pihole.request('/dns/blocking')['blocking']=='enabled'
  pihole.SID='expired-session'
  assert pihole.request('/dns/blocking')['blocking']=='enabled'
  pihole.action(c,{'operation':'device','mac':'02:00:00:00:00:01','enabled':False})
  assert pihole.request('/clients')['clients'][0]['groups']==[]
  assert pihole.view(c)['available']
  pihole.request('/action/flush/logs',{},'POST')
  if ENGINE=='podman':dataplane(c,state)
  print('Official Pi-hole image, private v6 API, local DNS, rules, clients, pause, statistics and purge: OK')
 finally:
  if ENGINE=='podman':
   subprocess.run(['systemctl','disable','--now','qspot-pihole-test'],capture_output=True)
   unit.unlink(missing_ok=True);subprocess.run(['systemctl','daemon-reload'],capture_output=True)
   subprocess.run(['nft','delete','table','inet','qspot'],capture_output=True)
  subprocess.run([ENGINE,'rm','-f',name],capture_output=True)
