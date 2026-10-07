export const CHAINS = ['TGDD','FPT Shop','CellphoneS','Viettel Store','Phong Vũ'] as const;
export type DailyPrice = {id?:number;category?:string;brand?:string;model_name?:string|null;variant_label?:string;run_id:string;captured_at:string;business_date:string;week_start:string;chain_name:string;sku:string;product_name:string;original_price:number|null;promo_price:number|null;promo_text:string;source_url:string};
export type ProductWeek = {key:string;chain:string;sku:string;name:string;days:(DailyPrice|null)[];latest:DailyPrice;change:number|null};
// Link trong catalog nhưng không đọc được giá ở lượt cào: hiển thị kèm lý do, không ẩn đi.
export type ScrapeIssue = {id?:number;run_id?:string;captured_at:string;business_date:string;week_start:string;stage:'catalog'|'price';chain_name:string;sku:string;product_name:string;category:string;brand?:string;model_name?:string|null;source_url:string;reason:string};

export type CatalogProduct=Pick<DailyPrice,'chain_name'|'sku'|'product_name'|'category'|'brand'|'model_name'|'source_url'>&{discovered_at:string;status:'ready'|'review';reason:string};
export type ProductMetadata=Pick<DailyPrice,'product_name'|'category'|'brand'|'model_name'>;
