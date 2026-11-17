"""CI-only source preparation: no modules are installed or loaded."""
import sys
from pathlib import Path
from drivers import REVISION,SOURCE,command,apply_usb_patches,write_dkms_source

repo=Path(sys.argv[1]).resolve();destination=Path(sys.argv[2]).resolve()
command('git','init',str(repo));command('git','remote','add','origin',SOURCE,cwd=repo)
command('git','sparse-checkout','init','--cone',cwd=repo)
command('git','sparse-checkout','set','src/USB','debian/patches',cwd=repo)
command('git','fetch','--depth','1','--filter=blob:none','origin',REVISION,cwd=repo)
command('git','checkout','--detach','FETCH_HEAD',cwd=repo)
assert command('git','rev-parse','HEAD',cwd=repo)==REVISION
apply_usb_patches(repo);destination.mkdir();write_dkms_source(repo,destination)
print('Pinned USB source and compatibility patches verified')
