import { useQuery } from '@tanstack/react-query';
import Page from '../components/animations/Page';
import { Card, Skeleton } from '../components/ui/Card';
import { EmptyState } from '../components/ui/EmptyState';
import { insights, money } from '../api/client';
import { Link } from 'react-router-dom';

const tone:any = { alta:'text-rose-200 bg-rose-400/10 border-rose-300/20', média:'text-amber-200 bg-amber-400/10 border-amber-300/20', baixa:'text-sky-200 bg-sky-400/10 border-sky-300/20' };

export default function Insights(){
  const {data,isLoading}=useQuery({queryKey:['insights'],queryFn:insights});
  const items=data?.items||[];
  return <Page>
    <div className="flex flex-wrap justify-between gap-3 mb-4"><div><h2 className="text-3xl font-black">Insights comerciais</h2><p className="text-slate-400">Recomendações automáticas por margem, concorrência, estoque, publicação e jobs.</p></div><span className="status-badge text-sky-200">{items.length} sinais detectados</span></div>
    {isLoading?<div className="grid md:grid-cols-3 gap-4">{[1,2,3].map(i=><Skeleton key={i} className="h-52"/>)}</div>:items.length?<div className="grid xl:grid-cols-3 md:grid-cols-2 gap-4">{items.map((it:any,idx:number)=><Card key={idx} className="hover:scale-[1.01] transition"><div className="flex items-start justify-between gap-3"><span className={`status-badge ${tone[it.priority]||''}`}>{it.priority}</span><span className="text-xs text-slate-400 uppercase">{it.type}</span></div><h3 className="text-xl font-black mt-4">{it.title}</h3><p className="text-slate-300 mt-2 min-h-16">{it.description}</p><div className="rounded-2xl bg-white/10 border border-white/10 p-3 mt-4"><p className="text-xs text-slate-400">Impacto estimado</p><b>{money(it.impact_estimated ?? it.impact_estimate)}</b></div><p className="text-sm text-slate-300 mt-4">{it.action ?? it.recommended_action}</p>{it.product_id&&<Link className="btn btn-primary inline-flex mt-4" to={`/app/produtos/${it.product_id}`}>{it.cta||'Abrir produto'}</Link>}</Card>)}</div>:<Card><EmptyState title="Nenhum risco crítico" description="A demo está saudável. Novos sinais aparecem quando produtos, concorrência, pricing e jobs gerarem alertas."/></Card>}
  </Page>
}
