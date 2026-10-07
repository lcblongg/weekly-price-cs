import {CHAINS,type ScrapeIssue} from './types';
const domains:Record<string,string>={'TGDD':'thegioididong.com','FPT Shop':'fptshop.com.vn','CellphoneS':'cellphones.com.vn','Viettel Store':'viettelstore.vn','Phong Vũ':'phongvu.vn'};
export function validateIssues(input:unknown):ScrapeIssue[] {
  if(!Array.isArray(input)) throw new Error('Dữ liệu không hợp lệ');
  return input.map(raw=>{
    const issue=raw as ScrapeIssue;
    if(!CHAINS.includes(issue.chain_name as typeof CHAINS[number])||!['catalog','price'].includes(issue.stage)||!/^\d{4}-\d{2}-\d{2}$/.test(issue.business_date)||!Number.isFinite(Date.parse(issue.captured_at))||typeof issue.reason!=='string'||!issue.reason.trim()) throw new Error('Dữ liệu không hợp lệ');
    const url=new URL(issue.source_url);const domain=domains[issue.chain_name];
    if(url.protocol!=='https:'||url.username||url.password||![domain,'www.'+domain].includes(url.hostname)) throw new Error('Nguồn không hợp lệ');
    return issue;
  });
}
// Theo ngày: đúng ngày đó. Theo tuần: lượt cào mới nhất của từng đại lý trong tuần (tình trạng hiện tại).
export function issuesFor(issues:ScrapeIssue[],period:'day'|'week',day:string,start:string):ScrapeIssue[] {
  const scoped=issues.filter(issue=>period==='day'?issue.business_date===day:issue.week_start===start);
  const latest=new Map<string,string>();
  for(const issue of scoped){const old=latest.get(issue.chain_name);if(!old||Date.parse(issue.captured_at)>Date.parse(old))latest.set(issue.chain_name,issue.captured_at);}
  const seen=new Set<string>();
  return scoped.filter(issue=>issue.captured_at===latest.get(issue.chain_name)).filter(issue=>{const key=JSON.stringify([issue.chain_name,issue.source_url,issue.sku]);if(seen.has(key))return false;seen.add(key);return true;})
    .sort((a,b)=>a.chain_name.localeCompare(b.chain_name,'vi')||a.product_name.localeCompare(b.product_name,'vi'));
}
