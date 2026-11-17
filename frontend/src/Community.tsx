import {useBranding,setBranding} from './branding'
import {StrictMode,Suspense,lazy,useEffect,useState} from 'react'
import {createRoot} from 'react-dom/client'
import {Gamepad2,MessageCircle,Wifi,ArrowLeft} from 'lucide-react'
import {Button} from '@/components/ui/button'
import {Badge} from '@/components/ui/badge'
import {Card,CardAction,CardContent,CardDescription,CardHeader,CardTitle} from '@/components/ui/card'
import {Input} from '@/components/ui/input'
import {Tabs,TabsList,TabsTrigger} from '@/components/ui/tabs'
import {Separator} from '@/components/ui/separator'
import {Alert,AlertDescription} from '@/components/ui/alert'
import {Toaster} from '@/components/ui/sonner'
import {toast} from 'sonner'
import Multiplayer from './Multiplayer'
import {singleplayerCatalog} from './singleplayer-catalog'
const Singleplayer=lazy(()=>import('./Singleplayer'))
import {Spinner} from '@/components/ui/spinner'
import './index.css';import './experience.css';import './community.css';import './chat.css'

type State=any
async function api(path:string,data?:object,signal?:AbortSignal){const r=await fetch(path,{method:data?'POST':'GET',headers:data?{'Content-Type':'application/json'}:{},body:data?JSON.stringify(data):undefined,cache:'no-store',signal:signal?AbortSignal.any([signal,AbortSignal.timeout(15000)]):AbortSignal.timeout(15000)});const j=await r.json();if(!r.ok)throw Error(j.error||'Aktion fehlgeschlagen');return j}
function Chat({state,refresh}:{state:State,refresh:()=>void}){const brand=useBranding();const [text,setText]=useState(''),[name,setName]=useState(state.you),[sending,setSending]=useState(false),[savingName,setSavingName]=useState(false);useEffect(()=>setName(state.you),[state.you]);const saveName=async()=>{setSavingName(true);try{await api('/api/community/profile',{name});await refresh();toast.success('Name gespeichert')}catch(e){toast.error((e as Error).message)}finally{setSavingName(false)}};const send=async(e:React.FormEvent)=>{e.preventDefault();if(!text.trim()||sending)return;setSending(true);try{await api('/api/community/chat',{text});setText('');await refresh()}catch(e){toast.error((e as Error).message)}finally{setSending(false)}};return <div className="chat-page"><div className="mobile-people" aria-label="Online-Geräte">{state.people.map((p:any)=><Badge key={p.name} variant="outline"><span/>{p.name}</Badge>)}</div><div className="chat-layout"><Card className="people-card"><CardHeader><CardTitle>Online</CardTitle><CardDescription>{state.people.length} Geräte im Raum</CardDescription></CardHeader><CardContent className="people-list">{state.people.map((p:any)=><div key={p.name}><span/>{p.name}</div>)}</CardContent></Card><Card className="chat-card"><CardHeader><CardTitle><div className="chat-title"><MessageCircle/>{brand.brand_name}</div></CardTitle><CardAction><div className="name-editor"><Input aria-label="Dein Chatname" value={name} onChange={e=>setName(e.target.value)} maxLength={24}/><Button variant="outline" disabled={savingName} onClick={saveName}>{savingName&&<Spinner/>}Speichern</Button></div></CardAction></CardHeader><CardContent className="messages">{state.messages.length===0?<div className="chat-empty"><MessageCircle/><strong>Noch keine Nachrichten</strong></div>:state.messages.map((m:any)=>{const own=m.name===state.you;return <div key={m.id} className={own?'own':''}><div className="message-meta"><strong>{own?'Du':m.name}</strong><time>{new Date(m.time*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</time></div><p>{m.text}</p></div>})}</CardContent><form className="chat-compose" onSubmit={send}><div className="compose-field"><Input aria-label="Nachricht" value={text} onChange={e=>setText(e.target.value)} maxLength={300} placeholder="Nachricht schreiben …" autoComplete="off"/><div><span>Keine Links</span><span>{text.length}/300</span></div></div><Button disabled={!text.trim()||sending}>{sending?<Spinner aria-label="Nachricht wird gesendet"/>:null}{sending?'Wird gesendet …':'Senden'}</Button></form></Card></div></div>}
function App(){
 const brand=useBranding();
 const [features,setFeatures]=useState<Record<string,boolean>>({});
 useEffect(()=>{api('/api/portal').then(c=>{setBranding(c);const f=c.features||{};setFeatures(f);if(f.chat===false)setSection('games');if(f.multiplayer===false)setMode('single')}).catch(()=>{})},[]);
 const [state,setState]=useState<State|null>(null)
 const [section,setSection]=useState(new URLSearchParams(location.search).get('view')==='chat'?'chat':'games')
 const [mode,setMode]=useState('multi'),[game,setGame]=useState('snake'),[error,setError]=useState('')
 const refresh=async()=>{try{setState(await api('/api/community/state?view=chat'));setError('')}catch(e){setError((e as Error).message)}}
 useEffect(()=>{
  let stopped=false,timer:ReturnType<typeof setTimeout>
  const controller=new AbortController()
  const poll=async()=>{
   if(!document.hidden){try{const result=await api('/api/community/state?view=chat',undefined,controller.signal);if(!stopped){setState(result);setError('')}}catch(e){if(!stopped)setError((e as Error).message)}}
   if(!stopped)timer=setTimeout(poll,1800)
  }
  if(section==='chat')poll()
  else{setError('');setState((s:State|null)=>s||{people:[]})}
  return()=>{stopped=true;clearTimeout(timer);controller.abort()}
 },[section])
 const loading=<div className="lobby-loading" role="status" aria-label="Lädt"><Spinner/></div>
 return <>
  <header className="community-header"><a href="/"><ArrowLeft/>{brand.brand_name}</a><Tabs value={section} onValueChange={setSection}><TabsList>{features.chat!==false&&<TabsTrigger value="chat"><MessageCircle/>Chat</TabsTrigger>}{(features.singleplayer!==false||features.multiplayer!==false)&&<TabsTrigger value="games"><Gamepad2/>Games</TabsTrigger>}</TabsList></Tabs>{section==='chat'&&<Badge variant="outline"><Wifi/>{state?.people.length||0} online</Badge>}</header>
  <main className="community-main">
   {error&&<Alert><AlertDescription>{error}</AlertDescription></Alert>}
   {!state?loading:section==='chat'?<Chat state={{...state,messages:state.messages||[]}} refresh={refresh}/>:<div className={'games-shell '+(mode==='multi'?'multiplayer-shell':'')}>
    <aside className="game-library"><div><h1>Games</h1></div>
     <Tabs value={mode} onValueChange={setMode}><TabsList className="w-full">{features.singleplayer!==false&&<TabsTrigger value="single">Einzelspieler</TabsTrigger>}{features.multiplayer!==false&&<TabsTrigger value="multi">Mehrspieler</TabsTrigger>}</TabsList></Tabs>
     <Separator/>
     {mode==='single'&&<div className="single-game-list" aria-label="Einzelspieler-Spiele">{singleplayerCatalog.map(g=><Button key={g.id} variant={game===g.id?'secondary':'ghost'} className="game-link" aria-pressed={game===g.id} title={g.desc} onClick={()=>setGame(g.id)}><g.icon/><span><strong>{g.name}</strong></span></Button>)}</div>}
    </aside>
    <section className="active-game">{features.singleplayer===false&&features.multiplayer===false?<p>Games sind deaktiviert.</p>:mode==='multi'?<Multiplayer/>:<Suspense fallback={loading}><Singleplayer key={game} game={game}/></Suspense>}</section>
   </div>}
  </main><Toaster theme="dark" position="bottom-right"/>
 </>
}
createRoot(document.getElementById('community-root')!).render(<StrictMode><App/></StrictMode>)
