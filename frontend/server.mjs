import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
const root=path.resolve('dist');
http.createServer((req,res)=>{const name=decodeURIComponent(new URL(req.url,'http://localhost').pathname);const file=path.resolve(root,'.'+(name==='/'?'/index.html':name));if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return;}fs.readFile(file,(error,data)=>{if(error){res.writeHead(404).end('Not found');return;}res.setHeader('Content-Type',({'html':'text/html','css':'text/css','js':'text/javascript'})[path.extname(file).slice(1)]||'application/octet-stream');res.end(data);});}).listen(5173,'127.0.0.1',()=>console.log('Monsoon preview: http://127.0.0.1:5173'));
