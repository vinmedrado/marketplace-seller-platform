import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Bell, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';
import { getAlerts, markAlertRead } from '../../api/client';

export default function AlertBell(){
  const [open,setOpen]=useState(false); const qc=useQueryClient();
  const {data}=useQuery({queryKey:['alerts'],queryFn:getAlerts,refetchInterval:30000});
  const read=useMutation({mutationFn:markAlertRead,onSuccess:()=>qc.invalidateQueries({queryKey:['alerts']})});
  const items=data?.items||[]; const unread=data?.unread||0;
  return <div className="relative"><button className="btn btn-ghost !p-3" onClick={()=>setOpen(!open)}><Bell size={18}/>{unread>0&&<span className="absolute -top-1 -right-1 h-5 min-w-5 rounded-full bg-rose-500 text-xs flex items-center justify-center">{unread}</span>}</button>
  {open&&<div className="absolute right-0 mt-3 w-[390px] glass premium-border rounded-3xl p-3 z-50"><div className="flex justify-between p-2"><b>Central de alertas</b><span className="status-badge">{unread} não lidos</span></div>{items.slice(0,6).map((a:any)=><div key={a.id} className="rounded-2xl p-3 bg-white/10 border border-white/10 mb-2"><div className="flex justify-between gap-2"><span className="status-badge uppercase">{a.priority}</span><button className="text-xs text-sky-200" onClick={()=>read.mutate(a.id)}>marcar lido</button></div><b className="block mt-2">{a.title}</b><p className="text-sm text-slate-300">{a.description}</p>{a.target_url&&<Link className="text-sky-200 text-sm inline-flex items-center gap-1 mt-2" to={a.target_url} onClick={()=>setOpen(false)}>abrir <ExternalLink size={13}/></Link>}</div>)}</div>}
  </div>
}
