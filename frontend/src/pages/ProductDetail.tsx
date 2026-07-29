import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import Page from '../components/animations/Page';
import { Card, Skeleton } from '../components/ui/Card';
import { EmptyState } from '../components/ui/EmptyState';
import { calculatePricing, money, pricingScenarios, productDetail, publishDryRun, publishPreview, runCompetition } from '../api/client';
import { useToast } from '../components/ui/Toast';

export default function ProductDetail() {
  const { id = '' } = useParams();
  const qc = useQueryClient();
  const { toast } = useToast();
  const { data, isLoading } = useQuery({ queryKey: ['product-detail', id], queryFn: () => productDetail(id), enabled: !!id });
  const { data: sc } = useQuery({ queryKey: ['pricing-scenarios', id], queryFn: () => pricingScenarios(id), enabled: !!id });
  const { data: preview } = useQuery({ queryKey: ['publish-preview', id], queryFn: () => publishPreview(id), enabled: !!id });
  const scrape = useMutation({ mutationFn: () => runCompetition(id), onSuccess: () => { qc.invalidateQueries({ queryKey: ['product-detail', id] }); toast('Scraping concluído.', 'success'); } });
  const price = useMutation({ mutationFn: () => calculatePricing(id), onSuccess: () => { qc.invalidateQueries({ queryKey: ['product-detail', id] }); qc.invalidateQueries({ queryKey: ['pricing-scenarios', id] }); toast('Preço calculado.', 'success'); } });
  const pub = useMutation({ mutationFn: () => publishDryRun(id), onSuccess: () => { qc.invalidateQueries({ queryKey: ['product-detail', id] }); toast('Dry-run gerado.', 'success'); } });
  if (isLoading) return <Page><Skeleton className="h-96" /></Page>;
  const p = data?.product;
  const pr = data?.pricing_current || sc?.recommended;
  const st = data?.competitor_stats || sc?.competitor || {};
  const status = Number(pr?.margin_pct || (pr?.margem_real_pct || 0) * 100) < Number(p?.margem_minima || 0.18) * 100 ? 'Risco de margem' : 'Saudável';
  return <Page>
    <div className="flex flex-wrap justify-between gap-3 mb-4"><div><h2 className="text-3xl font-black">{p?.titulo}</h2><p className="text-slate-400">Central de decisão comercial: margem, concorrência, pricing, estoque e publicação.</p></div><Link className="btn btn-ghost" to="/app/produtos">Voltar</Link></div>
    <div className="grid lg:grid-cols-4 gap-4"><Card><p className="text-slate-400">Status comercial</p><b className="text-2xl">{status}</b><p className="text-slate-400 mt-2">{p?.sku} · {p?.categoria_nome} · {p?.marca}</p></Card><Card><p className="text-slate-400">Preço sugerido</p><b className="text-3xl">{money(pr?.preco_sugerido || pr?.price)}</b><p className="text-emerald-300">Lucro {money(pr?.lucro_estimado || pr?.estimated_profit)}</p></Card><Card><p className="text-slate-400">Posição competitiva</p><b className="text-2xl">{sc?.recommended?.competitive_position || 'Aguardando dados'}</b><p className="text-slate-400 mt-2">Mediana {money(st.median_price || st.preco_medio)}</p></Card><Card><p className="text-slate-400">Estoque</p><b className="text-3xl">{p?.estoque}</b><p className="text-slate-400">mínimo {p?.estoque_minimo || 5}</p></Card></div>
    <div className="grid lg:grid-cols-3 gap-4 my-4"><Card><b>Ações rápidas</b><div className="flex flex-col gap-2 mt-3"><button className="btn btn-primary" disabled={price.isPending} onClick={() => price.mutate()}>{price.isPending ? 'Calculando...' : 'Recalcular preço'}</button><button className="btn btn-ghost" disabled={scrape.isPending} onClick={() => scrape.mutate()}>{scrape.isPending ? 'Rodando...' : 'Rodar concorrência'}</button><button className="btn btn-ghost" disabled={pub.isPending} onClick={() => pub.mutate()}>{pub.isPending ? 'Publicando...' : 'Publicar dry-run'}</button></div></Card><Card><b>Checklist de publicação</b><div className="mt-3 space-y-2">{preview?.checklist?.map((c:any)=><div key={c.label} className="flex justify-between gap-2 rounded-2xl bg-white/10 p-3"><span>{c.label}</span><span className="status-badge">{c.ok?'OK':'Risco'}</span></div>)}</div></Card><Card><b>Insights do produto</b><p className="text-slate-300 mt-2">{sc?.recommended?.recommendation || 'Rode pricing e concorrência para gerar recomendação.'}</p><p className="text-sky-200 mt-3">Riscos: {preview?.risks?.length ? preview.risks.join(', ') : 'sem riscos críticos'}</p></Card></div>
    <div className="grid md:grid-cols-4 gap-4 my-4"><Card><p className="text-slate-400">Concorrentes</p><b>{st.n_ofertas || st.count || data?.competitors?.length || 0}</b></Card><Card><p className="text-slate-400">Mínimo</p><b>{money(st.preco_min || st.min_price)}</b></Card><Card><p className="text-slate-400">Médio/Mediana</p><b>{money(st.preco_medio || st.median_price)}</b></Card><Card><p className="text-slate-400">Máximo</p><b>{money(st.preco_max || st.max_price)}</b></Card></div>
    <div className="grid lg:grid-cols-2 gap-4"><Card><b>Histórico de pricing</b>{sc?.scenarios?.length ? <div className="mt-3 space-y-2">{sc.scenarios.map((x:any)=><div key={x.name} className="rounded-2xl bg-white/10 p-3 border border-white/10"><b className="capitalize">{x.name}: {money(x.price)}</b><p className="text-slate-400 text-sm">Margem {x.margin_pct}% · lucro {money(x.estimated_profit)}</p></div>)}</div> : <EmptyState title="Sem histórico" description="Calcule preço para gerar cenários." />}</Card><Card><b>Ofertas concorrentes</b><div className="mt-3 space-y-2">{data?.competitors?.length ? data.competitors.map((o: any) => <div key={o.id} className="flex flex-wrap justify-between gap-3 rounded-2xl bg-white/10 p-3 border border-white/10"><span>{o.titulo} · {o.vendedor}</span><b>{money(o.preco)}</b></div>) : <EmptyState title="Sem ofertas concorrentes" description="Rode scraping para coletar concorrentes deste produto." />}</div></Card></div>
  </Page>;
}
