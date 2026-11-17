import base64, collections, hashlib, hmac, io, json, logging, os, secrets, sqlite3, threading, time
from functools import wraps
from pathlib import Path
from flask import Flask, request, session, jsonify, send_file, make_response
from werkzeug.serving import make_server
from common import atomic, password_hash, password_ok, rpc, totp
from community import Community
from branding import identity, portal_url, otp_uri
from html import escape
SIMULATE=os.environ.get('QSPOT_SIMULATE')=='1'
if SIMULATE:
 from simulation import rpc

WEB=Path(os.environ.get('QSPOT_WEB_STATE','/var/lib/qspot-web'))
WEB.mkdir(parents=True,exist_ok=True); os.umask(0o077)
if not (WEB/'secret').exists(): (WEB/'secret').write_bytes(secrets.token_bytes(32))
if not (WEB/'auth.json').exists() and not (WEB/'setup-token').exists(): (WEB/'setup-token').write_text(secrets.token_urlsafe(24))
if not (WEB/'matrix-token').exists(): (WEB/'matrix-token').write_text(secrets.token_urlsafe(32))
app=Flask(__name__,static_folder='static',static_url_path='/static')
app.secret_key=(WEB/'secret').read_bytes()
app.config.update(SESSION_COOKIE_NAME='qspot_admin',SESSION_COOKIE_SECURE=True,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Strict',MAX_CONTENT_LENGTH=1024*1024)
if SIMULATE:app.config['SESSION_COOKIE_SECURE']=False
attempts=collections.defaultdict(collections.deque); authlock=threading.RLock(); community=Community()

def auth(): return json.loads((WEB/'auth.json').read_text()) if (WEB/'auth.json').exists() else None
def portal_token():
 value=str(int(time.time()))+'.'+secrets.token_hex(16)
 signature=hmac.new(app.secret_key,(request.remote_addr+'|'+value).encode(),hashlib.sha256).hexdigest()
 return value+'.'+signature
def portal_token_ok(token):
 try:
  stamp,nonce,signature=token.split('.')
  if not 0<=time.time()-int(stamp)<=600 or len(nonce)!=32:return False
  expected=hmac.new(app.secret_key,(request.remote_addr+'|'+stamp+'.'+nonce).encode(),hashlib.sha256).hexdigest()
  return hmac.compare_digest(signature,expected)
 except (ValueError,TypeError):return False
def sessions(): return json.loads((WEB/'sessions.json').read_text()) if (WEB/'sessions.json').exists() else {}
def save_sessions(s): atomic(WEB/'sessions.json',s)
def valid_admin():
 token=session.get('login',''); s=sessions().get(hashlib.sha256(token.encode()).hexdigest())
 return bool(s and s['expires']>time.time())
def admin(fn):
 @wraps(fn)
 def f(*a,**k):
  if not valid_admin(): return jsonify(error='Anmeldung erforderlich'),401
  return fn(*a,**k)
 return f
@app.before_request
def guard():
 if request.path.startswith('/static/app/assets/') and request.accept_encodings['gzip']>0:
  from werkzeug.utils import safe_join
  name=request.path.removeprefix('/static/app/assets/')
  joined=safe_join(str(Path(__file__).parent/'static'/'app'/'assets'),name)
  if joined and name.endswith(('.js','.css')) and Path(joined+'.gz').is_file():
   r=send_file(joined+'.gz',mimetype='text/css' if name.endswith('.css') else 'application/javascript')
   r.headers['Content-Encoding']='gzip';r.headers['Vary']='Accept-Encoding';return r
 if request.path.startswith('/api/') and request.method!='GET' and not request.path.startswith('/api/community/'):
  if not request.is_secure and not SIMULATE: return jsonify(error='Diese Aktion benötigt HTTPS'),400
  if not hmac.compare_digest(request.headers.get('X-CSRF-Token',''),session.get('csrf','!')): return jsonify(error='Ungültige Sitzung; Seite neu laden'),403
 if request.content_length and request.content_length>1024*1024: return jsonify(error='Datei zu groß'),413
@app.after_request
def headers(r):
 r.headers['X-Content-Type-Options']='nosniff'; r.headers['Referrer-Policy']='no-referrer'; r.headers['Cache-Control']='no-store'
 r.headers['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
 if request.path.startswith('/static/app/assets/'):r.headers['Cache-Control']='public, max-age=31536000, immutable'
 return r
@app.errorhandler(Exception)
def error(e):
 from werkzeug.exceptions import HTTPException
 if request.path=='/portal/activate':
  from markupsafe import escape
  message=str(e) if isinstance(e,ValueError) else 'Der Zugang konnte gerade nicht freigeschaltet werden. Bitte erneut versuchen.'
  return '<!doctype html><html lang="de"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Zugang</title><link rel="stylesheet" href="/static/style.css"><body class="portal"><h1>Zugang noch nicht aktiv</h1><p>'+str(escape(message))+'</p><a href="/">Zurück zum Portal</a></body></html>',400
 return jsonify(error=str(e) if isinstance(e,(ValueError,HTTPException)) else 'Aktion fehlgeschlagen; Systemdiagnose prüfen'),e.code if isinstance(e,HTTPException) else 400

def public_identity():
 try:return identity(rpc('config'))
 except (OSError,ValueError):return identity({})

@app.get('/api/branding')
def branding():return jsonify(public_identity())

@app.get('/api/auth')
def auth_status():
 session.setdefault('csrf',secrets.token_urlsafe(32))
 return jsonify(csrf=session['csrf'],setup=auth() is None,authenticated=valid_admin(),simulation=SIMULATE,**public_identity())
@app.post('/api/setup')
def setup():
 with authlock:
  if auth(): raise ValueError('Ersteinrichtung bereits abgeschlossen')
  d=request.json
  if not hmac.compare_digest(str(d.get('token','')),(WEB/'setup-token').read_text().strip()): raise ValueError('Falscher lokaler Einrichtungsschlüssel')
  atomic(WEB/'auth.json',{'password':password_hash(d['password']),'totp':''})
  (WEB/'setup-token').unlink(); login_session()
 return jsonify(ok=True)
def login_session():
 session.clear(); session['csrf']=secrets.token_urlsafe(32); session['login']=secrets.token_urlsafe(32)
 s=sessions(); s[hashlib.sha256(session['login'].encode()).hexdigest()]={'expires':time.time()+8*3600,'created':time.time(),'ip':request.remote_addr}; save_sessions(s)
@app.post('/api/login')
def login():
 with authlock:
  key=request.remote_addr; now=time.monotonic(); q=attempts[key]
  while q and q[0]<now-300: q.popleft()
  if len(q)>=5: return jsonify(error='Zu viele Versuche; fünf Minuten warten'),429
  if len(attempts)>10000: attempts.clear(); return jsonify(error='Anmeldung vorübergehend gesperrt'),429
  q.append(now); a=auth(); d=request.json
  if not a or not password_ok(str(d.get('password','')),a['password']) or (a['totp'] and (time.time()<1735689600 or not totp(a['totp'],d.get('otp','')))): return jsonify(error='Anmeldedaten ungültig'),401
  q.clear(); login_session()
 return jsonify(ok=True)
@app.post('/api/logout')
def logout():
 with authlock:
  s=sessions(); s.pop(hashlib.sha256(session.get('login','').encode()).hexdigest(),None); save_sessions(s); session.clear()
 return jsonify(ok=True)
@app.get('/api/admin/status')
@admin
def status(): return jsonify(rpc('status'))
@app.get('/api/admin/config')
@admin
def config(): return jsonify(rpc('config'))
@app.post('/api/admin/action')
@admin
def action():
 d=dict(request.json); method=d.pop('method')
 if method not in {'scan','wifi_list','wifi_connect','wifi_priority','codes','revoke_code','delete_code','end','block','unblock','unblock_all','clear_devices','vpn_import','vpn_toggle','device_vpn','apply','confirm','rollback','restart','reboot','logs','matrix_test','matrix_config','web_activity','clear_web_activity'}: raise ValueError('Aktion nicht freigegeben')
 return jsonify(result=rpc(method,**d))
@app.get('/api/admin/sessions')
@admin
def admin_sessions(): return jsonify(sessions())
@app.get('/api/admin/matrix-health')
@admin
def matrix_health():
 p=WEB/'matrix-health.json'
 data=json.loads(p.read_text()) if p.exists() else {'last_ack':0}
 return jsonify(**data,connected=time.time()-data['last_ack']<10)
@app.post('/api/admin/security')
@admin
def security():
 d=request.json
 with authlock:
  a=auth()
  if not password_ok(d.get('password',''),a['password']): raise ValueError('Aktuelles Passwort erforderlich')
  if d.get('new_password'):
   a['password']=password_hash(d['new_password']); save_sessions({})
  if d.get('generate_totp'):
   secret=base64.b32encode(secrets.token_bytes(20)).decode(); session['pending_totp']=secret
   return jsonify(secret=secret,uri=otp_uri(rpc('config'),secret))
  if d.get('enable_totp'):
   secret=session.get('pending_totp','')
   if not secret or not totp(secret,d.get('otp','')): raise ValueError('2FA-Code ungültig')
   a['totp']=secret; session.pop('pending_totp',None)
  if d.get('disable_totp'):
   if a['totp'] and not totp(a['totp'],d.get('otp','')): raise ValueError('2FA-Code erforderlich')
   a['totp']=''
  if d.get('revoke_sessions'): save_sessions({})
  atomic(WEB/'auth.json',a)
 return jsonify(ok=True)
def derive(password,salt):
 if len(password)<12: raise ValueError('Exportpasswort: mindestens 12 Zeichen')
 return hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1,dklen=32)
@app.post('/api/admin/backup')
@admin
def backup():
 from cryptography.hazmat.primitives.ciphers.aead import AESGCM
 salt=secrets.token_bytes(16); nonce=secrets.token_bytes(12); key=derive(request.json['password'],salt)
 data=rpc('backup'); data['auth']=auth()
 encrypted=AESGCM(key).encrypt(nonce,json.dumps(data).encode(),b'QSpot backup v1')
 return jsonify(backup=base64.b64encode(b'QSPOT1'+salt+nonce+encrypted).decode())

@app.get('/api/portal')
def portal_status(): return jsonify(rpc('portal',ip=request.remote_addr))
def feature(name):
 if not rpc('config').get('features',{}).get(name,True):
  from werkzeug.exceptions import NotFound
  raise NotFound('Diese Funktion ist deaktiviert')

def community_allowed():
 data=rpc('portal',ip=request.remote_addr)
 if not (data.get('session') or {}).get('active'): raise ValueError('Zuerst verbinden')
 return request.remote_addr
@app.get('/api/community/state')
def community_state():
 view=request.args.get('view','all')
 feature('chat' if view=='chat' else 'multiplayer')
 with community.lock:return jsonify(community.state(community_allowed(),request.args.get('view','all')))
@app.post('/api/community/profile')
def community_profile():
 client=community_allowed()
 with community.lock:community.touch(client,(request.json or {}).get('name'));return jsonify(ok=True)
@app.post('/api/community/chat')
def community_chat():
 feature('chat')
 client=community_allowed()
 with community.lock:community.touch(client);community.post(client,(request.json or {}).get('text',''));return jsonify(ok=True)
@app.post('/api/community/game')
def community_game():
 feature('multiplayer')
 client=community_allowed()
 with community.lock:community.touch(client);community.game(client,request.json or {});return jsonify(ok=True)
@app.get('/api/matrix')
def matrix_status():
 if not hmac.compare_digest(request.headers.get('X-QSpot-Matrix',''),(WEB/'matrix-token').read_text()): return jsonify(error='Zugriff verweigert'),403
 return jsonify(json.loads(Path('/run/qspot/status.json').read_text()))
@app.post('/matrix/heartbeat')
def matrix_heartbeat():
 if not hmac.compare_digest(request.headers.get('X-QSpot-Matrix',''),(WEB/'matrix-token').read_text()):return jsonify(error='Zugriff verweigert'),403
 atomic(WEB/'matrix-health.json',{'last_ack':time.time()})
 return jsonify(ok=True)
@app.post('/portal/activate')
def portal_activate():
 # Browser form POST only: links and previews never redeem a code.
 if not portal_token_ok(request.form.get('portal_token','')): raise ValueError('Das Formular ist abgelaufen. Bitte zurück zum Portal gehen und die Seite neu laden.')
 if request.form.get('accepted')!='yes': raise ValueError('Nutzungsbedingungen bitte akzeptieren')
 if request.form.get('code','').strip() and not request.is_secure: raise ValueError('Zugangscodes benötigen HTTPS')
 result=rpc('activate',ip=request.remote_addr,code=request.form.get('code','').strip() or None)
 from flask import redirect
 return redirect('/?connected=1',code=303)
@app.get('/captive-api')
def captive_api():
 data=rpc('portal',ip=request.remote_addr); s=data.get('session')
 r=jsonify({'captive':not(s and s['active']),'user-portal-url':data.get('portal_url',portal_url(public_identity())),'seconds-remaining':s.get('remaining_seconds') if s else None}); r.content_type='application/captive+json'; return r
@app.get('/admin')
@app.get('/admin/')
def index():
 if not request.is_secure and not SIMULATE:
  from flask import redirect
  return redirect('https://'+request.host.split(':')[0]+'/admin',code=302)
 modern=Path(__file__).parent/'static'/'app'/'index.html'
 return send_file(modern if modern.exists() else Path(__file__).parent/'static'/'admin.html')
@app.get('/favicon.ico')
def favicon():return send_file(Path(__file__).parent/'static'/'icons'/'router.svg',mimetype='image/svg+xml')
@app.get('/')
def portal():
 from urllib.parse import urlsplit
 host=request.host.split(':')[0]
 c=public_identity()
 if host not in (c['portal_domain'],'127.0.0.1','localhost'):
  try:
   import ipaddress
   ipaddress.ip_address(host)
  except ValueError:
   from flask import redirect
   return redirect(portal_url(c,request.is_secure),code=302)
 return (Path(__file__).parent/'static'/'portal.html').read_text().replace('__PORTAL_TOKEN__',portal_token()).replace('__BRAND_NAME__',escape(c['brand_name'])).replace('__PORTAL_DOMAIN__',escape(c['portal_domain']))
@app.get('/community')
@app.get('/community/')
def community_page(): return send_file(Path(__file__).parent/'static'/'app'/'community.html')
@app.get('/<path:probe>')
def probes(probe):
 from flask import redirect
 data=rpc('portal',ip=request.remote_addr)
 if data.get('session',{} ) and data['session']['active']:
  if probe in ('generate_204','gen_204'): return '',204
  if probe in ('connecttest.txt','ncsi.txt'): return 'Microsoft Connect Test' if probe=='connecttest.txt' else 'Microsoft NCSI',200
  if probe=='hotspot-detect.html': return '<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>'
 return redirect(data.get('portal_url',portal_url(public_identity())),code=302)

if __name__=='__main__':
 logging.getLogger('werkzeug').setLevel(logging.ERROR)
 if SIMULATE:
  make_server('127.0.0.1',8080,app,threaded=True).serve_forever()
  raise SystemExit
 http=make_server('0.0.0.0',8080,app,threaded=True)
 import ssl
 context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
 context.load_cert_chain('/etc/qspot/tls/cert.pem','/etc/qspot/tls/key.pem')
 def reload_tls():
  stamp=None
  while True:
   try:
    current=Path('/etc/qspot/tls/cert.pem').stat().st_mtime_ns
    if current!=stamp:
     context.load_cert_chain('/etc/qspot/tls/cert.pem','/etc/qspot/tls/key.pem');stamp=current
   except (OSError,ssl.SSLError):pass
   time.sleep(2)
 threading.Thread(target=reload_tls,daemon=True).start()
 https=make_server('0.0.0.0',8443,app,threaded=True,ssl_context=context)
 threading.Thread(target=http.serve_forever,daemon=True).start(); https.serve_forever()
