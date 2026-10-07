import type {Metadata} from 'next';
import './globals.css';
export const metadata:Metadata={title:'Weekly Price CS',description:'Tra cứu giá và khuyến mãi theo tuần tài chính, dành cho đội ngũ CS.',robots:{index:false,follow:false}};
export default function RootLayout({children}:{children:React.ReactNode}) {return <html lang="vi"><body>{children}</body></html>;}
