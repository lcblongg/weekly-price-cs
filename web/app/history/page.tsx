import Dashboard from '@/components/dashboard';
import demo from '@/data/demo.json';
import {validateRows,validateCatalog} from '@/lib/prices';
import {validateIssues} from '@/lib/issues';
// Tính tuần FY theo thời điểm truy cập, tránh giữ tuần của ngày build Vercel.
export const dynamic='force-dynamic';
export default function Page() {
  const configured=Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL&&process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY);
  const setting=process.env.NEXT_PUBLIC_DATA_MODE;
  const mode=setting==='demo'||(!setting&&process.env.NODE_ENV==='development')?'demo':configured?'live':'setup';
  return <Dashboard mode={mode} initialRows={mode==='demo'?validateRows(demo.rows):[]} initialCatalog={mode==='demo'?validateCatalog((demo as {catalog?:unknown[]}).catalog??[]):[]} initialIssues={mode==='demo'?validateIssues((demo as {issues?:unknown[]}).issues??[]):[]} demoScope={demo.scope}/>;
}
