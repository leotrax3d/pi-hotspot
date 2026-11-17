import {cp,mkdir,readdir,readFile,writeFile,rm} from 'node:fs/promises'
import {gzipSync} from 'node:zlib'
import path from 'node:path'
const target=path.resolve(import.meta.dirname,'../qspot/static/app')
const workspace=path.resolve(import.meta.dirname,'..')
if(target!==path.join(workspace,'qspot','static','app'))throw Error('Unexpected static destination')
await rm(target,{recursive:true,force:true})
await mkdir(target,{recursive:true})
await cp(path.join(import.meta.dirname,'dist'),target,{recursive:true})
for(const name of await readdir(path.join(target,'assets'))){if(!/\.(css|js)$/.test(name))continue;const p=path.join(target,'assets',name);await writeFile(p+'.gz',gzipSync(await readFile(p),{level:9}))}
console.log('Static frontend packaged for Flask')
