import { useMutation, useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import Page from '../components/animations/Page';
import { Card } from '../components/ui/Card';
import { EmptyState } from '../components/ui/EmptyState';
import { insights, money, trainML } from '../api/client';
import { useToast } from '../components/ui/Toast';

const priorityClass: Record<string,string> = { alta: 'text-red-200 border-red-300/30 bg-red-400/10', media: 'text-amber-100 border-amber-300/30 bg-amber-400/10', baixa: 'text-emerald-100 border-emerald-300/30 bg-emerald-400/10' };

export default function Intelligence() {
  const { toast } = useToast();
  const { data } = useQuery({ queryKey: ['insights'], queryFn: insights });
  const train = useMutation({ mutationFn: trainML, onSuccess: () => toast('Treino MVP concluído.', 'success'), onError: () => toast('Falha no treino ML MVP.', 'error') });
  const r: any = train.data;
  const items = data?.items || [];
  return <Page>
    <div className="flex flex-wrap justify-between items-center gap-3 mb-4"><div><h2 className="text-3xl font-black">Insights Comerciais</h2><p className="text-slate-400">Recomendações automáticas por margem, concorrência, estoque, publicação e jobs.</p></div><button className="btn btn-primary" disabled={train.isPending} onClick={() => train.mutate()}>{train.isPending ? 'Treinando...' : 'Treinar modelo MVP'}</button></div>
    <div className="grid md:grid-cols-3 gap-4 mb-4"><Card><p className="text-slate-400">Insights críticos</p><b className="text-3xl">{items.filter((i:any)=>i.priority==='alta').length}</b></Card><Card><p className="text-slate-400">Impacto estimado</p><b className="text-3xl">{money(items.reduce((a:number,i:any)=>a+Number(i.impact_estimated||0),0))}</b></Card><Card><p className="text-slate-400">Status ML</p><b className="text-3xl">{r?.status || 'MVP seguro'}</b></Card></div>
    <div className="grid lg:grid-cols-2 gap-4">{items.length ? items.map((i:any, idx:number) => <Card key={`${i.type}-${idx}`}><div className="flex justify-between gap-3 mb-3"><span className={`status-badge border ${priorityClass[i.priority] || ''}`}>{i.priority}</span><b>{money(i.impact_estimated)}</b></div><h3 className="text-xl font-black">{i.title}</h3><p className="text-slate-300 mt-2">{i.description}</p><p className="text-sky-200 mt-3">Ação: {i.action}</p>{i.product_id && <Link className="btn btn-ghost mt-4 inline-block" to={`/app/produtos/${i.product_id}`}>Ir ao produto</Link>}</Card>) : <Card><EmptyState title="Nenhum insight crítico" description="A demo está saudável ou ainda precisa de dados de produto, pricing e concorrência." /></Card>}</div>
    {r && <Card className="mt-4"><b>Artefato ML</b><p className="text-slate-400 mt-2 break-all">{r.model_path}</p></Card>}
  </Page>;
}
