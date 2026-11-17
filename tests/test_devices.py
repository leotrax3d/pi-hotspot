import json,os,sqlite3,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
tmp=tempfile.TemporaryDirectory();os.environ['QSPOT_STATE']=tmp.name
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'qspot'))
import daemon
from common import atomic,DEFAULT
class DeviceActions(unittest.TestCase):
 def tearDown(self):
  daemon.DB.close()
 def setUp(self):
  config_patch=patch.object(daemon,'CONFIG',Path(tmp.name)/'config.json');config_patch.start();self.addCleanup(config_patch.stop)
  state_patch=patch.object(daemon,'STATE',Path(tmp.name));state_patch.start();self.addCleanup(state_patch.stop)
  atomic(daemon.CONFIG,DEFAULT)
  daemon.DB=sqlite3.connect(':memory:');daemon.DB.row_factory=sqlite3.Row
  daemon.DB.executescript('CREATE TABLE sessions(id INTEGER PRIMARY KEY,mac TEXT,ip TEXT,profile TEXT,code_id INTEGER,started REAL,deadline REAL,active INTEGER,used INTEGER,reason TEXT);CREATE TABLE codes(id INTEGER);CREATE TABLE blocked(mac TEXT);INSERT INTO sessions VALUES(1,"02:00:00:00:00:01","10.77.0.20","standard",NULL,0,0,1,0,"");INSERT INTO codes VALUES(10);INSERT INTO blocked VALUES("02:00:00:00:00:02");')
 def test_clear_devices_preserves_codes_and_blocks(self):
  with patch('daemon.network.nft') as nft,patch('daemon.network.revoke'),patch('daemon.network.cleanup_session'),patch('daemon.run',return_value='{"nftables":[]}'):
   daemon.dispatch({'method':'clear_devices'})
   self.assertIn('flush set inet qspot allowed',nft.call_args[0][0])
  self.assertEqual(daemon.rows('SELECT * FROM sessions'),[])
  self.assertEqual(len(daemon.rows('SELECT * FROM codes')),1)
  self.assertEqual(len(daemon.rows('SELECT * FROM blocked')),1)
 def test_unblock_all(self):
  with patch('daemon.network.nft') as nft:
   daemon.dispatch({'method':'unblock_all'});nft.assert_called_once_with('flush set inet qspot blocked')
  self.assertEqual(daemon.rows('SELECT * FROM blocked'),[])
if __name__=='__main__':unittest.main()
