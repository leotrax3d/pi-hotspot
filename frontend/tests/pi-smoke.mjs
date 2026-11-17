// Optional browser smoke test: node tests/pi-smoke.mjs
// Uses deterministic API fixtures; it never contacts router hardware.
import {chromium} from '@playwright/test'
import {createServer} from 'node:http'
import {readFile} from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'

const root=path.resolve(import.meta.dirname,'../../qspot/static/app')
const config={hostname:'pi-hotspot',ssid:'Test Hotspot',guest:'10.77.0.1/24',usb:'10.78.0.1/24',
 channel:6,country:'DE',portal_mode:'accept',title:'Welcome',description:'',terms:'',accept_text:'OK',
 profiles:{standard:{bytes:0,seconds:0,down_kbit:0,up_kbit:0,devices:0,concurrent:0}},
 default_profile:'standard',global_down_kbit:0,global_up_kbit:0,usb_down_kbit:0,usb_up_kbit:0,
 vpn:'both',vpn_server:'test',onboarding_complete:true,matrix:{enabled:false,brightness:2,night_start:'22:00',night_end:'07:00'},
 brand_name:'Campus',portal_domain:'login.campus.lan',features:{chat:true,singleplayer:true,multiplayer:true,vpn:true}}
const status={connected_guests:1,associated_macs:['02:00:00:00:00:01'],vpn_enabled:true,vpn:'connected',
 host_connected:true,internet:true,host:'',uplink_interface:'eth0',network_mode:'lan',
 rates:{eth0:{rx_bytes:10000,tx_bytes:1000,rx_Bps:1024,tx_Bps:512}},
 sessions:[{id:1,mac:'02:00:00:00:00:01',ip:'10.77.0.20',profile:'standard',active:1,used:100,
 remaining_seconds:null,limit_bytes:0,reason:'',vpn:true}],codes:[],blocked:[],
 vpn_servers:['test'],pending:false,cpu_load:0.2,ram_total:1073741824,ram_available:500000000,
 disk_free:10000000000,temperature_c:42,uptime:60}
const actions=[]
const server=createServer(async(req,res)=>{
 try{
  const url=new URL(req.url,'http://localhost')
  if(url.pathname.startsWith('/api/')){
   let result
   if(url.pathname==='/api/auth')result={csrf:'test',setup:false,authenticated:true,brand_name:config.brand_name,portal_domain:config.portal_domain}
   else if(url.pathname==='/api/branding')result={brand_name:config.brand_name,portal_domain:config.portal_domain}
   else if(url.pathname==='/api/admin/config')result=config
   else if(url.pathname==='/api/admin/status')result=status
   else if(url.pathname==='/api/admin/action'){
    const chunks=[];for await(const chunk of req)chunks.push(chunk)
    const action=JSON.parse(Buffer.concat(chunks));actions.push(action)
    if(action.method==='apply')Object.assign(config,action.config)
    if(action.method==='device_vpn')status.sessions[0].vpn=action.enabled
    if(action.method==='vpn_toggle'){status.vpn_enabled=action.enabled;status.vpn=action.enabled?'connected':'off';config.vpn=action.enabled?'both':'off'}
    result={result:true}
   }else result={}
   res.setHeader('Content-Type','application/json');res.end(JSON.stringify(result));return
  }
  const relative=url.pathname==='/admin'?'index.html':url.pathname.replace(/^\/static\/app\//,'')
  const file=path.resolve(root,relative)
  if(!file.startsWith(root+path.sep)){res.writeHead(404);res.end();return}
  const ext=path.extname(file);res.setHeader('Content-Type',({'.html':'text/html','.js':'application/javascript','.css':'text/css','.woff2':'font/woff2'})[ext]||'application/octet-stream')
  res.end(await readFile(file))
 }catch{res.writeHead(404);res.end()}
})
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))
let browser
try{
 browser=await chromium.launch(process.env.EDGE_PATH?{executablePath:process.env.EDGE_PATH}:{})
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message))
 await page.goto(`http://127.0.0.1:${server.address().port}/admin`)
 await page.getByText('Raspberry Pi',{exact:true}).waitFor()
 assert.equal(await page.getByRole('link',{name:'LED-Matrix',exact:true}).count(),0)
 const toggle=page.getByRole('switch',{name:'VPN f\u00fcr 10.77.0.20'})
 await toggle.click();await page.waitForFunction(()=>document.querySelector('button[role=switch][aria-label="VPN f\u00fcr 10.77.0.20"]')?.getAttribute('aria-checked')==='false')
 assert(actions.some(a=>a.method==='device_vpn'&&a.enabled===false))
 await page.getByRole('switch',{name:'Mullvad f\u00fcr alle Ger\u00e4te'}).click()
 await page.getByRole('status').filter({hasText:'Aus'}).waitFor()
 assert(actions.some(a=>a.method==='vpn_toggle'&&a.enabled===false))
 assert.equal(await page.title(),'Campus')
 assert.equal(await page.getByRole('link',{name:'Portal öffnen'}).getAttribute('href'),'https://login.campus.lan/')
 if(process.env.SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCREENSHOT_DIR,'dashboard-desktop.png'),fullPage:true})
 await page.getByRole('link',{name:'Einstellungen',exact:true}).click()
 await page.getByLabel('Name',{exact:true}).fill('Campus Nord')
 await page.getByLabel('Domain',{exact:true}).fill('nord.campus.lan')
 await page.getByRole('button',{name:'Speichern',exact:true}).click()
 await page.waitForFunction(()=>document.title==='Campus Nord')
 assert(actions.some(a=>a.method==='apply'&&a.config.brand_name==='Campus Nord'&&a.config.portal_domain==='nord.campus.lan'))
 if(process.env.SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCREENSHOT_DIR,'branding-settings.png'),fullPage:true})
 await page.getByRole('link',{name:'Übersicht',exact:true}).click()
 await page.locator('.console-dashboard').waitFor();await page.waitForFunction(()=>{const e=document.querySelector('.console-dashboard');return e&&Number(getComputedStyle(e.closest('[style]')||e).opacity)>0.99});
 await page.setViewportSize({width:390,height:844});await page.waitForTimeout(400)
 if(process.env.SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCREENSHOT_DIR,'dashboard-mobile.png'),fullPage:true})
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2),false)
 assert.deepEqual(errors,[])
 console.log('Pi dashboard, device VPN, global VPN and mobile layout: OK')
}finally{await browser?.close();await new Promise(resolve=>server.close(resolve))}
