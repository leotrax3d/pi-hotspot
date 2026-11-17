import {useSyncExternalStore} from 'react'
import type {Config} from './api'

export type Branding={brand_name:string;portal_domain:string}
let value:Branding={brand_name:document.querySelector<HTMLMetaElement>('meta[name="portal-brand"]')?.content||'SchülerWLAN',portal_domain:document.querySelector<HTMLMetaElement>('meta[name="portal-domain"]')?.content||'pi-hotspot.local'}
const listeners=new Set<()=>void>()
export function setBranding(next:Partial<Branding>){
 const updated={brand_name:next.brand_name||value.brand_name,portal_domain:next.portal_domain||value.portal_domain}
 if(updated.brand_name===value.brand_name&&updated.portal_domain===value.portal_domain)return
 value=updated;document.title=value.brand_name;listeners.forEach(fn=>fn())
}
export function useBranding(){return useSyncExternalStore(fn=>{listeners.add(fn);return()=>listeners.delete(fn)},()=>value)}

function slug(name:string){
 let result=name.toLowerCase().replaceAll('ä','ae').replaceAll('ö','oe').replaceAll('ü','ue').replaceAll('ß','ss').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||'wlan'
 if(!/^[a-z]/.test(result))result='wlan-'+result
 return result.slice(0,63).replace(/-$/,'')
}
export function renameDraft(config:Config,name:string):Config{
 const old=config.brand_name||'SchülerWLAN',next={...config,brand_name:name}
 if(!name.trim()||name===old)return next
 for(const key of ['ssid','title','description','accept_text','terms'] as const){
  const escaped=old.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')
  next[key]=config[key].replace(new RegExp(escaped,'gi'),()=>name)
 }
 const oldSlug=slug(old),newSlug=slug(name)
 if(['pi-hotspot',oldSlug].includes(config.hostname))next.hostname=newSlug
 next.portal_domain=(config.portal_domain||config.hostname+'.local').split('.').map(label=>['pi-hotspot',oldSlug,config.hostname].includes(label)?newSlug:label).join('.')
 return next
}
