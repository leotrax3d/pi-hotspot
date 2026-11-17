#!/usr/bin/env python3
"""Standalone boot recovery; it deliberately does not import application code."""
import json
import os
import subprocess
import sys
from pathlib import Path

STATE=Path('/var/lib/pi-hotspot')


def owner_alive(data):
 try:
  if data['boot']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():return False
  start=Path('/proc')/str(int(data['pid']))/'stat'
  return start.read_text().split(') ',1)[1].split()[19]==data['process_start']
 except (OSError,ValueError,KeyError,IndexError):return False


def recover(force=False):
 marker=STATE/'transaction.json'
 if not marker.exists():return
 data=json.loads(marker.read_text())
 if owner_alive(data):
  if force:raise ValueError('Installation läuft noch')
  return
 saved=Path(data['backup']).resolve()
 if saved.parent!=Path('/var/backups/pi-hotspot') or saved.stat().st_uid!=0:
  raise ValueError('Ungültige Wiederherstellungssicherung')
 env={**os.environ,'PI_HOTSPOT_BOOT_RECOVERY':'0' if force else '1'}
 subprocess.run(['/usr/bin/python3',str(saved/'rollback.py'),str(saved)],check=True,env=env)
 if not force:
  manifest=json.loads((saved/'manifest.json').read_text())
  for unit,state in manifest.get('services',{}).items():
   if state.get('active'):subprocess.run(['systemctl','--no-block','start',unit],check=True)


if __name__=='__main__':
 if '--guard' in sys.argv:
  marker=STATE/'transaction.json'
  if marker.exists() and not owner_alive(json.loads(marker.read_text())):raise SystemExit(1)
 else:recover(force='--manual' in sys.argv)
