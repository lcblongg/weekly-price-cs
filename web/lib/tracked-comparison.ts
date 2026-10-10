// Rút gọn trước khi phân trang; giữ nguyên SKU, thời điểm và lịch sử ngày.
export function trackedComparison<T extends {
 rows:Record<string,unknown>[];issues:Record<string,unknown>[];models:string[];
 model_meta:Record<string,{brand:string;category:string}>;
 preferences:{products:{model:string}[]};
}>(data:T):T{
 const models=data.preferences.products.map(p=>p.model);
 const wanted=new Set(models);
 return {...data,models,
  rows:data.rows.filter(r=>r.apple_selection==='selected'&&wanted.has(String(r.apple_model))),
  // Giữ lỗi cấp kênh; lỗi có model chỉ lấy phạm vi đang theo dõi.
  issues:data.issues.filter(i=>{
   const model=i.model_name||i.apple_model;
   return !model||wanted.has(String(model));
  }),
  model_meta:Object.fromEntries(Object.entries(data.model_meta).filter(([model])=>wanted.has(model))),
 };
}
