import config from '@/data/fiscal-calendar.json';
const DAY=86400000;
export function addDays(date:string,count:number) {return new Date(Date.parse(date+'T00:00:00Z')+count*DAY).toISOString().slice(0,10);}
export function vietnamDate(now=new Date()) {const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Ho_Chi_Minh',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now);const get=(name:string)=>parts.find(p=>p.type===name)!.value;return `${get('year')}-${get('month')}-${get('day')}`;}
export function weekStart(day=vietnamDate()) {const weekday=new Date(day+'T00:00:00Z').getUTCDay();return addDays(day,-((weekday+6)%7));}
export function datesForWeek(start:string) {return Array.from({length:7},(_,i)=>addDays(start,i));}
export function fiscalLabel(start:string) {
  const offset=Math.floor((Date.parse(start+'T00:00:00Z')-Date.parse(config.anchor_week_start+'T00:00:00Z'))/(7*DAY));
  const yearOffset=Math.floor(offset/52);const within=offset-yearOffset*52;
  return `W${within%13+1}Q${Math.floor(within/13)+1}FY${config.anchor_fiscal_year+yearOffset}`;
}
export function shortDate(date:string) {return date.slice(8,10)+'/'+date.slice(5,7);}
export const money=(amount:number|null|undefined)=>amount==null?'—':new Intl.NumberFormat('vi-VN').format(amount)+' ₫';
