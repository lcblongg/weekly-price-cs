import {categoryOf,modelOf,brandOf} from './product-meta';
import type {ProductMetadata} from './types';
export type ModelEntry={id:string;name:string;category:string;brand?:string};
export type Watchlist={version:1;models:ModelEntry[];hidden:string[];fresh:string[]};
export const emptyWatchlist=():Watchlist=>({version:1,models:[],hidden:[],fresh:[]});
// Định danh khớp chính xác, không dùng includes: iPhone 16 khác iPhone 16 Pro.
const normalize=(s:string)=>s.normalize('NFC').trim().replace(/\s+/g,' ').toLocaleLowerCase('vi');
export function modelEntry<T extends ProductMetadata>(row:T):ModelEntry {
 const category=categoryOf(row),name=modelOf(row);
 return {id:JSON.stringify([normalize(category),normalize(name)]),name,category,brand:brandOf(row)};
}
export function parseWatchlist(value:unknown):Watchlist {
 const v=value as Watchlist;
 if(!v||v.version!==1||!Array.isArray(v.models)||!Array.isArray(v.hidden)||!Array.isArray(v.fresh))throw new Error('Danh sách theo dõi không hợp lệ.');
 if(v.models.some(m=>!m||typeof m.id!=='string'||typeof m.name!=='string'||typeof m.category!=='string'||(m.brand!==undefined&&typeof m.brand!=='string')||m.id!==JSON.stringify([normalize(m.category),normalize(m.name)]))||[...v.hidden,...v.fresh].some(x=>typeof x!=='string'))throw new Error('Danh sách theo dõi không hợp lệ.');
 return {version:1,models:[...new Map(v.models.map(m=>[m.id,m])).values()],hidden:[...new Set(v.hidden)],fresh:[...new Set(v.fresh)]};
}
export function discoverModels(state:Watchlist,entries:ModelEntry[]):Watchlist {
 const known=new Map(state.models.map(m=>[m.id,m]));const added=entries.filter(m=>!known.has(m.id));
 const enriched=new Map(entries.filter(e=>e.brand&&e.brand!=='Chưa xác định').map(e=>[e.id,e]));
 const updated=state.models.map(m=>{const entry=enriched.get(m.id);return !m.brand&&entry?.brand?{...m,brand:entry.brand}:m;});
 if(!added.length&&updated.every((m,i)=>m===state.models[i]))return state;
 const unique=[...new Map(added.map(m=>[m.id,m])).values()];
 return {...state,models:[...updated,...unique],fresh:state.models.length?[...new Set([...state.fresh,...unique.map(m=>m.id)])]:state.fresh};
}
export function isWatched<T extends ProductMetadata>(state:Watchlist,row:T){return !state.hidden.includes(modelEntry(row).id);}
