import {setBranding} from './branding'
export type Profile = {down_kbit:number;up_kbit:number;seconds:number;bytes:number;devices:number;concurrent:number}
export type Config = {
 brand_name?:string;portal_domain?:string;features?:Record<string,boolean>;vpn_bypass?:string[];dns_logging?:boolean;dns_retention_hours?:number;ap_password?:string;hostname:string;ssid:string;channel:number;country:string;guest:string;usb:string;portal_mode:'both'|'accept'|'code';
 title:string;description:string;accept_text:string;terms:string;profiles:Record<string,Profile>;default_profile:string;
 global_down_kbit:number;global_up_kbit:number;usb_down_kbit:number;usb_up_kbit:number;
 vpn:'off'|'guest'|'usb'|'both';vpn_server:string;onboarding_complete?:boolean;
 matrix:{enabled:boolean;brightness:number;reduce_motion:boolean;night_start:string;night_end:string;timezone?:string};
}
export type GuestSession={vpn?:boolean;id:number;mac:string;ip:string;profile:string;active:number;used:number;reason:string;remaining_seconds:number|null;limit_bytes:number;code_id:number|null}
export type Status={features?:Record<string,boolean>;vpn_enabled?:boolean;uplink_interface?:string;network_mode?:string;connected_guests?:number;associated_macs?:string[];vpn_global?:boolean;host_connected:boolean;internet:boolean;host:string;vpn:string;vpn_handshake:number;rates:Record<string,{rx_bytes:number;tx_bytes:number;rx_Bps:number;tx_Bps:number}>;sessions:GuestSession[];codes:{id:number;label:string;profile:string;expires:number;duration:number;first:number;revoked:number}[];blocked:{mac:string}[];cpu_load:number;ram_total:number;ram_available:number;disk_free:number;temperature_c:number;error:string;uptime:number;pending:boolean;vpn_servers:string[];simulation?:boolean}
export type Auth={brand_name?:string;portal_domain?:string;csrf:string;setup:boolean;authenticated:boolean;simulation?:boolean}
let csrf=''
export async function api<T>(url:string,data?:unknown):Promise<T>{
 const r=await fetch(url,{method:data===undefined?'GET':'POST',headers:data===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:data===undefined?undefined:JSON.stringify(data)})
 const j=await r.json();if(!r.ok)throw new Error(j.error||'Verbindung fehlgeschlagen');return j
}
export async function authState(){const a=await api<Auth>('/api/auth');csrf=a.csrf;setBranding(a);return a}
export async function action<T=unknown>(method:string,data:Record<string,unknown>={}){return (await api<{result:T}>('/api/admin/action',{method,...data})).result}
export function download(name:string,text:string){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type:'text/plain'}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),3000)}
export function formatBytes(n:number){if(n>=1024**3)return (n/1024**3).toFixed(1)+' GB';if(n>=1024**2)return (n/1024**2).toFixed(1)+' MB';if(n>=1024)return (n/1024).toFixed(0)+' KB';return n+' B'}
export function formatRate(n:number){return (n*8/1000000).toFixed(1)}
export function formatTime(n:number|null){if(n===null)return 'Unbegrenzt';if(n<60)return n+' s';if(n<3600)return Math.ceil(n/60)+' min';return (n/3600).toFixed(1)+' h'}
