import {useBranding} from './branding'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { motion } from 'motion/react'
import { ArrowUpRight, Eye, EyeOff, KeyRound, LockKeyhole, Router } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from '@/components/ui/input-group'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Spinner } from '@/components/ui/spinner'
import { api, authState } from './api'
import type { Auth } from './api'

export function Logo({compact=false}:{compact?:boolean}){const brand=useBranding();return <span className="brand"><Router aria-hidden="true"/>{!compact&&<span>{brand.brand_name}</span>}</span>}
export function DotMatrix({small=false}:{small?:boolean}){
 const pattern=['0001111100000','0011000110000','0110000011000','0110000011000','0110001011000','0011000110000','0001111111000','0000000001100']
 return <svg className={small?'dot-matrix small':'dot-matrix'} viewBox="0 0 156 96" aria-hidden="true">{pattern.flatMap((row,y)=>Array.from(row).map((bit,x)=><motion.circle key={y*13+x} cx={6+x*12} cy={6+y*12} r="2.7" initial={{opacity:.15}} animate={{opacity:bit==='1'?1:.12}} transition={{delay:(x+y)*.025,duration:.4}} fill="currentColor"/>))}</svg>
}
export function Login({auth,onLogin}:{auth:Auth;onLogin:(a:Auth)=>void}){
 const [password,setPassword]=useState(''),[token,setToken]=useState(''),[otp,setOtp]=useState(''),[show,setShow]=useState(false),[withOtp,setWithOtp]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('')
 async function submit(e:FormEvent){e.preventDefault();setBusy(true);setError('');try{await api(auth.setup?'/api/setup':'/api/login',{password,token,otp});setPassword('');onLogin(await authState())}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <div className="login-scene"><section className="login-form-area"><motion.div className="login-form-wrap" initial={{opacity:0,x:8}} animate={{opacity:1,x:0}} transition={{duration:.45,delay:.1}}><div className="login-mobile-brand"><Logo/></div><div className="login-emblem"><KeyRound/></div><h2>{auth.setup?'Adminzugang einrichten':'Anmelden'}</h2><form onSubmit={submit}><FieldGroup>{auth.setup&&<Field><FieldLabel htmlFor="setup-token">Einrichtungsschlüssel</FieldLabel><Input id="setup-token" value={token} onChange={e=>setToken(e.target.value)} autoComplete="off" required/></Field>}<Field data-invalid={!!error}><FieldLabel htmlFor="password">{auth.setup?'Dein Adminpasswort':'Adminpasswort'}</FieldLabel><InputGroup><InputGroupAddon><LockKeyhole/></InputGroupAddon><InputGroupInput id="password" autoFocus type={show?'text':'password'} autoComplete={auth.setup?'new-password':'current-password'} minLength={8} placeholder="Passwort eingeben" value={password} onChange={e=>setPassword(e.target.value)} required aria-invalid={!!error}/><InputGroupAddon align="inline-end"><InputGroupButton type="button" aria-label={show?'Passwort verbergen':'Passwort anzeigen'} onClick={()=>setShow(!show)}>{show?<EyeOff/>:<Eye/>}</InputGroupButton></InputGroupAddon></InputGroup></Field>{withOtp&&<Field><FieldLabel htmlFor="otp">Zwei-Faktor-Code</FieldLabel><Input id="otp" inputMode="numeric" autoComplete="one-time-code" placeholder="000000" value={otp} onChange={e=>setOtp(e.target.value)} maxLength={6}/></Field>}{error&&<Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}<Button type="submit" size="lg" disabled={busy}>{busy?<Spinner data-icon="inline-start"/>:null}{busy?'Wird angemeldet …':auth.setup?'Zugang einrichten':'Anmelden'}{!busy&&<ArrowUpRight data-icon="inline-end"/>}</Button></FieldGroup></form><Button type="button" variant="link" onClick={()=>setWithOtp(!withOtp)}>{withOtp?'Ohne Zwei-Faktor-Code':'Mit Zwei-Faktor-Code anmelden'}</Button></motion.div><span className="login-footer"></span></section></div>
}
