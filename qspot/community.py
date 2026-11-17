import collections, math, threading, time
from moderation import moderate_message, moderate_name


class Community:
 def __init__(self):
  self.lock=threading.RLock(); self.people={}; self.messages=collections.deque(maxlen=120)
  self.chat_times=collections.defaultdict(collections.deque)
  self.pong=self._new_pong(); self.ttt=self._new_ttt(); self.connect4=self._new_connect4(); self.reaction=self._new_reaction()
  self.ready={k:set() for k in ('pong','ttt','connect4','reaction')}
  self.running={k:False for k in self.ready}

 def leave(self,client,kind):
  g=getattr(self,kind)
  if client not in g['players']:return
  g['players'].pop(client,None)
  if kind=='pong':g['paddles'].pop(client,None)
  self.ready[kind].clear();self.running[kind]=False
  # Leaving ends the round so a replacement never inherits an unfinished match.
  players=dict(g['players']);g=getattr(self,'_new_'+kind)();g['players']=players
  if kind=='pong':g['paddles']={k:.5 for k in players}
  setattr(self,kind,g)

 def rooms(self,client):
  result=[]
  for kind in self.ready:
   g=getattr(self,kind);capacity=8 if kind=='reaction' else 2
   finished=bool(g['winner']) or g.get('phase')=='done'
   result.append({'id':kind,'capacity':capacity,'joined':client in g['players'],
    'players':[{'name':self.name(k),'you':k==client,'ready':k in self.ready[kind], 'seat':v} for k,v in g['players'].items()],
    'status':'finished' if finished else 'playing' if self.running[kind] else 'waiting'})
  return result

 def _new_pong(self):
  return {'players':{},'paddles':{},'ball':[.5,.5],'velocity':[.34,.22],'score':[0,0],'updated':time.monotonic(),'winner':''}

 def _new_ttt(self):
  return {'players':{},'board':['']*9,'turn':'X','winner':''}

 def _new_connect4(self):
  return {'players':{},'board':['']*42,'turn':'X','winner':''}

 def _new_reaction(self):
  return {'players':{},'phase':'lobby','starts':0.0,'winner':'','times':{}}

 def touch(self,client,name=None):
  now=time.time(); current=self.people.get(client,{'name':'Gast-'+client.replace('.','')[-4:]})
  if name is not None:
   clean=moderate_name(name)
   current['name']=clean
  current['seen']=now; self.people[client]=current
  for key in list(self.people):
   if now-self.people[key]['seen']>45:
    self.people.pop(key,None);self.chat_times.pop(key,None)
    for kind in self.ready:self.leave(key,kind)
  return current

 def name(self,client): return self.people.get(client,{}).get('name','Gast')

 def post(self,client,text):
  now=time.time(); q=self.chat_times[client]
  while q and q[0]<now-10:q.popleft()
  if len(q)>=5: raise ValueError('Bitte kurz warten')
  clean=moderate_message(text)
  q.append(now); self.messages.append({'id':f'{now:.6f}-{client}','name':self.name(client),'text':clean,'time':now})

 def _pong_step(self):
  p=self.pong; now=time.monotonic(); elapsed=min(1,max(0,now-p['updated'])); p['updated']=now
  if len(p['players'])<2 or p['winner'] or not self.running['pong']:return
  for _ in range(max(1,math.ceil(elapsed/.016))):self._pong_tick(elapsed/max(1,math.ceil(elapsed/.016)))

 def _pong_tick(self,dt):
  p=self.pong
  if p['winner']:return
  x,y=p['ball']; vx,vy=p['velocity']; x+=vx*dt; y+=vy*dt
  if y<.05:y=.05;vy=abs(vy)
  if y>.95:y=.95;vy=-abs(vy)
  sides={v:k for k,v in p['players'].items()}
  for side,edge,direction in [('left',.08,1),('right',.92,-1)]:
   player=sides.get(side); paddle=p['paddles'].get(player,.5)
   crossed=(vx<0 and x<=edge) if side=='left' else (vx>0 and x>=edge)
   if crossed and abs(y-paddle)<.17:
    x=edge;vx=abs(vx)*direction*1.03;vy+=((y-paddle)/.17)*.13
  if x<0 or x>1:
   scorer=1 if x<0 else 0;p['score'][scorer]+=1
   if p['score'][scorer]>=7:p['winner']='Links' if scorer==0 else 'Rechts'
   x,y=.5,.5;vx=(.34 if scorer==0 else -.34);vy=.2 if p['score'][0]%2==0 else -.2
  p['ball']=[x,y];p['velocity']=[vx,vy]

 def game(self,client,data):
  action=data.get('action','')
  kind=action.split('_')[0]
  if kind not in self.ready:raise ValueError('Unbekanntes Spiel')
  g=getattr(self,kind)
  if action.endswith('_leave'):
   self.leave(client,kind);return
  if action.endswith('_ready'):
   if client not in g['players']:raise ValueError('Bitte zuerst beitreten')
   if self.running[kind]:return
   if client in self.ready[kind]:self.ready[kind].remove(client)
   else:self.ready[kind].add(client)
   return
  if action.endswith('_start'):
   if client not in g['players']:raise ValueError('Bitte zuerst beitreten')
   if self.running[kind]:return
   if len(g['players'])<2 or not all(k in self.ready[kind] for k in g['players']):raise ValueError('Mindestens zwei Spieler müssen bereit sein')
   self.running[kind]=True
   if kind=='pong':g['updated']=time.monotonic()
   if kind=='reaction':g.update(phase='wait',starts=time.time()+2.0+(hash(str(time.time()))%2500)/1000,winner='',times={})
   return
  if action.endswith('_join'):
   if self.running[kind]:raise ValueError('Die Runde läuft bereits. Du kannst zuschauen.')
   if client not in g['players'] and len(g['players'])>=(8 if kind=='reaction' else 2):raise ValueError('Dieser Raum ist voll')
   for other in self.ready:
    if other!=kind:self.leave(client,other)
  if action.endswith('_reset'):
   if client not in g['players']:raise ValueError('Nur Mitspieler können eine neue Runde anlegen')
   self.ready[kind].clear();self.running[kind]=False
   players=dict(g['players']);fresh=getattr(self,'_new_'+kind)();fresh['players']=players
   if kind=='pong':fresh['paddles']={k:.5 for k in players}
   setattr(self,kind,fresh);return
  if action.endswith('_move'):
   if not self.running[kind]:return
   if kind=='pong':self._pong_step()
  if action=='pong_join':
   if client not in self.pong['players']:
    occupied=set(self.pong['players'].values())
    side='left' if 'left' not in occupied else 'right' if 'right' not in occupied else ''
    if side:self.pong['players'][client]=side;self.pong['paddles'][client]=.5
  elif action=='pong_move' and client in self.pong['players']:
   self.pong['paddles'][client]=min(.85,max(.15,float(data.get('y',.5))))
  elif action=='pong_reset':
   players=dict(self.pong['players']);self.pong=self._new_pong();self.pong['players']=players;self.pong['paddles']={k:.5 for k in players}
  elif action=='ttt_join':
   if client not in self.ttt['players']:
    used=set(self.ttt['players'].values());mark='X' if 'X' not in used else 'O' if 'O' not in used else ''
    if mark:self.ttt['players'][client]=mark
  elif action=='ttt_move':
   mark=self.ttt['players'].get(client); cell=int(data.get('cell',-1))
   if mark==self.ttt['turn'] and 0<=cell<9 and not self.ttt['board'][cell] and not self.ttt['winner']:
    self.ttt['board'][cell]=mark
    lines=((0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6))
    if any(all(self.ttt['board'][i]==mark for i in line) for line in lines):self.ttt['winner']=mark
    elif all(self.ttt['board']):self.ttt['winner']='draw'
    else:self.ttt['turn']='O' if mark=='X' else 'X'
  elif action=='ttt_reset':
   players=dict(self.ttt['players']);self.ttt=self._new_ttt();self.ttt['players']=players
  elif action=='connect4_join':
   if client not in self.connect4['players']:
    used=set(self.connect4['players'].values());mark='X' if 'X' not in used else 'O' if 'O' not in used else ''
    if mark:self.connect4['players'][client]=mark
  elif action=='connect4_move':
   g=self.connect4; mark=g['players'].get(client); col=int(data.get('col',-1))
   if mark==g['turn'] and 0<=col<7 and not g['winner']:
    cells=[r*7+col for r in range(5,-1,-1) if not g['board'][r*7+col]]
    if cells:
     g['board'][cells[0]]=mark
     lines=[]
     for r in range(6):
      for c in range(7):
       for dr,dc in ((0,1),(1,0),(1,1),(1,-1)):
        line=[(r+i*dr)*7+c+i*dc for i in range(4) if 0<=r+i*dr<6 and 0<=c+i*dc<7]
        if len(line)==4:lines.append(line)
     if any(all(g['board'][i]==mark for i in line) for line in lines):g['winner']=mark
     elif all(g['board']):g['winner']='draw'
     else:g['turn']='O' if mark=='X' else 'X'
  elif action=='connect4_reset':
   players=dict(self.connect4['players']);self.connect4=self._new_connect4();self.connect4['players']=players
  elif action=='reaction_join':
   if client not in self.reaction['players'] and len(self.reaction['players'])<8:self.reaction['players'][client]=self.name(client)
  elif action=='reaction_start' and client in self.reaction['players']:
   self.reaction.update(phase='wait',starts=time.time()+2.0+(hash(str(time.time()))%2500)/1000,winner='',times={})
  elif action=='reaction_hit' and client in self.reaction['players']:
   g=self.reaction;now=time.time()
   if g['phase']=='wait' and now<g['starts']:g['times'][client]=-1;g['winner']=self.name(client)+' war zu früh';g['phase']='done'
   elif g['phase'] in ('wait','go') and not g['winner']:
    g['times'][client]=max(0,now-g['starts']);g['winner']=self.name(client);g['phase']='done'

 def state(self,client,view='all'):
  self.touch(client)
  base={'you':self.name(client),'people':[{'name':v['name']} for v in sorted(self.people.values(),key=lambda x:x['name'].lower())],'rooms':self.rooms(client),'server_time':time.time()}
  if view=='chat':return {**base,'messages':list(self.messages)}
  if view=='lobby':return base
  if view in ('all','pong'):self._pong_step()
  pong={k:v for k,v in self.pong.items() if k!='updated'}
  pong['players']={self.name(k):v for k,v in self.pong['players'].items()};pong['you']=self.pong['players'].get(client,'spectator')
  pong['paddles']={self.pong['players'].get(k,k):v for k,v in self.pong['paddles'].items()}
  ttt={**self.ttt,'players':{self.name(k):v for k,v in self.ttt['players'].items()},'you':self.ttt['players'].get(client,'spectator')}
  c4={**self.connect4,'players':{self.name(k):v for k,v in self.connect4['players'].items()},'you':self.connect4['players'].get(client,'spectator')}
  if self.reaction['phase']=='wait' and time.time()>=self.reaction['starts']:self.reaction['phase']='go'
  reaction={**self.reaction,'players':[self.name(k) for k in self.reaction['players']],'you':client in self.reaction['players']}
  games={'pong':pong,'ttt':ttt,'connect4':c4,'reaction':reaction}
  base['rooms']=self.rooms(client)
  if view in games:return {**base,view:games[view]}
  return {**base,'messages':list(self.messages),**games}
