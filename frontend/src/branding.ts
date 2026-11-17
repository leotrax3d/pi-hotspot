import {useSyncExternalStore} from 'react'

export type Branding={brand_name:string;portal_domain:string}
let value:Branding={brand_name:'SchülerWLAN',portal_domain:'pi-hotspot.local'}
const listeners=new Set<()=>void>()
export function setBranding(next:Partial<Branding>){
 const updated={brand_name:next.brand_name||value.brand_name,portal_domain:next.portal_domain||value.portal_domain}
 if(updated.brand_name===value.brand_name&&updated.portal_domain===value.portal_domain)return
 value=updated;document.title=value.brand_name;listeners.forEach(fn=>fn())
}
export function useBranding(){return useSyncExternalStore(fn=>{listeners.add(fn);return()=>listeners.delete(fn)},()=>value)}
