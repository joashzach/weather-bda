import { build } from 'esbuild';
import { gzipSync } from 'node:zlib';
import { readFileSync, copyFileSync } from 'node:fs';
await build({entryPoints:['src/motion.jsx'],bundle:true,minify:true,format:'esm',outfile:'dist/motion.js',jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'},legalComments:'eof'});
console.log(`Motion bundle: ${(gzipSync(readFileSync('dist/motion.js')).length/1024).toFixed(1)} kB gzip`);
copyFileSync('src/reactbits/LICENSE.md','dist/REACT-BITS-LICENSE.txt');
