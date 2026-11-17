#!/usr/bin/env python3
"""Read-only diagnostics; never prints configuration, logs or VPN keys."""
import json
import shutil
import subprocess
from pathlib import Path


def query(*args):
 try:return subprocess.run(args,text=True,capture_output=True,timeout=8).stdout.strip()
 except (OSError,subprocess.TimeoutExpired):return ''


def report():
 units=('qspot-net','qspot-web','qspot-hostapd','qspot-dns@guest','pi-hotspot-recover','qspot-pihole')
 handshakes=query('wg','show','qspot-wg','latest-handshakes')
 return {'services':{u:{'active':query('systemctl','is-active',u),'enabled':query('systemctl','is-enabled',u)} for u in units},
         'dns_ports':query('ss','-lntu'),
         'pihole_image':query('podman','inspect','-f','{{.Config.Image}}','qspot-pihole'),
         'disk_free_mb':shutil.disk_usage('/').free//1024**2,
         'pending_recovery':Path('/var/lib/pi-hotspot/transaction.json').exists(),
         'wifi':query('iw','dev'),'modules':query('dkms','status'),
         'route':query('ip','-4','route','show','default'),
         'vpn_handshake_seen':any(line.split()[-1].isdigit() and int(line.split()[-1])>0 for line in handshakes.splitlines() if line.split())}


if __name__=='__main__':print(json.dumps(report(),ensure_ascii=False,indent=2))
