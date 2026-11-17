import {useEffect,useRef,useState} from 'react'
import {ShieldCheck,Pause,Check,X,RefreshCw} from 'lucide-react'
import {toast} from 'sonner'
import {action,type Status} from './api'
import {Button} from '@/components/ui/button'
import {Card,CardContent,CardHeader,CardTitle} from '@/components/ui/card'
import {Input} from '@/components/ui/input'
import {Switch} from '@/components/ui/switch'
import {Badge} from '@/components/ui/badge'
import {Spinner} from '@/components/ui/spinner'
type Event={time:number;domain:string;ip:string;status:string}
type View={installed:boolean;available:boolean;blocking?:string;timer?:number;blocked_today?:number;ratio?:number;logging?:boolean;devices:Record<string,boolean>;events:Event[];error?:string}
export function DnsProtection({status}:{status:Status}){
 const [data,setData]=useState<View>();const [busy,setBusy]=useState(false)
 const [error,setError]=useState('');const [domain,setDomain]=useState('');const [search,setSearch]=useState('')
 const pending=useRef<Promise<void>|null>(null);const changing=useRef(false);const mounted=useRef(true)
 async function refresh(force=false){
  if(changing.current&&!force)return
  if(pending.current)return pending.current
  pending.current=(async()=>{
   try{const result=await action<View>('dns_status');if(mounted.current){setData(result);setError('')}}
   catch(e){if(mounted.current)setError((e as Error).message)}finally{pending.current=null}
  })()
  return pending.current
 }
 useEffect(()=>{mounted.current=true;let timer:ReturnType<typeof setTimeout>
  const poll=async()=>{await refresh();if(mounted.current)timer=setTimeout(poll,5000)};void poll()
  return()=>{mounted.current=false;clearTimeout(timer)}
 },[])
 async function run(operation:string,extra:Record<string,unknown>={}){
  if(changing.current)return;changing.current=true;setBusy(true)
  try{await pending.current;await action('dns_action',{operation,...extra});await refresh(true);toast.success('Gespeichert')}
  catch(e){toast.error((e as Error).message)}finally{changing.current=false;setBusy(false)}
 }
 const unavailable=busy||!data?.available
 const devices=status.sessions.filter((x,i,a)=>x.active&&a.findIndex(y=>y.mac===x.mac)===i)
 const events=(data?.events||[]).filter(e=>(e.domain+' '+e.ip+' '+e.status).toLowerCase().includes(search.toLowerCase()))
 return <div className="page-stack">
  <Card><CardHeader className="flex flex-row items-center justify-between"><CardTitle className="flex items-center gap-2"><ShieldCheck size={18}/>DNS-Schutz</CardTitle><Badge variant="outline">{data?.available?'Online':data?'Offline':'Verbinden'}</Badge></CardHeader>
   <CardContent className="space-y-5">
    {(error||data?.error)&&<p role="alert" className="text-sm text-destructive">{error||data?.error}</p>}
    {!data&&!error?<Spinner aria-label="Laden"/>:<>
     <div className="flex items-center justify-between gap-3"><label htmlFor="dns-blocking" className="text-sm">Filter</label><div className="flex items-center gap-3">{busy&&<Spinner/>}<Switch id="dns-blocking" checked={data?.blocking==='enabled'} disabled={unavailable} onCheckedChange={enabled=>void run('blocking',{enabled})}/><Button variant="outline" disabled={unavailable} onClick={()=>void run('pause')}><Pause size={16}/>{data?.timer?`${Math.ceil(data.timer)} s`:'5 min'}</Button></div></div>
     <div className="grid grid-cols-2 gap-4"><div><div className="text-xs text-muted-foreground">Heute blockiert</div><div className="text-3xl tabular-nums">{data?.blocked_today??'–'}</div></div><div><div className="text-xs text-muted-foreground">Blockierungsquote</div><div className="text-3xl tabular-nums">{data?.ratio===undefined?'–':`${data.ratio} %`}</div></div></div>
     <form className="flex flex-wrap gap-2" onSubmit={e=>{e.preventDefault();void run('domain',{domain,mode:'deny'})}}><Input aria-label="Domain" placeholder="example.org" value={domain} onChange={e=>setDomain(e.target.value)} className="min-w-0 flex-1 basis-40"/><Button type="button" variant="outline" disabled={unavailable||!domain.trim()} onClick={()=>void run('domain',{domain,mode:'allow'})}><Check size={16}/>Erlauben</Button><Button disabled={unavailable||!domain.trim()}><X size={16}/>Sperren</Button></form>
    </>}
   </CardContent></Card>
  <Card><CardHeader><CardTitle>Geräte</CardTitle></CardHeader><CardContent className="space-y-3">{devices.length===0?<div className="text-sm text-muted-foreground">Keine Geräte</div>:devices.map(d=><div key={d.mac} className="flex items-center justify-between gap-3"><div className="min-w-0"><div className="truncate text-sm">{d.hostname||d.ip}</div><div className="text-xs text-muted-foreground font-mono truncate">{d.ip} · {d.mac}</div></div><Switch aria-label={`Filter ${d.hostname||d.ip}`} checked={data?.devices?.[d.mac]!==false} disabled={unavailable} onCheckedChange={enabled=>void run('device',{mac:d.mac,enabled})}/></div>)}</CardContent></Card>
  <Card><CardHeader className="flex flex-row items-center justify-between"><CardTitle>Domains</CardTitle><Button size="icon" variant="ghost" aria-label="Aktualisieren" disabled={busy} onClick={()=>void refresh()}><RefreshCw size={16}/></Button></CardHeader><CardContent className="space-y-3"><Input aria-label="Domain-Log filtern" placeholder="Filtern" value={search} onChange={e=>setSearch(e.target.value)}/><div className="rounded-md border bg-muted/20 p-2 max-h-96 overflow-auto font-mono text-xs" aria-label="Domain-Log">{!data?.logging?<div className="p-2 text-muted-foreground">Logging aus</div>:!events.length?<div className="p-2 text-muted-foreground">Keine Anfragen</div>:events.map((e,i)=><div key={`${e.time}-${i}`} className="flex gap-3 py-1 min-w-0"><span className="text-muted-foreground shrink-0">{new Date(e.time*1000).toLocaleTimeString('de-DE')}</span><span className="text-muted-foreground hidden sm:inline shrink-0">{e.ip}</span><span title={e.status} className={`break-all ${/GRAVITY|DENY|REGEX|BLOCK/.test(e.status)?'text-red-500':'text-emerald-500'}`}>{e.domain}</span></div>)}</div></CardContent></Card>
 </div>
}
