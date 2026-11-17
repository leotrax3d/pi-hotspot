from pathlib import Path
import json, subprocess
from common import STATE, atomic
if (STATE/'pending.json').exists():
 atomic(STATE/'config.json',json.loads((STATE/'previous.json').read_text()))
 (STATE/'pending.json').unlink()
 subprocess.run(['systemctl','restart','qspot-net'],check=True)
