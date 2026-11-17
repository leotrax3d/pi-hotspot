"""Optional official ARM64 image. No remote installation shell scripts."""
import secrets
import socket
from pathlib import Path
import runtime

def prepare(c):
 if not c.get('features',{}).get('pihole'):return
 from pihole import IMAGE
 # Podman host networking preserves client identity without a bridge or daemon.
 runtime.apt('install','-y','--no-install-recommends','podman')
 runtime.command('podman','pull',IMAGE,timeout=600,quiet=True)
 running=runtime.command('podman','inspect','-f','{{.State.Running}}','qspot-pihole',check=False,quiet=True)=='true'
 if not running:
  for port in (5354,8081):
   for kind in ((socket.SOCK_STREAM,socket.SOCK_DGRAM) if port==5354 else (socket.SOCK_STREAM,)):
    with socket.socket(socket.AF_INET,kind) as probe:
     try:probe.bind(('0.0.0.0',port))
     except OSError:raise ValueError('DNS-Port belegt: '+str(port)) from None
 state=Path('/var/lib/qspot');state.mkdir(parents=True,exist_ok=True)
 password=state/'pihole-password'
 if not password.exists():password.write_text(secrets.token_urlsafe(48))
 password.chmod(0o600)
 (state/'pihole').mkdir(mode=0o700,exist_ok=True)
