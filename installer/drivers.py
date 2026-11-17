"""Detected USB Wi-Fi drivers. External sources are pinned to a reviewed commit."""
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

SOURCE='https://github.com/radxa-pkg/aic8800.git'
REVISION='5562c254b0231be34588dc608ec28c4f1d613285'
VERSION='0.1.'+REVISION[:12]
PACKAGE='pi-hotspot-aic8800'
AIC_IDS={'a69c:8d80','a69c:8d81','a69c:8d83','368b:8d88','a69c:88dc','a69c:88dd','a69c:88de'}
SWITCH_MESSAGE='555342431234567800000000000010fd0000000000000000000000000000f2'


def command(*args,check=True,cwd=None):
 p=subprocess.run(args,text=True,capture_output=True,cwd=cwd)
 if check and p.returncode:raise RuntimeError(f'{args[0]}: {p.stderr.strip()[-1200:]}')
 return p.stdout.strip() if p.returncode==0 else ''


def inventory(root=Path('/sys/bus/usb/devices'),net=Path('/sys/class/net')):
 result=[]
 if not root.exists():return result
 for device in sorted(root.iterdir()):
  if not (device/'idVendor').exists():continue
  vid=(device/'idVendor').read_text().strip().lower();pid=(device/'idProduct').read_text().strip().lower()
  product=(device/'product').read_text().strip() if (device/'product').exists() else ''
  manufacturer=(device/'manufacturer').read_text().strip() if (device/'manufacturer').exists() else ''
  interfaces=[n.name for n in net.iterdir() if (n/'phy80211').exists() and device.resolve() in (n/'device').resolve().parents]
  identity=vid+':'+pid
  family='aic8800' if identity in AIC_IDS or identity=='1111:1111' and re.search(r'aic|ax900|88m80|ugreen',product+' '+manufacturer,re.I) else ''
  if not family and re.search(r'wifi|wi-fi|wireless|wlan|802\.11',product,re.I):
   if vid in ('0bda','2357'):family='realtek'
   elif vid in ('0e8d','148f'):family='mediatek'
  if family or identity=='1111:1111':
   result.append({'path':str(device),'id':identity,'product':product,'family':family,'interfaces':interfaces,
                  'bus':(device/'busnum').read_text().strip(),'device':(device/'devnum').read_text().strip()})
 return result


def apply_usb_patches(repo):
 # Vendor sources mix CRLF and LF. Normalize before applying Debian's LF patches.
 for path in (repo/'src/USB').rglob('*'):
  if path.is_file() and (path.suffix in ('.c','.h','.mk') or path.name=='Makefile'):
   raw=path.read_bytes()
   if b'\r\n' in raw:path.write_bytes(raw.replace(b'\r\n',b'\n'))
 series=repo/'debian/patches/series'
 for line in series.read_text().splitlines():
  name=line.split('#',1)[0].strip()
  if not name:continue
  patch=repo/'debian/patches'/name
  if not patch.is_file():raise ValueError('Fehlender Treiber-Patch: '+name)
  if 'src/USB/' not in patch.read_text():continue
  command('git','apply','--ignore-whitespace','--include=src/USB/*','--allow-empty',str(patch),cwd=repo)


def dkms_config():
 return f'''PACKAGE_NAME="{PACKAGE}"
PACKAGE_VERSION="{VERSION}"
MAKE[0]="make -j2 -C ${{kernel_source_dir}} M=${{dkms_tree}}/{PACKAGE}/{VERSION}/build/aic_load_fw CONFIG_PLATFORM_UBUNTU=y modules && make -j2 -C ${{kernel_source_dir}} M=${{dkms_tree}}/{PACKAGE}/{VERSION}/build/aic8800_fdrv KBUILD_EXTRA_SYMBOLS=${{dkms_tree}}/{PACKAGE}/{VERSION}/build/aic_load_fw/Module.symvers CONFIG_PLATFORM_UBUNTU=y modules"
CLEAN="make -C aic_load_fw clean; make -C aic8800_fdrv clean"
BUILT_MODULE_NAME[0]="aic_load_fw"
BUILT_MODULE_LOCATION[0]="aic_load_fw"
DEST_MODULE_LOCATION[0]="/updates/dkms"
BUILT_MODULE_NAME[1]="aic8800_fdrv"
BUILT_MODULE_LOCATION[1]="aic8800_fdrv"
DEST_MODULE_LOCATION[1]="/updates/dkms"
AUTOINSTALL="yes"
'''


def write_dkms_source(repo,source):
 base=repo/'src/USB/driver_fw/drivers/aic8800'
 for module in ('aic_load_fw','aic8800_fdrv'):shutil.copytree(base/module,source/module)
 for makefile in source.rglob('Makefile'):
  text=makefile.read_text();text=re.sub(r'MAKEFLAGS\s*\+=-j\$\(shell nproc\)','MAKEFLAGS +=-j2',text)
  if makefile.parent.name=='aic8800_fdrv':
   text+='\nccflags-y += $(shell python3 $(src)/pi_hotspot_probe.py $(srctree)/include/net/cfg80211.h)\n'
  makefile.write_text(text)
 (source/'aic8800_fdrv/pi_hotspot_probe.py').write_text('import re,sys\nfrom pathlib import Path\ntext=Path(sys.argv[1]).read_text()\nmatch=re.search(r"int\\s+\\(\\*set_monitor_channel\\)\\s*\\((.*?)\\);",text,re.S)\nif match and "struct net_device" in match.group(1):print("-DPI_HOTSPOT_MONITOR_NETDEV")\n')
 # Stable distribution kernels backport cfg80211 API changes without changing
 # LINUX_VERSION_CODE. Select the signature from the actual build headers.
 monitor_condition=r'#if \(LINUX_VERSION_CODE >= KERNEL_VERSION\(6, 13, 0\)\) \|\| \\\n\s*\(LINUX_VERSION_CODE >= KERNEL_VERSION\(6, 12, 101\)\)'
 for path in (source/'aic8800_fdrv').iterdir():
  if path.suffix in ('.c','.h'):
   text=path.read_bytes().replace(b'\r\n',b'\n');text=re.sub(monitor_condition.encode(),b'#if defined(PI_HOTSPOT_MONITOR_NETDEV)',text);path.write_bytes(text)
 # Brostrend/post-switch variant uses the D81 firmware family.
 for module in ('aic_load_fw','aic8800_fdrv'):
  usb=source/module/'aicwf_usb.c';text=usb.read_text()
  text=text.replace('pid == USB_PRODUCT_ID_AIC8800D81)', 'pid == USB_PRODUCT_ID_AIC8800D81 || pid == 0x8d83)')
  text=text.replace('pid == USB_DEVICE_ID_AIC_8800D81)', 'pid == USB_DEVICE_ID_AIC_8800D81 || pid == 0x8d83)')
  text=text.replace('id->idProduct == USB_DEVICE_ID_AIC_8800D81 ||', 'id->idProduct == USB_DEVICE_ID_AIC_8800D81 || id->idProduct == 0x8d83 ||')
  text=text.replace('static struct usb_device_id aicwf_usb_id_table[] = {','static struct usb_device_id aicwf_usb_id_table[] = {\n    {USB_DEVICE(0xa69c, 0x8d83)},')
  usb.write_text(text)
 (source/'dkms.conf').write_text(dkms_config())


def install_aic():
 kernel=platform.release()
 command('apt-get','install','-y','--no-install-recommends','dkms','build-essential','git','patch','usb-modeswitch','usb-modeswitch-data')
 if not (Path('/lib/modules')/kernel/'build/Makefile').exists():
  command('apt-get','install','-y','linux-headers-'+kernel)
 if not (Path('/lib/modules')/kernel/'build/Makefile').exists():raise RuntimeError('Kernel-Header fehlen: '+kernel)
 source=Path('/usr/src')/(PACKAGE+'-'+VERSION)
 if source.exists():
  command('dkms','install','-m',PACKAGE,'-v',VERSION,'-k',kernel)
  command('depmod','-a',kernel);command('modprobe','aic_load_fw');command('modprobe','aic8800_fdrv');return
 with tempfile.TemporaryDirectory(prefix='pi-hotspot-driver-') as temporary:
  repo=Path(temporary)/'aic8800'
  command('git','init',str(repo));command('git','remote','add','origin',SOURCE,cwd=repo)
  command('git','sparse-checkout','init','--cone',cwd=repo)
  command('git','sparse-checkout','set','src/USB','debian/patches',cwd=repo)
  command('git','fetch','--depth','1','--filter=blob:none','origin',REVISION,cwd=repo)
  command('git','checkout','--detach','FETCH_HEAD',cwd=repo)
  if command('git','rev-parse','HEAD',cwd=repo)!=REVISION:raise ValueError('Unerwarteter Treiberstand')
  apply_usb_patches(repo)
  base=repo/'src/USB/driver_fw/drivers/aic8800'
  # No upstream installation scripts are executed.
  source.mkdir()
  try:
   write_dkms_source(repo,source)
   firmware=repo/'src/USB/driver_fw/fw'
   target=Path('/lib/firmware/aic8800_fw/USB')
   shutil.copytree(firmware,target,dirs_exist_ok=True)
   command('dkms','add','-m',PACKAGE,'-v',VERSION)
   command('dkms','build','-m',PACKAGE,'-v',VERSION,'-k',kernel)
   command('dkms','install','-m',PACKAGE,'-v',VERSION,'-k',kernel)
  except BaseException:
   command('dkms','remove','-m',PACKAGE,'-v',VERSION,'--all',check=False)
   if source.parent==Path('/usr/src') and source.name==PACKAGE+'-'+VERSION:shutil.rmtree(source,ignore_errors=True)
   raise
 command('depmod','-a',kernel);command('modprobe','aic_load_fw');command('modprobe','aic8800_fdrv')
 Path('/etc/modules-load.d/pi-hotspot-aic.conf').write_text('aic_load_fw\naic8800_fdrv\n')


def switch(device):
 if device['id']!='1111:1111':return
 command('usb_modeswitch','-v','0x1111','-p','0x1111','-b',device['bus'],'-g',device['device'],'-M',SWITCH_MESSAGE)
 # Match this device's product string, rather than every generic 1111:1111 disk.
 product=device['product']
 if product and re.fullmatch(r'[a-zA-Z0-9 ._+-]{1,100}',product):
  config=Path('/etc/usb_modeswitch.d/pi-hotspot-aic.conf')
  config.write_text('DefaultVendor=0x1111\nDefaultProduct=0x1111\nMessageContent="'+SWITCH_MESSAGE+'"\n')
  Path('/etc/udev/rules.d/71-pi-hotspot-aic.rules').write_text('ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="1111", ATTR{idProduct}=="1111", ATTR{product}=="'+product+'", RUN+="/usr/sbin/usb_modeswitch -c /etc/usb_modeswitch.d/pi-hotspot-aic.conf"\n')
  command('udevadm','control','--reload-rules')


def prepare(yes,choose):
 devices=inventory()
 for d in devices:
  if d['id']=='1111:1111' and not d['family'] and not d['interfaces']:
   if choose(d['product']+' | 1111:1111',['UGREEN CM762/CM763 / AIC8800','Anderes Gerät'],default=1).startswith('UGREEN'):d['family']='aic8800'
 pending=[d for d in devices if d['family'] and not d['interfaces']]
 if not pending:return devices
 print('\nUSB-WLAN: '+', '.join(d['product']+' ('+d['id']+')' for d in pending))
 print('Automatisch: Firmware, Kernel-Header, DKMS und USB-Moduswechsel, soweit erforderlich.')
 if not yes('Treiber jetzt einrichten?',True):return devices
 command('apt-get','update')
 families={d['family'] for d in pending}
 if 'aic8800' in families:
  install_aic()
  for device in pending:
   if device['family']=='aic8800':switch(device)
 if 'realtek' in families:command('apt-get','install','-y','firmware-realtek')
 if 'mediatek' in families:
  package='firmware-mediatek' if command('apt-cache','show','firmware-mediatek',check=False) else 'firmware-misc-nonfree'
  command('apt-get','install','-y',package)
 # Ask the kernel for the correct module for each interface after firmware setup.
 for device in pending:
  for entry in Path(device['path']).parent.glob(Path(device['path']).name+':*/modalias'):
   command('modprobe',entry.read_text().strip(),check=False)
 command('udevadm','trigger','--subsystem-match=usb');command('udevadm','settle')
 report=[]
 for _ in range(15):
  time.sleep(2);report=inventory()
  if all(any(r['path']==d['path'] and r['interfaces'] for r in report) for d in pending):break
 else:raise RuntimeError('USB-WLAN wurde nicht bereit. dmesg und dkms status prüfen; keine Netzwerkkonfiguration geändert.')
 Path('/var/lib/pi-hotspot').mkdir(exist_ok=True)
 Path('/var/lib/pi-hotspot/drivers.json').write_text(json.dumps({'source':SOURCE,'revision':REVISION,'devices':report},indent=2))
 return report


if __name__=='__main__':
 if os.geteuid()!=0:raise SystemExit('sudo erforderlich')
 import setup
 prepare(setup.yes,setup.choose)
