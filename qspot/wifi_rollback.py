import json
from common import STATE,run
p=STATE/'wifi-pending.json'
if p.exists():
 data=json.loads(p.read_text())
 run('nmcli','--wait','25','connection','up','uuid',data['previous'],timeout=30)
 p.unlink()
