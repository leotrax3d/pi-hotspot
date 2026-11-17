import base64, copy, sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'qspot'))
from common import DEFAULT, validate, password_hash, password_ok, totp
from network import import_wireguard
class SecurityTests(unittest.TestCase):
 def test_overlap(self):
  c=copy.deepcopy(DEFAULT);c['usb']=c['guest']
  with self.assertRaises(ValueError):validate(c)
  with self.assertRaises(ValueError):validate(DEFAULT,[{'dev':'eth0','dst':'10.77.0.0/16'}])
 def test_shell_payload_rejected(self):
  for key,value in [('ssid','QSpot\ninterface=wlan0'),('hostname','qspot;reboot'),('channel',36)]:
   c=copy.deepcopy(DEFAULT);c[key]=value
   with self.assertRaises(ValueError):validate(c)
 def test_password(self):
  value=password_hash('a unique passphrase 123')
  self.assertTrue(password_ok('a unique passphrase 123',value));self.assertFalse(password_ok('wrong',value))
 def test_wireguard_hooks(self):
  key=base64.b64encode(bytes(range(32))).decode()
  text=f'[Interface]\nPrivateKey={key}\nAddress=10.64.1.2/32\nDNS=10.64.0.1\n[Peer]\nPublicKey={key}\nEndpoint=se.example.net:51820\nAllowedIPs=0.0.0.0/0,::/0\n'
  self.assertEqual(import_wireguard(text)['addresses'],['10.64.1.2/32'])
  with self.assertRaises(ValueError):import_wireguard(text+'PostUp=touch /tmp/pwned\n')
  with self.assertRaises(ValueError):import_wireguard(text.replace('se.example.net:51820','$(reboot):53'))
 def test_totp_vector(self):
  self.assertTrue(totp(base64.b32encode(b'12345678901234567890').decode(),'287082',59))
 def test_matrix_counts_associated_stations(self):
  from unittest.mock import patch
  import network
  stations='Station 02:00:00:00:00:01 (on qspot-ap)\n\tassociated:\tyes\nStation 02:00:00:00:00:02 (on qspot-ap)\n\tassociated:\tno\n'
  with patch('network.run',return_value=stations):
   self.assertEqual(network.associated(),['02:00:00:00:00:01'])
if __name__=='__main__':unittest.main()
