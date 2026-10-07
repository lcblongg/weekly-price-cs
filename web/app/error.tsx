'use client';
export default function ErrorPage({reset}:{reset:()=>void}) {return <main className="error-page"><h1>Không tải được dashboard</h1><p>Kiểm tra kết nối và thử lại. Dữ liệu chưa tải được sẽ không được hiển thị thành giá 0.</p><button onClick={reset}>Thử lại</button></main>;}
