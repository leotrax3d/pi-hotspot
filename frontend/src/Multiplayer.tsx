import {useCallback,useEffect,useRef,useState} from 'react'
import {ArrowLeft,Check,Copy,Eye,Gamepad2,LogOut,Play,Users,UserPlus,Zap,RotateCcw} from 'lucide-react'
import {Button} from '@/components/ui/button'
import {Badge} from '@/components/ui/badge'
import {Card,CardContent,CardHeader,CardTitle} from '@/components/ui/card'
import {Spinner} from '@/components/ui/spinner'
import {Progress} from '@/components/ui/progress'
import {Input} from '@/components/ui/input'
import {toast} from 'sonner'
import './multiplayer.css'

const games=[
 {id:'pong',name:'Pong',description:'Steuere deinen Schläger per Finger oder Maus. Wer zuerst 7 Punkte hat, gewinnt.'},
 {id:'ttt',name:'Drei gewinnt',description:'Setze abwechselnd X und O. Drei in einer Reihe gewinnen.'},
 {id:'connect4',name:'Vier gewinnt',description:'Wähle eine Spalte. Vier eigene Steine in einer Linie gewinnen.'},
 {id:'reaction',name:'Reaktionsduell',description:'Warte auf das Signal und tippe zuerst. Bis zu acht Spieler können mitmachen.'},
]
type Room={id:string,capacity:number,joined:boolean,status:string,players:{name:string,you:boolean,ready:boolean,seat:string}[]}
async function request(path:string,data?:object,signal?:AbortSignal){
 const response=await fetch(path,{method:data?'POST':'GET',headers:data?{'Content-Type':'application/json'}:undefined,body:data?JSON.stringify(data):undefined,cache:'no-store',signal:signal?AbortSignal.any([signal,AbortSignal.timeout(15000)]):AbortSignal.timeout(15000)})
 const result=await response.json();if(!response.ok)throw Error(result.error||'Verbindung fehlgeschlagen');return result
}

export default function Multiplayer(){
 const [selected,setSelected]=useState(()=>new URLSearchParams(location.search).get('room')||'')
 const [state,setState]=useState<any>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[name,setName]=useState(''),[task,setTask]=useState('')
 const [refreshKey,refresh]=useState(0)
 const current=useRef<any>(null),mounted=useRef(true),inputBusy=useRef(false),lastInput=useRef(0)
 const room:Room|undefined=state?.rooms?.find((r:Room)=>r.id===selected)
 const info=games.find(g=>g.id===selected)
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false}},[])
 useEffect(()=>{
  let stopped=false,timer:ReturnType<typeof setTimeout>;const controller=new AbortController()
  const poll=async()=>{
   if(document.hidden){timer=setTimeout(poll,2000);return}
   try{const next=await request('/api/community/state?view='+ (info?selected:'lobby'),undefined,controller.signal)
    if(!stopped){if(next.reaction)next.reaction.starts=Date.now()/1000+next.reaction.starts-next.server_time;current.current=next;setState(next);setError('');setName(n=>n||next.you)}
   }catch(e){if(!stopped)setError((e as Error).message)}
   if(!stopped){const room=current.current?.rooms?.find((r:Room)=>r.id===selected);const active=room?.status==='playing';timer=setTimeout(poll,active&&selected==='pong'?(room.joined?100:250):active&&selected==='reaction'?(room.joined?120:500):info?750:2000)}
  }
  const visible=()=>{if(!document.hidden){clearTimeout(timer);controller.abort();refresh(k=>k+1)}}
  poll();document.addEventListener('visibilitychange',visible)
  return()=>{stopped=true;clearTimeout(timer);controller.abort();document.removeEventListener('visibilitychange',visible)}
 },[selected,refreshKey])
 const send=useCallback(async(data:any)=>{
  if(inputBusy.current&&data.action==='pong_move')return
  const move=data.action==='pong_move';if(move)inputBusy.current=true;else{setBusy(true);setTask(data.action)}
  try{await request('/api/community/game',data);if(!move&&mounted.current)refresh(k=>k+1)}catch(e){toast.error((e as Error).message)}finally{if(move)inputBusy.current=false;else if(mounted.current)setBusy(false)}
 },[])
 const open=(id:string)=>{setSelected(id);const url=new URL(location.href);if(id)url.searchParams.set('room',id);else url.searchParams.delete('room');history.replaceState(null,'',url)}
 const enter=async(id:string,r:Room)=>{if(r.joined||r.status!=='waiting'||r.players.length>=r.capacity){open(id);return}setBusy(true);setTask(id+'_join');try{await request('/api/community/game',{action:id+'_join'});open(id)}catch(e){toast.error((e as Error).message)}finally{setBusy(false)}}
 const saveName=async(e:React.FormEvent)=>{e.preventDefault();setBusy(true);setTask('profile');try{await request('/api/community/profile',{name});refresh(k=>k+1);toast.success('Name gespeichert')}catch(e){toast.error((e as Error).message)}finally{setBusy(false)}}
 const copy=async()=>{try{await navigator.clipboard.writeText(location.href);toast.success('Einladungslink kopiert')}catch{toast.info('Teile diese Adresse: '+location.href)}}
 const move=(y:number)=>{const now=performance.now();if(now-lastInput.current<65)return;lastInput.current=now;send({action:'pong_move',y})}
 const status=(r:Room)=>r.status==='playing'?'Läuft':r.status==='finished'?'Beendet':r.players.length===r.capacity?'Voll':'Offen'
 const me=room?.players.find(p=>p.you)
 const canStart=!!room&&room.players.length>=2&&room.players.every(p=>p.ready)
 const g=info?state?.[selected]:null
 return <div className="multiplayer"><div className="lobby-heading"><div><h2>{info?info.name:'Multiplayer-Lobby'}</h2></div><Badge variant="outline"><Users/>{state?.people?.length||0} online</Badge></div>
 <form className="lobby-profile" onSubmit={saveName}><label htmlFor="player-name">Dein Spielername</label><Input id="player-name" value={name} maxLength={24} onChange={e=>setName(e.target.value)} autoComplete="nickname"/><Button variant="outline" disabled={busy||!name.trim()||name===state?.you}>{busy&&task==='profile'?<Spinner aria-label="Name wird gespeichert"/>:<Check/>}<span className="sr-only">Speichern</span></Button></form>
 {error&&state&&<p role="alert" className="lobby-error">{error} – Verbindung wird erneut versucht.</p>}
 {!state?error?<Card><CardContent className="lobby-loading"><p role="alert">{error}</p><div className="room-actions"><Button onClick={()=>refresh(k=>k+1)}>Erneut versuchen</Button>{error.includes('Zuerst')&&<Button asChild variant="outline"><a href="/">Verbinden</a></Button>}</div></CardContent></Card>:<div className="lobby-loading" role="status" aria-label="Lobby wird geladen"><Spinner/><div className="loading-track"/></div>:!info?<div className="lobby-rooms">{games.map(game=>{const r:Room=state.rooms.find((r:Room)=>r.id===game.id);return <Card key={game.id} className="lobby-room"><CardHeader><div className="room-title"><Gamepad2/><CardTitle>{game.name}</CardTitle><Badge variant={r.status==='playing'?'secondary':'outline'}>{status(r)}</Badge></div><GamePreview kind={game.id}/></CardHeader><CardContent><div className="room-seats"><Users/><strong>{r.players.length}/{r.capacity}</strong><span>{r.players.map(p=>p.name+(p.you?' (du)':'')).join(', ')}</span></div><div className="room-actions"><Button disabled={busy} onClick={()=>enter(game.id,r)}>{busy&&task===game.id+'_join'?<Spinner aria-label="Beitritt läuft"/>:null}{r.joined?'Zurück zum Spiel':r.status!=='waiting'||r.players.length===r.capacity?<><Eye/>Zuschauen</>:<><UserPlus/>Beitreten</>}</Button>{r.joined&&<Badge variant="secondary">Du bist dabei</Badge>}</div></CardContent></Card>})}</div>:<>
 <div className="room-toolbar"><Button variant="ghost" onClick={()=>open('')}><ArrowLeft/>Alle Räume</Button><Button variant="outline" onClick={copy}><Copy/>Einladen</Button></div>
 {room&&<Card className="match-room"><CardHeader><div className="room-title"><CardTitle>{info.name}</CardTitle><Badge variant="outline">{status(room)}</Badge></div></CardHeader><CardContent>
 <ol className="match-steps" aria-label="Spielvorbereitung"><li data-done={!!me}><Users/><span className="sr-only">Beitreten</span></li><li data-done={canStart}><Check/><span className="sr-only">Bereit</span></li><li data-done={room.status!=='waiting'}><Play/><span className="sr-only">Spielen</span></li></ol><div className="match-players">{room.players.map((p,i)=><div key={i} className="player-seat"><span className="player-avatar">{p.name.slice(0,2).toUpperCase()}</span><div><strong>{p.name}{p.you?' (du)':''}</strong><small>{room.status==='playing'?'Spielt':p.ready?'Bereit':'Wartet'}</small></div>{p.ready&&<Check className="ready-check"/>}</div>)}{room.players.length<room.capacity&&<button className="player-seat vacant" onClick={copy} aria-label="Mitspieler einladen"><UserPlus/><span>Einladen</span></button>}</div>
 <div className="match-controls">{!me?<Button disabled={busy||room.status==='playing'||room.players.length===room.capacity} onClick={()=>send({action:selected+'_join'})}>{busy?<Spinner/>:<UserPlus/>}Beitreten</Button>:<>{room.status==='waiting'&&<><Button variant={me.ready?'secondary':'default'} disabled={busy} onClick={()=>send({action:selected+'_ready'})} aria-pressed={me.ready}>{busy&&task.endsWith('_ready')?<Spinner/>:<Check/>}{me.ready?'Bereit':'Bereit machen'}</Button>{me.ready&&<Button disabled={busy||!canStart} onClick={()=>send({action:selected+'_start'})}>{busy&&task.endsWith('_start')||!canStart?<Spinner aria-label="Wartet auf Mitspieler"/>:<Play/>}{canStart?'Starten':'Warten'}</Button>}</>}{room.status==='finished'&&<Button disabled={busy} onClick={()=>send({action:selected+'_reset'})}>{busy&&task.endsWith('_reset')?<Spinner/>:<RotateCcw/>}Revanche</Button>}<Button variant="outline" disabled={busy} onClick={()=>send({action:selected+'_leave'})} aria-label="Spiel verlassen" title="Verlassen">{busy&&task.endsWith('_leave')?<Spinner/>:<LogOut/>}</Button></>}{!me&&<Badge variant="outline"><Eye/>Zuschauer</Badge>}</div>
 {room.status==='waiting'&&<div className="ready-progress"><Progress aria-label="Bereite Spieler" value={100*room.players.filter(p=>p.ready).length/Math.max(2,room.players.length)}/><Badge variant="outline">{room.players.filter(p=>p.ready).length}/{Math.max(2,room.players.length)} <Check/></Badge></div>}
 {g&&room.status!=='waiting'&&<div className="match-field">{selected==='pong'?<Pong state={g} move={move} playing={room.status==='playing'} joined={!!me}/>:selected==='reaction'?<Reaction state={g} joined={!!me} send={send}/>:<Board kind={selected} state={g} joined={!!me} send={send}/>}</div>}
 {room.status==='finished'&&<p className="match-result" role="status">{g?.winner==='draw'?'Unentschieden':g?.winner?g?.times&&Object.values(g.times).includes(-1)?g.winner:`${g.winner} gewinnt!`:'Runde beendet'}</p>}
 </CardContent></Card>}</>}
 </div>
}

function Board({kind,state:s,joined,send}:{kind:string,state:any,joined:boolean,send:(d:any)=>void}){
 const connect=kind==='connect4';const own=joined&&s.you===s.turn&&!s.winner
 return <><p className="turn-status" role="status">{s.winner?'Runde beendet':own?'Du bist am Zug':`${Object.entries(s.players).find(([,mark])=>mark===s.turn)?.[0]||s.turn} ist am Zug`}{joined&&` · Du spielst ${s.you}`}</p>
 {connect&&<div className="connect-drop">{Array.from({length:7},(_,i)=><Button key={i} size="sm" variant="outline" aria-label={`Stein in Spalte ${i+1}`} disabled={!own||!!s.board[i]} onClick={()=>send({action:'connect4_move',col:i})}>↓</Button>)}</div>}
 <div className={connect?'connect-board':'ttt-board'}>{s.board.map((v:string,i:number)=>connect?<div className="connect-cell" key={i}>{v&&<span data-mark={v}/>}</div>:<Button key={i} variant="outline" aria-label={`Feld ${i+1}${v?': '+v:''}`} disabled={!!v||!own} onClick={()=>send({action:'ttt_move',cell:i})}>{v||''}</Button>)}</div></>
}
function Reaction({state:s,joined,send}:{state:any,joined:boolean,send:(d:any)=>void}){
 const [go,setGo]=useState(false)
 useEffect(()=>{setGo(s.phase==='go');if(s.phase!=='wait')return;const timer=setTimeout(()=>setGo(true),Math.max(0,s.starts*1000-Date.now()));return()=>clearTimeout(timer)},[s.starts,s.phase])
 return <button disabled={!joined||s.phase==='done'} className="reaction-field" data-phase={go&&s.phase!=='done'?'go':s.phase} onClick={()=>send({action:'reaction_hit'})}>{s.phase==='done'?s.winner:go?'JETZT!':'…'}</button>
}
function Pong({state:s,move,playing,joined}:{state:any,move:(y:number)=>void,playing:boolean,joined:boolean}){
 const canvas=useRef<HTMLCanvasElement>(null),latest=useRef({s,at:performance.now()})
 useEffect(()=>{latest.current={s,at:performance.now()}},[s])
 useEffect(()=>{let frame=0;const draw=()=>{const c=canvas.current;if(!c)return;const x=c.getContext('2d')!;const {s,at}=latest.current;const dt=playing?Math.min(.12,(performance.now()-at)/1000):0
  x.fillStyle='#060606';x.fillRect(0,0,900,520);x.strokeStyle='#444';x.setLineDash([8,14]);x.beginPath();x.moveTo(450,0);x.lineTo(450,520);x.stroke();x.setLineDash([]);x.fillStyle='#eee'
  x.fillRect(32,((s.paddles.left??.5)-.15)*520,12,156);x.fillRect(856,((s.paddles.right??.5)-.15)*520,12,156);x.beginPath();x.arc(Math.max(0,Math.min(1,s.ball[0]+s.velocity[0]*dt))*900,Math.max(.05,Math.min(.95,s.ball[1]+s.velocity[1]*dt))*520,10,0,Math.PI*2);x.fill();x.font='500 28px sans-serif';x.textAlign='center';x.fillText(s.score.join(' : '),450,42);if(!document.hidden)frame=requestAnimationFrame(draw)
 };draw();const visible=()=>{if(!document.hidden){cancelAnimationFrame(frame);draw()}};document.addEventListener('visibilitychange',visible);return()=>{cancelAnimationFrame(frame);document.removeEventListener('visibilitychange',visible)}},[playing])
 const pointer=(e:React.PointerEvent<HTMLCanvasElement>)=>{if(!joined||!playing)return;const box=e.currentTarget.getBoundingClientRect();move(Math.max(.15,Math.min(.85,(e.clientY-box.top)/box.height)))}
 return <><p className="turn-status">{joined?s.you==='left'?'← Du':'Du →':'Zuschauermodus'} · Bis 7 Punkte</p><canvas ref={canvas} width={900} height={520} className="play-canvas" aria-label="Pong-Spielfeld" onPointerDown={e=>{e.currentTarget.setPointerCapture(e.pointerId);pointer(e)}} onPointerMove={e=>{if(e.buttons)pointer(e)}}/></>
}

function GamePreview({kind}:{kind:string}){return <div className={'game-preview preview-'+kind} aria-hidden="true">{kind==='pong'?<><i/><b/><i/></>:kind==='ttt'?Array.from({length:9},(_,i)=><span key={i}>{['X','','O','','X','','O','',''][i]}</span>):kind==='connect4'?Array.from({length:21},(_,i)=><span key={i} data-filled={[10,16,17,18,19].includes(i)}/>):<Zap/>}</div>}
