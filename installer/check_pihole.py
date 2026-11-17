"""Real official-image/API/DNS integration check, on an isolated Linux CI runner."""
import copy,json,os,socket,struct,subprocess,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'qspot'))
import pihole
from common import DEFAULT

def run(*args):return subprocess.run(args,check=True,capture_output=True,text=True).stdout.strip()

with tempfile.TemporaryDirectory() as temp:
 state=Path(temp);pihole.STATE=state
 (state/'pihole-password').write_text('integration-test-only-password')
 c=copy.deepcopy(DEFAULT);c['features']['pihole']=True;c['dns_logging']=True
 env=pihole.environment(c,['192.0.2.1']);env.pop('FTLCONF_dns_blocking_active')
 env['FTLCONF_dns_port']='1053';env['FTLCONF_webserver_port']='127.0.0.1:18081'
 env['FTLCONF_misc_dnsmasq_lines']='address=/blocked.test/192.0.2.5'
 path=state/'env';path.write_text(''.join(k+'='+v+'\n' for k,v in env.items()))
 pihole.API='http://127.0.0.1:18081/api';pihole.PORT=1053
 run('docker','pull',pihole.IMAGE)
 name='pi-hotspot-integration'
 try:
  run('docker','run','-d','--name',name,'--network','host','--env-file',str(path),'--log-driver','none',pihole.IMAGE)
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
  pihole.action(c,{'operation':'device','mac':'02:00:00:00:00:01','enabled':False})
  assert pihole.request('/clients')['clients'][0]['groups']==[]
  assert pihole.view(c)['available']
  pihole.request('/action/flush/logs',{},'POST')
  print('Official Pi-hole image, private v6 API, local DNS, rules, clients, pause, statistics and purge: OK')
 finally:subprocess.run(['docker','rm','-f',name],capture_output=True)
