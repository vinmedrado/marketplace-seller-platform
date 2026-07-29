import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, ArrowUpRight, BarChart3, Boxes, Clock3, PackageCheck, RefreshCw, ShoppingCart, TrendingDown, TrendingUp } from 'lucide-react';
import { demandForecastOverview } from '../api/client';

const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

function riskLabel(risk?: string) {
  const map: Record<string, string> = { critical: 'Crítico', high: 'Alto', medium: 'Médio', low: 'Baixo' };
  return map[risk || ''] || 'Indefinido';
}
function trendLabel(trend?: string) {
  const map: Record<string, string> = { increasing: 'Crescente', stable: 'Estável', decreasing: 'Queda', insufficient_history: 'Histórico curto' };
  return map[trend || ''] || 'Histórico curto';
}
function riskClass(risk?: string) {
  if (risk === 'critical') return 'bg-red-500/15 text-red-200 border-red-400/30';
  if (risk === 'high') return 'bg-orange-500/15 text-orange-200 border-orange-400/30';
  if (risk === 'medium') return 'bg-amber-500/15 text-amber-200 border-amber-400/30';
  return 'bg-emerald-500/15 text-emerald-200 border-emerald-400/30';
}
function trendIcon(trend?: string) {
  if (trend === 'increasing') return <TrendingUp size={15} />;
  if (trend === 'decreasing') return <TrendingDown size={15} />;
  return <BarChart3 size={15} />;
}
function fmtDays(days: any) {
  if (days === null || days === undefined) return 'Sem histórico';
  return `${Number(days).toFixed(Number(days) < 10 ? 1 : 0)} dias`;
}

function MiniProjection({ points }: { points: any[] }) {
  const max = Math.max(1, ...points.map((p) => Number(p.projected_stock || 0)));
  return <div className="flex items-end gap-1 h-16 min-w-32">
    {points.slice(0, 11).map((p) => <div key={p.day} title={`Dia ${p.day}: ${p.projected_stock}`} className="w-2 rounded-t bg-sky-300/70" style={{ height: `${Math.max(6, (Number(p.projected_stock || 0) / max) * 62)}px` }} />)}
  </div>;
}

export default function DemandForecast() {
  const [leadTime, setLeadTime] = useState(7);
  const q = useQuery({ queryKey: ['demand-forecast', leadTime], queryFn: () => demandForecastOverview(100, leadTime), staleTime: 60_000 });
  const data = q.data || {};
  const summary = data.summary || {};
  const products = useMemo(() => data.products || [], [data.products]);
  const sorted = useMemo(() => [...products].sort((a: any, b: any) => {
    const da = a.forecast?.estimated_days_remaining ?? 999999;
    const db = b.forecast?.estimated_days_remaining ?? 999999;
    const riskOrder: any = { critical: 0, high: 1, medium: 2, low: 3 };
    return (riskOrder[a.forecast?.stock_risk] ?? 9) - (riskOrder[b.forecast?.stock_risk] ?? 9) || da - db;
  }), [products]);

  return <div className="space-y-5">
    <section className="glass premium-border rounded-[2rem] p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
      <div>
        <p className="text-sm text-slate-400">PATCH 11/15 FINAL</p>
        <h2 className="text-2xl font-black">Previsão de Demanda + Ponto de Recompra</h2>
        <p className="text-slate-300 mt-2 max-w-3xl">Projeção operacional baseada no catálogo real sincronizado, estoque atual, vendas acumuladas e snapshots. Não usa ML fake e não inventa vendas.</p>
      </div>
      <div className="flex items-center gap-3">
        <label className="text-sm text-slate-300">Lead time</label>
        <input value={leadTime} min={1} max={90} onChange={(e) => setLeadTime(Number(e.target.value || 7))} type="number" className="input w-24" />
        <button onClick={() => q.refetch()} disabled={q.isFetching} className="btn btn-primary flex items-center gap-2"><RefreshCw size={16} className={q.isFetching ? 'animate-spin' : ''}/> Atualizar</button>
      </div>
    </section>

    {q.isError && <div className="rounded-3xl border border-red-400/30 bg-red-500/10 p-5 text-red-100">Não foi possível carregar a previsão. Verifique se há produtos sincronizados e se a API está online.</div>}

    <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
      <Metric icon={<AlertTriangle/>} label="Risco alto" value={summary.high_risk_count ?? 0} hint="Produtos com ruptura provável" />
      <Metric icon={<Clock3/>} label="Acabando" value={summary.ending_soon_count ?? 0} hint="Até 14 dias estimados" />
      <Metric icon={<TrendingUp/>} label="Demanda crescente" value={summary.increasing_demand_count ?? 0} hint="Tendência positiva" />
      <Metric icon={<ShoppingCart/>} label="Recompra" value={summary.reorder_recommended_count ?? 0} hint="Abaixo do ponto" />
      <Metric icon={<Boxes/>} label="Analisados" value={summary.products_analyzed ?? 0} hint="Produtos do tenant" />
    </section>

    {!q.isLoading && products.length === 0 && <div className="glass premium-border rounded-[2rem] p-8 text-center">
      <PackageCheck className="mx-auto text-sky-200" size={42}/>
      <h3 className="text-xl font-black mt-3">Nenhum produto sincronizado ainda</h3>
      <p className="text-slate-300 mt-2">Sincronize seu catálogo Mercado Livre para gerar previsão de demanda, risco de ruptura e ponto de recompra.</p>
    </div>}

    <section className="glass premium-border rounded-[2rem] overflow-hidden">
      <div className="p-5 border-b border-white/10 flex items-center justify-between">
        <div>
          <h3 className="font-black text-lg">Cockpit de estoque projetado</h3>
          <p className="text-sm text-slate-400">Ordenado por risco, dias restantes e tendência.</p>
        </div>
        <span className="text-xs text-slate-400">{data.generated_at ? `Gerado em ${new Date(data.generated_at).toLocaleString('pt-BR')}` : ''}</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-white/[0.04] text-slate-400">
            <tr>
              <th className="text-left p-4">Produto</th><th className="text-left p-4">Estoque</th><th className="text-left p-4">Vendas/dia</th><th className="text-left p-4">Dias restantes</th><th className="text-left p-4">Ponto recompra</th><th className="text-left p-4">Tendência</th><th className="text-left p-4">Risco</th><th className="text-left p-4">Projeção</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row: any) => {
              const p = row.product || {}; const f = row.forecast || {};
              return <tr key={p.id} className="border-t border-white/10 hover:bg-white/[0.04] transition">
                <td className="p-4 min-w-80"><div className="flex items-center gap-3">
                  {p.thumbnail ? <img src={p.thumbnail} className="h-12 w-12 object-cover rounded-xl border border-white/10"/> : <div className="h-12 w-12 rounded-xl bg-white/10"/>}
                  <div><p className="font-bold line-clamp-2">{p.title}</p><p className="text-xs text-slate-400">{p.price ? money.format(Number(p.price)) : 'Sem preço'} · {p.status || 'status n/d'}</p></div>
                </div></td>
                <td className="p-4 font-bold">{p.available_quantity ?? 0}</td>
                <td className="p-4">{Number(f.avg_daily_sales || 0).toFixed(2)}</td>
                <td className="p-4 font-bold">{fmtDays(f.estimated_days_remaining)}</td>
                <td className="p-4">{f.reorder_point ?? 0} un.</td>
                <td className="p-4"><span className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/10 px-3 py-1">{trendIcon(f.demand_trend)} {trendLabel(f.demand_trend)}</span></td>
                <td className="p-4"><span className={`inline-flex rounded-full border px-3 py-1 font-bold ${riskClass(f.stock_risk)}`}>{riskLabel(f.stock_risk)}</span></td>
                <td className="p-4"><MiniProjection points={f.projected_stock || []}/></td>
              </tr>;
            })}
          </tbody>
        </table>
      </div>
    </section>

    <section className="grid grid-cols-1 xl:grid-cols-2 gap-4">
      <Panel title="Alertas de ruptura" rows={data.high_risk || []} empty="Nenhum risco alto no momento." />
      <Panel title="Oportunidades de demanda" rows={data.opportunities || []} empty="Sem tendência crescente suficiente ainda." />
    </section>

    <p className="text-xs text-slate-500">{data.disclaimer || 'Previsão heurística interna SellerOS; use como apoio operacional, não como garantia.'}</p>
  </div>;
}

function Metric({ icon, label, value, hint }: any) {
  return <div className="glass premium-border rounded-[1.6rem] p-5"><div className="flex items-center justify-between text-sky-200">{icon}<ArrowUpRight size={16}/></div><p className="text-3xl font-black mt-3">{value}</p><p className="font-bold">{label}</p><p className="text-xs text-slate-400 mt-1">{hint}</p></div>;
}
function Panel({ title, rows, empty }: any) {
  return <div className="glass premium-border rounded-[2rem] p-5"><h3 className="font-black text-lg mb-3">{title}</h3>{rows.length === 0 ? <p className="text-slate-400">{empty}</p> : <div className="space-y-3">{rows.slice(0, 6).map((r: any) => <div key={r.product?.id} className="rounded-2xl border border-white/10 bg-white/[0.04] p-4"><div className="flex justify-between gap-3"><p className="font-bold line-clamp-1">{r.product?.title}</p><span className={`shrink-0 rounded-full border px-2 py-1 text-xs ${riskClass(r.forecast?.stock_risk)}`}>{riskLabel(r.forecast?.stock_risk)}</span></div><p className="text-sm text-slate-300 mt-1">{r.recommendation}</p></div>)}</div>}</div>;
}
