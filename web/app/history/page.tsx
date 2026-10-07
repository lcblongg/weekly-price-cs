import LiveComparison from '@/components/live-comparison';
import Comparison from '@/components/comparison';
import data from '@/data/comparison.json';
export const dynamic='force-dynamic';
export default function Page(){if(process.env.NEXT_PUBLIC_DATA_MODE==='live')return <LiveComparison initialPeriod="week"/>;if(process.env.NODE_ENV==='production'&&process.env.NEXT_PUBLIC_DATA_MODE!=='demo')return <main style={{padding:32}}><h1>Weekly Price CS</h1><p>Chưa cấu hình kết nối dữ liệu. Cần cấu hình Supabase và chế độ live trước khi vận hành.</p></main>;return <Comparison data={data} initialPeriod="week"/>;}
