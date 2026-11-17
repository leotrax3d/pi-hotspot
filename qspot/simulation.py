"""Explicit UI development mode. No Linux commands or network changes."""
import copy, time
from common import DEFAULT, validate
C=copy.deepcopy(DEFAULT)
def rpc(method,**d):
 if method=='config':return copy.deepcopy(C)
 if method=='apply':C.clear();C.update(validate(copy.deepcopy(d['config'])));return {'simulation':True}
 if method in ('confirm','rollback'):return True
 if method=='status':return {'simulation':True,'host_connected':True,'internet':True,'vpn':'off','host':'SIMULATION – keine Hardwaremessung','rates':{},'ram_available':2*1024**3,'disk_free':4*1024**3,'temperature_c':42,'cpu_load':.3,'sessions':[],'codes':[],'blocked':[],'pending':False,'error':'','vpn_servers':[]}
 if method=='portal':return {k:C[k] for k in ('title','description','accept_text','terms','portal_mode')}
 raise ValueError('Diese Aktion ist im Simulationsmodus nicht mit Hardware verbunden')
