// Chạy script Python của dự án (chỉ dùng trong route local/development).
import {resolve,join} from 'node:path';
import {execFile} from 'node:child_process';
const root=resolve(process.cwd(),'..');
export function runPython(script:string,args:string[],input:string,timeout=600000):Promise<{code:number;body:Record<string,unknown>}>{
 return new Promise(done=>{const child=execFile(join(root,'.venv/bin/python'),[join(root,script),...args],{cwd:root,timeout,maxBuffer:4_000_000},(error,stdout)=>{
  let body:Record<string,unknown>;try{body=JSON.parse(String(stdout).trim().split('\n').at(-1)||'{}');}catch{body={ok:false,error:'Không đọc được kết quả xử lý.'};}
  done({code:error?(typeof error.code==='number'?error.code:1):0,body});});child.stdin?.end(input);});
}
