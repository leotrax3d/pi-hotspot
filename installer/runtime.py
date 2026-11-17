"""Bounded commands, one installer at a time, and persistent recovery state."""
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import signal
import time
from pathlib import Path

STATE=Path('/var/lib/pi-hotspot')
LOCK=Path('/run/lock/pi-hotspot.lock')
RECOVERY_UNIT='''[Unit]
Description=pi-hotspot interrupted installation recovery
After=NetworkManager.service
Before=qspot-net.service qspot-web.service
ConditionPathExists=/var/lib/pi-hotspot/transaction.json
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /var/lib/pi-hotspot/recovery.py
TimeoutStartSec=600
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
'''


def command(*args,check=True,quiet=False,timeout=120,cwd=None):
 env={**os.environ,'LC_ALL':'C.UTF-8'}
 if args[0] in ('apt-get','dpkg'):env['DEBIAN_FRONTEND']='noninteractive'
 with subprocess.Popen(args,text=True,encoding='utf-8',errors='replace',stdout=subprocess.PIPE if quiet else None,
                       stderr=subprocess.PIPE if quiet else None,env=env,cwd=cwd,start_new_session=True) as process:
  try:output,_=process.communicate(timeout=timeout)
  except subprocess.TimeoutExpired:
   if os.name=='posix':os.killpg(process.pid,signal.SIGTERM)
   else:process.terminate()
   try:process.communicate(timeout=5)
   except subprocess.TimeoutExpired:
    if os.name=='posix':os.killpg(process.pid,signal.SIGKILL)
    else:process.kill()
    process.communicate()
   raise RuntimeError(f'{args[0]}: Zeitlimit ({timeout}s) überschritten') from None
  if check and process.returncode:raise RuntimeError(f'{args[0]} fehlgeschlagen (Code {process.returncode})')
  return (output or '').strip() if quiet else process.returncode


def apt(*args):
 return command('apt-get','-o','DPkg::Lock::Timeout=120','-o','Acquire::Retries=3',
                '-o','Acquire::http::Timeout=30','-o','Acquire::https::Timeout=30',
                '-o','Dpkg::Options::=--force-confold',*args,timeout=1200)


@contextlib.contextmanager
def exclusive():
 import fcntl
 LOCK.parent.mkdir(parents=True,exist_ok=True)
 with LOCK.open('a+') as file:
  os.chmod(LOCK,0o600)
  try:fcntl.flock(file,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise ValueError('Eine Installation oder ein Update läuft bereits') from None
  file.seek(0);file.truncate();file.write(str(os.getpid()));file.flush()
  try:yield
  finally:fcntl.flock(file,fcntl.LOCK_UN)


def digest(path):
 value=hashlib.sha256()
 with Path(path).open('rb') as file:
  for data in iter(lambda:file.read(1024*1024),b''):value.update(data)
 return value.hexdigest()


def save(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 temporary=path.with_suffix('.tmp')
 with temporary.open('w') as file:
  os.chmod(temporary,0o600);json.dump(value,file);file.flush();os.fsync(file.fileno())
 os.replace(temporary,path)
 fd=os.open(path.parent,os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)


def begin(saved,kind,source):
 STATE.mkdir(parents=True,exist_ok=True);STATE.chmod(0o700)
 if (STATE/'transaction.json').exists():raise ValueError('Offene Wiederherstellung: sudo pi-hotspot recover')
 shutil.copy2(Path(source)/'installer/recovery.py',STATE/'recovery.py')
 (STATE/'recovery.py').chmod(0o700)
 unit=Path('/etc/systemd/system/pi-hotspot-recover.service');unit.write_text(RECOVERY_UNIT);unit.chmod(0o644)
 command('systemctl','daemon-reload');command('systemctl','enable','pi-hotspot-recover.service')
 os.sync()
 pid=os.getpid();process=Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split()[19]
 save(STATE/'transaction.json',{'backup':str(saved),'kind':kind,'stage':'prepared','time':time.time(),
                              'boot':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                              'pid':pid,'process_start':process})
 try:
  command('systemd-run','--collect','--unit=pi-hotspot-transaction-rollback','--on-active='+('45m' if kind=='install' else '15m'),
          '/usr/bin/python3',str(Path(saved)/'rollback.py'),str(saved),'--watchdog')
 except BaseException:
  (STATE/'transaction.json').unlink(missing_ok=True);raise


def stage(name):
 path=STATE/'transaction.json'
 if path.exists():
  data=json.loads(path.read_text());data['stage']=name;save(path,data)
 print('› '+name,flush=True)


def finish():
 command('systemctl','stop','pi-hotspot-transaction-rollback.timer')
 path=STATE/'transaction.json'
 if path.exists():
  data=json.loads(path.read_text());data['stage']='complete';save(STATE/'last-operation.json',data)
  path.unlink()
  fd=os.open(STATE,os.O_DIRECTORY)
  try:os.fsync(fd)
  finally:os.close(fd)
