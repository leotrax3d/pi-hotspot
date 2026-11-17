"""Installation-specific interface names; never shell fragments."""
import json
import os
import re
from pathlib import Path

PATH = Path(os.environ.get('PI_HOTSPOT_PLATFORM', '/etc/qspot/platform.json'))


def load():
    data = json.loads(PATH.read_text()) if PATH.exists() else {}
    result = {'uplink': 'eth0', 'radio': 'wlan0', 'ap': 'wlan0',
              'mode': 'lan', **data}
    for key in ('uplink', 'radio', 'ap'):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,15}', result[key]):
            raise ValueError('Ungültiger Schnittstellenname')
    if result['mode'] not in ('lan', 'dual', 'single'):
        raise ValueError('Ungültiger Netzwerkmodus')
    if result['uplink'] == result['ap']:
        raise ValueError('Uplink und Hotspot benötigen unterschiedliche Interfaces')
    return result
