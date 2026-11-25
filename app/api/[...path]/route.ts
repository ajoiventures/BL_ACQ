import {NextRequest,NextResponse} from 'next/server';
async function proxy(req:NextRequest,{params}:{params:Promise<{path:string[]}>}) {
 const origin=req.headers.get('origin');
 if(origin){
  try {
   if(new URL(origin).host!==req.headers.get('host'))return NextResponse.json({detail:'Cross-origin request denied'},{status:403});
  } catch {
   return NextResponse.json({detail:'Invalid request origin'},{status:403});
  }
 }
 const {path}=await params;
 if(path.some(segment=>segment==='.'||segment==='..'||/[\\/]/.test(segment))){
  return NextResponse.json({detail:'Invalid API path'},{status:400});
 }
 const supplied=req.headers.get('authorization');
 const localMode=process.env.BR_PROXY_AUTH_MODE==='local-founder';
 const unauthenticatedProbe=req.method==='GET'&&path.length===1&&['health','ready'].includes(path[0]);
 const founderToken=localMode?process.env.BR_FOUNDER_TOKEN:undefined;
 const authorization=supplied??(founderToken&&!unauthenticatedProbe?'Bearer '+founderToken:undefined);
 if((supplied!==null||!unauthenticatedProbe)&&!/^Bearer [^\s]+$/.test(authorization??'')){
  return NextResponse.json({detail:'Caller credential required'},{status:401});
 }
 const isAttachment=path[0]==='intelligence-flow'&&path[2]==='revisions'&&path[4]==='attachments';
 if(req.method==='DELETE'&&(!isAttachment||path.length!==6)){
  return NextResponse.json({detail:'Method not allowed'},{status:405});
 }
 const url='http://127.0.0.1:8000/api/'+path.map(encodeURIComponent).join('/')+req.nextUrl.search;
 try {
  const headers=new Headers();
  if(authorization)headers.set('Authorization',authorization);
  const contentType=req.headers.get('content-type');
  if(contentType)headers.set('Content-Type',contentType);
  const options:RequestInit&{duplex?:'half'}={
   method:req.method,headers,cache:'no-store',signal:req.signal,redirect:'error',
  };
  if(req.body){
   options.body=req.body;
   options.duplex='half';
  }
  const upstream=await fetch(url,options);
  const responseHeaders=new Headers({'Cache-Control':'no-store'});
  for(const name of ['Content-Type','Content-Disposition','X-Content-Type-Options']){
   const value=upstream.headers.get(name);
   if(value)responseHeaders.set(name,value);
  }
  return new NextResponse(upstream.body,{status:upstream.status,headers:responseHeaders});
 } catch {
  return NextResponse.json({detail:'Backend unavailable. Start with npm run dev.'},{status:503});
 }
}
export const GET=proxy,POST=proxy,PUT=proxy,DELETE=proxy;
