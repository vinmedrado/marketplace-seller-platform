import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import Page from '../components/animations/Page';
import { Card } from '../components/ui/Card';
import { EmptyState } from '../components/ui/EmptyState';
import { Pagination, usePagination } from '../components/ui/Pagination';
import { calculatePricing, money, pricingHistory, pricingScenarios, products } from '../api/client';
import { useToast } from '../components/ui/Toast';

export default function Pricing() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [pid, setPid] = useState('');
  const [page, setPage] = useState(1);
  const { data: ps = [] } = useQuery({ queryKey: ['products'], queryFn: products });
  const selected = pid || ps[0]?.id;
  const { data: hist = [] } = useQuery({ queryKey: ['pricing-history', pid], queryFn: () => pricingHistory(pid || undefined) });
  const { data: sc } = useQuery({ queryKey: ['pricing-scenarios', selected], queryFn: () => pricingScenarios(selected), enabled: !!selected });
  const calc = useMutation({ mutationFn: () => calculatePricing(selected), onSuccess: () => { qc.invalidateQueries({ queryKey: ['pricing-history'] }); qc.invalidateQueries({ queryKey: ['pricing-scenarios'] }); toast('Preço recalculado e salvo no histórico.', 'success'); }, onError: () => toast('Não foi possível calcular o preço.', 'error') });
  const last = calc.data || hist[0] || sc?.recommended;
  const paginated = usePagination(hist, page, 8);
  return <Page>
    <div className="flex flex-wrap justify-between items-center gap-3 mb-4"><div><h2 className="text-3xl font-black">Precificação Inteligente</h2><p className="text-slate-400">Preço explicado por margem, lucro, concorrência e cenários comerciais.</p></div><button className="btn btn-primary" onClick={() => calc.mutate()} disabled={!selected || calc.isPending}>{calc.isPending ? 'Calculando...' : 'Recalcular'}</button></div>
    <select className="input mb-4" value={pid} onChange={e => { setPid(e.target.value); setPage(1); }}><option value="">Selecione ou use primeiro produto</option>{ps.map((p: any) => <option key={p.id} value={p.id}>{p.sku} · {p.titulo}</option>)}</select>
    <div className="grid md:grid-cols-4 gap-4 mb-4"><Card><p className="text-slate-400">Preço sugerido</p><b className="text-3xl">{money(last?.preco_sugerido || last?.price)}</b></Card><Card><p className="text-slate-400">Lucro estimado</p><b className="text-3xl">{money(last?.lucro_estimado || last?.estimated_profit)}</b></Card><Card><p className="text-slate-400">Margem</p><b className="text-3xl">{Math.round(Number(last?.margem_real_pct ? last.margem_real_pct * 100 : last?.margin_pct || 0))}%</b></Card><Card><p className="text-slate-400">Score</p><b className="text-3xl">{Math.round(Number(last?.score_competitividade || 0) * 100)}</b></Card></div>
    <Card className="mb-4"><div className="flex justify-between gap-3 mb-4"><div><b>Cenários de preço</b><p className="text-slate-400">Conservador, competitivo, agressivo e margem protegida.</p></div><span className="status-badge">Recomendado: {sc?.recommended?.name || '-'}</span></div>{sc?.scenarios?.length ? <div className="grid md:grid-cols-4 gap-3">{sc.scenarios.map((x:any) => <div key={x.name} className="rounded-2xl bg-white/10 p-4 border border-white/10"><b className="capitalize">{x.name}</b><p className="text-2xl font-black mt-2">{money(x.price)}</p><p className="text-slate-300 text-sm">Margem {x.margin_pct}% · lucro {money(x.estimated_profit)}</p><p className="text-sky-200 text-sm mt-2">{x.competitive_position}</p><p className="text-slate-400 text-xs mt-2">{x.recommendation}</p></div>)}</div> : <EmptyState title="Sem cenários" description="Selecione um produto para simular cenários de preço." />}</Card>
    <Card><b>Histórico de pricing</b>{hist.length ? <><div className="mt-4 space-y-2">{paginated.items.map((r: any) => <div key={r.id} className="flex flex-wrap justify-between gap-3 rounded-2xl bg-white/10 p-3 border border-white/10"><span>{new Date(r.criado_em).toLocaleString('pt-BR')}</span><span>{money(r.preco_sugerido)} · lucro {money(r.lucro_estimado)}</span></div>)}</div><Pagination page={paginated.page} totalPages={paginated.totalPages} onPage={setPage}/></> : <div className="mt-4"><EmptyState title="Sem histórico de pricing" description="Clique em recalcular para gerar o primeiro preço sugerido real da demo." /></div>}</Card>
  </Page>;
}
