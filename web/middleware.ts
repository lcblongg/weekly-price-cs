import {NextResponse,type NextRequest} from 'next/server';
// Trang nghiệm thu chỉ dùng local. Không để bản HTML tĩnh bỏ qua Auth khi deploy.
export function middleware(request:NextRequest){
 if(process.env.NODE_ENV!=='development'&&request.nextUrl.pathname.endsWith('-review.html'))return new NextResponse(null,{status:404});
 return NextResponse.next();
}
export const config={matcher:['/mw-review.html','/cps-review.html','/fpt-review.html','/viettel-review.html','/phongvu-review.html']};
