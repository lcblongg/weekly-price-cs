import standard from '../../config/apple_models.json';
import preferences from '../../config/apple_colors.json';
// Cùng quy tắc với apple_rules.literal_pattern (Python). Có test đối chiếu chéo trong tests/test_apple_rules.py.
const SUFFIXES='(?!\\s+(?:pro|max|plus|mini|ultra|air|neo)\\b)';
const escape=(word:string)=>word.replace(/[.*+?^${}()|[\]\\\-#&~\s]/g,'\\$&');
export function literalPattern(model:string):string{return '\\b'+model.split(/\s+/).filter(Boolean).map(escape).join('\\s+')+SUFFIXES+'(?![\\w])';}
const rules:{name:string;pattern:string}[]=[...standard.models,...preferences.products.filter(p=>!standard.models.some(r=>r.name===p.model)).map(p=>({name:p.model,pattern:literalPattern(p.model)}))];
const compiled=rules.map(r=>({name:r.name,pattern:new RegExp(r.pattern,'i')}));
export const APPLE_MODELS=[...preferences.products.map(r=>r.model),...rules.map(r=>r.name).filter(n=>!preferences.products.some(r=>r.model===n))];
export function canonicalAppleModel(name:string):string|null {
 const matches=compiled.filter(r=>r.pattern.test(name));
 return matches.length===1?matches[0].name:null;
}
export function compareModels(a:string,b:string):number {
 const modelA=canonicalAppleModel(a)??a,modelB=canonicalAppleModel(b)??b;
 const ai=APPLE_MODELS.indexOf(modelA),bi=APPLE_MODELS.indexOf(modelB);
 return (ai<0?APPLE_MODELS.length:ai)-(bi<0?APPLE_MODELS.length:bi)||a.localeCompare(b,'vi',{numeric:true});
}
