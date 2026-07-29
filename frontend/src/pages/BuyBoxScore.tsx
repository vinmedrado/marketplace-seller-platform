import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { buyboxOverview, productBuyboxScore, money } from '../api/client';
import Page from '../components/animations/Page';
import { Card } from '../components/ui/Card';

function pct(v:any){return v===null||v===undefined?'—':`${Math.round(Number(v))}%`}
function riskClass(v:number){return v<45?'text-red-200':v<65?'text-amber-200':'text-emerald-200'}
function riskLabel(v:number){return v<45?'Buy Box baixo':v<65?'Buy Box médio':'Buy Box forte'}

export default function BuyBoxScore(){
  const [selected,setSelected]=useState<any|null>(null);
  const overview=useQuery({queryKey:['buybox-overview'],queryFn:()=>buyboxOverview(30),refetchInterval:60000});
  const detail=useQuery({queryKey:['buybox-detail',selected?.product_id],queryFn:()=>productBuyboxScore(selected.product_id,true),enabled:Boolean(selected?.product_id)});
  const data=overview.data||{}; const summary=data.summary||{}; const items=data.items||[];
  return <Page>
    <div className="mb-5">
      <h2 className="text-3xl font-black">Buy Box Probability Score</h2>
      <p className="text-slate-400 mt-2">Score interno SellerOS baseado em sinais operacionais e mercado. Não é uma métrica oficial do Mercado Livre.</p>
    </div>

    <div className="grid md:grid-cols-4 gap-4 mb-5">
      <Card><p className="text-slate-400">Produtos analisados</p><b className="text-3xl">{summary.products_analyzed||0}</b></Card>
      <Card><p className="text-slate-400">Risco alto</p><b className="text-3xl text-red-200">{summary.high_risk||0}</b></Card>
      <Card><p className="text-slate-400">Oportunidades</p><b className="text-3xl text-emerald-200">{summary.opportunities||0}</b></Card>
      <Card><p className="text-slate-400">Menor probabilidade</p><b className="text-3xl">{pct(summary.lowest_probability)}</b></Card>
    </div>

    <div className="grid xl:grid-cols-3 gap-4">
      <Card className="xl:col-span-2">
        <div className="flex justify-between gap-3 items-start mb-4">
          <div><h3 className="text-xl font-black">Produtos e risco estimado</h3><p className="text-slate-400">Clique em “Ver simulação” para consultar mercado público e salvar snapshot.</p></div>
          <span className="status-badge">{overview.isLoading?'Carregando':'Score interno'}</span>
        </div>
        {overview.error&&<p className="text-red-200">Não foi possível carregar Buy Box Score.</p>}
        {!overview.isLoading&&!items.length&&<div className="rounded-3xl bg-white/[0.06] border border-white/10 p-8 text-center"><b>Nenhum produto sincronizado ainda.</b><p className="text-slate-400 mt-2">Sincronize o catálogo Mercado Livre para gerar score interno de Buy Box.</p></div>}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-slate-400 border-b border-white/10"><tr><th className="py-3">Produto</th><th>Preço</th><th>Prob.</th><th>Confiança</th><th>Melhor ajuste</th><th>Recomendação</th><th></th></tr></thead>
            <tbody>{items.map((p:any)=><tr key={p.product_id} className="border-b border-white/5 align-top">
              <td className="py-3 min-w-[300px]"><div className="flex gap-3 items-center"><img src={p.thumbnail||'https://placehold.co/56x56'} className="w-12 h-12 rounded-xl object-cover bg-white/10"/><div><b>{p.title}</b><p className="text-xs text-slate-500">{p.external_product_id||p.product_id}</p><span className={`text-xs ${riskClass(Number(p.current_probability||0))}`}>{riskLabel(Number(p.current_probability||0))}</span></div></div></td>
              <td>{money(p.current_price)}</td><td><b className={riskClass(Number(p.current_probability||0))}>{pct(p.current_probability)}</b></td><td>{pct(p.confidence)}</td>
              <td>{p.best_adjustment_percent!==null&&p.best_adjustment_percent!==undefined?`${p.best_adjustment_percent}% → ${money(p.best_adjustment_price)}`:'—'}</td>
              <td className="min-w-[260px] text-slate-300">{p.recommendation}</td>
              <td><button className="btn btn-primary" onClick={()=>setSelected(p)}>Ver simulação</button></td>
            </tr>)}</tbody>
          </table>
        </div>
      </Card>

      <Card>
        <h3 className="text-xl font-black">Simulação detalhada</h3>
        {!selected&&<p className="text-slate-400 mt-2">Selecione um produto para ver preço atual, cenários -3%, -5%, -8%, +3%, fatores positivos/negativos e recomendação.</p>}
        {selected&&detail.isLoading&&<p className="text-slate-400 mt-4">Consultando mercado e gerando snapshot...</p>}
        {detail.error&&<p className="text-red-200 mt-4">Falha ao gerar simulação. Tente novamente.</p>}
        {detail.data&&<div className="mt-4 space-y-4">
          <div className="rounded-3xl bg-white/[0.06] border border-white/10 p-4"><p className="text-slate-400 text-sm">{detail.data.title}</p><div className="flex items-end justify-between mt-2"><b className={`text-4xl ${riskClass(Number(detail.data.current_probability||0))}`}>{pct(detail.data.current_probability)}</b><span className="status-badge">Confiança {pct(detail.data.confidence)}</span></div><p className="text-slate-300 mt-3">{detail.data.recommendation}</p></div>
          <div><h4 className="font-black mb-2">Cenários de preço</h4><div className="space-y-2">{(detail.data.simulated_prices||[]).map((s:any)=><div key={`${s.variation_percent}-${s.price}`} className="rounded-2xl bg-white/10 p-3"><div className="flex justify-between"><b>{s.variation_percent===0?'Preço atual':`${s.variation_percent}%`}</b><b>{money(s.price)} · {pct(s.estimated_probability)}</b></div><p className="text-xs text-slate-400 mt-1">{s.recommendation}</p>{s.margin_note&&<p className="text-xs text-amber-200 mt-1">{s.margin_note}</p>}</div>)}</div></div>
          <div><h4 className="font-black mb-2">Fatores positivos</h4>{(detail.data.positive_factors||[]).map((f:any)=><p key={f.name} className="text-sm text-emerald-200">✓ {f.reason}</p>)}{!(detail.data.positive_factors||[]).length&&<p className="text-sm text-slate-400">Sem fatores positivos fortes.</p>}</div>
          <div><h4 className="font-black mb-2">Fatores negativos / faltantes</h4>{[...(detail.data.negative_factors||[]),...(detail.data.factors||[]).filter((f:any)=>f.polarity==='missing')].map((f:any)=><p key={f.name} className="text-sm text-amber-200">• {f.reason}</p>)}</div>
          <p className="text-xs text-slate-500">{detail.data.disclaimer}</p>
        </div>}
      </Card>
    </div>
  </Page>
}
