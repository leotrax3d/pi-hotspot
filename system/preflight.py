import runpy, sys
from pathlib import Path
sys.argv=[str(Path(__file__).resolve().parents[1]/"installer/setup.py"),"--check"]
runpy.run_path(sys.argv[0],run_name="__main__")
