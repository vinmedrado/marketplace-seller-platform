import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Page from '../components/animations/Page';
import { Card, Skeleton } from '../components/ui/Card';
import { EmptyState } from '../components/ui/EmptyState';
import { Pagination, usePagination } from '../components/ui/Pagination';
import { competition, competitionAnalytics, money, products, runCompetition } from '../api/client';
import { useState } from 'react';
import { useToast } from '../components/ui/Toast';

export default function Competition() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [pid, setPid] = useState('');
  const [page, setPage] = useState(1);
  const { data: ps = [] } = useQuery({ queryKey: ['products'], queryFn: products });
  const { data, isLoading } = useQuery({ queryKey: ['competition', pid], queryFn: () => competition(pid || undefined) });
  const { data: an } = useQuery({ queryKey: ['competition-analytics', pid], queryFn: () => competitionAnalytics(pid || undefined) });
  const rows = data?.items || [];
  const paginated = usePagination(rows, page, 10);
  const run = useMutation({ mutationFn: () => runCompetition(pid || ps[0]?.id), onSuccess: () => { qc.invalidateQueries({ queryKey: ['competition'] }); qc.invalidateQueries({ queryKey: ['competition-analytics'] }); toast('Scraping concluído e concorrência atualizada.', 'success'); }, onError: () => toast('Falha ao executar scraping.', 'error') });
  return <Page>
    <div className="flex flex-wrap justify-between items-center gap-3 mb-4"><div><h2 className="text-3xl font-black">Concorrência</h2><p className="text-slate-400">Ranking de sellers, dispersão, mediana, agressividade e status da última coleta.</p></div><button disabled={(!pid && !ps[0]) || run.isPending} onClick={() => run.mutate()} className="btn btn-primary">{run.isPending ? 'Processando...' : 'Monitorar novamente'}</button></div>
    <select className="input mb-4" value={pid} onChange={e => { setPid(e.target.value); setPage(1); }}><option value="">Todos os produtos</option>{ps.map((p: any) => <option key={p.id} value={p.id}>{p.sku} · {p.titulo}</option>)}</select>
    <div className="grid md:grid-cols-5 gap-4 mb-4">{[['Ofertas', an?.count], ['Menor preço', money(an?.min_price)], ['Mediana', money(an?.median_price)], ['Dispersão', money(an?.price_dispersion)], ['Status', an?.last_collection_status || '-']].map(([a, b]) => <Card key={a as string}><p className="text-slate-400">{a}</p><b className="text-2xl">{b}</b></Card>)}</div>
    {an?.aggressive_alert && <Card className="mb-4"><b className="text-amber-200">Alerta de concorrente agressivo</b><p className="text-slate-300 mt-2">Existe preço muito abaixo da média. Avalie reduzir estrategicamente apenas se a margem mínima continuar protegida.</p></Card>}
    <div className="grid lg:grid-cols-3 gap-4 mb-4"><Card className="lg:col-span-1"><b>Ranking de concorrentes</b><div className="mt-3 space-y-2">{an?.ranking?.length ? an.ranking.slice(0,5).map((r:any) => <div key={r.seller} className="rounded-2xl bg-white/10 p-3 border border-white/10"><b>{r.seller}</b><p className="text-slate-400 text-sm">{r.offers} ofertas · mínimo {money(r.min_price)} · score {r.aggressiveness_score}</p></div>) : <EmptyState title="Sem ranking" description="Rode uma coleta para gerar ranking competitivo." />}</div></Card>
    <Card className="lg:col-span-2">{isLoading ? <Skeleton className="h-80" /> : rows.length ? <><table className="table-premium text-sm"><thead><tr><th>Oferta</th><th>Preço</th><th>Vendedor</th><th>Reputação</th><th>Frete</th></tr></thead><tbody>{paginated.items.map((o: any) => <tr className="border-t border-white/10" key={o.id}><td>{o.titulo}</td><td>{money(o.preco)}</td><td>{o.vendedor}</td><td>{o.reputacao || '-'}</td><td><span className="status-badge">{o.frete_gratis ? 'Grátis' : 'Pago'}</span></td></tr>)}</tbody></table><Pagination page={paginated.page} totalPages={paginated.totalPages} onPage={setPage}/></> : <EmptyState title="Concorrência vazia" description="Selecione um produto e rode o scraping para popular ofertas reais/demo no banco." />}</Card></div>
  </Page>;
}
